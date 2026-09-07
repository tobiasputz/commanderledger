"""All multiplayer calculations live here, shared by pages, exports and API."""
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Game, Participant, Deck
ELIGIBLE={'win','shared','draw'}

def ratings_summary(values: list[int]) -> dict:
    return {'mean': round(mean(values),2) if values else None,'median':median(values) if values else None,'n':len(values),'distribution':{str(i):values.count(i) for i in range(1,6)},'small_sample':len(values)<5,'recent_mean':round(mean(values[:5]),2) if values else None,'recent_n':min(5,len(values)),'previous_mean':round(mean(values[5:10]),2) if len(values)>5 else None,'trend':round(mean(values[:5])-mean(values[5:10]),2) if len(values)>5 else None}

def select_games(db: Session, filters: dict | None = None) -> list[Game]:
    f=filters or {}
    games=list(db.scalars(select(Game).where(Game.deleted==False).order_by(Game.played_at.desc())))
    def match(g: Game) -> bool:
        if f.get('deck_status') and not any(p.deck_id and db.get(Deck,p.deck_id).status==f['deck_status'] for p in g.participants): return False
        if f.get('date_from') and g.played_at[:10]<f['date_from']: return False
        if f.get('date_to') and g.played_at[:10]>f['date_to']: return False
        for k in ('location_id','event_id','setting'):
            if f.get(k) and getattr(g,k)!=f[k]: return False
        if f.get('pod_size'):
            try: pod_size=int(f['pod_size'])
            except ValueError: return False
            if len(g.participants)!=pod_size: return False
        for k in ('player_id','deck_id'):
            if f.get(k) and not any(getattr(p,k)==f[k] for p in g.participants): return False
        for k in ('commanders','archetype'):
            if f.get(k) and not any(f[k].casefold() in getattr(p,k).casefold() for p in g.participants): return False
        anon=sum(p.player_id is None for p in g.participants)
        if f.get('pod_type')=='known' and anon: return False
        if f.get('pod_type')=='mixed' and not 0<anon<len(g.participants): return False
        if f.get('pod_type')=='anonymous' and not anon: return False
        if f.get('tag') and not any(f['tag'].casefold()==str(t).casefold() for t in g.tags): return False
        if f.get('q'):
            hay=' '.join([g.notes,g.memorable,*g.tags]+[' '.join([p.player_name,p.deck_name,p.commanders,*p.deck_links]) for p in g.participants])
            if f['q'].casefold() not in hay.casefold(): return False
        return True
    return [g for g in games if match(g)]

def record(pairs: list[tuple[Game,Participant]]) -> dict:
    eligible=[(g,p) for g,p in pairs if g.result in ELIGIBLE]
    n=len(eligible)
    wins=sum(g.result=='win' and p.winner for g,p in eligible)
    shared=sum(g.result=='shared' and p.winner for g,p in eligible)
    draws=sum(g.result=='draw' for g,p in eligible)
    losses=n-wins-shared-draws
    shares=sum((1/sum(x.winner for x in g.participants)) if p.winner else 0 for g,p in eligible)
    expected=mean([1/len(g.participants) for g,p in eligible]) if n else None
    actual=shares/n if n else None
    rs=[r.value for g,p in pairs for r in g.ratings if r.kind=='deck' and r.participant_id==p.id]
    overall=[r.value for g,p in pairs for r in g.ratings if r.kind=='overall']
    durations=[g.duration for g,p in pairs if g.duration is not None]
    dates=[g.played_at[:10] for g,p in eligible]
    return {'games':len(pairs),'eligible':n,'wins':wins,'shared':shared,'draws':draws,'losses':losses,'win_rate':wins/n if n else None,'win_share':actual,'expected':expected,'difference':actual-expected if n else None,'ratio':actual/expected if n else None,'average_pod':mean([len(g.participants) for g,p in eligible]) if n else None,'date_from':min(dates) if dates else None,'date_to':max(dates) if dates else None,'enjoyment':ratings_summary(rs),'overall':ratings_summary(overall),'average_duration':round(mean(durations),1) if durations else None,'small_sample':n<5}

def group_records(games: list[Game], key: str) -> list[dict]:
    groups=defaultdict(list)
    for g in games:
        for p in g.participants:
            value=getattr(p,key)
            if value is not None: groups[value].append((g,p))
    return [{'id':key_value,'name':pairs[0][1].player_name if key=='player_id' else pairs[0][1].deck_name if key=='deck_id' else str(key_value),**record(pairs)} for key_value,pairs in groups.items()]

def breakdown(pairs: list[tuple[Game,Participant]], kind: str) -> list[dict]:
    groups=defaultdict(list)
    for g,p in pairs:
        key=g.location_id or 'Unspecified' if kind=='location' else str(p.seat) if kind=='seat' else g.played_at[:7]
        groups[key].append((g,p))
    return [{'name':k,**record(v)} for k,v in sorted(groups.items())]

def matchups(pairs: list[tuple[Game,Participant]], kind: str='player_id') -> list[dict]:
    groups=defaultdict(list)
    for g,p in pairs:
        seen=set()
        for other in g.participants:
            if other.id==p.id: continue
            key=getattr(other,kind) or ('All LGS opponents' if kind=='player_id' else other.deck_name)
            if key in seen: continue
            seen.add(key)
            groups[key].append((g,p,other))
    return [{'id':k,'name':v[0][2].player_name if kind=='player_id' and k!='All LGS opponents' else v[0][2].deck_name if kind=='deck_id' else k,**record([(g,p) for g,p,_ in v])} for k,v in groups.items()]

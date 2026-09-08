from collections import Counter,defaultdict
from itertools import combinations
from app.services.stats import select_games,group_records
from app.models import Deck,Player

def report(db,season):
    games=select_games(db,{'date_from':season.date_from,'date_to':season.date_to})
    players=group_records(games,'player_id');decks=group_records(games,'deck_id');achievements=[]
    for p in players:
        appearances=sorted([(g,s) for g in games for s in g.participants if s.player_id==p['id']],key=lambda pair:pair[0].played_at)
        streak=best=0
        for g,s in appearances:
            streak=streak+1 if s.winner and g.result in ('win','shared') else 0;best=max(best,streak)
        variety=len({s.deck_id or s.commanders for _,s in appearances})
        achievements.append({'player':db.get(Player,p['id']).name,'longest_streak':best,'different_decks':variety,'games':len(appearances)})
    rivalries=defaultdict(lambda:{'games':0,'wins':Counter()})
    for g in games:
        named=[p for p in g.participants if p.player_id]
        for a,b in combinations(named,2):
            key=tuple(sorted((a.player_id,b.player_id)));r=rivalries[key];r['games']+=1
            for p in (a,b):
                if p.winner:r['wins'][p.player_id]+=1
    rivalry_rows=[{'players':[db.get(Player,k).name for k in ids],'games':r['games'],'wins':[r['wins'][k] for k in ids]} for ids,r in rivalries.items()]
    rivalry_rows.sort(key=lambda r:(-r['games'],abs(r['wins'][0]-r['wins'][1])))
    first_wins=[]
    all_games=sorted(select_games(db),key=lambda g:g.played_at);seen=set()
    for g in all_games:
        for p in g.participants:
            if p.deck_id and p.winner and p.deck_id not in seen:
                seen.add(p.deck_id)
                if season.date_from<=g.played_at[:10]<=season.date_to:first_wins.append({'deck':p.deck_name,'date':g.played_at[:10]})
    commanders=Counter(p.commanders for g in games for p in g.participants)
    colors=Counter(db.get(Deck,p.deck_id).color_identity or 'C' for g in games for p in g.participants if p.deck_id)
    return {'name':season.name,'from':season.date_from,'to':season.date_to,'games':len(games),'players':players,'decks':decks,'achievements':sorted(achievements,key=lambda r:-r['different_decks']),'rivalries':rivalry_rows[:10],'first_wins':first_wins,'commanders':commanders.most_common(10),'current_deck_colors':colors.most_common(),'moments':[{'date':g.played_at[:10],'text':g.memorable} for g in games if g.memorable],'note':'Multiplayer rivalry wins are pod outcomes, not head-to-head victories. Color totals use current deck identities. Small samples are descriptive.'}

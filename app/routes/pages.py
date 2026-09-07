from collections import Counter
from statistics import mean
import json
from fastapi import APIRouter,Request,Depends,HTTPException
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
import plotly.graph_objects as go
from app.db import ROOT,get_db
from app.models import Player,Deck,Game,Participant,Rating,Location,Event,Setting,Ownership,DeckVersion
from app.routes.api import catalog,game_dict
from app.services.games import require
from app.services.stats import select_games,group_records,record,ratings_summary,breakdown,matchups
router=APIRouter()
templates=Jinja2Templates(directory=ROOT/'app/templates')
templates.env.filters['pct']=lambda v: '—' if v is None else f'{v*100:.1f}%'
templates.env.filters['num']=lambda v: '—' if v is None else f'{v:.2f}'

def context(db: Session,**kwargs: object) -> dict:
    cat=catalog(db)
    settings={s.key:s.value for s in db.scalars(select(Setting))}
    from app.security import config
    import os
    if config().hosted: settings['backup_directory']=os.environ['COMMANDER_BACKUPS']
    return {'catalog':cat,'names':{x['id']:x['name'] for values in cat.values() for x in values},'settings':settings,**kwargs}

def chart(title: str,x: list,y: list,second: list | None = None,kind: str='bar',hovertext: list[str] | None = None) -> dict:
    fig=go.Figure()
    if kind=='scatter': fig.add_trace(go.Scatter(x=x,y=y,mode='markers',text=hovertext,hovertemplate='%{text}<br>Win rate %{x:.1f}%<br>Enjoyment %{y:.2f}<extra></extra>',marker={'size':13,'color':'#9eddb8'}))
    elif kind=='line': fig.add_trace(go.Scatter(x=x,y=y,mode='lines+markers',line={'color':'#9eddb8'}))
    elif kind=='hist': fig.add_trace(go.Histogram(x=x,marker_color='#a995ef',nbinsx=15))
    else: fig.add_trace(go.Bar(x=x,y=y,name='Actual' if second is not None else title,marker_color='#a995ef'))
    if second is not None: fig.add_trace(go.Bar(x=x,y=second,name='Expected',marker_color='#82cbb0'))
    fig.update_layout(title={'text':title,'font':{'size':15}},height=310,margin={'l':45,'r':20,'t':50,'b':65},paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font={'color':'#9aa7b7'},xaxis={'gridcolor':'#34404b'},yaxis={'gridcolor':'#34404b'},legend={'orientation':'h'})
    return json.loads(fig.to_json())

@router.get('/')
def home(request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    games=select_games(db)
    players=group_records(games,'player_id'); decks=group_records(games,'deck_id')
    return templates.TemplateResponse(request=request,name='home.html',context=context(db,games=games[:6],total=len(games),players=sorted(players,key=lambda r:r['games'],reverse=True)[:5],decks=sorted(decks,key=lambda r:r['games'],reverse=True)[:5],enjoyment=ratings_summary([r.value for g in games for r in g.ratings if r.kind=='overall']),duration=round(mean([g.duration for g in games if g.duration]),1) if any(g.duration for g in games) else None))

@router.get('/games/new')
def new_game(request: Request,duplicate: str='',edit: str='',db: Session=Depends(get_db)) -> HTMLResponse:
    data=game_dict(require(db,Game,edit or duplicate)) if edit or duplicate else None
    return templates.TemplateResponse(request=request,name='entry.html',context=context(db,initial=data,editing=edit,duplicate=bool(duplicate)))

@router.get('/games')
def games_page(request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    f=dict(request.query_params)
    games=list(db.scalars(select(Game).where(Game.deleted==True).order_by(Game.played_at.desc()))) if f.get('trash') else select_games(db,f)
    try: page=max(1,int(f.get('page',1)))
    except ValueError: page=1
    if f.get('sort')=='oldest': games.reverse()
    if f.get('sort')=='duration': games.sort(key=lambda g:g.duration or 0,reverse=True)
    total=len(games)
    return templates.TemplateResponse(request=request,name='games.html',context=context(db,games=games[(page-1)*20:page*20],total=total,page=page,filters=f))

@router.get('/games/{identity}')
def game_page(identity: str,request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request=request,name='game.html',context=context(db,game=require(db,Game,identity),version_names={v.id:v.name for v in db.scalars(select(DeckVersion))}))

@router.get('/manage/{kind}')
def manage(kind: str,request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    if kind not in ('players','decks','locations','events'): raise HTTPException(404)
    return templates.TemplateResponse(request=request,name='manage.html',context=context(db,kind=kind))

@router.get('/profiles/{kind}/{identity}')
def profile(kind: str,identity: str,request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    model={'players':Player,'decks':Deck,'events':Event,'locations':Location}.get(kind)
    if not model: raise HTTPException(404)
    obj=require(db,model,identity)
    filters=dict(request.query_params)
    filters[{'players':'player_id','decks':'deck_id','events':'event_id','locations':'location_id'}[kind]]=identity
    games=select_games(db,filters)
    pairs=[(g,p) for g in games for p in g.participants if kind in ('events','locations') or (p.player_id==identity if kind=='players' else p.deck_id==identity)]
    compare=filters.get('compare','')
    before=record([(g,p) for g,p in pairs if compare and g.played_at[:10]<compare]) if compare else None
    after=record([(g,p) for g,p in pairs if compare and g.played_at[:10]>=compare]) if compare else None
    records=group_records(games,'deck_id' if kind=='players' else 'player_id')
    if kind=='players':
        records=[]
        from collections import defaultdict
        groups=defaultdict(list)
        for g,p in pairs: groups[p.deck_id or p.deck_name].append((g,p))
        records=[{'id':k,'name':v[0][1].deck_name or v[0][1].commanders,**record(v)} for k,v in groups.items()]
    mode=filters.get('matchup','player_id')
    if mode not in ('player_id','deck_id','commanders','archetype'): mode='player_id'
    stats=record(pairs)
    threshold_setting=db.get(Setting,'minimum_games')
    try: threshold=max(1,int(filters.get('minimum',threshold_setting.value if threshold_setting else 5)))
    except ValueError: threshold=5
    matchup_rows=sorted(matchups(pairs,mode),key=lambda r:r['eligible'],reverse=True)
    qualified=sorted([r for r in matchup_rows if r['eligible']>=threshold],key=lambda r:r['win_share'])
    favorite=qualified[-1] if qualified else None
    difficult=qualified[0] if qualified else None
    best=sorted([r for r in records if r['eligible']>=threshold],key=lambda r:r['win_rate'],reverse=True)
    enjoyed=sorted([r for r in records if r['games']>=threshold and r['enjoyment']['n']>=threshold],key=lambda r:r['enjoyment']['mean'],reverse=True)
    event_enjoyment=ratings_summary([r.value for g in games for r in g.ratings if r.kind=='overall'])
    charts=[chart('Deck enjoyment distribution',list(stats['enjoyment']['distribution']),list(stats['enjoyment']['distribution'].values())),chart('Results over time — fractional win share (%)',[r['name'] for r in breakdown(pairs,'month')],[100*(r['win_share'] or 0) for r in breakdown(pairs,'month')])]
    history=list(db.scalars(select(Ownership).where(Ownership.deck_id==identity))) if kind=='decks' else []
    return templates.TemplateResponse(request=request,name='profile.html',context=context(db,obj=obj,kind=kind,games=games,stats=stats,records=records,event_decks=len({p.deck_id or p.deck_name or p.commanders for g in games for p in g.participants}),matchups=matchup_rows,minimum=threshold,favorite=favorite,difficult=difficult,best=best,enjoyed=enjoyed,event_enjoyment=event_enjoyment,event_duration=round(mean([g.duration for g in games if g.duration]),1) if any(g.duration for g in games) else None,seat_records=breakdown(pairs,'seat'),location_records=breakdown(pairs,'location'),before=before,after=after,filters=filters,charts=charts,history=history))

@router.get('/analytics')
def analytics(request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    f=dict(request.query_params); games=select_games(db,f)
    config={s.key:s.value for s in db.scalars(select(Setting))}
    try: threshold=max(1,int(f.get('minimum',config.get('minimum_games',5))))
    except ValueError: threshold=5
    players=group_records(games,'player_id'); decks=group_records(games,'deck_id')
    deck_map={d.id:d for d in db.scalars(select(Deck))}
    if f.get('deck_status'): decks=[r for r in decks if deck_map[r['id']].status==f['deck_status']]
    for rows,model in ((players,Player),(decks,Deck)):
        for row in rows: row['name']=db.get(model,row['id']).name
    ranked_players=sorted([p for p in players if p['eligible']>=threshold],key=lambda p:p['win_rate'],reverse=True)
    ranked_decks=sorted([p for p in decks if p['eligible']>=threshold],key=lambda p:p['win_rate'],reverse=True)
    enjoyable=sorted([p for p in decks if p['games']>=threshold and p['enjoyment']['n']>=threshold],key=lambda p:p['enjoyment']['mean'],reverse=True)
    months=Counter(g.played_at[:7] for g in games); pods=Counter(len(g.participants) for g in games)
    commanders=Counter(p.commanders for g in games for p in g.participants)
    pairs=[(g,p) for g in games for p in g.participants]
    seat=breakdown(pairs,'seat'); locations=breakdown(pairs,'location')
    # Per-seat records naturally sum to one win share per decided pod.
    charts=[chart('Games played over time',sorted(months),[months[m] for m in sorted(months)],kind='line'),chart('Player outright win rate (%)',[p['name'] for p in ranked_players],[100*p['win_rate'] for p in ranked_players]),chart('Deck outright win rate (%)',[p['name'] for p in ranked_decks],[100*p['win_rate'] for p in ranked_decks]),chart('Deck win share: actual vs expected (%)',[p['name'] for p in ranked_decks],[100*p['win_share'] for p in ranked_decks],[100*p['expected'] for p in ranked_decks]),chart('Duration distribution (minutes)',[g.duration for g in games if g.duration],[],kind='hist'),chart('Win rate by seat (%)',[r['name'] for r in seat],[100*(r['win_rate'] or 0) for r in seat]),chart('Commander frequency',list(commanders),list(commanders.values())),chart('Pod-size distribution',list(pods),list(pods.values())),chart('Seat wins by location',[db.get(Location,r['name']).name if db.get(Location,r['name']) else 'Unspecified' for r in locations],[r['wins'] for r in locations])]
    if not config.get('hide_sensitive',False):
        charts += [chart('Game enjoyment involving player (1–5)',[p['name']+' (n='+str(p['overall']['n'])+')' for p in ranked_players],[p['overall']['mean'] for p in ranked_players]),chart('Opponent enjoyment of decks (1–5)',[p['name']+' (n='+str(p['enjoyment']['n'])+')' for p in enjoyable],[p['enjoyment']['mean'] for p in enjoyable]),chart('Deck win rate (%) vs opponent enjoyment',[100*p['win_rate'] for p in enjoyable],[p['enjoyment']['mean'] for p in enjoyable],kind='scatter',hovertext=[p['name']+' · '+str(p['enjoyment']['n'])+' ratings · '+str(p['eligible'])+' eligible games · avg pod '+str(round(p['average_pod'],2))+' · expected '+str(round(p['expected']*100,1))+'% · '+str(p['date_from'])+' to '+str(p['date_to']) for p in enjoyable])]
    segments=[]
    for name,subset in [('LGS games',[g for g in games if g.setting=='LGS']),('Private playgroup',[g for g in games if g.setting=='home']),('Known-player pods',[g for g in games if all(p.player_id for p in g.participants)]),('Mixed pods',[g for g in games if any(p.player_id for p in g.participants) and any(p.player_id is None for p in g.participants)])]:
        segments.append({'name':name,'games':len(subset),'enjoyment':ratings_summary([r.value for g in subset for r in g.ratings if r.kind=='overall'])})
    return templates.TemplateResponse(request=request,name='analytics.html',context=context(db,filters=f,total=len(games),players=ranked_players,decks=ranked_decks,enjoyable=enjoyable,all_players=players,all_decks=decks,minimum=threshold,charts=charts,segments=segments,overall=ratings_summary([r.value for g in games for r in g.ratings if r.kind=='overall']),average_duration=round(mean([g.duration for g in games if g.duration]),1) if any(g.duration for g in games) else None,most_player=max(ranked_players,key=lambda r:r['games']) if ranked_players else None,most_deck=max(ranked_decks,key=lambda r:r['games']) if ranked_decks else None,lgs=record([(g,p) for g in games for p in g.participants if p.player_id is None])))

@router.get('/settings')
def settings_page(request: Request,db: Session=Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request=request,name='settings.html',context=context(db))

@router.get('/search')
def search(request: Request,q: str='',db: Session=Depends(get_db)) -> HTMLResponse:
    cat=catalog(db)
    results={k:[x for x in values if q.casefold() in ' '.join(str(v) for v in x.values()).casefold()] for k,values in cat.items()} if q else {}
    return templates.TemplateResponse(request=request,name='search.html',context=context(db,results=results,games=select_games(db,{'q':q})[:50] if q else [],q=q))

@router.get('/fragments/decks')
def deck_options(request: Request,player_id: str='',db: Session=Depends(get_db)) -> HTMLResponse:
    decks=list(db.scalars(select(Deck).where(Deck.owner_id==player_id,Deck.status=='active',Deck.deleted_at.is_(None)).order_by(Deck.name)))
    return templates.TemplateResponse(request=request,name='deck_options.html',context={'decks':decks})

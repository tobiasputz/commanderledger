"""Owner studio, protected player portal and live/league operations."""
import json,time,hashlib,secrets,hmac
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Form,UploadFile,File,BackgroundTasks
from fastapi.responses import RedirectResponse,Response,FileResponse
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from app.db import get_db,ROOT
from app.models import *
from app.schemas import Input,DeckInput,GameInput
from app.schemas.playgroup import *
from app.services.games import require,save_game
from app.services.backup import dump_record,export_json,restore_json
from app.services.stats import select_games,record,group_records
from app.services.leagues import pair,standings,guard_game
from app.security import config,connect,COOKIE,LOGIN_COOKIE,login_attempt,create_session
from app.services.accounts import issue,accept,list_accounts
router=APIRouter()

def validate_live(db,state):
    if state.location_id:require(db,Location,state.location_id)
    if state.event_id:require(db,Event,state.event_id)
    for p in state.participants:
        if p.player_id:
            player=require(db,Player,p.player_id);p.player_name=player.name
        if p.deck_id:
            if not p.player_id:raise HTTPException(422,'Select a named player for a permanent deck')
            deck=require(db,Deck,p.deck_id)
            if deck.deleted_at:raise HTTPException(409,'A selected deck is in Trash')
            p.deck_name=deck.name;p.commanders=deck.commanders
        if not p.deck_name and not p.commanders:raise HTTPException(422,'Each player needs a deck or commander description')
    return state

@router.get('/studio')
@router.get('/live')
def studio(request: Request,db: Session=Depends(get_db)):
    from app.routes.pages import context,templates
    return templates.TemplateResponse(request=request,name='studio.html',context=context(db,request,live_mode=request.url.path=='/live'))

def member_live_guard(request:Request,obj:LiveGame,state=None):
    if getattr(request.state,'role','owner')!='member':return
    pid=request.state.player_id
    existing={p.get('player_id') for p in (obj.state or {}).get('participants',[])}
    if pid not in existing:raise HTTPException(403,'You may only open live tables you are seated in')
    if state is not None and pid not in {p.player_id for p in state.participants}:
        raise HTTPException(403,'Your player account must remain seated in this live table')

@router.get('/api/live')
def lives(request:Request,db: Session=Depends(get_db)):
    rows=list(db.scalars(select(LiveGame).order_by(LiveGame.created_at.desc()).limit(100)))
    if getattr(request.state,'role','owner')=='member':
        pid=request.state.player_id;rows=[g for g in rows if pid in {p.get('player_id') for p in (g.state or {}).get('participants',[])}]
    return [dump_record(g) for g in rows]
@router.post('/api/live')
def create_live(data: LiveCreate,request:Request,db: Session=Depends(get_db)):
    state=validate_live(db,data.state)
    if getattr(request.state,'role','owner')=='member' and request.state.player_id not in {p.player_id for p in state.participants}:
        raise HTTPException(403,'Your player account must be one of the seats in a live game you create')
    obj=LiveGame(name=data.name,state=state.model_dump());db.add(obj);db.commit();return dump_record(obj)
@router.get('/api/live/{identity}')
def read_live(identity: str,request:Request,db: Session=Depends(get_db)):
    obj=require(db,LiveGame,identity);member_live_guard(request,obj);return dump_record(obj)

def update_live(db,identity,data,request=None):
    obj=require(db,LiveGame,identity)
    if request is not None:member_live_guard(request,obj,data.state)
    if obj.game_id:raise HTTPException(409,'This live game is already complete')
    validate_live(db,data.state)
    result=db.execute(update(LiveGame).where(LiveGame.id==identity,LiveGame.revision==data.revision,LiveGame.game_id.is_(None)).values(state=data.state.model_dump(),revision=data.revision+1,updated_at=now()))
    if result.rowcount!=1:raise HTTPException(409,'Another device saved a newer revision. Keep your local copy, then reload the server state.')
    db.flush();db.refresh(obj);return obj
@router.put('/api/live/{identity}')
def put_live(identity: str,data: LiveUpdate,request:Request,db: Session=Depends(get_db)):
    obj=update_live(db,identity,data,request);db.commit();return dump_record(obj)
@router.post('/api/live/{identity}/finish')
def finish_live(identity: str,data: LiveFinish,request:Request,db: Session=Depends(get_db)):
    obj=require(db,LiveGame,identity);member_live_guard(request,obj,data.state)
    if obj.game_id:return {'game_id':obj.game_id}
    obj=update_live(db,identity,data,request);state=data.state
    elapsed=state.elapsed+max(0,int(time.time()*1000)-(state.timer_since or int(time.time()*1000)))
    participants=[{'player_id':p.player_id,'deck_id':p.deck_id,'player_name':p.player_name,'deck_name':p.deck_name,'commanders':p.commanders,'seat':i+1,'starting':i==state.starting,'winner':p.winner if data.result in ('win','shared') else False,'elimination':None if p.winner else p.elimination} for i,p in enumerate(state.participants)]
    values=GameInput(played_at=state.started_at,location_id=state.location_id,event_id=state.event_id,result=data.result,duration=max(1,round(elapsed/60000)),turns=state.turn,notes=state.notes,memorable=data.memorable,overall_rating=None if getattr(request.state,'role','owner')=='member' else data.enjoyment,participants=participants,submission_key='live-'+identity)
    game=save_game(db,values);obj.game_id=game.id;db.commit();return {'game_id':game.id}

class InviteInput(Input):player_id:str
@router.get('/api/accounts')
def accounts():return list_accounts(config())
@router.post('/api/accounts/invite')
def invite(data: InviteInput,request: Request,db: Session=Depends(get_db)):
    if not config().enabled:raise HTTPException(409,'Enable authentication before inviting players')
    require(db,Player,data.player_id);token=issue(config(),data.player_id)
    db.add(AuditLog(actor='owner',action='invite/reset',entity='account',entity_id=data.player_id,before={},after={}));db.commit()
    return {'url':(config().origin or str(request.base_url).rstrip('/'))+'/join#'+token,'expires_hours':48}
class AccountFlag(Input):disabled:bool
@router.post('/api/accounts/{username}/status')
def account_status(username:str,data:AccountFlag,db:Session=Depends(get_db)):
    with connect(config()) as con:
        result=con.execute('UPDATE accounts SET disabled=? WHERE username=?',(int(data.disabled),username))
        if not result.rowcount:raise HTTPException(404,'Account not found')
        if data.disabled:con.execute('DELETE FROM sessions WHERE token IN (SELECT token FROM session_accounts WHERE username=?)',(username,))
    db.add(AuditLog(actor='owner',action='account access',entity='account',entity_id=username,before={},after={'disabled':data.disabled}));db.commit();return {'ok':True}
@router.delete('/api/accounts/{username}')
def unlink_account(username:str,db:Session=Depends(get_db)):
    with connect(config()) as con:
        con.execute('DELETE FROM sessions WHERE token IN (SELECT token FROM session_accounts WHERE username=?)',(username,))
        con.execute('DELETE FROM invitations WHERE player_id IN (SELECT player_id FROM accounts WHERE username=?)',(username,))
        con.execute('DELETE FROM session_accounts WHERE username=?',(username,));con.execute('DELETE FROM accounts WHERE username=?',(username,))
    db.add(AuditLog(actor='owner',action='unlink account',entity='account',entity_id=username,before={},after={}));db.commit();return {'ok':True}
@router.get('/join')
def join_get(request:Request):
    from app.routes.auth import templates
    token=secrets.token_urlsafe(32)
    response=templates.TemplateResponse(request=request,name='join.html',context={'csrf':token,'message':''})
    response.set_cookie(LOGIN_COOKIE,token,secure=config().hosted,httponly=True,samesite='strict',max_age=1800)
    return response
@router.post('/join')
def join_post(request:Request,token:str=Form(max_length=200),username:str=Form(max_length=80),password:str=Form(max_length=1024),csrf:str=Form(max_length=200)):
    cfg=config()
    if not csrf or not hmac.compare_digest(csrf,request.cookies.get(LOGIN_COOKIE,'')):raise HTTPException(403,'Reload the invitation and try again')
    if not login_attempt(cfg,request.client.host if request.client else 'unknown'):raise HTTPException(429,'Too many attempts; try later')
    try:username=accept(cfg,token,username,password)
    except ValueError as exc:raise HTTPException(422,str(exc))
    raw=create_session(cfg,username)
    response=RedirectResponse('/member',status_code=303)
    response.set_cookie(COOKIE,raw,max_age=7*86400,secure=cfg.hosted,httponly=True,samesite='strict',path='/')
    response.delete_cookie(LOGIN_COOKIE,secure=cfg.hosted,httponly=True,samesite='strict')
    return response

def member_id(request,db):
    pid=request.state.player_id
    if not pid:raise HTTPException(403,'Sign in with a player account to open the player portal')
    require(db,Player,pid);return pid

def feedback_view(db,g,pid):
    rows=list(db.scalars(select(Feedback).where(Feedback.game_id==g.id)))
    registered={a['player_id'] for a in list_accounts(config()) if not a['disabled']}
    expected={p.player_id for p in g.participants if p.player_id in registered}
    done={r.player_id for r in rows if r.confirmed}
    visible=bool(expected) and expected<=done
    mine=next((r for r in rows if r.player_id==pid),None)
    result={'submitted':len(expected&done),'expected':len(expected),'revealed':visible,'mine':dump_record(mine) if mine else None}
    if visible:
        scores=[r.values['overall'] for r in rows if r.player_id in expected and r.values.get('overall') is not None]
        result['overall']=round(sum(scores)/len(scores),2) if scores else None
        result['deck_ratings']={p.id:round(sum(values)/len(values),2) for p in g.participants if (values:=[r.values.get('deck_ratings',{}).get(p.id) for r in rows if r.player_id in expected and r.values.get('deck_ratings',{}).get(p.id) is not None])}
    return result
@router.get('/member')
def member_page(request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db)
    from app.routes.pages import templates
    return templates.TemplateResponse(request=request,name='member.html',context={'player':require(db,Player,pid)})
@router.get('/api/member/home')
def member_home(request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db);games=select_games(db,{'player_id':pid})
    decks=[dump_record(d) for d in db.scalars(select(Deck).where(Deck.owner_id==pid))]
    stats=record([(g,p) for g in games for p in g.participants if p.player_id==pid]);stats.pop('overall',None);stats.pop('enjoyment',None)
    return {'player_id':pid,'name':require(db,Player,pid).name,'decks':decks,'stats':stats,'games':[{'id':g.id,'date':g.played_at,'result':g.result,'participants':[{'id':p.id,'player_id':p.player_id,'name':p.player_name,'deck':p.deck_name,'winner':p.winner} for p in g.participants],'feedback':feedback_view(db,g,pid)} for g in games[:100]]}
@router.post('/api/member/decks')
def member_create(data:DeckInput,request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db)
    if data.owner_id!=pid:raise HTTPException(403,'Choose your own player identity')
    if data.source_url and db.scalar(select(Deck).where(Deck.owner_id==pid,Deck.source_url==data.source_url)):raise HTTPException(409,'You already imported that source. Edit the existing deck instead.')
    from app.routes.api import create_deck
    return create_deck(data,db)
@router.put('/api/member/decks/{identity}')
def member_edit(identity:str,data:DeckInput,request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db);deck=require(db,Deck,identity)
    if deck.owner_id!=pid or data.owner_id!=pid:raise HTTPException(403,'You may only edit your own decks')
    from app.routes.api import edit_deck
    return edit_deck(identity,data,db)
@router.post('/api/member/import')
def member_import(data:dict,request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db)
    from app.routes.features import preview,PreviewInput
    return preview(PreviewInput(url=str(data.get('url','')),owner_id=pid),db)
@router.post('/api/member/games/{identity}/feedback')
def submit_feedback(identity:str,data:FeedbackInput,request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db);g=require(db,Game,identity)
    if g.deleted or pid not in {p.player_id for p in g.participants}:raise HTTPException(403,'You must participate in this game')
    eligible={p.id for p in g.participants if p.player_id!=pid}
    if set(data.deck_ratings)-eligible:raise HTTPException(422,'Only rate opponents’ seats in this game')
    row=db.scalar(select(Feedback).where(Feedback.game_id==identity,Feedback.player_id==pid))
    if row and feedback_view(db,g,pid)['revealed']:raise HTTPException(409,'Feedback is revealed and locked; ask the administrator to reopen it for corrections')
    if not row:row=Feedback(game_id=identity,player_id=pid);db.add(row)
    row.confirmed=data.confirmed;row.values=data.model_dump(exclude={'confirmed'});db.flush()
    if feedback_view(db,g,pid)['revealed']:
        from app.schemas import RatingInput
        from app.services.games import save_rating
        for feedback in db.scalars(select(Feedback).where(Feedback.game_id==identity,Feedback.confirmed==True)):
            for kind in ('overall','sportsmanship'):
                if feedback.values.get(kind) is not None:save_rating(db,RatingInput(game_id=identity,rater_id=feedback.player_id,kind=kind,value=feedback.values[kind]))
            for target,value in feedback.values.get('deck_ratings',{}).items():save_rating(db,RatingInput(game_id=identity,rater_id=feedback.player_id,kind='deck',participant_id=target,value=value))
    db.commit();return feedback_view(db,g,pid)
@router.post('/api/feedback/{identity}/reopen')
def reopen_feedback(identity:str,data:Reason,db:Session=Depends(get_db)):
    rows=list(db.scalars(select(Feedback).where(Feedback.game_id==identity)))
    for row in rows:row.confirmed=False
    for rating in db.scalars(select(Rating).where(Rating.game_id==identity,Rating.rater_id.in_([r.player_id for r in rows]))):db.delete(rating)
    db.add(AuditLog(actor='owner',action='reopen feedback',entity='games',entity_id=identity,before={},after={'reason':data.reason}));db.commit();return {'ok':True}

@router.get('/api/seasons')
def seasons(db:Session=Depends(get_db)):return [dump_record(s) for s in db.scalars(select(Season).order_by(Season.date_from.desc()))]
@router.post('/api/seasons')
def create_season(data:SeasonInput,db:Session=Depends(get_db)):
    obj=Season(**data.model_dump(mode='json'));db.add(obj);db.commit();return dump_record(obj)
@router.put('/api/seasons/{identity}')
def edit_season(identity:str,data:SeasonInput,db:Session=Depends(get_db)):
    obj=require(db,Season,identity)
    for k,v in data.model_dump(mode='json').items():setattr(obj,k,v)
    db.commit();return dump_record(obj)
@router.get('/api/seasons/{identity}/report')
def season_report(identity:str,db:Session=Depends(get_db)):
    from app.services.seasons import report
    return report(db,require(db,Season,identity))

@router.get('/api/leagues')
def leagues(db:Session=Depends(get_db)):return [dump_record(x) for x in db.scalars(select(League))]
@router.post('/api/leagues')
def create_league(data:LeagueInput,db:Session=Depends(get_db)):
    for pid in data.player_ids:require(db,Player,pid)
    obj=League(**data.model_dump());db.add(obj);db.commit();return dump_record(obj)
@router.get('/api/leagues/{identity}')
def get_league(identity:str,db:Session=Depends(get_db)):
    league=require(db,League,identity)
    return {**dump_record(league),'rounds':[dump_record(r) for r in db.scalars(select(LeagueRound).where(LeagueRound.league_id==identity).order_by(LeagueRound.number))],'standings':standings(db,league)}
@router.post('/api/leagues/{identity}/pair')
def pair_round(identity:str,data:PairInput,db:Session=Depends(get_db)):
    league=require(db,League,identity)
    if len(data.attendance)!=len(set(data.attendance)) or set(data.attendance)-set(league.player_ids):raise HTTPException(422,'Attendance must be unique league players')
    previous=list(db.scalars(select(LeagueRound).where(LeagueRound.league_id==identity)))
    if any(not r.locked for r in previous):raise HTTPException(409,'Complete and lock the current round before pairing another')
    if data.exact_pods and len(data.attendance)<data.pod_size:raise HTTPException(422,'Not enough attendees for one pod')
    pods,byes,cost=pair(data.attendance,previous,data.pod_size,data.exact_pods)
    obj=LeagueRound(league_id=identity,number=max((r.number for r in previous),default=0)+1,pairings=pods,byes=byes,results={},scoring=league.scoring.copy());db.add(obj);db.commit();return {**dump_record(obj),'repeat_cost':cost}
@router.put('/api/rounds/{identity}/results')
def round_results(identity:str,data:RoundResults,db:Session=Depends(get_db)):
    rnd=require(db,LeagueRound,identity)
    if rnd.locked:raise HTTPException(409,'Unlock this round with a reason before correcting it')
    if set(data.results)!={str(i) for i in range(len(rnd.pairings))}:raise HTTPException(422,'Choose one recorded game for every pod')
    used={gid for r in db.scalars(select(LeagueRound)) if r.id!=identity for gid in r.results.values()}
    if len(set(data.results.values()))!=len(data.results) or set(data.results.values())&used:raise HTTPException(409,'A game cannot count in two pods or rounds')
    for index,gid in data.results.items():
        g=require(db,Game,gid)
        if g.deleted or g.result not in ('win','shared','draw') or {p.player_id for p in g.participants}!=set(rnd.pairings[int(index)]):raise HTTPException(422,'Each result must be a completed game containing exactly that pod’s players')
    rnd.results=data.results;rnd.locked=True;db.commit();return dump_record(rnd)
@router.post('/api/rounds/{identity}/unlock')
def unlock_round(identity:str,data:Reason,db:Session=Depends(get_db)):
    rnd=require(db,LeagueRound,identity);rnd.locked=False
    db.add(AuditLog(actor='owner',action='unlock round',entity='league_rounds',entity_id=identity,before={},after={'reason':data.reason}));db.commit();return dump_record(rnd)
@router.get('/api/leagues/{identity}/export')
def league_export(identity:str,db:Session=Depends(get_db)):
    import csv,io
    rows=standings(db,require(db,League,identity));out=io.StringIO();w=csv.DictWriter(out,fieldnames=['id','name','points','games','wins','byes']);w.writeheader()
    for row in rows:
        if row['name'].startswith(('=','+','-','@')):row['name']="'"+row['name']
        w.writerow(row)
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="league-standings.csv"'})

@router.post('/api/decks/{identity}/analyze')
def start_analysis(identity:str,tasks:BackgroundTasks,db:Session=Depends(get_db)):
    from app.services.analysis import analyze_job
    from app.db import SessionLocal
    require(db,Deck,identity);job=db.scalar(select(DeckAnalysis).where(DeckAnalysis.deck_id==identity)) or DeckAnalysis(deck_id=identity)
    if job.status=='running' and (datetime.now(timezone.utc)-datetime.fromisoformat(job.updated_at).replace(tzinfo=timezone.utc)).total_seconds()<180:raise HTTPException(409,'Analysis is already running')
    job.status='running';job.error='';db.add(job);db.commit();tasks.add_task(analyze_job,identity,SessionLocal);return {'status':'running'}
@router.get('/api/decks/{identity}/analysis')
def analysis_result(identity:str,db:Session=Depends(get_db)):
    from app.services.analysis import fingerprint,parse_list
    deck=require(db,Deck,identity);job=db.scalar(select(DeckAnalysis).where(DeckAnalysis.deck_id==identity))
    quantities=parse_list(deck.decklist)[0];overlap=[]
    for other in db.scalars(select(Deck).where(Deck.id!=identity,Deck.deleted_at.is_(None))):
        shared=sorted(set(quantities)&set(parse_list(other.decklist)[0]))
        if shared:overlap.append({'deck':other.name,'cards':shared})
    return {**(dump_record(job) if job else {'status':'not_run','result':{}}),'stale':bool(job and job.source_hash!=fingerprint(deck)),'overlap':overlap}
class RoleOverrides(Input):overrides:dict[str,list[str]]
@router.put('/api/decks/{identity}/analysis/roles')
def analysis_roles(identity:str,data:RoleOverrides,db:Session=Depends(get_db)):
    from app.services.analysis import ROLES
    job=db.scalar(select(DeckAnalysis).where(DeckAnalysis.deck_id==identity))
    if not job:raise HTTPException(409,'Run analysis first')
    if len(data.overrides)>250 or any(set(v)-set(ROLES) for v in data.overrides.values()):raise HTTPException(422,'Unknown role or too many overrides')
    job.overrides=data.overrides
    result=json.loads(json.dumps(job.result));counts={}
    for card in result.get('cards',[]):
        if card['name'] in data.overrides:card['roles']=data.overrides[card['name']]
        for role in card['roles']:counts[role]=counts.get(role,0)+card['quantity']
    result['roles']=counts;job.result=result;db.commit();return dump_record(job)
@router.post('/api/decks/{identity}/source-check')
def check_deck_source(identity:str,tasks:BackgroundTasks,db:Session=Depends(get_db)):
    from app.db import SessionLocal
    from app.services.analysis import check_source
    deck=require(db,Deck,identity)
    if not deck.source_url:raise HTTPException(422,'Import this deck from a supported source first')
    tasks.add_task(check_source,identity,SessionLocal);return {'status':'checking'}
@router.get('/api/source-checks')
def source_checks(db:Session=Depends(get_db)):
    from app.services.deck_import import diff
    result=[]
    for obj in db.scalars(select(SourceCheck)):
        deck=db.get(Deck,obj.deck_id)
        if not deck or deck.deleted_at:continue
        changes={k:diff(getattr(deck,k),obj.payload.get(k,'')) for k in ('decklist','sideboard','maybeboard')}
        result.append({**dump_record(obj),'name':deck.name,'changed':any(v['added'] or v['removed'] for v in changes.values()) or any(getattr(deck,k)!=obj.payload.get(k,getattr(deck,k)) for k in ('name','commanders','color_identity')),'changes':changes})
    return result
@router.post('/api/decks/{identity}/source-apply')
def source_apply(identity:str,data:Reason,db:Session=Depends(get_db)):
    from app.services.analysis import fingerprint
    from app.routes.api import edit_deck
    deck=require(db,Deck,identity);check=db.scalar(select(SourceCheck).where(SourceCheck.deck_id==identity))
    if not check or check.error:raise HTTPException(409,'Run a successful source check first')
    if fingerprint(deck)!=check.source_hash:raise HTTPException(409,'The local deck changed after this preview. Check again before applying.')
    values={k:getattr(deck,k) for k in DeckInput.model_fields}
    for k in ('name','commanders','color_identity','decklist','sideboard','maybeboard'):values[k]=check.payload[k]
    db.add(AuditLog(actor='owner',action='apply source',entity='decks',entity_id=identity,before={},after={'reason':data.reason}))
    return edit_deck(identity,DeckInput(**values),db)
class Toggle(Input):enabled:bool
@router.post('/api/maintenance/source-checks')
def auto_checks(data:Toggle,db:Session=Depends(get_db)):
    obj=db.get(Setting,'auto_source_checks') or Setting(key='auto_source_checks');obj.value=data.enabled;db.add(obj);db.commit();return {'enabled':data.enabled}
@router.get('/api/maintenance')
def maintenance_status(db:Session=Depends(get_db)):
    from app.services.maintenance import directory
    enabled=db.get(Setting,'auto_source_checks')
    return {'auto_source_checks':bool(enabled and enabled.value),'backups':[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(directory().glob('scheduled-*.json'),reverse=True)]}
@router.get('/api/backups/download/{name}')
def download_scheduled(name:str):
    import re
    from app.services.maintenance import directory
    if not re.fullmatch(r'scheduled-\d{8}\.json',name):raise HTTPException(404)
    path=directory()/name
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,filename=name,media_type='application/json')
@router.post('/api/backups/scheduled-now')
def scheduled_now():
    from app.services.maintenance import daily_backup
    from app.db import SessionLocal
    daily_backup(SessionLocal);return {'ok':True}
@router.post('/api/restore/preview')
async def restore_preview(file:UploadFile=File(...),db:Session=Depends(get_db)):
    raw=await file.read(50*1024*1024+1)
    if len(raw)>50*1024*1024:raise HTTPException(413,'Backup exceeds 50 MiB')
    try:counts=restore_json(db,json.loads(raw),validate_only=True)
    except Exception as exc:raise HTTPException(422,'Backup rejected: '+str(exc)[:250])
    return {'valid':True,'tables':counts,'current':{k:len(v) for k,v in export_json(db)['tables'].items()},'sha256':hashlib.sha256(raw).hexdigest()}
@router.get('/api/integrity')
def integrity(db:Session=Depends(get_db)):
    try:counts=restore_json(db,export_json(db),validate_only=True)
    except Exception as exc:return {'ok':False,'message':str(exc)[:500]}
    return {'ok':True,'tables':counts}
@router.get('/api/duplicates')
def duplicate_games(db:Session=Depends(get_db)):
    from collections import defaultdict
    groups=defaultdict(list)
    for g in select_games(db):
        key=(g.played_at[:16],tuple(sorted((p.player_id or p.player_name,p.deck_id or p.commanders) for p in g.participants)))
        groups[key].append(g.id)
    return [{'games':ids,'reason':'Same recorded minute, players and decks. Review before deleting.'} for ids in groups.values() if len(ids)>1]
@router.get('/api/audit')
def audit(page:int=1,db:Session=Depends(get_db)):
    return [dump_record(r) for r in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset((max(1,page)-1)*50).limit(50))]
@router.get('/api-documentation')
def api_documentation():
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url='/admin/openapi.json',title='Commander Ledger API')
@router.get('/admin/openapi.json')
def owner_openapi():
    from app.main import app
    return app.openapi()

@router.get('/api/league-game-options')
def league_games(db:Session=Depends(get_db)):
    return [{'id':g.id,'date':g.played_at[:16],'result':g.result,'players':[p.player_id for p in g.participants]} for g in select_games(db) if g.result in ('win','shared','draw') and all(p.player_id for p in g.participants)]

class MemberTrash(Input):deleted:bool
@router.post('/api/member/decks/{identity}/trash')
def member_trash(identity:str,data:MemberTrash,request:Request,db:Session=Depends(get_db)):
    pid=member_id(request,db);deck=require(db,Deck,identity)
    if deck.owner_id!=pid:raise HTTPException(403,'You may only manage your own decks')
    deck.deleted_at=now() if data.deleted else None;db.commit();return dump_record(deck)

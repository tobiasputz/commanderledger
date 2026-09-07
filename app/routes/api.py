from difflib import SequenceMatcher
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.db import get_db
from app.models import Player, Deck, Ownership, Game, Participant, Rating, Location, Event, Setting, now, uid
from app.schemas import PlayerInput, DeckInput, CatalogInput, GameInput, RatingInput
from app.services.games import save_game, save_rating, require
from app.services.backup import dump_record, export_json, restore_json, export_csv, backup_database
from app.services.stats import select_games, group_records, record, matchups
router=APIRouter(prefix='/api')
CATALOG={'players':Player,'decks':Deck,'locations':Location,'events':Event}

def game_dict(g: Game, private: bool=False) -> dict:
    return {**dump_record(g),'participants':[dump_record(p) for p in sorted(g.participants,key=lambda p:p.seat)],'ratings':[dump_record(r,private) for r in g.ratings]}

@router.get('/catalog')
def catalog(db: Session=Depends(get_db)) -> dict:
    return {k:[dump_record(x) for x in db.scalars(select(m))] for k,m in CATALOG.items()}

@router.get('/players/similar')
def similar(name: str, exclude: str='', db: Session=Depends(get_db)) -> list:
    return [dump_record(p) for p in db.scalars(select(Player)) if p.id!=exclude and SequenceMatcher(None,name.casefold(),p.name.casefold()).ratio()>=.75]

@router.post('/players')
def create_player(data: PlayerInput, db: Session=Depends(get_db)) -> dict:
    obj=Player(**data.model_dump()); db.add(obj); db.commit(); return dump_record(obj)

@router.put('/players/{identity}')
def edit_player(identity: str,data: PlayerInput, db: Session=Depends(get_db)) -> dict:
    obj=require(db,Player,identity)
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); return dump_record(obj)

class MergeInput(BaseModel):
    target_id: str
    confirm: bool = False

@router.post('/players/{identity}/merge')
def merge_player(identity: str,data: MergeInput,db: Session=Depends(get_db)) -> dict:
    if not data.confirm or identity==data.target_id: raise HTTPException(400,'Confirm a merge into a different player')
    source=require(db,Player,identity); target=require(db,Player,data.target_id)
    source_games=set(db.scalars(select(Participant.game_id).where(Participant.player_id==identity)))
    target_games=set(db.scalars(select(Participant.game_id).where(Participant.player_id==target.id)))
    if source_games & target_games: raise HTTPException(409,'Both players appear in the same game; resolve those seats first')
    backup_database(db)
    # Historical display and owner snapshots intentionally remain unchanged.
    db.execute(update(Participant).where(Participant.player_id==identity).values(player_id=target.id))
    for deck in db.scalars(select(Deck).where(Deck.owner_id==identity)): deck.owner_id=target.id
    db.execute(update(Ownership).where(Ownership.owner_id==identity).values(owner_id=target.id))
    db.execute(update(Rating).where(Rating.rater_id==identity).values(rater_id=target.id))
    from app.models import SavedPod
    for pod in db.scalars(select(SavedPod)):
        pod.player_ids=list(dict.fromkeys(target.id if pid==identity else pid for pid in pod.player_ids))
        if len(pod.player_ids)<2: db.delete(pod)
    source.archived=True; source.notes+='\nMerged into '+target.name+' ('+target.id+')'
    db.commit(); return {'ok':True}

class ConvertInput(BaseModel):
    participant_ids: list[str]=Field(min_length=1)
    player_id: str | None = None
    name: str | None = None

@router.post('/participants/convert')
def convert(data: ConvertInput, db: Session=Depends(get_db)) -> dict:
    if len(set(data.participant_ids))!=len(data.participant_ids): raise HTTPException(400,'Duplicate appearance selected')
    ps=[require(db,Participant,i) for i in data.participant_ids]
    if any(p.player_id for p in ps): raise HTTPException(400,'Only anonymous seats can be converted')
    if len({p.game_id for p in ps})!=len(ps): raise HTTPException(400,'Select at most one appearance per game')
    player=require(db,Player,data.player_id) if data.player_id else Player(**PlayerInput(name=data.name or '').model_dump())
    db.add(player); db.flush()
    for p in ps:
        if db.scalar(select(Participant).where(Participant.game_id==p.game_id,Participant.player_id==player.id)): raise HTTPException(409,'Player already appears in this game')
        p.player_id=player.id
    db.commit(); return dump_record(player)

@router.post('/decks')
def create_deck(data: DeckInput,db: Session=Depends(get_db)) -> dict:
    require(db,Player,data.owner_id)
    obj=Deck(**data.model_dump(),retired_at=now() if data.status!='active' else None)
    db.add(obj); db.flush(); db.add(Ownership(deck_id=obj.id,owner_id=obj.owner_id))
    from app.services.versions import snapshot
    snapshot(db,obj); db.commit(); return dump_record(obj)

@router.put('/decks/{identity}')
def edit_deck(identity: str,data: DeckInput,db: Session=Depends(get_db)) -> dict:
    obj=require(db,Deck,identity); require(db,Player,data.owner_id)
    if obj.deleted_at: raise HTTPException(409,'Restore this deck before editing it.')
    from app.services.versions import snapshot
    snapshot(db,obj)
    if obj.owner_id!=data.owner_id:
        for history in db.scalars(select(Ownership).where(Ownership.deck_id==obj.id,Ownership.ended_at==None)): history.ended_at=now()
        db.add(Ownership(deck_id=obj.id,owner_id=data.owner_id))
    if obj.status=='active' and data.status!='active': obj.retired_at=now()
    if data.status=='active': obj.retired_at=None
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    snapshot(db,obj)
    db.commit(); return dump_record(obj)

@router.post('/decks/{identity}/copy')
def copy_deck(identity: str,db: Session=Depends(get_db)) -> dict:
    obj=require(db,Deck,identity)
    data={k:getattr(obj,k) for k in DeckInput.model_fields}; data['name']+=' (copy)'; data['status']='active'
    return create_deck(DeckInput(**data),db)

@router.post('/catalog/{kind}')
def create_catalog(kind: str,data: CatalogInput,db: Session=Depends(get_db)) -> dict:
    if kind not in ('locations','events'): raise HTTPException(404)
    obj=CATALOG[kind](**data.model_dump()); db.add(obj); db.commit(); return dump_record(obj)

@router.put('/catalog/{kind}/{identity}')
def edit_catalog(kind: str,identity: str,data: CatalogInput,db: Session=Depends(get_db)) -> dict:
    if kind not in ('locations','events'): raise HTTPException(404)
    obj=require(db,CATALOG[kind],identity)
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); return dump_record(obj)

@router.post('/games')
def create_game(data: GameInput,db: Session=Depends(get_db)) -> dict:
    obj=save_game(db,data); db.commit(); return game_dict(obj)

@router.put('/games/{identity}')
def edit_game(identity: str,data: GameInput,db: Session=Depends(get_db)) -> dict:
    obj=save_game(db,data,identity); db.commit(); return game_dict(obj)

@router.get('/games/{identity}')
def get_game(identity: str, db: Session=Depends(get_db)) -> dict:
    return game_dict(require(db,Game,identity))

class FlagInput(BaseModel):
    deleted: bool

@router.post('/games/{identity}/trash')
def trash_game(identity: str,data: FlagInput,db: Session=Depends(get_db)) -> dict:
    game=require(db,Game,identity); game.deleted=data.deleted; db.commit(); return {'ok':True}

@router.post('/ratings')
def rating(data: RatingInput, db: Session=Depends(get_db)) -> dict:
    obj=save_rating(db,data); db.commit(); return dump_record(obj,False)

@router.get('/ratings/{identity}/private')
def private_rating(identity: str,db: Session=Depends(get_db)) -> dict:
    return dump_record(require(db,Rating,identity))

@router.delete('/ratings/{identity}')
def delete_rating(identity: str,db: Session=Depends(get_db)) -> dict:
    db.delete(require(db,Rating,identity)); db.commit(); return {'ok':True}

@router.get('/statistics')
def statistics(request: Request,db: Session=Depends(get_db)) -> dict:
    games=select_games(db,dict(request.query_params))
    return {'games':len(games),'players':group_records(games,'player_id'),'decks':group_records(games,'deck_id'),'lgs':record([(g,p) for g in games for p in g.participants if p.player_id is None])}

@router.get('/export/json')
def json_backup(db: Session=Depends(get_db)) -> Response:
    import json
    return Response(json.dumps(export_json(db),indent=2,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="commander-backup.json"'})

@router.get('/export/csv/{table}')
def csv_backup(table: str,db: Session=Depends(get_db)) -> Response:
    try: content=export_csv(db,table)
    except ValueError as e: raise HTTPException(400,str(e))
    return Response('\ufeff'+content,media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{table}.csv"'})

@router.get('/export/history')
def history(db: Session=Depends(get_db)) -> Response:
    lines=['COMMANDER LEDGER — GAME HISTORY','']
    for g in select_games(db):
        lines += [f'{g.played_at} | {g.result} | {len(g.participants)} players',g.notes,g.memorable]
        lines += [f'  Seat {p.seat}: {p.player_name} — {p.deck_name or p.commanders}'+(' [winner]' if p.winner else '') for p in g.participants]
        lines += ['']
    return Response('\n'.join(lines),media_type='text/plain',headers={'Content-Disposition':'attachment; filename="game-history.txt"'})

@router.post('/restore')
async def restore(file: UploadFile=File(...),confirm: bool=False,db: Session=Depends(get_db)) -> dict:
    if not confirm: raise HTTPException(400,'Restoring replaces all current records. Confirmation required.')
    import json
    raw=await file.read(50*1024*1024+1)
    if len(raw)>50*1024*1024: raise HTTPException(413,'Backup exceeds 50 MiB')
    try: restore_json(db,json.loads(raw)); db.commit()
    except Exception as e:
        db.rollback(); raise HTTPException(400,'Backup rejected; current data preserved. '+str(e)[:250])
    return {'ok':True}

@router.post('/backup')
def manual_backup(db: Session=Depends(get_db)) -> dict:
    return {'path':str(backup_database(db))}

class SettingsInput(BaseModel):
    backup_directory: str = Field(min_length=1)
    minimum_games: int = Field(default=5,ge=1,le=1000)
    hide_sensitive: bool = False
    rating_labels: list[str] = Field(default=['Very unenjoyable','Unenjoyable','Neutral','Enjoyable','Very enjoyable'],min_length=5,max_length=5)
    current_event: str = ''

@router.get('/settings')
def settings(db: Session=Depends(get_db)) -> dict:
    from app.security import config
    import os
    values={s.key:s.value for s in db.scalars(select(Setting))}
    if config().hosted: values['backup_directory']=os.environ['COMMANDER_BACKUPS']
    return values

@router.put('/settings')
def save_settings(data: SettingsInput,db: Session=Depends(get_db)) -> dict:
    from pathlib import Path
    from app.security import config
    import os
    if config().hosted: data.backup_directory=os.environ['COMMANDER_BACKUPS']
    directory=Path(data.backup_directory).expanduser(); directory.mkdir(parents=True,exist_ok=True)
    for k,v in data.model_dump().items():
        obj=db.get(Setting,k)
        if obj: obj.value=v
        else: db.add(Setting(key=k,value=v))
    db.commit(); return {'ok':True}

@router.get('/anonymous')
def anonymous(db: Session=Depends(get_db)) -> list:
    return [{**dump_record(p),'played_at':g.played_at} for g in select_games(db) for p in g.participants if p.player_id is None]

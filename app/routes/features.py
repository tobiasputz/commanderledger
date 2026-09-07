"""Collection and at-table features, protected by the existing auth boundary."""
from datetime import datetime
from collections import Counter
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import Field,field_validator
from app.schemas import Input,DeckInput
from app.db import get_db
from app.models import Deck,DeckVersion,SavedPod,Player,Participant,now
from app.services.games import require
from app.services.backup import dump_record
from app.services.versions import snapshot
from app.services.stats import select_games,record,ratings_summary
from app.services.deck_import import client,identify,diff,ImportError
router=APIRouter()

class PodInput(Input):
    name: str=Field(min_length=1,max_length=180)
    player_ids: list[str]=Field(min_length=2,max_length=20)
    @field_validator('player_ids')
    @classmethod
    def unique(cls,v):
        if len(v)!=len(set(v)): raise ValueError('Choose each player once.')
        return v

@router.get('/api/pods')
def pods(db: Session=Depends(get_db)):
    return [dump_record(p) for p in db.scalars(select(SavedPod).order_by(SavedPod.name))]

@router.post('/api/pods')
def save_pod(data: PodInput,db: Session=Depends(get_db)):
    for pid in data.player_ids: require(db,Player,pid)
    obj=SavedPod(**data.model_dump());db.add(obj);db.commit();return dump_record(obj)

@router.put('/api/pods/{identity}')
def edit_pod(identity: str,data: PodInput,db: Session=Depends(get_db)):
    for pid in data.player_ids: require(db,Player,pid)
    obj=require(db,SavedPod,identity)
    for key,value in data.model_dump().items(): setattr(obj,key,value)
    db.commit();return dump_record(obj)

@router.delete('/api/pods/{identity}')
def delete_pod(identity: str,db: Session=Depends(get_db)):
    db.delete(require(db,SavedPod,identity));db.commit();return {'ok':True}

class TrashInput(Input):
    deleted: bool

@router.post('/api/decks/{identity}/trash')
def trash(identity: str,data: TrashInput,db: Session=Depends(get_db)):
    deck=require(db,Deck,identity);deck.deleted_at=now() if data.deleted else None;db.commit();return dump_record(deck)

class VersionInput(Input):
    name: str=Field(min_length=1,max_length=180)

@router.post('/api/decks/{identity}/versions')
def new_version(identity: str,data: VersionInput,db: Session=Depends(get_db)):
    deck=require(db,Deck,identity)
    if deck.deleted_at: raise HTTPException(409,'Restore this deck first.')
    v=snapshot(db,deck,data.name);db.commit();return dump_record(v)

@router.get('/api/decks/{identity}/versions')
def versions(identity: str,db: Session=Depends(get_db)):
    require(db,Deck,identity)
    pairs=[(g,p) for g in select_games(db,{'deck_id':identity}) for p in g.participants if p.deck_id==identity]
    rows=[{**dump_record(v),'stats':record([(g,p) for g,p in pairs if p.deck_version_id==v.id])} for v in db.scalars(select(DeckVersion).where(DeckVersion.deck_id==identity).order_by(DeckVersion.created_at.desc(),DeckVersion.id.desc()))]
    return {'versions':rows,'unrecorded':record([(g,p) for g,p in pairs if not p.deck_version_id])}

class PreviewInput(Input):
    url: str=Field(max_length=1000)
    owner_id: str
    refresh: bool=False
    deck_id: str | None=None

@router.post('/api/deck-import/preview')
def preview(data: PreviewInput,db: Session=Depends(get_db)):
    require(db,Player,data.owner_id)
    try: result=client.fetch(data.url,data.refresh)
    except ImportError as exc: raise HTTPException(422,str(exc))
    # Enrich only commanders when the source has no color identity.
    if result['commanders'] and not result['color_identity']:
        from app.services.scryfall import client as scryfall,ScryfallError
        try: result['color_identity']=scryfall.lookup(result['commanders'])['color_identity']
        except ScryfallError: result['warnings']=[*result['warnings'],'Color identity could not be looked up; check it manually.']
    matches=[]
    for deck in db.scalars(select(Deck).where(Deck.owner_id==data.owner_id)):
        urls=[deck.source_url,*deck.links]
        for url in urls:
            try: canonical=identify(url)[2]
            except ImportError: continue
            if canonical==result['source_url']:
                matches.append({'id':deck.id,'name':deck.name,'deleted':bool(deck.deleted_at)});break
    result['matches']=matches
    if data.deck_id:
        deck=require(db,Deck,data.deck_id)
        result['changes']={k:diff(getattr(deck,k),result[k]) for k in ('decklist','sideboard','maybeboard')}
        result['metadata_changes']={k:{'before':getattr(deck,k),'after':result[k]} for k in ('name','commanders','color_identity') if getattr(deck,k)!=result[k]}
    return result

class ImportSave(Input):
    deck: DeckInput
    target_id: str | None=None
    create_copy: bool=False

@router.post('/api/deck-import/save')
def import_save(data: ImportSave,db: Session=Depends(get_db)):
    from app.routes.api import create_deck,edit_deck
    if not data.deck.source_url: raise HTTPException(422,'Import requires its source link.')
    canonical=identify(data.deck.source_url)[2]
    if not data.target_id and not data.create_copy:
        for d in db.scalars(select(Deck).where(Deck.owner_id==data.deck.owner_id)):
            for url in [d.source_url,*d.links]:
                try: match=identify(url)[2]==canonical
                except ImportError: continue
                if match: raise HTTPException(409,'This owner already has this source deck. Choose Update existing, Create copy, or restore it from Trash.')
    return edit_deck(data.target_id,data.deck,db) if data.target_id else create_deck(data.deck,db)

@router.get('/api/deck-suggestions')
def suggestions(owner_id: str='',bracket: int | None=None,mode: str='least_recent',db: Session=Depends(get_db)):
    if mode not in ('least_recent','fewest_games'): raise HTTPException(422,'Unknown suggestion mode')
    if bracket is not None and not 1<=bracket<=5: raise HTTPException(422,'Bracket must be 1–5')
    games=select_games(db);rows=[]
    for d in db.scalars(select(Deck).where(Deck.deleted_at.is_(None),Deck.status=='active')):
        if owner_id and d.owner_id!=owner_id or bracket is not None and d.bracket!=bracket: continue
        played=[g.played_at for g in games if any(p.deck_id==d.id for p in g.participants)]
        rows.append({**dump_record(d),'games':len(played),'last_played':max(played) if played else None,'reason':'Never played' if not played else f'{len(played)} games · last played {max(played)[:10]}'})
    rows.sort(key=lambda r:(r['games'],r['last_played'] or '',r['name']) if mode=='fewest_games' else (r['last_played'] or '',r['games'],r['name']))
    return rows[:12]

@router.get('/api/recap')
def recap(month: str,db: Session=Depends(get_db)):
    import re
    if not re.fullmatch(r'\d{4}-\d{2}',month): raise HTTPException(422,'Choose a month as YYYY-MM')
    try: datetime.strptime(month,'%Y-%m')
    except ValueError: raise HTTPException(422,'Choose a valid month')
    games=[g for g in select_games(db) if g.played_at.startswith(month)]
    durations=[g.duration for g in games if g.duration]
    favorites=[]
    from app.models import Setting
    hidden=db.get(Setting,'hide_sensitive');sensitive=bool(hidden and hidden.value)
    for g in games:
        values=[r.value for r in g.ratings if r.kind=='overall']
        if values and not sensitive: favorites.append({'id':g.id,'date':g.played_at[:10],'score':sum(values)/len(values),'ratings':len(values)})
    return {'month':month,'games':len(games),'players':len({p.player_id for g in games for p in g.participants if p.player_id}),'anonymous_appearances':sum(not p.player_id for g in games for p in g.participants),'decks':len({p.deck_id or ('anonymous',p.deck_name,p.commanders) for g in games for p in g.participants}),'minutes':sum(durations),'timed_games':len(durations),'favorites':sorted(favorites,key=lambda x:x['score'],reverse=True)[:5],'moments':[{'id':g.id,'date':g.played_at[:10],'text':g.memorable} for g in games if g.memorable]}

@router.get('/table')
def table_page(request: Request,db: Session=Depends(get_db)):
    from app.routes.pages import templates,context
    return templates.TemplateResponse(request=request,name='table.html',context=context(db))

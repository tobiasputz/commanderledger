import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.models import Base, Player, Deck, Ownership, Location, Event, Game, Participant, Rating, Setting, DeckVersion, SavedPod, LiveGame, Season, League, LeagueRound, Feedback, DeckAnalysis, SourceCheck, AuditLog
from app.db import DB_PATH, ROOT
TABLES=[Player,Deck,DeckVersion,Ownership,Location,Event,SavedPod,Game,Participant,Rating,Setting,LiveGame,Season,League,LeagueRound,Feedback,DeckAnalysis,SourceCheck,AuditLog]

def dump_record(obj: object, private: bool = True) -> dict:
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if private or c.name!='private_note'}

def export_json(db: Session) -> dict:
    return {'format':'commander-ledger','version':3,'exported_at':datetime.now(timezone.utc).isoformat(),'tables':{m.__tablename__:[dump_record(x) for x in db.scalars(select(m))] for m in TABLES}}

def backup_database(db: Session | None = None, source: Path = DB_PATH) -> Path | None:
    if db is not None and db.get_bind().dialect.name!='sqlite':
        directory=Path(os.getenv('COMMANDER_BACKUPS',str(ROOT/'backups')));directory.mkdir(parents=True,exist_ok=True)
        path=directory/('commander-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
        path.write_text(json.dumps(export_json(db),ensure_ascii=False),encoding='utf-8');return path
    if not source.exists(): return None
    setting=db.get(Setting,'backup_directory') if db else None
    saved_directory=setting.value if setting else None
    if db is None and source.exists():
        with sqlite3.connect(str(source)) as con:
            if con.execute("SELECT name FROM sqlite_master WHERE name='settings'").fetchone():
                row=con.execute("SELECT value FROM settings WHERE key='backup_directory'").fetchone()
                if row: saved_directory=json.loads(row[0])
    from app.security import config
    if config().hosted: saved_directory=None
    directory=Path(saved_directory or os.getenv('COMMANDER_BACKUPS',str(ROOT/'backups'))).expanduser()
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/('commander-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(path)) as dst: src.backup(dst)
    return path

def restore_json(db: Session, data: dict, validate_only: bool=False) -> dict | None:
    if data.get('format')!='commander-ledger' or data.get('version') not in (1,2,3): raise ValueError('Unsupported backup format')
    import copy
    tables=copy.deepcopy(data.get('tables',{}))
    new_tables={'live_games','seasons','leagues','league_rounds','feedback','deck_analysis','source_checks','audit_log'}
    if data['version']<3:
        if set(tables)&new_tables: raise ValueError('Unexpected tables for this backup version')
        for name in new_tables: tables[name]=[]
    if data['version']==1:
        expected={m.__tablename__ for m in TABLES}-{'deck_versions','saved_pods'}
        if set(tables)!=expected: raise ValueError('Backup is missing required tables')
        tables['deck_versions']=[];tables['saved_pods']=[]
        for row in tables['decks']:
            for key,value in {'deleted_at':None,'source_url':'','sideboard':'','maybeboard':''}.items(): row.setdefault(key,value)
        for row in tables['participants']: row.setdefault('deck_version_id',None)
    if set(tables)!={m.__tablename__ for m in TABLES}: raise ValueError('Backup is missing required tables')
    # Validate in isolated database first, including constraints and every foreign key.
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session as TestSession
    temp=create_engine('sqlite:///:memory:')
    @event.listens_for(temp,'connect')
    def fk(conn: object, _: object) -> None: conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(temp)
    try:
        with TestSession(temp) as check:
            check.info['skip_audit']=True
            for model in TABLES:
                if not isinstance(tables[model.__tablename__],list): raise ValueError('Invalid table rows')
                for row in tables[model.__tablename__]:
                    if set(row)!={c.name for c in model.__table__.columns}: raise ValueError('Invalid backup columns')
                    if 'id' in row:
                        from uuid import UUID
                        UUID(row['id'])
                    check.add(model(**row))
                check.flush()
            # Apply the same user-input validation before trusting imported URLs or colors.
            from app.schemas import GameInput, PlayerInput, DeckInput, ParticipantInput, CatalogInput
            for model, schema in ((Player,PlayerInput),(Deck,DeckInput),(Location,CatalogInput),(Event,CatalogInput)):
                for obj in check.scalars(select(model)):
                    schema(**{key:getattr(obj,key) for key in schema.model_fields})
            for obj in check.scalars(select(Participant)):
                ParticipantInput(**{key:getattr(obj,key) for key in ParticipantInput.model_fields})
            for pod in check.scalars(select(SavedPod)):
                from app.routes.features import PodInput
                PodInput(name=pod.name,player_ids=pod.player_ids)
                if any(not check.get(Player,pid) for pid in pod.player_ids): raise ValueError('Saved pod references a missing player')
            for version in check.scalars(select(DeckVersion)):
                if not version.name.strip() or len(version.name)>180: raise ValueError('Invalid version name')
            for participant in check.scalars(select(Participant)):
                if participant.deck_version_id and check.get(DeckVersion,participant.deck_version_id).deck_id!=participant.deck_id: raise ValueError('Version belongs to another deck')
            # Validate cross-row game result invariants.
            for game in check.scalars(select(Game)):
                participants=[{k:getattr(p,k) for k in ('id','player_id','deck_id','player_name','deck_name','commanders','archetype','deck_links','notes','seat','starting','winner','elimination')} for p in game.participants]
                GameInput(**{k:getattr(game,k) for k in GameInput.model_fields if hasattr(game,k) and k!='participants'},participants=participants)
            for rating in check.scalars(select(Rating)):
                if rating.participant_id and check.get(Participant,rating.participant_id).game_id!=rating.game_id: raise ValueError('Rating target belongs to another game')
                if (rating.kind=='deck') != (rating.participant_id is not None): raise ValueError('Invalid rating target')
                if rating.rater_id and not any(p.player_id==rating.rater_id for p in check.get(Game,rating.game_id).participants): raise ValueError('Rater did not participate')
            rating_keys=[(r.game_id,r.participant_id,r.rater_id,r.kind) for r in check.scalars(select(Rating))]
            if len(set(rating_keys))!=len(rating_keys): raise ValueError('Duplicate ratings in backup')
            # Validate all structured v5 data as strictly as ordinary API input.
            from app.schemas.playgroup import LiveState,SeasonInput,LeagueInput,Scoring,FeedbackInput
            players={p.id for p in check.scalars(select(Player))}
            counted_games=set()
            for live in check.scalars(select(LiveGame)):
                LiveState(**live.state)
                if live.revision<0: raise ValueError('Invalid live-game revision')
                if live.game_id and not check.get(Game,live.game_id): raise ValueError('Live game references a missing recorded game')
            for season in check.scalars(select(Season)):
                SeasonInput(name=season.name,date_from=season.date_from,date_to=season.date_to)
            for league in check.scalars(select(League)):
                LeagueInput(name=league.name,player_ids=league.player_ids,scoring=league.scoring)
                if set(league.player_ids)-players: raise ValueError('League references a missing player')
                rounds=list(check.scalars(select(LeagueRound).where(LeagueRound.league_id==league.id)))
                if len({r.number for r in rounds})!=len(rounds): raise ValueError('Duplicate league round number')
                for rnd in rounds:
                    Scoring(**rnd.scoring)
                    seats=[pid for pod in rnd.pairings for pid in pod]
                    if len(seats)!=len(set(seats)) or set(seats+rnd.byes)-set(league.player_ids): raise ValueError('Invalid league pairings')
                    if any(not 3<=len(pod)<=5 for pod in rnd.pairings): raise ValueError('League pods must contain 3–5 players')
                    if set(rnd.results)!={str(i) for i in range(len(rnd.pairings))} and rnd.locked: raise ValueError('Locked round is missing results')
                    for index,gid in rnd.results.items():
                        if gid in counted_games: raise ValueError('A game is counted in multiple league pods')
                        counted_games.add(gid);game=check.get(Game,gid)
                        if not game or game.deleted or {p.player_id for p in game.participants}!=set(rnd.pairings[int(index)]): raise ValueError('League result does not match its pod')
            for feedback in check.scalars(select(Feedback)):
                game=check.get(Game,feedback.game_id)
                if not game or feedback.player_id not in {p.player_id for p in game.participants}: raise ValueError('Feedback author did not participate')
                FeedbackInput(confirmed=feedback.confirmed,**feedback.values)
                targets={p.id for p in game.participants if p.player_id!=feedback.player_id}
                if set(feedback.values.get('deck_ratings',{}))-targets: raise ValueError('Feedback targets another game or the author')
    finally: temp.dispose()
    if validate_only: return {name:len(rows) for name,rows in tables.items()}
    backup_database(db)
    db.info['skip_audit']=True
    # Caller commits the complete replacement once; failures roll back all tables.
    db.expunge_all()
    for model in reversed(TABLES): db.execute(delete(model))
    for model in TABLES:
        for row in tables[model.__tablename__]: db.add(model(**row))
        db.flush()
    db.info['skip_audit']=False

def export_csv(db: Session, table: str) -> str:
    model=next((m for m in TABLES if m.__tablename__==table),None)
    if model is None: raise ValueError('Unknown export table')
    columns=[c.name for c in model.__table__.columns if c.name!='private_note']
    output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=columns); writer.writeheader()
    for obj in db.scalars(select(model)):
        row=dump_record(obj,False)
        for key,value in row.items():
            if isinstance(value,(list,dict)): row[key]=json.dumps(value,ensure_ascii=False)
            elif isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')): row[key]="'"+value
        writer.writerow(row)
    return output.getvalue()

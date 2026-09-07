import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.models import Base, Player, Deck, Ownership, Location, Event, Game, Participant, Rating, Setting
from app.db import DB_PATH, ROOT
TABLES=[Player,Deck,Ownership,Location,Event,Game,Participant,Rating,Setting]

def dump_record(obj: object, private: bool = True) -> dict:
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if private or c.name!='private_note'}

def export_json(db: Session) -> dict:
    return {'format':'commander-ledger','version':1,'exported_at':datetime.now(timezone.utc).isoformat(),'tables':{m.__tablename__:[dump_record(x) for x in db.scalars(select(m))] for m in TABLES}}

def backup_database(db: Session | None = None, source: Path = DB_PATH) -> Path | None:
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

def restore_json(db: Session, data: dict) -> None:
    if data.get('format')!='commander-ledger' or data.get('version')!=1: raise ValueError('Unsupported backup format')
    tables=data.get('tables',{})
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
    finally: temp.dispose()
    backup_database(db)
    # Caller commits the complete replacement once; failures roll back all tables.
    db.expunge_all()
    for model in reversed(TABLES): db.execute(delete(model))
    for model in TABLES:
        for row in tables[model.__tablename__]: db.add(model(**row))
        db.flush()

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

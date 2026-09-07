import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.models import Base,Player,Deck,Ownership,uid
from app.db import get_db
from app.main import app

@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(conn,_): conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as session: yield session
    engine.dispose()

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db]=lambda:db
    # Do not run lifespan against the user's real database.
    client=TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def records(db):
    players=[];decks=[]
    for i in range(5):
        p=Player(name=f'Player {i}');db.add(p);db.flush()
        d=Deck(name=f'Deck {i}',owner_id=p.id,commanders=f'Commander {i}')
        db.add(d);db.flush();db.add(Ownership(deck_id=d.id,owner_id=p.id,started_at='2025-01-01T00:00:00+00:00'))
        players.append(p);decks.append(d)
    db.commit()
    return players,decks

def payload(records,size=4,result='win',winners=None,anonymous=False):
    players,decks=records
    winners=([0] if result=='win' else [0,1] if result=='shared' else []) if winners is None else winners
    return {'played_at':'2026-07-01T20:00:00','result':result,'submission_key':uid(),'participants':[{'player_id':None if anonymous and i==size-1 else players[i].id,'deck_id':None if anonymous and i==size-1 else decks[i].id,'commanders':'LGS commander' if anonymous and i==size-1 else '', 'seat':i+1,'winner':i in winners,'starting':i==0} for i in range(size)]}

@pytest.fixture(autouse=True)
def isolate_backup_directory(tmp_path,monkeypatch):
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path/'backups'))

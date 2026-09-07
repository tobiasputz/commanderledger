import copy
import json
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,inspect,text
from app.db import ROOT
from app.models import Player
from app.services.backup import export_json,restore_json,export_csv
from conftest import payload

def test_round_trip(client,records,db,tmp_path,monkeypatch):
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path))
    g=client.post('/api/games',json=payload(records,anonymous=True)).json()
    before=export_json(db)
    db.add(Player(name='Not in backup'));db.commit()
    restore_json(db,before);db.commit()
    after=export_json(db)
    assert before['tables']==after['tables']
    assert g['id'] in export_csv(db,'games')

def test_invalid_restore_preserves_records(client,records,db):
    client.post('/api/games',json=payload(records))
    before=export_json(db)
    broken=copy.deepcopy(before);broken['tables']['participants'][0]['player_id']='missing'
    with pytest.raises(Exception): restore_json(db,broken)
    assert export_json(db)['tables']==before['tables']

def test_restore_http(client,records,tmp_path,monkeypatch):
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path))
    client.post('/api/games',json=payload(records))
    data=client.get('/api/export/json').content
    assert client.post('/api/restore',files={'file':('backup.json',data,'application/json')}).status_code==400
    assert client.post('/api/restore?confirm=true',files={'file':('backup.json',data,'application/json')}).status_code==200

def test_csv_formula_escaping(client,db):
    client.post('/api/players',json={'name':'=1+1'})
    assert "'=1+1" in export_csv(db,'players')

def test_migration_upgrade_downgrade_and_backup(tmp_path,monkeypatch):
    monkeypatch.setenv('COMMANDER_BACKUPS',str(tmp_path/'backups'))
    path=tmp_path/'migrate.sqlite3'
    config=Config(str(ROOT/'alembic.ini'));config.attributes['url']='sqlite:///'+str(path)
    command.upgrade(config,'head')
    engine=create_engine(config.attributes['url'])
    assert {'games','participants','players','decks','ratings','ownerships'}<=set(inspect(engine).get_table_names())
    with engine.begin() as conn: conn.execute(text("INSERT INTO players (id,name,preferred_name,notes,color,archived,created_at,updated_at) VALUES ('p','P','','','#a995ef',0,'now','now')"))
    command.upgrade(config,'head')
    with engine.connect() as conn: assert conn.execute(text('SELECT count(*) FROM players')).scalar()==1
    assert list((tmp_path/'backups').glob('*.sqlite3'))
    command.downgrade(config,'base')
    assert 'players' not in inspect(engine).get_table_names()
    command.upgrade(config,'head');engine.dispose()

def test_restore_rejects_unsafe_urls(client,records,db):
    original=export_json(db)
    unsafe=copy.deepcopy(original)
    unsafe['tables']['decks'][0]['links']=['javascript:alert(1)']
    with pytest.raises(ValueError): restore_json(db,unsafe)
    assert export_json(db)['tables']==original['tables']

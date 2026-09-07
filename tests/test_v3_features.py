import copy
import httpx
import pytest
from sqlalchemy import select,create_engine,text
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.db import ROOT
from app.models import Deck,DeckVersion,Participant,Game
from app.services.backup import export_json,restore_json
from app.services.deck_import import identify,normalize,ImportClient,ImportError
from tests.conftest import payload

ARCH={'name':'Partner build','categories':[{'name':'Considering','includedInDeck':False}],'cards':[
 {'quantity':1,'categories':['Commander'],'card':{'oracleCard':{'name':'Tymna the Weaver','colorIdentity':['W','B']}}},
 {'quantity':1,'categories':['Commander'],'card':{'oracleCard':{'name':'Thrasios, Triton Hero','colorIdentity':['G','U']}}},
 {'quantity':10,'categories':['Land'],'card':{'oracleCard':{'name':'Forest'}}},
 {'quantity':1,'categories':['Maybeboard'],'card':{'oracleCard':{'name':'Sol Ring'}}},
 {'quantity':1,'categories':['Considering'],'card':{'oracleCard':{'name':'Arcane Signet'}}}]}

def deck_input(d,**changes):
 from app.schemas import DeckInput
 return {**{k:getattr(d,k) for k in DeckInput.model_fields},**changes}

@pytest.mark.parametrize('url',['http://archidekt.com/decks/123','https://archidekt.com.evil.org/decks/123','https://localhost/decks/123','https://archidekt.com:123/decks/1','https://a@archidekt.com/decks/1','https://archidekt.com/decks/../foo','https://moxfield.com/help'])
def test_import_url_boundary(url):
 with pytest.raises(ImportError): identify(url)

def test_normalizers():
 a=normalize('archidekt',ARCH,'https://archidekt.com/decks/1')
 assert a['commanders']=='Tymna the Weaver; Thrasios, Triton Hero'
 assert a['color_identity']=='WUBG'
 assert '10 Forest' in a['decklist'] and 'Sol Ring' not in a['decklist']
 assert a['maybeboard']=='1 Sol Ring' and a['sideboard']=='1 Arcane Signet'
 m={'name':'Test','commanders':{'a':{'quantity':1,'card':{'name':'A','color_identity':['R']}}},'mainboard':{'b':{'quantity':2,'card':{'name':'Mountain'}}},'sideboard':{},'maybeboard':{}}
 r=normalize('moxfield',m,'https://moxfield.com/decks/abc')
 assert r['commanders']=='A' and r['color_identity']=='R' and '2 Mountain' in r['decklist']
 m['boards']={k:{'cards':m[k]} for k in ('commanders','mainboard','sideboard','maybeboard')}
 assert normalize('moxfield',m,'url')['decklist']==r['decklist']

def test_import_network_cache_and_denial():
 calls=[]
 def handler(req):
  calls.append(str(req.url));return httpx.Response(200,json=ARCH)
 c=ImportClient(httpx.MockTransport(handler))
 assert c.fetch('https://www.archidekt.com/decks/123/title')['name']=='Partner build'
 assert c.fetch('https://archidekt.com/decks/123')['name']=='Partner build'
 assert calls==['https://archidekt.com/api/decks/123/']
 for status in (302,403,404,429):
  c=ImportClient(httpx.MockTransport(lambda r:httpx.Response(status,headers={'Location':'http://127.0.0.1'})))
  with pytest.raises(ImportError): c.fetch('https://moxfield.com/decks/abc')

def test_import_duplicate_refresh_preserves_identity(client,records,monkeypatch):
 from app.services.deck_import import client as provider
 monkeypatch.setattr(provider,'fetch',lambda *a,**k:normalize('archidekt',ARCH,'https://archidekt.com/decks/123'))
 owner=records[0][0].id
 preview=client.post('/api/deck-import/preview',json={'url':'https://archidekt.com/decks/123','owner_id':owner}).json()
 data={k:preview[k] for k in ('name','commanders','color_identity','source_url','links','decklist','sideboard','maybeboard')};data['owner_id']=owner
 result=client.post('/api/deck-import/save',json={'deck':data});assert result.status_code==200,result.text
 identity=result.json()['id']
 assert client.post('/api/deck-import/save',json={'deck':data}).status_code==409
 assert client.post('/api/deck-import/save',json={'deck':data,'create_copy':True}).status_code==200
 preview=client.post('/api/deck-import/preview',json={'url':data['source_url'],'owner_id':owner,'deck_id':identity}).json()
 assert len(preview['matches'])==2 and preview['changes']['decklist']['added']==[]
 data['decklist']+='\n1 Island'
 saved=client.post('/api/deck-import/save',json={'deck':data,'target_id':identity})
 assert saved.json()['id']==identity
 versions=client.get(f'/api/decks/{identity}/versions').json()['versions'];assert len(versions)==2

def test_trash_history_and_versions(client,db,records):
 data=payload(records);saved=client.post('/api/games',json=data).json();identity=records[1][0].id
 p=next(p for p in saved['participants'] if p['deck_id']==identity);original_version=p['deck_version_id']
 assert original_version
 update=deck_input(records[1][0],decklist='1 Forest')
 assert client.put('/api/decks/'+identity,json=update).status_code==200
 assert client.get('/api/games/'+saved['id']).json()['participants'][0]['deck_version_id']==original_version
 assert client.post('/api/decks/'+identity+'/trash',json={'deleted':True}).status_code==200
 assert identity not in client.get('/fragments/decks?player_id='+records[0][0].id).text
 assert client.post('/api/games',json=payload(records)).status_code==409
 edit=copy.deepcopy(data);edit['participants']=saved['participants']
 from app.schemas import ParticipantInput
 edit['participants']=[{k:v for k,v in p.items() if k in ParticipantInput.model_fields} for p in saved['participants']]
 assert client.put('/api/games/'+saved['id'],json=edit).status_code==200
 assert client.get('/api/statistics').json()['games']==1
 assert client.post('/api/decks/'+identity+'/trash',json={'deleted':False}).status_code==200
 assert client.post('/api/games',json=payload(records)).status_code==200


def test_version_selection_and_foreign_version_rejected(client,records):
 client.post('/api/games',json=payload(records))
 deck=records[1][0];versions=client.get('/api/decks/'+deck.id+'/versions').json()['versions'];old=versions[0]['id']
 client.put('/api/decks/'+deck.id,json=deck_input(deck,commanders='New Commander'))
 data=payload(records);data['participants'][0]['deck_version_id']=old
 result=client.post('/api/games',json=data);assert result.status_code==200,result.text
 assert result.json()['participants'][0]['commanders']=='Commander 0'
 data=payload(records);data['participants'][1]['deck_version_id']=old
 assert client.post('/api/games',json=data).status_code==400

def test_pods_recap_and_suggestions(client,db,records):
 ids=[p.id for p in records[0][:3]]
 p=client.post('/api/pods',json={'name':'Friday','player_ids':ids}).json()
 assert client.get('/api/pods').json()[0]['player_ids']==ids
 assert client.post('/api/pods',json={'name':'Bad','player_ids':[ids[0],ids[0]]}).status_code==422
 assert client.put('/api/pods/'+p['id'],json={'name':'Saturday','player_ids':ids[::-1]}).status_code==200
 game=payload(records);game.update(duration=60,overall_rating=5,memorable='Topdeck win!')
 client.post('/api/games',json=game)
 recap=client.get('/api/recap?month=2026-07').json()
 assert recap['games']==1 and recap['minutes']==60 and recap['moments'][0]['text']=='Topdeck win!'
 assert client.get('/api/recap?month=2026-99').status_code==422
 rows=client.get('/api/deck-suggestions').json();assert rows[0]['id']==records[1][4].id
 client.post('/api/decks/'+rows[0]['id']+'/trash',json={'deleted':True})
 assert rows[0]['id'] not in [r['id'] for r in client.get('/api/deck-suggestions').json()]
 assert client.delete('/api/pods/'+p['id']).status_code==200
 for page in ('/table','/manage/decks','/games/new'):
  result=client.get(page);assert result.status_code==200,result.text

def test_backup_v2_and_legacy(client,db,records):
 client.post('/api/games',json=payload(records))
 client.post('/api/pods',json={'name':'Pod','player_ids':[p.id for p in records[0][:2]]})
 client.post('/api/decks/'+records[1][0].id+'/trash',json={'deleted':True})
 backup=export_json(db);restore_json(db,backup);db.commit()
 assert export_json(db)['tables']==backup['tables']
 legacy=copy.deepcopy(backup);legacy['version']=1
 del legacy['tables']['deck_versions'];del legacy['tables']['saved_pods']
 for row in legacy['tables']['decks']:
  for k in ('deleted_at','source_url','sideboard','maybeboard'):row.pop(k)
 for row in legacy['tables']['participants']:row.pop('deck_version_id')
 restore_json(db,legacy);db.commit()
 assert db.scalar(select(Game)) and db.scalar(select(Participant)).deck_version_id is None


def test_upgrade_populated_v1(tmp_path):
 config=Config(str(ROOT/'alembic.ini'));config.attributes['url']='sqlite:///'+str(tmp_path/'old.db')
 command.upgrade(config,'0001')
 from migrations.schema_v1 import Player as OldPlayer,Deck as OldDeck
 engine=create_engine(config.attributes['url'])
 with Session(engine) as db:
  p=OldPlayer(name='Existing');db.add(p);db.flush();d=OldDeck(name='Old deck',owner_id=p.id,commanders='Old commander');db.add(d);db.commit();identity=d.id
 command.upgrade(config,'head')
 with Session(engine) as db:
  d=db.get(Deck,identity);assert d.name=='Old deck' and d.source_url=='' and d.deleted_at is None
  assert not list(db.scalars(select(DeckVersion)))

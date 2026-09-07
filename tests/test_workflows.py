from app.models import Player,Deck,Participant,Rating,Ownership,Game
from app.services.backup import dump_record
from conftest import payload
from sqlalchemy import select

def test_duplicate_submission(client,records,db):
    data=payload(records)
    one=client.post('/api/games',json=data);two=client.post('/api/games',json=data)
    assert one.status_code==two.status_code==200
    assert one.json()['id']==two.json()['id']
    assert len(list(db.scalars(select(Game))))==1

def test_anonymous_conversion_preserves_history(client,records,db):
    data=payload(records,anonymous=True);data['participants'][-1]['player_name']='Red hat'
    g=client.post('/api/games',json=data).json();p=g['participants'][-1]
    assert len(client.get('/api/catalog').json()['players'])==5
    result=client.post('/api/participants/convert',json={'participant_ids':[p['id']],'name':'Taylor'})
    assert result.status_code==200
    saved=db.get(Participant,p['id'])
    assert saved.player_id==result.json()['id'] and saved.player_name=='Red hat'
    assert len(client.get('/api/catalog').json()['players'])==6

def test_conversion_conflict(client,records):
    g=client.post('/api/games',json=payload(records,anonymous=True)).json()
    r=client.post('/api/participants/convert',json={'participant_ids':[g['participants'][-1]['id']],'player_id':records[0][0].id})
    assert r.status_code==409

def test_rename_and_transfer_preserve_snapshots(client,records,db):
    g=client.post('/api/games',json=payload(records)).json()
    p=records[0][0];d=records[1][0]
    assert client.put('/api/players/'+p.id,json={'name':'Renamed'}).status_code==200
    assert client.put('/api/decks/'+d.id,json={'name':'New build title','commanders':'New commander','owner_id':records[0][1].id}).status_code==200
    participant=db.get(Participant,g['participants'][0]['id'])
    assert participant.player_name=='Player 0'
    assert participant.deck_name=='Deck 0'
    assert participant.owner_name=='Player 0'
    assert participant.owner_id_snapshot==p.id
    history=list(db.scalars(select(Ownership).where(Ownership.deck_id==d.id)))
    assert len(history)==2 and sum(h.ended_at is None for h in history)==1

def test_game_edit_retains_ratings_and_snapshots(client,records,db):
    data=payload(records);data['deck_ratings']={1:5}
    g=client.post('/api/games',json=data).json()
    for i,p in enumerate(data['participants']): p['id']=g['participants'][i]['id']
    data['notes']='Changed';data['participants'][0]['seat']=2;data['participants'][1]['seat']=1
    data['deck_ratings']={2:5}
    result=client.put('/api/games/'+g['id'],json=data)
    assert result.status_code==200,result.text
    assert len(result.json()['ratings'])==1
    assert result.json()['ratings'][0]['participant_id']==g['participants'][0]['id']

def test_player_merge_conflict(client,records):
    client.post('/api/games',json=payload(records))
    r=client.post('/api/players/'+records[0][0].id+'/merge',json={'target_id':records[0][1].id,'confirm':True})
    assert r.status_code==409

def test_player_merge_safe(client,records,db):
    g=client.post('/api/games',json=payload(records,size=2)).json()
    r=client.post('/api/players/'+records[0][0].id+'/merge',json={'target_id':records[0][4].id,'confirm':True})
    assert r.status_code==200
    p=db.get(Participant,g['participants'][0]['id']);db.refresh(p)
    assert p.player_id==records[0][4].id and p.player_name=='Player 0'
    assert records[0][0].archived

def test_ratings_validate_targets_and_hide_notes(client,records):
    g=client.post('/api/games',json=payload(records)).json()
    data={'game_id':g['id'],'kind':'deck','participant_id':g['participants'][0]['id'],'rater_id':records[0][1].id,'value':4,'private_note':'Keep this private'}
    r=client.post('/api/ratings',json=data)
    assert r.status_code==200 and 'private_note' not in r.json()
    assert 'Keep this private' not in client.get('/games/'+g['id']).text
    assert 'Keep this private' not in client.get('/api/export/csv/ratings').text
    assert client.get('/api/ratings/'+r.json()['id']+'/private').json()['private_note']=='Keep this private'
    data['rater_id']=records[0][0].id
    assert client.post('/api/ratings',json=data).status_code==400

def test_validation(client,records):
    data=payload(records);data['participants'][1]['winner']=True
    assert client.post('/api/games',json=data).status_code==422
    data=payload(records);data['participants'][1]['seat']=1
    assert client.post('/api/games',json=data).status_code==422
    data=payload(records);data['participants'][1]['player_id']=data['participants'][0]['player_id']
    assert client.post('/api/games',json=data).status_code==422
    data=payload(records);data['duration']=-1
    assert client.post('/api/games',json=data).status_code==422

def test_external_url_validation(client,records):
    data={'name':'Test','owner_id':records[0][0].id,'commanders':'Test','links':['https://custom-deck-site.example/mydeck']}
    assert client.post('/api/decks',json=data).status_code==200
    data['links']=['javascript:alert(1)']
    assert client.post('/api/decks',json=data).status_code==422

def test_csrf(client):
    assert client.post('/api/players',json={'name':'Injected'},headers={'Origin':'https://evil.example'}).status_code==403

def test_all_pages(client,records):
    g=client.post('/api/games',json=payload(records)).json()
    routes=['/','/analytics','/games','/games/new','/settings','/search?q=Player','/manage/players','/manage/decks','/manage/events','/manage/locations','/games/'+g['id'],'/games/new?edit='+g['id'],'/games/new?duplicate='+g['id'],'/profiles/players/'+records[0][0].id,'/profiles/decks/'+records[1][0].id]
    for route in routes: assert client.get(route).status_code==200,route

def test_backdated_game_uses_historical_owner(client,records,db):
    deck=records[1][0]
    r=client.put('/api/decks/'+deck.id,json={'name':deck.name,'commanders':deck.commanders,'owner_id':records[0][1].id})
    assert r.status_code==200
    old=client.post('/api/games',json=payload(records)).json()
    assert old['participants'][0]['owner_id_snapshot']==records[0][0].id

def test_archive_restore_and_copy(client,records):
    p=records[0][0];d=records[1][0]
    assert client.put('/api/players/'+p.id,json={'name':p.name,'archived':True}).json()['archived']
    assert not client.put('/api/players/'+p.id,json={'name':p.name,'archived':False}).json()['archived']
    copy=client.post('/api/decks/'+d.id+'/copy',json={}).json()
    assert copy['id']!=d.id and copy['commanders']==d.commanders
    game=client.post('/api/games',json=payload(records)).json()
    client.post('/api/games/'+game['id']+'/trash',json={'deleted':True})
    assert client.get('/api/statistics').json()['games']==0
    client.post('/api/games/'+game['id']+'/trash',json={'deleted':False})
    assert client.get('/api/statistics').json()['games']==1

def test_edit_removes_target_ratings_with_removed_seat(client,records):
    data=payload(records);data['deck_ratings']={4:2}
    g=client.post('/api/games',json=data).json()
    for i,p in enumerate(data['participants']): p['id']=g['participants'][i]['id']
    data['participants'].pop();data['deck_ratings']={}
    r=client.put('/api/games/'+g['id'],json=data)
    assert r.status_code==200,r.text
    assert r.json()['ratings']==[]

def test_event_and_location_workflows(client,records):
    loc=client.post('/api/catalog/locations',json={'name':'Test LGS'}).json()
    event=client.post('/api/catalog/events',json={'name':'League night'}).json()
    data=payload(records);data.update(location_id=loc['id'],event_id=event['id'])
    client.post('/api/games',json=data)
    assert client.get('/profiles/locations/'+loc['id']).status_code==200
    assert client.get('/profiles/events/'+event['id']).status_code==200
    assert client.put('/api/catalog/locations/'+loc['id'],json={'name':'Renamed LGS','archived':True}).status_code==200
    assert client.get('/api/statistics?location_id='+loc['id']).json()['games']==1

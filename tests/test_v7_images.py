from app.services import analysis

def test_card_images_safe_faces_and_batch_validation(client,monkeypatch):
    monkeypatch.setattr(analysis,'resolve_cards',lambda names:[{
        'name':'Day // Night','type_line':'Creature','artist':'Artist',
        'card_faces':[{'name':'Day','image_uris':{'normal':'https://cards.scryfall.io/normal/day.jpg'}},
                      {'name':'Night','image_uris':{'normal':'https://cards.scryfall.io/normal/night.jpg'}}]},
        {'name':'Unsafe','image_uris':{'normal':'https://evil.example/card.png'}}])
    response=client.post('/api/scryfall/card-images',json={'names':['Day // Night']})
    assert response.status_code==200
    cards=response.json()['cards']
    assert cards[0]['image']=='https://cards.scryfall.io/normal/day.jpg'
    assert len(cards[0]['faces'])==2
    assert cards[1]['image']==''
    assert client.post('/api/scryfall/card-images',json={'names':['Card']*76}).status_code==422
    assert client.post('/api/scryfall/card-images',json={'names':[' ']}).status_code==422

def test_card_images_failure_preserves_text_fallback(client,monkeypatch):
    def fail(names):raise RuntimeError('private exception details')
    monkeypatch.setattr(analysis,'resolve_cards',fail)
    response=client.post('/api/scryfall/card-images',json={'names':['Sol Ring']})
    assert response.status_code==503
    assert 'Text decklists still work' in response.json()['detail']
    assert 'private exception' not in response.text

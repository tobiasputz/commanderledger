from fastapi import APIRouter,Query,HTTPException
from app.services.scryfall import client,ScryfallError
from pydantic import BaseModel,Field
router=APIRouter(prefix='/api/scryfall')

@router.get('/autocomplete')
def autocomplete(q: str=Query(min_length=2,max_length=100)) -> dict:
    try: return client.autocomplete(q.strip())
    except ScryfallError as exc: return {'names':[],'available':False,'message':str(exc)}

@router.get('/lookup')
def lookup(names: str=Query(min_length=2,max_length=300)) -> dict:
    try: return client.lookup(names.strip())
    except ScryfallError as exc: raise HTTPException(503,str(exc))


@router.get('/artwork')
def artwork(names: str=Query(min_length=1,max_length=300)) -> dict:
    return client.artwork(names.strip())

class CardImagesInput(BaseModel):
    names: list[str]=Field(min_length=1,max_length=75)

@router.post('/card-images')
def card_images(data: CardImagesInput) -> dict:
    """Small fixed-origin collection batches; never accept remote image URLs."""
    from app.services.analysis import resolve_cards
    from urllib.parse import urlsplit
    if any(not n.strip() or len(n)>200 for n in data.names):raise HTTPException(422,'Use card names of 1–200 characters')
    try:cards=resolve_cards(list(dict.fromkeys(n.strip() for n in data.names)))
    except Exception:raise HTTPException(503,'Card images are temporarily unavailable. Text decklists still work.')
    def safe(url):
        parsed=urlsplit(url or '')
        return url if parsed.scheme=='https' and (parsed.hostname or '').endswith('.scryfall.io') and not parsed.username else ''
    result=[]
    for card in cards:
        images=card.get('image_uris') or (card.get('card_faces') or [{}])[0].get('image_uris',{})
        result.append({'name':card['name'],'type_line':card.get('type_line',''),'image':safe(images.get('normal')),'artist':card.get('artist') or (card.get('card_faces') or [{}])[0].get('artist',''),'faces':[{'name':f.get('name',''),'image':safe(f.get('image_uris',{}).get('normal'))} for f in card.get('card_faces',[]) if safe(f.get('image_uris',{}).get('normal'))]})
    return {'cards':result}

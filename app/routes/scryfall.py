from fastapi import APIRouter,Query,HTTPException
from app.services.scryfall import client,ScryfallError
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

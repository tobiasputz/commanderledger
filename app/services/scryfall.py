"""Optional Scryfall integration: fixed origin, durable cache, conservative rate limit."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from app.db import DB_PATH

class ScryfallError(Exception):
    pass

class ScryfallClient:
    def __init__(self,path: Path,transport: httpx.BaseTransport | None=None) -> None:
        self.path=path
        self.transport=transport
        self.lock=threading.Lock()
        self.next_request=0.0
        self.cooldown=0.0

    def connection(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(self.path,timeout=10)
        con.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, fetched REAL NOT NULL)')
        return con

    def get(self,endpoint: str,params: dict,ttl: int) -> dict:
        if endpoint not in ('/cards/autocomplete','/cards/named'): raise ValueError('Unsupported endpoint')
        key=endpoint+json.dumps(params,sort_keys=True)
        with self.lock:
            with self.connection() as con: cached=con.execute('SELECT value,fetched FROM cache WHERE key=?',(key,)).fetchone()
            if cached and time.time()-cached[1]<ttl:
                return {'data':json.loads(cached[0]),'cached':True,'stale':False}
            if os.getenv('COMMANDER_SCRYFALL','true').lower() not in ('1','true','yes'):
                if cached: return {'data':json.loads(cached[0]),'cached':True,'stale':True}
                raise ScryfallError('Scryfall is disabled. You can enter any commander manually.')
            if time.monotonic()<self.cooldown:
                if cached: return {'data':json.loads(cached[0]),'cached':True,'stale':True}
                raise ScryfallError('Scryfall is temporarily unavailable. Try later or enter the name manually.')
            time.sleep(max(0,self.next_request-time.monotonic()))
            try:
                headers={'User-Agent':os.getenv('SCRYFALL_USER_AGENT','CommanderLedger/2.0 (personal Commander game tracker)'), 'Accept':'application/json'}
                with httpx.Client(headers=headers,timeout=8,follow_redirects=False,transport=self.transport) as http:
                    response=http.get('https://api.scryfall.com'+endpoint,params=params)
                self.next_request=time.monotonic()+0.55
                if response.status_code==429:
                    try: retry=max(60,min(3600,int(response.headers.get('retry-after','60'))))
                    except ValueError: retry=60
                    self.cooldown=time.monotonic()+retry
                    raise ScryfallError('Scryfall requested a pause. Try later; manual entry still works.')
                if response.status_code==404:
                    raise ScryfallError('No unambiguous card found. Choose a suggestion or keep your custom name.')
                if response.status_code>=400:
                    self.cooldown=time.monotonic()+60
                    raise ScryfallError('Scryfall could not be reached. Manual entry still works.')
                data=response.json()
                if not isinstance(data,dict): raise ValueError('Invalid card response')
                with self.connection() as con:
                    con.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(data),time.time()))
                    # Bound the regenerable cache to the most recent 3000 responses.
                    con.execute('DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY fetched DESC LIMIT 3000)')
                return {'data':data,'cached':False,'stale':False}
            except (httpx.HTTPError,ValueError,ImportError,ScryfallError) as exc:
                self.next_request=time.monotonic()+0.55
                if not isinstance(exc,ScryfallError): self.cooldown=time.monotonic()+30
                if cached: return {'data':json.loads(cached[0]),'cached':True,'stale':True}
                if isinstance(exc,ScryfallError): raise
                raise ScryfallError('Scryfall is unavailable. Manual entry still works.') from exc

    def artwork(self, names: str) -> dict:
        """Exact-name decoration; unknown/custom commanders never get guessed art."""
        names_list=list(dict.fromkeys(n.strip() for n in names.split(';') if n.strip()))
        if not 1<=len(names_list)<=2: return {'cards':[], 'available':False}
        cards=[]
        for name in names_list:
            try: result=self.get('/cards/named',{'exact':name},7*86400)
            except ScryfallError: continue
            card=result['data'];faces=card.get('card_faces') or []
            face=faces[0] if faces else {}
            images=card.get('image_uris') or face.get('image_uris',{})
            def safe_image(value):
                parsed=urlsplit(value or '')
                return value if parsed.scheme=='https' and (parsed.hostname or '').endswith('.scryfall.io') and not parsed.username else ''
            crop=safe_image(images.get('art_crop'))
            if not crop: continue
            link=card.get('scryfall_uri','')
            if urlsplit(link).scheme!='https' or urlsplit(link).hostname!='scryfall.com': link=''
            cards.append({'name':card.get('name',name),'art':crop,'image':safe_image(images.get('normal')),
                          'artist':card.get('artist') or face.get('artist',''),'url':link,'stale':result['stale']})
        return {'cards':cards,'available':bool(cards)}

    def autocomplete(self,q: str) -> dict:
        result=self.get('/cards/autocomplete',{'q':q,'include_extras':'false'},86400)
        return {'names':result['data'].get('data',[])[:20],'cached':result['cached'],'stale':result['stale']}

    def lookup(self,names: str) -> dict:
        names_list=[s.strip() for s in names.split(';') if s.strip()]
        if not 1<=len(names_list)<=2: raise ScryfallError('Enter one or two names, separated by a semicolon.')
        cards=[];stale=False
        for name in names_list:
            result=self.get('/cards/named',{'fuzzy':name},7*86400)
            data=result['data'];faces=data.get('card_faces') or []
            images=data.get('image_uris') or (faces[0].get('image_uris',{}) if faces else {})
            image=images.get('normal','')
            if urlsplit(image).scheme!='https' or not (urlsplit(image).hostname or '').endswith('.scryfall.io'): image=''
            url=data.get('scryfall_uri','')
            if urlsplit(url).scheme!='https' or urlsplit(url).hostname!='scryfall.com': url=''
            cards.append({'id':data.get('id'),'name':data.get('name',name),'color_identity':data.get('color_identity',[]),'type_line':data.get('type_line',''),'oracle_text':data.get('oracle_text') or '\n\n'.join(f.get('oracle_text','') for f in faces),'image':image,'url':url,'commander_legality':data.get('legalities',{}).get('commander','unknown')})
            stale=stale or result['stale']
        colors=set(c for card in cards for c in card['color_identity'])
        return {'cards':cards,'commanders':'; '.join(c['name'] for c in cards),'color_identity':''.join(c for c in 'WUBRG' if c in colors),'stale':stale,'pairing_note':'Two-card commander pairing is not validated. Check both Oracle texts.' if len(cards)>1 else 'Format legality does not by itself establish eligibility as a commander.'}

client=ScryfallClient(DB_PATH.with_name('scryfall-cache.sqlite3'))

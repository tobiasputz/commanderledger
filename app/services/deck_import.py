"""Bounded public-deck imports. Never fetch user-supplied hosts or follow redirects."""
import os,re,time,threading
from urllib.parse import urlsplit
from collections import Counter
import httpx

class ImportError(ValueError): pass

def identify(url):
    try:
        u=urlsplit(url.strip())
        if u.scheme!='https' or u.username or u.password or u.port not in (None,443): raise ValueError()
        host=(u.hostname or '').lower().removeprefix('www.')
        match=re.fullmatch(r'/decks/([A-Za-z0-9_-]+)(?:/[^/]*)?/?',u.path)
        if host not in ('moxfield.com','archidekt.com') or not match: raise ValueError()
        identity=match[1]
        if host=='archidekt.com' and not identity.isdigit(): raise ValueError()
        return host.split('.')[0],identity,f'https://{host}/decks/{identity}'
    except ValueError: raise ImportError('Paste a complete HTTPS Moxfield or Archidekt deck link.')

def text_card(name,quantity):
    if not isinstance(name,str) or not name.strip() or len(name)>300 or '\n' in name: raise ImportError('Provider returned an invalid card name.')
    if not isinstance(quantity,int) or not 1<=quantity<=1000: raise ImportError('Provider returned an invalid card quantity.')
    return f'{quantity} {name.strip()}'

def normalize(provider,data,url):
    if not isinstance(data,dict) or not isinstance(data.get('name'),str): raise ImportError('Provider returned an unsupported deck format. Use its text export instead.')
    sections={k:[] for k in ('decklist','sideboard','maybeboard')};commanders=[];colors=set()
    if provider=='archidekt':
        cards=data.get('cards')
        if not isinstance(cards,list): raise ImportError('Archidekt did not include cards. Use a text export.')
        excluded={c['name'] for c in data.get('categories',[]) if isinstance(c,dict) and c.get('includedInDeck') is False}
        for row in cards:
            card=row.get('card',{}).get('oracleCard',{})
            name=card.get('name','');cats=row.get('categories',[]);lower={str(c).lower() for c in cats}
            command='commander' in lower or bool(row.get('isCommander'))
            section='maybeboard' if 'maybeboard' in lower else 'sideboard' if 'sideboard' in lower or excluded.intersection(cats) else 'decklist'
            sections[section].append(text_card(name,row.get('quantity',1)))
            if command:
                commanders.append(name);colors.update(card.get('colorIdentity',[]))
    else:
        boards=data.get('boards')
        sources={k:(boards.get(k,{}).get('cards',{}) if isinstance(boards,dict) else data.get(k,{})) for k in ('commanders','mainboard','sideboard','maybeboard','companions')}
        if not any(sources.values()): raise ImportError('Moxfield did not include cards. Use a text export.')
        for board,entries in sources.items():
            if not isinstance(entries,dict): raise ImportError('Unsupported Moxfield card format.')
            for row in entries.values():
                card=row.get('card',{});name=card.get('name','')
                section='decklist' if board in ('mainboard','commanders') else 'maybeboard' if board=='maybeboard' else 'sideboard'
                sections[section].append(text_card(name,row.get('quantity',1)))
                if board=='commanders':
                    commanders.append(name);colors.update(card.get('color_identity',card.get('colorIdentity',[])))
    colors={str(c).upper() for c in colors};warnings=[]
    commanders=list(dict.fromkeys(commanders))
    if not commanders: warnings.append('No commander was marked by the source. Choose it in the preview.')
    if not sections['decklist']: warnings.append('The playable decklist is empty. Check the source categories.')
    return {'name':data['name'][:180],'commanders':'; '.join(commanders),'color_identity':''.join(c for c in 'WUBRG' if c in colors),'source_url':url,'links':[url],**{k:'\n'.join(sorted(v,key=str.casefold)) for k,v in sections.items()},'warnings':warnings}

class ImportClient:
    def __init__(self,transport=None):
        self.transport=transport;self.lock=threading.Lock();self.cache={};self.cooldowns={}
    def fetch(self,url,refresh=False):
        provider,identity,canonical=identify(url)
        with self.lock:
            stamp=time.monotonic();cached=self.cache.get(canonical)
            if cached and not refresh and stamp-cached[0]<300: return {**cached[1]}
            if stamp<self.cooldowns.get(provider,0): raise ImportError('Provider requested a pause. Retry shortly or paste a text export.')
            endpoint=f'https://archidekt.com/api/decks/{identity}/' if provider=='archidekt' else f'https://api2.moxfield.com/v2/decks/all/{identity}'
            headers={'Accept':'application/json','User-Agent':'CommanderLedger/3.0 (personal deck importer)'}
            # Only use a provider-issued identifier if Moxfield grants API access.
            if provider=='moxfield' and os.getenv('MOXFIELD_USER_AGENT'): headers['User-Agent']=os.environ['MOXFIELD_USER_AGENT']
            try:
                with httpx.Client(timeout=12,follow_redirects=False,transport=self.transport) as http:
                    with http.stream('GET',endpoint,headers=headers) as response:
                        self.cooldowns[provider]=time.monotonic()+1
                        if response.status_code==429:
                            self.cooldowns[provider]=time.monotonic()+60
                            raise ImportError('Provider rate limit reached. Retry in a minute or use a text export.')
                        if response.status_code in (401,403): raise ImportError(f'{provider.title()} denied access. Make the deck public; if it still fails, use Export → text on the source site and paste it here. Moxfield may require approved API access.')
                        if response.status_code==404: raise ImportError('Deck not found or private. Check the link or paste a text export.')
                        if response.status_code!=200: raise ImportError('Provider is unavailable. Retry later or paste a text export.')
                        raw=bytearray()
                        for chunk in response.iter_bytes():
                            raw.extend(chunk)
                            if len(raw)>5*1024*1024: raise ImportError('Deck response is too large. Use a text export.')
                        import json
                        result=normalize(provider,json.loads(raw),canonical)
                if len(self.cache)>=100: self.cache.pop(next(iter(self.cache)))
                self.cache[canonical]=(time.monotonic(),result)
                return {**result}
            except (httpx.HTTPError,ValueError,KeyError,TypeError,AttributeError) as exc:
                if isinstance(exc,ImportError): raise
                raise ImportError('Could not read this deck. Retry later or use the source site’s text export.') from exc

client=ImportClient()

def diff(old,new):
    a=Counter(x.strip() for x in old.splitlines() if x.strip());b=Counter(x.strip() for x in new.splitlines() if x.strip())
    return {'removed':list((a-b).elements()),'added':list((b-a).elements())}

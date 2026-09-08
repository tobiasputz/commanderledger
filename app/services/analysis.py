"""Transparent deck composition checks; heuristic roles are editable, not a power score."""
import re,json,hashlib,time
from collections import Counter
from sqlalchemy import select
from app.models import Deck,DeckAnalysis,SourceCheck,now
from app.services.scryfall import client as scryfall,ScryfallError
from app.services.deck_import import client as imports,diff
ROLES=('ramp','draw','removal','board_wipe','protection','tutor','fast_mana','free_interaction')
FAST={'Sol Ring','Mana Vault','Grim Monolith','Chrome Mox','Mox Diamond','Lotus Petal','Ancient Tomb','Dark Ritual'}

def fingerprint(deck):
    return hashlib.sha256(json.dumps({k:getattr(deck,k) for k in ('commanders','color_identity','decklist','sideboard','maybeboard')},sort_keys=True).encode()).hexdigest()

def parse_list(text):
    rows=Counter();ignored=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith(('#','//')) or line.lower() in ('commander','commanders','deck','mainboard'):continue
        m=re.fullmatch(r'(\d{1,4})x?\s+(.+)',line)
        if not m:ignored.append(line[:180]);continue
        n=int(m[1]);name=re.sub(r'\s+\([^)]*\)(?:\s+\S+)*$','',m[2]).strip()
        name=re.sub(r'\s+\*[^*]*\*$', '', name).strip()
        if not 1<=n<=1000:ignored.append(line[:180]);continue
        rows[name]+=n
    return rows,ignored

def roles(card):
    text=(card.get('oracle_text') or '\n'.join(f.get('oracle_text','') for f in card.get('card_faces',[]))).lower();found=[]
    if 'add {' in text and ('land' not in card.get('type_line','').lower()) or 'search your library' in text and 'land card' in text and 'battlefield' in text:found.append('ramp')
    if re.search(r'\bdraw (a|one|two|three|x|that many|\d+) cards?\b',text):found.append('draw')
    if re.search(r'(destroy|exile) target (creature|permanent|artifact|enchantment)',text) or 'counter target spell' in text:found.append('removal')
    if re.search(r'(destroy|exile) all (creatures|permanents|artifacts|enchantments)',text):found.append('board_wipe')
    if 'hexproof' in text or 'indestructible' in text or 'protection from' in text:found.append('protection')
    if 'search your library' in text and 'land card' not in text:found.append('tutor')
    if card.get('name') in FAST:found.append('fast_mana')
    if 'without paying' in text and ('counter target' in text or 'exile target' in text):found.append('free_interaction')
    return found

def summarize(deck,cards,overrides=None):
    quantities,ignored=parse_list(deck.decklist);known={c['name'].casefold():c for c in cards};commanders=[s.strip() for s in deck.commanders.split(';') if s.strip()]
    for name in commanders:
        if not any(n.casefold()==name.casefold() for n in quantities):quantities[name]=1
    curve=Counter();types=Counter();role_counts=Counter();warnings=[];missing=[];entries=[];nonland_mv=[];priced=0;usd=eur=0;usd_n=eur_n=0
    identity=set(deck.color_identity.replace('C',''));total=sum(quantities.values())
    for name,n in quantities.items():
        card=known.get(name.casefold())
        if not card:missing.append(name);continue
        type_line=card.get('type_line','');text=card.get('oracle_text','');mv=float(card.get('cmc',0));land='Land' in type_line
        if not land:curve[str(min(7,int(mv)))]+=n;nonland_mv.extend([mv]*n)
        for typ in ('Land','Creature','Artifact','Enchantment','Instant','Sorcery','Planeswalker','Battle'):
            if typ in type_line:types[typ]+=n
        detected=(overrides or {}).get(card['name'],roles(card))
        for role in detected:role_counts[role]+=n
        legal=card.get('legalities',{}).get('commander','unknown')
        if legal!='legal':warnings.append(f'{name}: Commander format status {legal}.')
        if set(card.get('color_identity',[]))-identity:warnings.append(f'{name}: outside the recorded color identity.')
        if n>1 and 'Basic' not in type_line and not re.search(r'A deck can have (any number|up to)',text):warnings.append(f'{name}: {n} copies; review the singleton rule.')
        if n>1 and 'A deck can have up to' in text:
            count=re.search(r'A deck can have up to (\w+)',text);limit={'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9}.get(count[1] if count else '')
            if limit and n>limit:warnings.append(f'{name}: {n} copies exceeds its {limit}-copy exception.')
        prices=card.get('prices',{});entry={'name':name,'quantity':n,'mana_value':mv,'types':type_line,'roles':detected,'usd':prices.get('usd'),'eur':prices.get('eur')}
        for currency in ('usd','eur'):
            try:value=float(prices[currency]);assert value>=0
            except (KeyError,TypeError,ValueError,AssertionError):continue
            if currency=='usd':usd+=value*n;usd_n+=n
            else:eur+=value*n;eur_n+=n
        entries.append(entry)
    if total!=100:warnings.insert(0,f'{total} cards including commanders; a usual Commander deck has 100.')
    if not quantities:warnings.append('Paste or import a decklist first.')
    return {'total_cards':total,'resolved_cards':total-sum(quantities[n] for n in missing),'missing':missing,'ignored_lines':ignored,'curve':dict(curve),'types':dict(types),'roles':dict(role_counts),'average_nonland_mv':round(sum(nonland_mv)/len(nonland_mv),2) if nonland_mv else None,'usd':round(usd,2),'eur':round(eur,2),'usd_priced_cards':usd_n,'eur_priced_cards':eur_n,'warnings':warnings,'cards':entries,'checked_at':now(),'notes':['Role labels are text heuristics; edit them below. They can miss or misclassify interactions.','Prices are estimates for Scryfall-returned printings; missing prices are excluded.','This is not a power score or a full commander-pairing/combo legality validator.']}

def resolve_cards(names):
    """Batch unresolved names; cache card objects alongside existing named-card entries."""
    import httpx
    cards=[];unknown=[]
    with scryfall.lock:
        for name in names:
            key='/cards/named'+json.dumps({'exact':name},sort_keys=True)
            with scryfall.connection() as con:row=con.execute('SELECT value,fetched FROM cache WHERE key=?',(key,)).fetchone()
            if row and time.time()-row[1]<86400:cards.append(json.loads(row[0]))
            else:unknown.append(name)
        import os
        if os.getenv('COMMANDER_SCRYFALL','true').lower() not in ('true','1','yes'):raise ScryfallError('Scryfall is disabled; enable it to analyze card metadata.')
        for offset in range(0,len(unknown),75):
            if time.monotonic()<scryfall.cooldown:raise ScryfallError('Scryfall requested a pause. Retry analysis later.')
            time.sleep(max(0,scryfall.next_request-time.monotonic()))
            with httpx.Client(timeout=15,follow_redirects=False,transport=scryfall.transport) as http:
                response=http.post('https://api.scryfall.com/cards/collection',headers={'Accept':'application/json','User-Agent':'CommanderLedger/5.0'},json={'identifiers':[{'name':n} for n in unknown[offset:offset+75]]})
            scryfall.next_request=time.monotonic()+.55
            if response.status_code==429:scryfall.cooldown=time.monotonic()+60;raise ScryfallError('Rate limited. Retry in a minute.')
            response.raise_for_status();data=response.json()
            batch=data.get('data',[])
            with scryfall.connection() as con:
                for card in batch:
                    key='/cards/named'+json.dumps({'exact':card['name']},sort_keys=True)
                    con.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(card),time.time()))
                con.execute('DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY fetched DESC LIMIT 3000)')
            cards.extend(batch)
    return cards

def analyze_job(deck_id,session_factory):
    with session_factory() as db:
        obj=db.scalar(select(DeckAnalysis).where(DeckAnalysis.deck_id==deck_id));deck=db.get(Deck,deck_id)
        if not obj or not deck:return
        try:
            names=list(parse_list(deck.decklist)[0]);names+=deck.commanders.split(';');names=list(dict.fromkeys(n.strip() for n in names if n.strip()))
            if len(names)>250:raise ValueError('Analysis supports up to 250 distinct playable cards.')
            current=fingerprint(deck);result=summarize(deck,resolve_cards(names),obj.overrides)
            db.refresh(deck)
            if fingerprint(deck)!=current:raise ValueError('Deck changed during analysis. Run it again on the current version.')
            obj.result=result;obj.source_hash=current;obj.status='ready';obj.error=''
        except Exception as exc:obj.status='failed';obj.error=str(exc)[:500]
        db.commit()

def check_source(deck_id,session_factory):
    with session_factory() as db:
        deck=db.get(Deck,deck_id)
        if not deck or not deck.source_url or deck.deleted_at:return
        obj=db.scalar(select(SourceCheck).where(SourceCheck.deck_id==deck_id)) or SourceCheck(deck_id=deck_id)
        db.add(obj)
        try:
            payload=imports.fetch(deck.source_url,refresh=True)
            obj.payload=payload;obj.source_hash=fingerprint(deck);obj.error=''
        except Exception as exc:obj.error=str(exc)[:500]
        obj.updated_at=now();db.commit()

'use strict';
// Attach to static and dynamically added commander inputs. No game/player data is sent.
let scryfallCounter=0;
function attachScryfall(input){
 if(input.dataset.scryfallAttached)return;input.dataset.scryfallAttached='true';
 const id='scryfall-list-'+(++scryfallCounter),list=document.createElement('datalist');list.id=id;input.setAttribute('list',id);input.setAttribute('autocomplete','off');input.after(list);
 const area=document.createElement('div');area.className='scryfall-tools';area.innerHTML='<button class="quiet scryfall-lookup" type="button">Look up on Scryfall ↗</button><small>Online suggestions · custom names always welcome</small><div class="scryfall-results" aria-live="polite"></div>';
 input.closest('label').after(area);let timer,version=0;
 input.closest('form')?.addEventListener('reset',()=>{clearTimeout(timer);version++;list.replaceChildren();area.querySelector('.scryfall-results').replaceChildren()});
 input.addEventListener('input',()=>{clearTimeout(timer);const queryVersion=++version;area.querySelector('.scryfall-results').replaceChildren();const parts=input.value.split(';'),q=parts.at(-1).trim();if(q.length<2)return;timer=setTimeout(async()=>{try{const response=await api('/api/scryfall/autocomplete?q='+encodeURIComponent(q),undefined,'GET');if(queryVersion!==version)return;list.replaceChildren();const prefix=parts.length>1?parts.slice(0,-1).join(';').trim()+'; ':'';response.names.forEach(name=>list.append(new Option(prefix+name,prefix+name)));if(response.message)area.querySelector('small').textContent=response.message}catch{area.querySelector('small').textContent='Suggestions unavailable · manual entry works'}},450)});
 area.querySelector('.scryfall-lookup').onclick=()=>showScryfall(input.value,area.querySelector('.scryfall-results'),input);
}
async function showScryfall(names,target,input=null){
 target.textContent='Looking up card details…';
 try{
  const result=await api('/api/scryfall/lookup?names='+encodeURIComponent(names),undefined,'GET');target.replaceChildren();
  for(const card of result.cards){const article=document.createElement('article');article.className='scryfall-card';
   if(card.image){const img=document.createElement('img');img.src=card.image;img.alt=card.name;img.loading='lazy';img.referrerPolicy='no-referrer';img.onerror=()=>img.remove();article.append(img)}
   const details=document.createElement('div');const title=document.createElement('strong');title.textContent=card.name;details.append(title);
   for(const text of [card.type_line,'Color identity: '+(card.color_identity.join('')||'C'),card.oracle_text,'Commander-format legality: '+card.commander_legality]){const p=document.createElement('p');p.textContent=text;details.append(p)}
   if(card.url){const a=document.createElement('a');a.href=card.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='View on Scryfall ↗';details.append(a)}article.append(details);target.append(article)
  }
  const note=document.createElement('p');note.className='muted';note.textContent=(result.stale?'Offline / stale cached details. ':'')+result.pairing_note;target.append(note);
  if(input){const apply=document.createElement('button');apply.type='button';apply.className='button small';apply.textContent=input.closest('form')?.querySelector('[name=color_identity]')?'Use these names & colors':'Use these names';apply.onclick=()=>{input.value=result.commanders;const color=input.closest('form')?.querySelector('[name=color_identity]');if(color)color.value=result.color_identity;input.dispatchEvent(new Event('change',{bubbles:true}));input.dispatchEvent(new Event('input',{bubbles:true}));toast('Scryfall names applied')};target.append(apply)}
 }catch(err){target.textContent=err.message+' You can still save your typed commander.'}
}
function scanCommanders(root){if(root.matches?.('input[name=commanders]'))attachScryfall(root);root.querySelectorAll?.('input[name=commanders]').forEach(attachScryfall)}
scanCommanders(document);
new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{if(node.nodeType===1)scanCommanders(node)}))).observe(document.body,{childList:true,subtree:true});
document.querySelectorAll('[data-scryfall-preview]').forEach(button=>button.addEventListener('click',()=>showScryfall(button.dataset.scryfallPreview,button.nextElementSibling)));

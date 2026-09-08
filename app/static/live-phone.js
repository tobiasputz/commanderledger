'use strict';
// Presentation adapter: mutations use the original live controller, preserving CAS,
// undo, server saves, and v5 local recovery. No parallel game-state implementation.
(()=>{
 const board=document.querySelector('#live-board'),session=document.querySelector('#live-session');
 const q=s=>document.querySelector(s);let ready=false,gesture=null,page=0,seat=0,mode='counters';
 const cards=()=>[...board.querySelectorAll('.live-player-card')];
 // Tap-only quick start; saved players/decks can still be selected in setup.
 const setup=q('#live-setup-seats'),presets=document.createElement('div');presets.className='phone-presets';presets.innerHTML='<p>Phone table · v8 — choose seats, optionally choose decks, then start.</p><div class="actions"></div>';
 [2,3,4,5,6].forEach(n=>{const b=document.createElement('button');b.type='button';b.className='button';b.textContent=n+' players';b.onclick=()=>{while(setup.children.length<n)q('#live-add').click();while(setup.children.length>n)setup.lastElementChild.remove();presets.querySelectorAll('button').forEach(x=>x.classList.toggle('primary',x===b))};presets.lastChild.append(b)});q('#live-create').prepend(presets);presets.querySelectorAll('button')[2].click();
 q('#live-create').addEventListener('submit',()=>{setup.querySelectorAll('.live-setup-row').forEach(row=>{if(!row.querySelector('.live-deck').value&&!row.querySelector('.live-description').value.trim())row.querySelector('.live-description').value='Untracked commander'})},true);
 function dialog(id,title){const d=document.createElement('dialog');d.id=id;d.className='phone-dialog';d.innerHTML=`<div class="dialog-head"><h2>${title}</h2><button type="button" class="dialog-close" aria-label="Close">×</button></div><div class="dialog-content"></div>`;d.querySelector('button').onclick=()=>d.close();document.body.append(d);return d}
 let counter,tools,finish,conflictDialog,seatsDialog;
 function press(i,delta){const b=cards()[i]?.querySelector(`[data-counter="life"][data-delta="${Math.sign(delta)}"]`);if(!b||b.disabled)return;board.onclick({target:{closest:()=>({dataset:{counter:'life',seat:String(i),delta:String(delta)}})}})}
 function init(){if(ready||session.hidden)return;ready=true;document.body.classList.add('phone-table');
  const viewport=document.querySelector('meta[name="viewport"]');if(viewport&&!viewport.content.includes('viewport-fit'))viewport.content+=', viewport-fit=cover';
  // Existing forms remain available for recording after play, not on the table.
  counter=dialog('phone-counter','Counters');tools=dialog('phone-tools','Table tools · v8');finish=dialog('phone-finish','Finish game');conflictDialog=dialog('phone-conflict','Save conflict');seatsDialog=dialog('phone-seats','Arrange seats');
  const oldToolbar=session.firstElementChild,oldNotes=board.nextElementSibling;
  oldToolbar.hidden=true;oldNotes.hidden=true;
  const conflict=q('#live-conflict');conflictDialog.querySelector('.dialog-content').append(conflict);
  new MutationObserver(()=>{if(!conflict.hidden&&!conflictDialog.open)conflictDialog.showModal()}).observe(conflict,{attributes:true,attributeFilter:['hidden']});
  if(!conflict.hidden)conflictDialog.showModal();
  const hub=document.createElement('div');hub.className='phone-hub';hub.innerHTML='<button aria-label="Undo" id="phone-undo">↶</button><button aria-label="Table tools" id="phone-menu">☰</button><button aria-label="Next turn" id="phone-next">↦</button>';session.append(hub);
  const saveNote=document.createElement('span');saveNote.className='phone-save-dot';saveNote.setAttribute('aria-label','Save status');hub.append(saveNote);
  new MutationObserver(()=>{const message=q('#live-save-state').textContent;saveNote.title=message;saveNote.style.background=/retained|unavailable|waiting|Saving/.test(message)?'#ffd276':'#9ee9b8';saveNote.setAttribute('aria-label',message)}).observe(q('#live-save-state'),{childList:true,subtree:true,characterData:true});
  q('#phone-undo').onclick=()=>q('#live-undo').click();q('#phone-next').onclick=()=>q('#live-next').click();q('#phone-menu').onclick=showTools;
  finish.querySelector('.dialog-content').append(q('#live-finish'));
  // Result selection and winner controls are tap-only; optional prose is hidden.
  q('#live-finish [name="memorable"]').closest('label').hidden=true;
  const credit=document.createElement('p');credit.className='phone-result';credit.textContent='Card art via Scryfall · © respective artists / Wizards of the Coast.';finish.querySelector('.dialog-content').append(credit);
  sync();
 }
 function sync(){init();if(!ready)return;const list=cards(),n=list.length;board.dataset.count=n;board.style.gridTemplateRows=`repeat(${n===2?1:Math.ceil(n/2)},minmax(0,1fr))`;if(n===2&&innerHeight>innerWidth)board.style.gridTemplateRows='repeat(2,minmax(0,1fr))';
  list.forEach((card,i)=>{card.classList.toggle('face-away',n===2?i===0:i<Math.floor(n/2));
   if(card.querySelector('.seat-controls'))return;
   const badges=document.createElement('button');badges.type='button';badges.className='quadrant-counters';badges.setAttribute('aria-label','View counters for '+card.querySelector('h2').textContent);
   const summary=[];card.querySelectorAll('[data-value]').forEach(input=>{const n=Number(input.value);if(n||input.dataset.value==='poison')summary.push(({'poison':'☠','energy':'ϟ','experience':'XP'}[input.dataset.value]||input.dataset.value)+' '+n)});
   const damage=[...card.querySelectorAll('[data-damage]')].map(x=>Number(x.value));summary.push('⚔ max '+Math.max(0,...damage));
   card.querySelectorAll('[data-casts]').forEach((x,j)=>{if(Number(x.value))summary.push('Tax '+(j+1)+': '+2*Number(x.value))});
   summary.forEach(label=>{const span=document.createElement('span');span.textContent=label;badges.append(span)});
   badges.title='⚔ shows the highest damage from one commander. Tap for all counters; Damage opens each commander separately.';badges.onclick=e=>{e.stopPropagation();showCounter(i,'counters')};card.append(badges);
   const controls=document.createElement('div');controls.className='seat-controls';controls.innerHTML='<button type="button" data-phone="damage">⚔ Damage</button><button type="button" data-phone="counters">◎</button>';controls.querySelectorAll('button').forEach(b=>b.onclick=e=>{e.stopPropagation();showCounter(i,b.dataset.phone)});card.append(controls);
   const loss=card.querySelector('[data-delta="-1"]'),gain=card.querySelector('[data-delta="1"]');loss.textContent='−';gain.textContent='+';
   // Card art is decorative here, never a competing tap target.
   card.querySelectorAll('.art-open').forEach(b=>b.tabIndex=-1);
  });
  q('#phone-undo').disabled=q('#live-undo').disabled;
 }
 new MutationObserver(()=>sync()).observe(board,{childList:true});
 new MutationObserver(()=>init()).observe(session,{attributes:true,attributeFilter:['hidden']});
 window.addEventListener('resize',sync);
 // Capture the pointer on the stable board, not a button replaced by a life update.
 board.addEventListener('pointerdown',e=>{const b=e.target.closest('[data-counter="life"]');if(!b||b.disabled||Math.abs(Number(b.dataset.delta))!==1)return;e.preventDefault();gesture={id:e.pointerId,seat:Number(b.dataset.seat),delta:Number(b.dataset.delta),x:e.clientX,y:e.clientY,held:false,moved:false};board.setPointerCapture?.(e.pointerId);gesture.timer=setTimeout(()=>{if(!gesture||gesture.moved)return;gesture.held=true;press(gesture.seat,gesture.delta*10);gesture.repeat=setInterval(()=>{if(gesture)press(gesture.seat,gesture.delta*10)},300)},450)},true);
 board.addEventListener('pointermove',e=>{if(!gesture||gesture.id!==e.pointerId)return;if(Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>20){gesture.moved=true;clearTimeout(gesture.timer);clearInterval(gesture.repeat)}},true);
 function stop(e,cancel=false){if(!gesture||e.pointerId!==gesture.id)return;const g=gesture;gesture=null;clearTimeout(g.timer);clearInterval(g.repeat);if(cancel)return;const dx=e.clientX-g.x,dy=e.clientY-g.y;if(Math.abs(dx)>55||Math.abs(dy)>55)showCounter(g.seat,Math.abs(dx)>Math.abs(dy)?'damage':'counters');else if(!g.held&&!g.moved)press(g.seat,g.delta)}
 board.addEventListener('pointerup',e=>stop(e),true);board.addEventListener('pointercancel',e=>stop(e,true),true);
 window.addEventListener('blur',()=>{if(gesture)stop({pointerId:gesture.id},true)});
 board.addEventListener('click',e=>{if(e.target.closest('[data-counter="life"]')&&e.detail!==0){e.preventDefault();e.stopImmediatePropagation()}},true);
 function inputs(){const card=cards()[seat];return [...card.querySelectorAll(mode==='damage'?'[data-damage]':'[data-value],[data-casts]')]}
 function showCounter(i,m){seat=i;mode=m;page=0;paintCounter();if(!counter.open)counter.showModal()}
 function paintCounter(){const list=inputs(),el=list[page];counter.querySelector('h2').textContent=cards()[seat].querySelector('h2').textContent;
  const body=counter.querySelector('.dialog-content');body.className='dialog-content counter-screen';
  if(cards()[seat].querySelector('[data-counter="life"]').disabled){body.innerHTML='<p>This game has already been recorded. Start a new table to play again.</p>';return}
  if(!el){body.innerHTML='<p>No commander recorded for opposing seats.</p>';return}
  body.replaceChildren();const label=document.createElement('p');label.className='counter-label';label.textContent=el.closest('label').firstChild.textContent.trim();const value=document.createElement('strong');value.textContent=el.value;body.append(label,value);
  const adjust=document.createElement('div');adjust.className='counter-adjust';[-1,1].forEach(delta=>{const b=document.createElement('button');b.textContent=delta<0?'−':'+';b.onclick=()=>{const target=inputs()[page];target.value=Math.max(0,Math.min(target.dataset.casts!==undefined?999:9999,Number(target.value)+delta));target.dispatchEvent(new Event('change',{bubbles:true}));paintCounter()};adjust.append(b)});body.append(adjust);
  const nav=document.createElement('div');nav.className='counter-pages';nav.innerHTML=`<button aria-label="Previous counter">‹</button><span>${page+1} / ${list.length}</span><button aria-label="Next counter">›</button>`;nav.firstChild.onclick=()=>{page=(page+list.length-1)%list.length;paintCounter()};nav.lastChild.onclick=()=>{page=(page+1)%list.length;paintCounter()};body.append(nav);
  const flags=document.createElement('div');flags.className='actions';const win=document.createElement('button');const original=cards()[seat].querySelector('[data-winner]');win.textContent=original.checked?'★ Winner':'☆ Set winner';win.onclick=()=>{const x=cards()[seat].querySelector('[data-winner]');x.checked=!x.checked;x.dispatchEvent(new Event('change',{bubbles:true}));paintCounter()};const out=document.createElement('button');out.textContent=cards()[seat].querySelector('[data-eliminate]').textContent;out.onclick=()=>{cards()[seat].querySelector('[data-eliminate]').click();paintCounter()};flags.append(win,out);body.append(flags);
 }

 function screenPosition(i,n){
  if(n===2)return innerHeight>innerWidth?(i===0?'top':'bottom'):(i===0?'left':'right');
  if(n===3)return i===0?'top':(i===1?'bottom left':'bottom right');
  const rows=Math.ceil(n/2),row=Math.floor(i/2);let vertical='middle';
  if(row===0)vertical='top';else if(row===rows-1)vertical='bottom';
  return vertical+' '+(i%2===0?'left':'right');
 }

 function showSeats(){
  const state=window.ledgerLiveSeats?.state?.();if(!state)return;
  const body=seatsDialog.querySelector('.dialog-content');body.replaceChildren();
  const intro=document.createElement('p');intro.className='phone-result';intro.textContent='Match this order to the real table. Moving a seat also keeps turn order and commander-damage sources attached to the correct player.';body.append(intro);
  const rotate=document.createElement('div');rotate.className='seat-rotate-actions';
  for(const [label,dir] of [['Rotate left',-1],['Rotate right',1]]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{window.ledgerLiveSeats.rotate(dir);showSeats()};rotate.append(b)}body.append(rotate);
  const list=document.createElement('div');list.className='phone-seat-list';body.append(list);
  state.participants.forEach((p,i)=>{const row=document.createElement('div');row.className='phone-seat-row';const label=document.createElement('span'),name=(p.player_name||'LGS random').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));label.innerHTML=`<b>Seat ${i+1} · ${screenPosition(i,state.participants.length)}</b><small>${name}</small>`;const controls=document.createElement('div');for(const [symbol,to] of [['↑',i-1],['↓',i+1]]){const b=document.createElement('button');b.textContent=symbol;b.disabled=to<0||to>=state.participants.length;b.onclick=()=>{window.ledgerLiveSeats.move(i,to);showSeats()};controls.append(b)}row.append(label,controls);list.append(row)});
  if(!seatsDialog.open)seatsDialog.showModal();
 }
 function showTools(){const body=tools.querySelector('.dialog-content');body.replaceChildren();const status=document.createElement('p');status.className='phone-result';status.textContent=q('#live-turn').textContent+' · '+q('#live-clock').textContent;body.append(status);const grid=document.createElement('div');grid.className='phone-tools';body.append(grid);
  const actions=[['Undo','live-undo'],['Redo','live-redo'],[q('#live-timer').textContent,'live-timer'],['Keep awake','live-wake'],['Random first','live-random'],['Next turn','live-next']];for(const [label,id] of actions){const b=document.createElement('button');b.textContent=label;b.disabled=q('#'+id).disabled;b.onclick=()=>{q('#'+id).click();tools.close()};grid.append(b)}
  for(const [label,fn] of [['Arrange seats',()=>{tools.close();showSeats()}],['Roll d20',()=>result('d20: '+random(20))],['Coin flip',()=>result(random(2)===1?'Heads':'Tails')],['Finish game',()=>{tools.close();finish.showModal()}],['Exit table',()=>{location.href=window.ledgerUser?.role==='member'?'/member':'/table'}]]){const b=document.createElement('button');b.textContent=label;b.onclick=fn;grid.append(b)}
  const r=document.createElement('p');r.className='phone-result';r.id='phone-dice';body.append(r);const hint=document.createElement('p');hint.textContent='Tap ±1 · Hold ±10 · Swipe sideways for damage · Up/down for counters · Arrange seats from this menu';hint.style.fontSize='12px';body.append(hint);const saved=document.createElement('small');saved.textContent=q('#live-save-state').textContent;body.append(saved);if(!tools.open)tools.showModal();
 }
 function random(n){const a=new Uint32Array(1);crypto.getRandomValues(a);return a[0]%n+1}function result(t){q('#phone-dice').textContent=t}
 init();
})();

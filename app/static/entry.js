'use strict';
const state=JSON.parse(document.querySelector('#entry-data').textContent),form=document.querySelector('#game-form'),container=document.querySelector('#participants'),memberId=window.ledgerUser?.role==='member'?window.ledgerUser.player_id:null;
const uid=()=>globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
let savingGame=false;
let submissionKey=state.editing?state.game.submission_key:uid(),quickTarget=null,dirty=false;
async function loadSeatVersions(card,selected='',historical=false){
 const deckId=card.querySelector('[name=deck_id]').value,select=card.querySelector('[name=deck_version_id]');
 card.querySelector('.version-field').hidden=!deckId;select.innerHTML='<option value="">'+(historical?'Keep recorded version':'Current deck at save time')+'</option>';
 if(!deckId)return;try{const data=await api('/api/decks/'+deckId+'/versions',undefined,'GET');if(card.querySelector('[name=deck_id]').value!==deckId)return;data.versions.forEach(v=>{const option=new Option(v.name+' · '+v.created_at.slice(0,10),v.id);option.dataset.commanders=v.commanders;select.add(option)});select.value=selected;card.dispatchEvent(new Event('ledger:version-loaded',{bubbles:true}))}catch(err){toast('Version list unavailable; current/recorded version will be used.',true)}
}
const initial=state.game;
const localDate=new Date();localDate.setMinutes(localDate.getMinutes()-localDate.getTimezoneOffset());
form.elements.played_at.value=initial?initial.played_at.slice(0,16):localDate.toISOString().slice(0,16);
form.elements.event_id.value=initial?.event_id||ledgerSettings.current_event||'';
if(initial){['location_id','setting'].forEach(k=>form.elements[k].value=initial[k]||'');if(state.editing){['result','duration','turns','ending','notes','memorable'].forEach(k=>form.elements[k].value=initial[k]??'');form.elements.tags.value=initial.tags.join(', ');['overall','sportsmanship'].forEach(k=>{const r=initial.ratings.find(r=>r.kind===k&&!r.rater_id);form.elements[k==='overall'?'overall_rating':k].value=r?.value||''})}else form.elements.played_at.value=localDate.toISOString().slice(0,16)}
function updateSeats(){[...container.children].forEach((card,index)=>{card.querySelector('.seat-title').textContent=`SEAT ${index+1}`;card.dataset.seat=index+1});document.querySelector('#pod-count').textContent=`${container.children.length} players`}
function deckOptions(card,selected=''){
 const player=card.querySelector('[name=player_id]').value;
 const select=card.querySelector('[name=deck_id]');select.innerHTML='<option value="">Commander / deck description</option>';
 catalog.decks.filter(d=>(d.owner_id===player&&d.status==='active'&&!d.deleted_at)||(state.editing&&d.id===selected)).forEach(d=>select.add(new Option(`${d.name} · ${d.commanders}`,d.id)));
 select.value=selected;card.querySelector('.quick-deck').disabled=!player||!!memberId&&player!==memberId;
 card.querySelector('.description-fields').hidden=!!selected;
}
function addSeat(random=false,data={}){
 if(container.children.length>=20){toast('Maximum 20 participants',true);return}
 const card=document.createElement('article');card.className='panel participant';card.dataset.id=state.editing?data.id||'':'';
 const index=container.children.length+1;
 const playerOptions=catalog.players.filter(p=>!p.archived||p.id===data.player_id).map(p=>`<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
 const key=uid();
 card.innerHTML=`<div class="section-heading"><span class="eyebrow seat-title"></span><div class="actions"><button type="button" class="quiet move-up" aria-label="Move seat earlier">↑</button><button type="button" class="quiet move-down" aria-label="Move seat later">↓</button><button type="button" class="quiet remove-seat" aria-label="Remove participant">Remove ×</button></div></div>
 <label>Player<select name="player_id" id="player-${key}"><option value="">LGS random / temporary</option>${playerOptions}</select></label>
 <label class="temporary-name">Temporary nickname<input name="player_name" placeholder="LGS random ${index}" value="${escapeHtml(data.player_name||'')}"></label>
 <label class="named-decks">Deck<select name="deck_id" id="deck-${key}"><option value="">Commander / deck description</option></select></label>
 <label class="version-field" hidden>Deck version<select name="deck_version_id"><option value="">Current deck at save time</option></select></label><button type="button" class="quiet quick-deck">+ Create a deck for this player</button>
 <div class="description-fields"><label>Commander(s)<input name="commanders" value="${escapeHtml(data.commanders||'')}" placeholder="Commander, partner, background…"></label><label>Deck description<input name="deck_name" value="${escapeHtml(data.deck_name||'')}" placeholder="A name or quick description"></label></div>
 <div class="seat-flags"><label class="inline"><input type="checkbox" name="winner"> Winner</label><label class="inline"><input type="radio" name="starting-seat" value="${key}"> Started</label></div>
 <label>Enjoyment playing against this deck<select name="deck_rating" class="rating-select"><option value="">Not rated</option></select></label>
 <div class="advanced"><label>Deck links (one per line)<textarea name="deck_links" rows="2">${escapeHtml((data.deck_links||[]).join('\n'))}</textarea></label><label>Archetype<input name="archetype" value="${escapeHtml(data.archetype||'')}"></label><label>Elimination order<input type="number" min="1" max="20" name="elimination" value="${state.editing?data.elimination||'':''}"></label><label>Seat notes<textarea name="seat_notes">${state.duplicate?'':escapeHtml(data.notes||'')}</textarea></label></div>`;
 container.append(card);fillRatings(card);
 const playerSelect=card.querySelector('[name=player_id]');playerSelect.value=data.player_id||(!random?catalog.players.find(p=>!p.archived&&!Array.from(container.querySelectorAll('[name=player_id]')).some(el=>el!==playerSelect&&el.value===p.id))?.id||'':'');
 function playerChanged(){const named=!!playerSelect.value;card.querySelector('.temporary-name').hidden=named;card.querySelector('.named-decks').hidden=!named;card.querySelector('.quick-deck').hidden=!named||!!memberId&&playerSelect.value!==memberId;deckOptions(card);dirty=true}
 playerSelect.addEventListener('change',playerChanged);playerChanged();deckOptions(card,data.deck_id||'');
 card.querySelector('[name=deck_id]').onchange=e=>{card.querySelector('.description-fields').hidden=!!e.target.value;loadSeatVersions(card);dirty=true};
 playerSelect.addEventListener('change',()=>loadSeatVersions(card));
 loadSeatVersions(card,data.deck_version_id||'',!!state.editing);
 card.querySelector('.move-up').onclick=()=>{if(card.previousElementSibling)container.insertBefore(card,card.previousElementSibling);updateSeats();dirty=true};
 card.querySelector('.move-down').onclick=()=>{if(card.nextElementSibling)container.insertBefore(card.nextElementSibling,card);updateSeats();dirty=true};
 card.querySelector('.remove-seat').onclick=()=>{card.remove();updateSeats();dirty=true};
 card.querySelector('.quick-deck').onclick=()=>{quickTarget=card;document.querySelector('#quick-deck-form').reset();document.querySelector('#quick-dialog').showModal()};
 if(state.editing){card.querySelector('[name=winner]').checked=!!data.winner;card.querySelector('[name=starting-seat]').checked=!!data.starting;const r=initial.ratings.find(r=>r.kind==='deck'&&r.participant_id===data.id&&!r.rater_id);card.querySelector('[name=deck_rating]').value=r?.value||''}
 card.querySelector('[name=winner]').onchange=e=>{if(form.elements.result.value==='win'&&e.target.checked)container.querySelectorAll('[name=winner]').forEach(el=>{if(el!==e.target)el.checked=false})};
 if(memberId)card.querySelector('[name=deck_rating]').closest('label').hidden=true;if(window.htmx)htmx.process(card);updateSeats();syncResult();
}
function syncResult(){const result=form.elements.result.value;container.querySelectorAll('[name=winner]').forEach(el=>{el.disabled=!['win','shared'].includes(result);if(el.disabled)el.checked=false});document.querySelector('#entry-hint').textContent=result==='win'?'Select one winner on their participant card.':result==='shared'?'Select every shared winner.':'This result has no winner.'}
document.querySelector('#add-named').onclick=()=>addSeat(false);
document.querySelector('#add-random').onclick=()=>addSeat(true);
document.querySelector('#detailed').onchange=e=>form.classList.toggle('detailed',e.target.checked);
form.elements.result.onchange=syncResult;
if(initial)initial.participants.forEach(p=>addSeat(!p.player_id,state.duplicate?{...p,deck_version_id:null}:p));else{addSeat(false,memberId?{player_id:memberId}:{});addSeat(catalog.players.filter(p=>!p.archived).length<2)}
if(state.editing){document.querySelector('#detailed').checked=true;form.classList.add('detailed')}
document.querySelector('#quick-deck-form').onsubmit=async e=>{e.preventDefault();const f=e.target;const data={name:f.elements.name.value,commanders:f.elements.commanders.value,color_identity:f.elements.color_identity.value,owner_id:quickTarget.querySelector('[name=player_id]').value,links:f.elements.link.value?[f.elements.link.value]:[]};try{const deck=await api(memberId?'/api/member/decks':'/api/decks',data);catalog.decks.push(deck);deckOptions(quickTarget,deck.id);loadSeatVersions(quickTarget);dirty=true;document.querySelector('#quick-dialog').close();toast('Deck created')}catch(err){toast(err.message,true)}};
form.addEventListener('input',()=>dirty=true);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});dirty=false;
form.onsubmit=async e=>{e.preventDefault();if(savingGame)return;savingGame=true;const nextGame=e.submitter?.name==='next-game';const button=document.querySelector('#save-game');button.disabled=true;const error=document.querySelector('#form-error');error.textContent='';try{
 const get=name=>form.elements[name].value;
 const participants=[...container.children].map((card,i)=>{const v=name=>card.querySelector(`[name=${name}]`).value;return {id:card.dataset.id||null,player_id:v('player_id')||null,deck_id:v('player_id')?v('deck_id')||null:null,deck_version_id:v('player_id')&&v('deck_id')?v('deck_version_id')||null:null,player_name:v('player_name'),deck_name:v('deck_name'),commanders:v('commanders'),seat:i+1,starting:card.querySelector('[name=starting-seat]').checked,winner:card.querySelector('[name=winner]').checked,elimination:Number(v('elimination'))||null,archetype:v('archetype'),deck_links:v('deck_links').split('\n').map(s=>s.trim()).filter(Boolean),notes:v('seat_notes')}});
 const deck_ratings={};[...container.children].forEach((card,i)=>{const v=Number(card.querySelector('[name=deck_rating]').value);if(v)deck_ratings[i+1]=v});
 const data={played_at:get('played_at'),location_id:get('location_id')||null,event_id:get('event_id')||null,setting:get('setting'),result:get('result'),duration:Number(get('duration'))||null,turns:Number(get('turns'))||null,ending:get('ending'),notes:get('notes'),memorable:get('memorable'),tags:get('tags').split(',').map(x=>x.trim()).filter(Boolean),overall_rating:Number(get('overall_rating'))||null,sportsmanship:Number(get('sportsmanship'))||null,deck_ratings,participants,submission_key:submissionKey};
 const saved=await api('/api/games'+(state.editing?'/'+state.editing:''),data,state.editing?'PUT':'POST');dirty=false;window.clearEntryDraft?.();location.href=nextGame?'/games/new?duplicate='+saved.id:'/games/'+saved.id;
 }catch(err){savingGame=false;error.textContent=err.message;error.scrollIntoView({behavior:'smooth'});button.disabled=false}};

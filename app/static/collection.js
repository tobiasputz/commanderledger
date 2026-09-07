'use strict';
if(window.recordKind==='decks'){
 document.querySelector('#import-deck').onclick=()=>{if(!catalog.players.length){toast('Add a player first so the imported deck has an owner.',true);return}openDeckImport({onSaved:()=>render()})};
 document.querySelector('#record-grid').addEventListener('click',async e=>{
  const b=e.target.closest('button[data-id]');if(!b)return;const deck=catalog.decks.find(d=>d.id===b.dataset.id);
  if(b.classList.contains('deck-trash')){
   if(!deck.deleted_at&&!confirm(`Move “${deck.name}” to Trash? Its games and statistics stay intact. You can restore it later.`))return;
   b.disabled=true;try{const saved=await api('/api/decks/'+deck.id+'/trash',{deleted:!deck.deleted_at});Object.assign(deck,saved);render();toast(deck.deleted_at?'Deck moved to Trash. Choose Trash → Restore to undo.':'Deck restored')}catch(err){toast(err.message,true);b.disabled=false}
  }
  if(b.classList.contains('refresh-deck'))openDeckImport({deck,onSaved:()=>render()});
  if(b.classList.contains('deck-versions')){
   const dialog=document.createElement('dialog');dialog.innerHTML='<form method="dialog"><button class="button">Close</button></form><h2>Deck versions</h2><p>Versions are captured when cards or commanders change. Past games keep their recorded version. Comparisons describe results, not what caused them.</p><div class="version-list"></div>';
   document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
   async function draw(){const data=await api('/api/decks/'+deck.id+'/versions',undefined,'GET');dialog.querySelector('.version-list').innerHTML=`<p>Unrecorded version: ${data.unrecorded.games} games</p>`+data.versions.map(v=>`<details><summary>${escapeHtml(v.name)} · ${v.created_at.slice(0,10)} · ${v.stats.games} games</summary><p>${v.stats.wins} outright wins · ${v.stats.eligible} eligible games · ${v.stats.win_rate===null?'—':(v.stats.win_rate*100).toFixed(1)+'%'} win rate · average pod ${v.stats.average_pod===null?'—':v.stats.average_pod.toFixed(1)}${v.stats.small_sample?' · Small sample':''}</p>${!ledgerSettings.hide_sensitive?`<p>Opponent enjoyment: ${v.stats.enjoyment.mean===null?'—':v.stats.enjoyment.mean.toFixed(2)+' / 5'} (${v.stats.enjoyment.n} ratings)</p>`:''}<p>${escapeHtml(v.commanders)}</p><pre>${escapeHtml(v.decklist||'No decklist recorded')}</pre><p>Sideboard</p><pre>${escapeHtml(v.sideboard)}</pre><p>Maybeboard</p><pre>${escapeHtml(v.maybeboard)}</pre></details>`).join('')}
   if(!deck.deleted_at){const f=document.createElement('form');f.innerHTML='<label>Name a snapshot of the current deck<input name="name" required maxlength="180" placeholder="September rebuild"></label><button class="button primary">Save version</button>';f.onsubmit=async ev=>{ev.preventDefault();await api('/api/decks/'+deck.id+'/versions',{name:f.elements.name.value});f.reset();await draw()};dialog.append(f)}await draw();
  }
 });
}

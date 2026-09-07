'use strict';
// Shared importer for the collection and quick deck creation at the table.
window.openDeckImport=({ownerId='',deck=null,onSaved=()=>location.reload()}={})=>{
 const dialog=document.createElement('dialog');dialog.className='import-dialog';
 dialog.innerHTML=`<form method="dialog"><div class="section-heading"><h2>${deck?'Refresh deck from source':'Import a deck'}</h2><button class="quiet" aria-label="Close importer">Close ×</button></div></form>
 <p>Paste a public deck link. Review the details before saving. Manual creation and file upload remain available.</p>
 <label>Owner<select id="import-owner">${catalog.players.filter(p=>!p.archived||p.id===(deck?.owner_id||ownerId)).map(p=>`<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join('')}</select></label>
 <label>Moxfield or Archidekt link<input id="import-url" type="url" placeholder="https://archidekt.com/decks/…"></label>
 <button type="button" class="button primary" id="fetch-import">Load preview</button>
 <p id="import-message" role="status"></p>
 <div id="import-preview" hidden><label>Action<select id="import-action"></select></label><div id="import-diff" class="notice"></div>
 <label>Deck name<input id="import-name" maxlength="180" required></label><label>Commander(s)<input id="import-commanders" maxlength="300" placeholder="Commander; partner or background"></label><label>Color identity<input id="import-colors" placeholder="WUBRG"></label>
 <label>Playable decklist<textarea id="import-list" rows="7"></textarea></label><details><summary>Sideboard and maybeboard</summary><label>Sideboard<textarea id="import-side" rows="4"></textarea></label><label>Maybeboard<textarea id="import-maybe" rows="4"></textarea></label></details>
 <button type="button" class="button primary" id="commit-import">Create deck</button></div>
 <details><summary>Source unavailable? Paste or upload its text export</summary><p>Export the deck as text on the source site. The link is retained; fill in its name and commander below.</p><label>Text export<input id="import-file" type="file" accept=".txt,.dek,.csv"></label><button class="button" type="button" id="manual-import">Enter exported list manually</button></details>`;
 document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
 const el=id=>dialog.querySelector('#import-'+id);let loaded=null;
 let remembered='';try{remembered=localStorage.getItem('ledger-import-owner')||''}catch{}
 el('owner').value=deck?.owner_id||ownerId||remembered||el('owner').value;
 if(!el('owner').value&&el('owner').options.length)el('owner').selectedIndex=0;
 if(ownerId&&!deck)el('owner').disabled=true;
 el('url').value=deck?.source_url||deck?.links?.find(u=>/moxfield|archidekt/.test(u))||'';
 const reset=()=>{loaded=null;el('preview').hidden=true};el('url').oninput=reset;el('owner').onchange=reset;
 function show(result){loaded=result;el('preview').hidden=false;
  const matches=result.matches||[];el('action').innerHTML=deck?`<option value="${escapeHtml(deck.id)}">Update ${escapeHtml(deck.name)}</option><option value="copy">Create separate copy</option>`:`<option value="${matches.length?'copy':'new'}">${matches.length?'Create separate copy':'Create new deck'}</option>`+matches.map(m=>`<option ${m.deleted?'disabled':''} value="${escapeHtml(m.id)}">${escapeHtml(m.name)} ${m.deleted?'(in Trash — restore first)':'— Update existing'}</option>`).join('');
  for(const [id,key] of [['name','name'],['commanders','commanders'],['colors','color_identity'],['list','decklist'],['side','sideboard'],['maybe','maybeboard']])el(id).value=result[key]||'';
  el('message').textContent=[...(result.warnings||[]),...(matches.length?['This owner already has this source deck. Choose whether to update it or create a separate copy.']:[])].join(' ');
  el('diff').textContent='';if(result.changes)for(const [section,changes] of Object.entries(result.changes)){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=`${section}: ${changes.added.length} added lines, ${changes.removed.length} removed lines`;const pre=document.createElement('pre');pre.textContent=[...changes.removed.map(x=>'− '+x),...changes.added.map(x=>'+ '+x)].join('\n')||'No card changes';details.append(summary,pre);el('diff').append(details)}
  if(result.metadata_changes){const p=document.createElement('p');p.textContent=Object.entries(result.metadata_changes).map(([k,v])=>`${k}: ${v.before} → ${v.after}`).join(' · ');el('diff').prepend(p)}
  el('action').onchange=()=>{dialog.querySelector('#commit-import').textContent=['new','copy'].includes(el('action').value)?'Create deck':'Save update'};el('action').onchange();
 }
 dialog.querySelector('#fetch-import').onclick=async e=>{e.target.disabled=true;el('message').textContent='Loading deck…';el('preview').hidden=true;try{show(await api('/api/deck-import/preview',{url:el('url').value,owner_id:el('owner').value,refresh:!!deck,deck_id:deck?.id||null}))}catch(err){el('message').textContent=err.message}finally{e.target.disabled=false}};
 dialog.querySelector('#manual-import').onclick=()=>show({source_url:el('url').value,links:[el('url').value],name:deck?.name||'',commanders:deck?.commanders||'',color_identity:deck?.color_identity||'',decklist:'',warnings:['Paste the playable decklist, enter its name and commanders, then save.']});
 el('file').onchange=async e=>{const f=e.target.files[0];if(!f)return;if(f.size>200000){el('message').textContent='Choose a text export smaller than 200 KB.';return}if(!loaded)dialog.querySelector('#manual-import').click();el('list').value=await f.text()};
 dialog.querySelector('#commit-import').onclick=async e=>{if(!loaded)return;e.target.disabled=true;try{
  const action=el('action').value;const target=['new','copy'].includes(action)?null:action;const previous=target?catalog.decks.find(d=>d.id===target):null;
  const data={name:el('name').value,owner_id:el('owner').value,commanders:el('commanders').value,color_identity:el('colors').value,decklist:el('list').value,sideboard:el('side').value,maybeboard:el('maybe').value,source_url:loaded.source_url,links:[...new Set([...(previous?.links||[]),loaded.source_url])],archetype:previous?.archetype||'',bracket:previous?.bracket??null,budget:previous?.budget??null,notes:previous?.notes||'',status:previous?.status||'active',color:previous?.color||'#89cbb1'};
  const saved=await api('/api/deck-import/save',{deck:data,target_id:target,create_copy:action==='copy'});const at=catalog.decks.findIndex(d=>d.id===saved.id);if(at<0)catalog.decks.push(saved);else catalog.decks[at]=saved;
  try{localStorage.setItem('ledger-import-owner',saved.owner_id)}catch{}dialog.close();toast(target?'Deck updated; historical versions retained':'Deck imported');onSaved(saved);
 }catch(err){el('message').textContent=err.message}finally{e.target.disabled=false}};
};

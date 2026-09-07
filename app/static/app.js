'use strict';
window.catalog=JSON.parse(document.querySelector('#catalog-data').textContent);
window.ledgerSettings=JSON.parse(document.querySelector('#settings-data').textContent);
window.escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.toast=(message,error=false)=>{const t=document.querySelector('#toast');t.textContent=message;t.className='show'+(error?' error':'');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.className='',6000)};
window.api=async(url,data,method='POST')=>{const response=await fetch(url,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]')?.content||''},body:data===undefined?undefined:JSON.stringify(data)});const body=await response.json();if(!response.ok){const d=body.detail;throw new Error(Array.isArray(d)?d.map(e=>e.loc.join('.')+': '+e.msg).join('\n'):d||'Request failed')}return body};
window.labels=ledgerSettings.rating_labels||['Very unenjoyable','Unenjoyable','Neutral','Enjoyable','Very enjoyable'];
window.fillRatings=(root=document)=>root.querySelectorAll('.rating-select').forEach(select=>{if(select.dataset.filled)return;labels.forEach((text,i)=>select.add(new Option(`${i+1} · ${text}`,i+1)));select.dataset.filled='true'});
fillRatings();
document.querySelector('#theme-button').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;localStorage.setItem('ledger-theme',theme)};
window.addEventListener('unhandledrejection',e=>{toast(e.reason.message||'Something went wrong',true);e.preventDefault()});
// Small reusable table controller: filtering, column sorting and pagination.
document.querySelectorAll('.table-wrap table').forEach(table=>{
 const tbody=table.tBodies[0];if(!tbody||tbody.rows.length<2)return;
 const rows=Array.from(tbody.rows);let page=1,order=1,sortCol=-1;
 const controls=document.createElement('div');controls.className='table-controls';
 const search=document.createElement('input');search.type='search';search.placeholder='Filter this table…';search.setAttribute('aria-label','Filter table');
 const previous=document.createElement('button');previous.type='button';previous.className='quiet';previous.textContent='← Previous';
 const next=document.createElement('button');next.type='button';next.className='quiet';next.textContent='Next →';
 const status=document.createElement('small');controls.append(search,previous,status,next);table.parentElement.before(controls);
 function render(){let filtered=rows.filter(row=>row.textContent.toLowerCase().includes(search.value.toLowerCase()));if(sortCol>=0)filtered.sort((a,b)=>{const av=a.cells[sortCol]?.textContent.trim()||'',bv=b.cells[sortCol]?.textContent.trim()||'';const an=Number.parseFloat(av),bn=Number.parseFloat(bv);return order*(Number.isFinite(an)&&Number.isFinite(bn)?an-bn:av.localeCompare(bv))});const pages=Math.max(1,Math.ceil(filtered.length/15));page=Math.min(page,pages);rows.forEach(row=>row.hidden=true);filtered.forEach((row,i)=>{tbody.append(row);row.hidden=i<(page-1)*15||i>=page*15});status.textContent=`${filtered.length} rows · ${page}/${pages}`;previous.disabled=page===1;next.disabled=page===pages}
 table.querySelectorAll('thead th').forEach((th,i)=>{const button=document.createElement('button');button.type='button';button.className='quiet sort-heading';button.textContent=th.textContent+' ↕';button.onclick=()=>{order=sortCol===i?-order:1;sortCol=i;render()};th.replaceChildren(button)});
 search.oninput=()=>{page=1;render()};previous.onclick=()=>{page--;render()};next.onclick=()=>{page++;render()};render();
});

document.querySelector('#logout-button')?.addEventListener('click',async()=>{await fetch('/logout',{method:'POST',headers:{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}});location.href='/login'});
document.body.addEventListener('htmx:configRequest',e=>{e.detail.headers['X-CSRF-Token']=document.querySelector('meta[name=csrf-token]')?.content||''});

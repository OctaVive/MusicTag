const key='musictag-selection';
let stored=[];try{stored=JSON.parse(sessionStorage.getItem(key)||'[]')}catch{}
export const selection=new Set(stored);
export function syncSelection(){
  document.querySelectorAll('.track-select').forEach(box=>{box.checked=selection.has(Number(box.value));box.closest('tr').classList.toggle('selected',box.checked)});
  const bar=document.querySelector('#bulk-bar');if(bar)bar.hidden=!selection.size||!!document.querySelector('#workspace .bulk-editor,#workspace .diff-card,#workspace .job-panel');
  const count=document.querySelector('#selected-count');if(count)count.textContent=`${selection.size} tracks selected`;
  const tool=document.querySelector('#tool-ids');if(tool&&!tool.value)tool.value=[...selection].join(',');
  try{sessionStorage.setItem(key,JSON.stringify([...selection]))}catch{}
}
let anchor=null;
document.addEventListener('change',e=>{
 if(e.target.matches('.track-select')){const id=Number(e.target.value);e.target.checked?selection.add(id):selection.delete(id);syncSelection()}
 if(e.target.id==='select-page'){document.querySelectorAll('.track-select').forEach(b=>{e.target.checked?selection.add(Number(b.value)):selection.delete(Number(b.value))});syncSelection()}
});
document.addEventListener('click',e=>{
 const row=e.target.closest('tr[data-track]');
 if(row&&(e.shiftKey||e.ctrlKey||e.metaKey)&&!e.target.closest('button,a,input')){
   const rows=[...document.querySelectorAll('tr[data-track]')],id=Number(row.dataset.track);
   if(e.shiftKey&&anchor){let a=rows.findIndex(r=>Number(r.dataset.track)===anchor),b=rows.indexOf(row);if(a>=0)rows.slice(Math.min(a,b),Math.max(a,b)+1).forEach(r=>selection.add(Number(r.dataset.track)))}else{selection.has(id)?selection.delete(id):selection.add(id)}anchor=id;syncSelection();
 }
 if(e.target.closest('#clear-selection')){selection.clear();syncSelection()}
});

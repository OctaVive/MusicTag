import {selection,syncSelection} from './selection.js';
import {startQueue} from './player.js';

document.addEventListener('keydown',event=>{
 if(event.target.matches('input,textarea,select,[contenteditable]'))return;
 if((event.ctrlKey||event.metaKey)&&event.key==='z'){
  event.preventDefault();event.stopImmediatePropagation();
  if(confirm('Undo the most recent operation? Changed files will be skipped.'))window.htmx.ajax('POST','/actions/history/latest/undo',{target:'#workspace',values:{csrfmiddlewaretoken:document.querySelector('[name=csrfmiddlewaretoken]').value}});
 }
 if(event.key===' '&&document.activeElement.matches('tr[data-track]')){
  event.preventDefault();event.stopImmediatePropagation();const params=new URLSearchParams(location.search),album=document.querySelector('.track-table')?.dataset.album;if(album)params.set('album',album);startQueue(params,document.activeElement.dataset.track).catch(()=>{});
 }
 if(event.shiftKey&&['ArrowUp','ArrowDown'].includes(event.key)&&document.activeElement.matches('tr[data-track]')){
  event.preventDefault();event.stopImmediatePropagation();const rows=[...document.querySelectorAll('tr[data-track]')],current=rows.indexOf(document.activeElement),next=rows[Math.max(0,Math.min(rows.length-1,current+(event.key==='ArrowDown'?1:-1)))];selection.add(Number(document.activeElement.dataset.track));selection.add(Number(next.dataset.track));next.focus();syncSelection();
 }
},true);

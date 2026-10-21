export function setupChips(){
 document.querySelectorAll('input[data-multi]:not([data-chipped])').forEach(source=>{
  source.dataset.chipped='1';
  const container=document.createElement('div'),entry=document.createElement('input');container.className='chips-input';entry.type='text';entry.placeholder='Add a value…';entry.setAttribute('aria-label',source.id.replace('field-','')+' new value');entry.disabled=source.readOnly;
  let values=source.value.split(';').map(v=>v.trim()).filter(Boolean);
  function render(changed=false){container.replaceChildren();values.forEach((value,i)=>{const chip=document.createElement('span');chip.className='value-chip';const text=document.createElement('span');text.textContent=value;chip.append(text);if(!source.readOnly){const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','Remove '+value);remove.onclick=()=>{values.splice(i,1);render(true);entry.focus()};chip.append(remove)}container.append(chip)});container.append(entry);if(changed){source.value=values.join('; ');source.dispatchEvent(new Event('input',{bubbles:true}))}}
  function add(){const additions=entry.value.split(/[;,\n]/).map(v=>v.trim()).filter(Boolean);if(additions.length){values.push(...additions);entry.value='';render(true)}}
  entry.addEventListener('keydown',e=>{if(['Enter',',',';'].includes(e.key)){e.preventDefault();add()}else if(e.key==='Backspace'&&!entry.value&&values.length){values.pop();render(true)}});
  entry.addEventListener('paste',e=>{const text=e.clipboardData.getData('text');if(/[;\n]/.test(text)){e.preventDefault();entry.value=text;add()}});
  entry.addEventListener('blur',add);
  source.form?.addEventListener('reset',()=>setTimeout(()=>{values=source.value.split(';').map(v=>v.trim()).filter(Boolean);render()},0));
  source.type='hidden';source.after(container);render();
 });
}

const $ = (id) => document.getElementById(id);
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
async function api(url, method='GET', body=null) {
  const response = await fetch(url, {method, headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()}, body:body===null?null:JSON.stringify(body)});
  if (response.status===401) { location.href='/login'; throw new Error('Iniciar sesión'); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No se pudo completar la operación');
  return data;
}
function feedback(text,error=false) { $('feedback').textContent=text; $('feedback').className=error?'alert alert-danger':'alert alert-success'; }
function node(tag,text,cls='') { const el=document.createElement(tag); el.textContent=text; el.className=cls; return el; }
function date(value) { return value?new Date(value).toLocaleString():'Sin evidencia'; }
function table(target, rows, fields) {
  if(!$(target)) return;
  const container=$(target); container.replaceChildren();
  if (!rows.length) { container.textContent='Sin registros'; return; }
  const table=document.createElement('table'); table.className='table';
  const head=document.createElement('tr'); fields.forEach(([key,label])=>head.append(node('th',label))); table.append(head);
  rows.forEach(row=>{ const tr=document.createElement('tr'); fields.forEach(([key])=>tr.append(node('td',row[key]??'—'))); table.append(tr); });
  const wrap=node('div','','table-responsive'); wrap.append(table); container.append(wrap);
}
async function controlStatus(fill=false) {
  if (!$('control-summary')) return;
  const data=await api('/api/control/status');
  $('control-summary').textContent=`${data.mode} · setpoint ${data.config.setpoint} · salida ${data.output.toFixed(1)}% · ${data.reason}`;
  $('actuators').replaceChildren(); data.actuators.forEach(a=>{
    const fresh=a.reported_at && Date.now()-Date.parse(a.reported_at)<5000;
    $('actuators').append(node('p',`${a.name}: solicitado ${a.requested_output.toFixed(1)}% · ${fresh?'reportado '+a.reported_output.toFixed(1)+'%':'sin confirmación reciente'}`));
  });
  if(fill && $('pid-form')) Object.entries(data.config).forEach(([key,value])=>{ const input=$('pid-form').elements.namedItem(key); if(input) input.value=value; });
  if($('control-events')) table('control-events',data.events,[['timestamp','Fecha UTC'],['measured','pH'],['setpoint','Objetivo'],['error','Error'],['output','Salida %'],['reason','Motivo']]);
}
async function cards() {
  if(!$('sensor-cards')) return;
  const rows=await api('/api/sensors/latest'); $('sensor-cards').replaceChildren();
  rows.forEach(r=>{const card=node('article',''); card.append(node('h2',r.label)); const reading=node('strong',r.value===null?'—':Number(r.value).toFixed(2),'reading'); reading.append(node('small',r.unit)); card.append(reading);
    const stale=r.value===null || Date.now()-Date.parse(r.measured_at)>5000;
    card.append(node('p',stale?'Sin lectura reciente':r.value<r.minimum?'Bajo':r.value>r.maximum?'Alto':'En rango',stale?'text-secondary':r.value<r.minimum||r.value>r.maximum?'text-danger':'text-success'));
    card.append(node('small',`${r.source||'Sin origen'} · ${date(r.measured_at)}`)); $('sensor-cards').append(card);});
}
const charts={};
async function histories() {
  if(!$('charts')) return;
  const types=await api('/api/sensors/types'); const params=new URLSearchParams();
  if($('history-filter')) for(const [key,value] of new FormData($('history-filter'))) if(value) params.set(key,new Date(value).toISOString());
  const all=await Promise.all(types.map(t=>api(`/api/sensors/history/${t.variable}?${params}`)));
  let events=[]; try { events=await api('/api/control/events'); } catch(e) { /* history remains usable without control */ }
  types.forEach((type,i)=>{ const rows=all[i]; let chart=charts[type.variable];
    if(!chart) {
      const box=node('div','','chart-box');
      const heading=node('div','','chart-heading'); heading.append(node('h3',type.label));
      const link=node('a','Descargar CSV'); link.id=`csv-${type.variable}`; link.setAttribute('aria-label',`Descargar CSV de ${type.label}`); heading.append(link); box.append(heading);
      const frame=node('div','','chart-canvas'); const canvas=document.createElement('canvas');
      canvas.setAttribute('aria-label',`${type.label} a lo largo del tiempo, en ${type.unit}`); canvas.setAttribute('role','img'); frame.append(canvas); box.append(frame);
      const empty=node('p','','chart-empty'); empty.id=`empty-${type.variable}`; box.append(empty); $('charts').append(box);
      chart=new Chart(canvas,{type:'line',data:{datasets:[]},options:{
        animation:false,responsive:true,maintainAspectRatio:false,parsing:false,
        interaction:{mode:'index',intersect:false},
        scales:{x:{type:'linear',grid:{display:false},border:{display:false},ticks:{color:'#64736d',maxTicksLimit:5,maxRotation:0,callback:function(value){const span=this.max-this.min; const d=new Date(value); return span>=86400000?d.toLocaleDateString([], {day:'2-digit',month:'2-digit'}):d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',...(span<300000?{second:'2-digit'}:{}),hour12:false});}}},
          y:{border:{display:false},grid:{color:'#edf1ee'},ticks:{color:'#64736d',maxTicksLimit:5},title:{display:!!type.unit,text:type.unit,color:'#64736d'}}},
        plugins:{legend:{display:type.variable==='ph',position:'bottom',labels:{boxWidth:16,boxHeight:2,color:'#64736d',font:{size:11}}},
          tooltip:{backgroundColor:'#243731',padding:12,displayColors:false,callbacks:{title:items=>items.length?date(items[0].parsed.x):'',label:item=>`${item.dataset.label}: ${Number(item.parsed.y).toFixed(2)} ${type.unit}`}}}
      }}); charts[type.variable]=chart;
    }
    $(`csv-${type.variable}`).href=`/api/sensors/history/${type.variable}?${params}&format=csv`;
    const points=rows.map(r=>({x:Date.parse(r.measured_at),y:r.value})).sort((a,b)=>a.x-b.x);
    $(`empty-${type.variable}`).textContent=points.length?'':'Sin lecturas en este intervalo.';
    chart.data.datasets=[{label:type.label,data:points,borderColor:'#28735b',backgroundColor:'#28735b0a',fill:true,pointRadius:points.length===1?3:0,pointHitRadius:12,pointHoverRadius:4,borderWidth:2,spanGaps:false}];
    if(type.variable==='ph') {
      const ordered=events.slice().sort((a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp));
      chart.data.datasets.push({label:'Objetivo registrado',data:points.map(p=>{const e=ordered.find(e=>Date.parse(e.timestamp)<=p.x);return {x:p.x,y:e?e.setpoint:null};}),borderColor:'#a88448',borderDash:[4,4],pointRadius:0,borderWidth:1.5,stepped:true});
    }
    chart.update();
  });
}
async function alerts() {
  if(!$('recent-alerts')&&!$('alert-table')) return;
  const rows=await api(`/api/alerts?status=${$('alert-filter')?.value||'active'}`);
  table($('alert-table')?'alert-table':'recent-alerts',rows,[['severity','Nivel'],['message','Condición'],['opened_at','Inicio UTC'],['resolved_at','Resuelta UTC']]);
}
async function visions() {
  if(!$('vision-list')&&!$('vision-summary')) return;
  const data=await api('/api/vision/latest');
  if($('vision-summary')) { $('vision-summary').textContent=data?`${data.coverage.toFixed(1)}% cobertura verde · ${date(data.timestamp)}`:'Sin análisis'; if(data) {const img=document.createElement('img');img.src=`/api/vision/image/${data.processed_image}`;img.alt='Última segmentación vegetal';$('vision-summary').append(img);} }
  if($('vision-list')) { const rows=await api('/api/vision'); $('vision-list').replaceChildren();rows.forEach(r=>{const card=node('article','');const img=document.createElement('img');img.src=`/api/vision/image/${r.processed_image}`;img.alt='Segmentación de '+r.filename;card.append(img,node('h3',`${r.coverage.toFixed(2)}% verde`),node('p',`${r.filename} · ${date(r.timestamp)}`),node('small',r.observations));$('vision-list').append(card);}); }
}
async function mlReport() {
  if(!$('ml-tests')) return;
  try {
    const report=await api('/api/vision/ml/report');
    const test=report.splits.test;
    const format=value=>Number(value).toLocaleString('es', {maximumFractionDigits:2});
    $('ml-status').textContent=`Entrenamiento registrado: ${date(report.created_at)}. Precisión insuficiente para uso operativo; R² de prueba: ${format(test.model.r2)}.`;
    $('ml-metrics').replaceChildren();
    for(const [title,value,description] of [
      ['Muestra del dataset',`${report.raw_samples} imágenes`,'Distribuidas entre tres experimentos'],
      ['Error medio en prueba',`${format(test.model.mae_days)} días`,`${test.images} imágenes de ${test.experiment}`],
      ['Referencia simple',`${format(test.baseline_train_median.mae_days)} días`,'Error al responder siempre la mediana del entrenamiento']
    ]) {
      const card=node('article',''); card.append(node('h3',title),node('strong',value,'ml-value'),node('p',description,'note')); $('ml-metrics').append(card);
    }
    const labels={train:'Entrenamiento',validation:'Validación',test:'Prueba reservada'};
    table('ml-splits',Object.entries(report.splits).map(([key,s])=>({split:labels[key]||key,experiment:s.experiment,images:s.images,days:s.dates,mae:format(s.model.mae_days),baseline:format(s.baseline_train_median.mae_days),r2:format(s.model.r2)})),[['split','Conjunto'],['experiment','Experimento'],['images','Imágenes'],['days','Fechas'],['mae','Error medio (días)'],['baseline','Referencia (días)'],['r2','R²']]);
    $('ml-figure').hidden=false;
  } catch(error) { $('ml-status').textContent='Resultados no disponibles: '+error.message; }
}
function bindForm(id,url,transform=x=>x,after=()=>{}) { if(!$(id)) return;$(id).addEventListener('submit',async e=>{e.preventDefault();try{await api(url,'POST',transform(Object.fromEntries(new FormData(e.target))));feedback('Operación registrada');await after();}catch(e){feedback(e.message,true);}}); }
function button(id,url,body,after=()=>controlStatus()) { if($(id)) $(id).onclick=async()=>{try{await api(url,'POST',body);feedback('Operación registrada');await after();}catch(e){feedback(e.message,true);}}; }
async function adminPages() {
  if($('ranges')) { const rows=await api('/api/sensors/types'); rows.forEach(r=>{const form=node('form','','form-grid mb-3');form.append(node('strong',r.label));['minimum','maximum'].forEach(key=>{const label=node('label',key==='minimum'?'Mínimo':'Máximo');const input=document.createElement('input');Object.assign(input,{name:key,type:'number',step:'any',value:r[key],required:true,className:'form-control'});label.append(input);form.append(label);});const submit=node('button','Guardar','btn btn-success');form.append(submit);form.onsubmit=async e=>{e.preventDefault();try{await api('/api/settings/ranges','POST',{variable:r.variable,minimum:Number(form.minimum.value),maximum:Number(form.maximum.value)});feedback('Rango guardado');}catch(e){feedback(e.message,true);}};$('ranges').append(form);}); }
  if($('users-table')) table('users-table',await api('/api/users'),[['username','Usuario'],['role','Rol'],['active','Activo']]);
  if($('audit-table')) table('audit-table',await api('/api/audit'),[['timestamp','Fecha UTC'],['username','Usuario'],['action','Acción'],['details','Detalle']]);
  if($('metrics')) {const m=await api('/api/metrics');$('metrics').textContent=JSON.stringify(m,null,2);}
}
async function refresh() {try{const state=await api('/api/health');$('connection').textContent=`Perfil: ${state.profile || 'local'} · SQLite: ${state.database} · MQTT: ${state.services.mqtt} · ${new Date().toLocaleTimeString()}`;await Promise.all([cards(),controlStatus(),alerts()]);}catch(e){$('connection').textContent='Sin actualización: '+e.message;}}
(async()=>{
  bindForm('pid-form','/api/control/config',data=>Object.fromEntries(Object.entries(data).map(([k,v])=>[k,Number(v)])));
  bindForm('manual-form','/api/control/manual',d=>({output:Number(d.output)}));
  bindForm('disturbance-form','/api/simulation/disturbance',d=>({variable:d.variable,delta:Number(d.delta)}));
  bindForm('vision-form','/api/vision/analyze',d=>({filename:d.filename,roi:d.roi?d.roi.split(',').map(Number):null}),visions);
  bindForm('user-form','/api/users',d=>d,adminPages);
  button('auto','/api/control/mode',{mode:'automatic'});button('stop','/api/control/manual',{output:0});button('emergency','/api/control/emergency',{});button('reset','/api/control/reset',{});button('webcam','/api/vision/capture',{},visions);
  if($('backup')) $('backup').onclick=async()=>{try{const response=await fetch('/api/backup',{method:'POST',headers:{'X-CSRF-Token':csrf()}});if(!response.ok)throw new Error('Error al crear respaldo');const a=document.createElement('a');a.href=URL.createObjectURL(await response.blob());a.download='hidroponia-backup.sqlite3';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}catch(e){feedback(e.message,true);}};
  if($('history-filter')) $('history-filter').onsubmit=e=>{e.preventDefault();histories().catch(e=>feedback(e.message,true));};
  if($('alert-filter')) $('alert-filter').onchange=()=>alerts().catch(e=>feedback(e.message,true));
  try { if($('image-files')) (await api('/api/vision/files')).forEach(f=>{const o=node('option',f);o.value=f;$('image-files').append(o);});await refresh();await controlStatus(true);await histories();await visions();await mlReport();await adminPages(); } catch(e){feedback(e.message,true);}
  setInterval(refresh,2000);if($('charts'))setInterval(()=>histories().catch(e=>feedback(e.message,true)),10000);
})();

'use strict';
const $ = (id) => document.getElementById(id);
const token = () => $('token').value.trim();
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const state = { overview: null, query: '' };
const colors = ['#72dacf','#ae9eff','#f2c873','#83b9ff','#ff9bae','#8fdba9'];
const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
const percent = (used,total) => total > 0 ? Math.min(100, Math.max(0, (n(used)/n(total))*100)) : 0;
const mb = (value) => { const size=n(value); if(size>=1024*1024) return (size/1024/1024).toFixed(1)+' TB'; if(size>=1024) return (size/1024).toFixed(1)+' GB'; return Math.round(size)+' MB'; };
const shortDate = (value) => { if(!value) return '—'; const date=new Date(String(value).replace(' ','T')+'Z'); return Number.isNaN(date.getTime())?String(value):date.toLocaleString([], {month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'}); };
const statusBadge = (status) => `<span class="status-badge status-${esc(String(status||'UNKNOWN').toUpperCase())}">${esc(String(status||'UNKNOWN').replaceAll('_',' '))}</span>`;

async function api(url, options={}) {
  const response = await fetch(url, {
    ...options,
    headers: {'Content-Type':'application/json','Authorization':'Bearer '+token(), ...(options.headers||{})},
  });
  let data;
  try { data = await response.json(); } catch { data = {error:'The server returned a non-JSON response.'}; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function toast(message, isError=false) {
  const element=$('toast');
  element.textContent=message;
  element.classList.toggle('error',isError);
  element.classList.add('show');
  clearTimeout(toast.timeout);
  toast.timeout=setTimeout(()=>element.classList.remove('show'),4200);
}

function setConnection(connected, detail='') {
  const badge=$('connectionBadge');
  badge.innerHTML=`<span class="status-dot ${connected?'good':'bad'}"></span> MySQL · ${connected?'Connected':'Needs attention'}`;
  $('sideDot').className='status-dot '+(connected?'good':'bad');
  $('sideDbStatus').textContent=connected?'MySQL connected':'MySQL disconnected';
  $('sideDbDetail').textContent=detail || (connected?'Live queries ready':'Check .env and MySQL Server');
  $('authDrawer').classList.toggle('connected',connected);
}

function renderServers(resources) {
  const servers=resources?.servers||[];
  $('serverCountTag').textContent=`${servers.length} server${servers.length===1?'':'s'}`;
  if(!servers.length) {
    $('serverCards').innerHTML='<div class="empty-state">No logical servers found. Check that the schema initialized successfully.</div>';
    return;
  }
  $('serverCards').innerHTML=servers.map((server,index)=>{
    const cpuUsed=server.cpu_total-server.cpu_available;
    const ramUsed=server.ram_total_mb-server.ram_available_mb;
    const diskUsed=server.disk_total_mb-server.disk_available_mb;
    const load=(percent(cpuUsed,server.cpu_total)+percent(ramUsed,server.ram_total_mb)+percent(diskUsed,server.disk_total_mb))/3;
    return `<article class="server-mini">
      <div class="server-mini-top"><span class="server-mini-name">${esc(server.server_name)}</span><span class="server-mini-status">${esc(server.status||'ONLINE')}</span></div>
      <div class="resource-line"><div class="resource-line-head"><span>CPU</span><strong>${n(server.cpu_available)} / ${n(server.cpu_total)}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${percent(cpuUsed,server.cpu_total)}%"></div></div></div>
      <div class="resource-line"><div class="resource-line-head"><span>RAM</span><strong>${mb(server.ram_available_mb)} free</strong></div><div class="bar-track"><div class="bar-fill ram" style="width:${percent(ramUsed,server.ram_total_mb)}%"></div></div></div>
      <div class="resource-line"><div class="resource-line-head"><span>Storage</span><strong>${mb(server.disk_available_mb)} free</strong></div><div class="bar-track"><div class="bar-fill disk" style="width:${percent(diskUsed,server.disk_total_mb)}%"></div></div></div>
      <div class="server-load-label"><span>Capacity utilised</span><strong>${load.toFixed(0)}%</strong></div>
    </article>`;
  }).join('');
}

function renderJobs(jobs) {
  const query=state.query.trim().toLowerCase();
  const filtered=(jobs||[]).filter(job=>[job.job_id,job.name,job.job_type,job.status,job.worker_id].some(v=>String(v??'').toLowerCase().includes(query)));
  $('jobTableCount').textContent=`${filtered.length} record${filtered.length===1?'':'s'}`;
  $('jobsBody').innerHTML=filtered.length?filtered.map(job=>{
    const result = job.result ? 'Result saved' : (job.error_text?'Error recorded':'No result yet');
    return `<tr>
      <td><div class="job-main"><span class="job-glyph">▤</span><span><strong>${esc(job.name)}</strong><small>${esc(job.job_id)} · ${esc(shortDate(job.created_at))}</small></span></div></td>
      <td>${esc(String(job.job_type||'').replaceAll('_',' '))}</td>
      <td><span class="resource-chip">${n(job.cpu_cores)} CPU</span> · <span class="resource-chip">${mb(job.ram_mb)} RAM</span></td>
      <td>${statusBadge(job.status)}</td><td>${esc(job.worker_id||'Unassigned')}</td><td title="${esc(result)}">${esc(shortDate(job.updated_at))}</td>
    </tr>`;
  }).join(''):'<tr><td colspan="6" class="table-empty">No jobs match this search.</td></tr>';
}

function renderWorkers(workers) {
  $('workerTableCount').textContent=`${(workers||[]).length} worker${(workers||[]).length===1?'':'s'}`;
  $('workersBody').innerHTML=(workers||[]).length?workers.map(worker=>{
    const metrics=worker.metrics||{};
    const cpu=n(metrics.cpu_percent);
    const platform=metrics.platform||(worker.capabilities||{}).platform||'—';
    return `<tr>
      <td><div class="worker-name"><span class="worker-icon">⌘</span><span><strong>${esc(worker.name)}</strong><small>${esc(worker.worker_id)}</small></span></div></td>
      <td>${statusBadge(worker.online?'ONLINE':'OFFLINE')}</td>
      <td><div class="cpu-meter"><div class="bar-track"><div class="bar-fill ${cpu>80?'disk':''}" style="width:${Math.min(100,cpu)}%"></div></div><span>${cpu.toFixed(0)}%</span></div></td>
      <td>${mb(metrics.ram_available_mb)}</td><td>${mb(metrics.disk_free_mb)}</td><td>${esc(platform)}</td><td>${esc(shortDate(worker.last_seen))}</td>
    </tr>`;
  }).join(''):'<tr><td colspan="7" class="table-empty">No workers have registered yet. Start a worker agent to see live heartbeats.</td></tr>';
}

function renderResources(resources) {
  const allocations=resources?.allocations||[];
  $('allocationsBody').innerHTML=allocations.length?allocations.map(row=>`<tr><td>${esc(row.owner)}</td><td>${esc(row.server_id)}</td><td>${n(row.cpu_cores)}</td><td>${mb(row.ram_mb)}</td><td>${mb(row.disk_mb)}</td><td>${esc(shortDate(row.allocated_at))}</td></tr>`).join(''):'<tr><td colspan="6" class="table-empty">There are no active allocations.</td></tr>';
  const logs=resources?.recent_logs||[];
  $('logsBody').innerHTML=logs.length?logs.slice(0,12).map(row=>`<tr><td>${statusBadge(row.event_type)}</td><td>${esc(row.owner||'—')}</td><td>${n(row.cpu_cores)} CPU · ${mb(row.ram_mb)}</td><td>${esc(shortDate(row.created_at))}</td></tr>`).join(''):'<tr><td colspan="4" class="table-empty">No resource events recorded.</td></tr>';
}

function renderOverview(data) {
  state.overview=data;
  const summary=data.summary||{};
  $('online').textContent=summary.online_workers??0;
  $('workerCountLabel').textContent=`${summary.total_workers??0} registered`;
  $('jobsCount').textContent=summary.total_jobs??0;
  $('queuedCount').textContent=summary.queued_jobs??0;
  $('runningLabel').textContent=`${summary.running_jobs??0} running`;
  $('jobFootLabel').textContent=`${summary.completed_jobs??0} completed`;
  $('freeCpu').textContent=summary.available_cpu??0;
  $('cpuTotalLabel').textContent=`of ${summary.total_cpu??0} total cores`;
  renderServers(data.resources);
  renderJobs(data.jobs);
  renderWorkers(data.workers);
  renderResources(data.resources);
  $('lastUpdated').textContent=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  setConnection(true,`${summary.total_workers??0} workers seen · Live queries ready`);
}

async function refresh() {
  if(!token()) {
    $('token').focus();
    toast('Enter ADMIN_TOKEN in the access panel, then connect the dashboard.',true);
    return;
  }
  $('refresh').disabled=true;
  $('refresh').innerHTML='<span class="refresh-glyph">↻</span> Loading…';
  try {
    const data=await api('/api/overview');
    renderOverview(data);
    $('authDrawer').classList.add('connected');
    toast('Dashboard data refreshed.');
  } catch (error) {
    setConnection(false,'Check MySQL Server, .env and admin token');
    toast(error.message,true);
  } finally {
    $('refresh').disabled=false;
    $('refresh').innerHTML='<span class="refresh-glyph">↻</span> Refresh data';
  }
}

function setInlineResult(id, message, error=false) {
  const target=$(id);
  target.className=`inline-result ${error?'error':'success'}`;
  target.textContent=message;
}

function renderSchedule(data) {
  const result=data.result;
  const wrapper=$('scheduleResult');
  const metrics=[['Avg. waiting',result.average_waiting],['Avg. turnaround',result.average_turnaround],['Avg. response',result.average_response]];
  const makespan=Math.max(1,n(result.makespan));
  const gantt=(result.schedule||[]).map((segment,index)=>{
    const idle=segment.pid===null;
    const color=idle?'#252f42':colors[Math.abs(String(segment.pid).split('').reduce((sum,ch)=>sum+ch.charCodeAt(0),0))%colors.length];
    const width=Math.max(2,((n(segment.end)-n(segment.start))/makespan)*100);
    return `<div class="gantt-segment ${idle?'idle':''}" title="${esc(segment.pid??'Idle')}: ${segment.start}–${segment.end}" style="flex:0 0 ${width}%;background:${color}">${esc(segment.pid??'Idle')}</div>`;
  }).join('');
  const rows=(result.processes||[]).map(row=>`<tr><td>${esc(row.pid)}</td><td>${n(row.arrival)}</td><td>${n(row.burst)}</td><td>${n(row.start)}</td><td>${n(row.completion)}</td><td>${n(row.waiting)}</td><td>${n(row.turnaround)}</td><td>${n(row.response)}</td></tr>`).join('');
  wrapper.innerHTML=`<div class="result-success"><span class="result-icon">✓</span><div><span class="result-title">${esc(String(data.algorithm).replaceAll('_',' ').toUpperCase())} completed</span><span class="result-caption">${(result.processes||[]).length} processes · Makespan ${makespan} time units</span></div></div>
    <div class="metric-grid">${metrics.map(([label,value])=>`<div class="metric-box"><span>${label}</span><strong>${n(value).toFixed(2)}</strong></div>`).join('')}</div>
    <div class="gantt-wrap"><div class="gantt-title"><span>Gantt timeline</span><span>0 — ${makespan}</span></div><div class="gantt-chart">${gantt}</div><div class="gantt-ticks"><span>0</span><span>${(makespan/2).toFixed(1)}</span><span>${makespan}</span></div></div>
    <div class="table-wrap"><table class="mini-table"><thead><tr><th>PID</th><th>Arr.</th><th>Burst</th><th>Start</th><th>Finish</th><th>Wait</th><th>TAT</th><th>Resp.</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderBanker(data) {
  const safe=Boolean(data.safe);
  const wrapper=$('bankerResult');
  const sequence=safe?(data.safe_sequence||[]).map(index=>`P${index}`).join(' → '):'No complete safe sequence';
  wrapper.innerHTML=`<div class="${safe?'result-success':'result-danger'}"><span class="result-icon">${safe?'✓':'!'}</span><div><span class="result-title">${safe?'SAFE STATE':'UNSAFE STATE'}</span><span class="result-caption">${safe?'The system can finish all processes in a valid order.':'The supplied state cannot guarantee a finish order for every process.'}</span></div></div>
    ${safe?`<div class="metric-box"><span>Safe sequence · process indexes from the matrix</span><div class="safe-sequence">${esc(sequence)}</div></div>`:`<div class="code-result">Unfinished process indexes: ${esc(JSON.stringify(data.unfinished_processes||[]))}</div>`}
    <div class="code-result" style="margin-top:9px">Need matrix (Maximum − Allocation):\n${esc(JSON.stringify(data.need,null,2))}</div>`;
}

$('refresh').addEventListener('click',refresh);
$('connect').addEventListener('click',refresh);
$('authToggle').addEventListener('click',()=>{ $('authDrawer').classList.remove('connected'); $('token').focus(); });
$('toggleToken').addEventListener('click',()=>{$('token').type=$('token').type==='password'?'text':'password';});
$('jobSearch').addEventListener('input',(event)=>{state.query=event.target.value;renderJobs(state.overview?.jobs||[]);});
$('token').addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();refresh();}});

$('jobForm').addEventListener('submit',async(event)=>{
  event.preventDefault();
  const form=event.currentTarget;
  const payload=Object.fromEntries(new FormData(form));
  for(const key of ['cpu_cores','ram_mb','disk_mb']) payload[key]=Number(payload[key]);
  try {
    const data=await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)});
    setInlineResult('submitResult',`${data.message}\nJob ID: ${data.job.job_id}\nStatus: ${data.job.status}`);
    form.querySelector('input[name="name"]').value='';
    await refresh();
  } catch(error) { setInlineResult('submitResult',error.message,true); }
});

$('schedulerForm').addEventListener('submit',async(event)=>{
  event.preventDefault();
  const values=Object.fromEntries(new FormData(event.currentTarget));
  try {
    const processes=JSON.parse(values.processes);
    const data=await api('/api/phase2/schedule',{method:'POST',body:JSON.stringify({algorithm:values.algorithm,quantum:Number(values.quantum),processes})});
    renderSchedule(data);
  } catch(error) {
    $('scheduleResult').innerHTML=`<div class="result-danger"><span class="result-icon">!</span><div><span class="result-title">Scheduling failed</span><span class="result-caption">${esc(error.message)}</span></div></div>`;
  }
});

$('bankerForm').addEventListener('submit',async(event)=>{
  event.preventDefault();
  try {
    const payload=JSON.parse(new FormData(event.currentTarget).get('banker'));
    const data=await api('/api/phase2/banker',{method:'POST',body:JSON.stringify(payload)});
    renderBanker(data);
  } catch(error) {
    $('bankerResult').innerHTML=`<div class="result-danger"><span class="result-icon">!</span><div><span class="result-title">Safety check failed</span><span class="result-caption">${esc(error.message)}</span></div></div>`;
  }
});

$('resourceForm').addEventListener('submit',async(event)=>{
  event.preventDefault();
  const values=Object.fromEntries(new FormData(event.currentTarget));
  const payload={owner:values.owner,request:{cpu_cores:Number(values.cpu_cores),ram_mb:Number(values.ram_mb),disk_mb:Number(values.disk_mb)}};
  try {
    const data=await api('/api/phase2/resources/allocate',{method:'POST',body:JSON.stringify(payload)});
    const message=data.allocated?`Allocation ${data.allocation_id} created on ${data.server.server_name}.\nCPU: ${data.allocation.cpu_cores}, RAM: ${mb(data.allocation.ram_mb)}, Storage: ${mb(data.allocation.disk_mb)}`:(data.reason||'Allocation rejected');
    setInlineResult('resourceResult',message,!data.allocated);
    if(data.allocated) await refresh();
  } catch(error) { setInlineResult('resourceResult',error.message,true); }
});

$('releaseResource').addEventListener('click',async()=>{
  const owner=new FormData($('resourceForm')).get('owner')?.trim();
  if(!owner){setInlineResult('resourceResult','Enter the allocation owner first.',true);return;}
  try {
    const data=await api('/api/phase2/resources/release',{method:'POST',body:JSON.stringify({owner})});
    const released=data.released;
    setInlineResult('resourceResult',released?`Resources released for ${owner}.\nCPU: ${data.released_resources.cpu_cores}, RAM: ${mb(data.released_resources.ram_mb)}, Storage: ${mb(data.released_resources.disk_mb)}`:(data.reason||'No active allocation found.'),!released);
    if(released) await refresh();
  } catch(error) { setInlineResult('resourceResult',error.message,true); }
});

// Sidebar navigation updates the breadcrumb and active item without a page reload.
document.querySelectorAll('.nav-link').forEach(link=>link.addEventListener('click',()=>{
  document.querySelectorAll('.nav-link').forEach(item=>item.classList.toggle('active',item===link));
  $('pageName').textContent=link.textContent.trim().replace(/^\S+\s*/, '');
}));

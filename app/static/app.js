'use strict';
const $ = id => document.getElementById(id);
// Open classroom deployment: no application login. Central tracker tokens remain separate.
let token='classroom-open';
let bwCancelled=false;
let lastStatus=null;
let alertTimer=null;
let currentPage='overview';
let stressTarget=sessionStorage.getItem('koolab_stress_target')||'';
const PAGES={architecture:'Distributed Architecture',overview:'Infrastructure Overview',rds:'RDS Connection',elb:'Elastic Load Balancer',scaling:'Compute Auto Scaling',bandwidth:'EIP Bandwidth Lab',security:'Security Center',assessment:'Student Lab Assessment',tracker:'Student Progress'};
function plainError(e){return e && e.message ? e.message : String(e);}
async function api(path, options={}){
 const headers={...(options.headers||{})};
 if(options.body && !(options.body instanceof Uint8Array) && !headers['Content-Type'])headers['Content-Type']='application/json';
 const res=await fetch(path,{...options,headers,cache:'no-store'});
 let data;const typ=res.headers.get('content-type')||'';
 if(typ.includes('application/json'))data=await res.json();else data=await res.text();
 if(!res.ok)throw Error((data && (data.detail||data.error))||`HTTP ${res.status}`);
 return data;
}
function notice(message,error=false){const el=$('flash');el.textContent=message;el.className='flash'+(error?' error':'');clearTimeout(alertTimer);alertTimer=setTimeout(()=>el.classList.add('hidden'),6500);}
function feedback(id,message,bad=false){const el=$(id);el.textContent=message;el.className='feedback '+(bad?'error':'good');}
function badge(result){return result==='pass'?'<b class="ok">● PASS</b>':result==='fail'?'<b class="fail">● FAIL</b>':result==='warn'?'<b class="warn">● WARN</b>':result==='info'?'<b class="manual">● INFO</b>':'<b class="manual">○ VERIFY</b>';}
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;}
function goto(page){if(!PAGES[page])return;currentPage=page;document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id==='page-'+page));document.querySelectorAll('[data-page]').forEach(x=>x.classList.toggle('active',x.dataset.page===page));$('pageTitle').textContent=PAGES[page];window.scrollTo({top:0,behavior:'smooth'});
 if(page==='architecture')loadArchitecture();if(page==='rds'){loadRDS();loadMessages();}if(page==='security')runSecurity();if(page==='assessment')renderAssessment();if(page==='tracker')trackerPage();if(page==='scaling')loadStress();}
async function refresh(){try{const s=await api('/api/status');lastStatus=s;$('statApp').textContent=s.live?'ONLINE':'OFFLINE';$('statNode').textContent=s.node;$('sidebarNode').textContent=s.node;$('footerNode').textContent=s.node;$('statDb').textContent=s.database_mode.toUpperCase();$('statDbHelp').textContent=s.shared_rds?'Connected to Huawei RDS':s.database_mode==='sqlite'?'Local SQLite — NOT shared':'RDS connection failed';$('statLoad').textContent=s.stress_running?'ACTIVE':'IDLE';$('viewUrl').textContent=location.host;$('containerId').textContent=s.container;$('upTime').textContent=fmtTime(s.uptime_seconds);
 const data=[['Website responding','pass'],['Container instance identified','pass'],['Database accepts queries',s.database_ok?'pass':'fail'],['Real external RDS configured',s.shared_rds?'pass':'warn'],['ELB routing validated','manual'],['Huawei Auto Scaling action','manual'],['Cloud security groups verified','manual']];
 const box=$('quickChecks');box.replaceChildren();data.forEach(([name,status])=>{const div=el('div','quickline');div.append(el('span','',name));const b=el('b',status==='pass'?'ok':status==='fail'?'fail':'manual',status.toUpperCase());div.append(b);box.append(div);});
 }catch(e){$('statApp').textContent='ERROR';notice('Unable to retrieve current app status: '+plainError(e),true);}}
function fmtTime(n){n=Number(n)||0;return `${Math.floor(n/3600)}h ${Math.floor(n%3600/60)}m ${n%60}s`;}
async function allTests(){const box=$('selfTests');box.textContent='Running genuine application checks…';try{const response=await api('/api/self-test');box.replaceChildren();response.tests.forEach(t=>{let r=t.passed===true?'pass':t.passed===false?'warn':'manual';const div=el('div','test-row');const label=el('strong');label.textContent=(r==='pass'?'✓ ':r==='manual'?'○ ':'! ')+t.name;label.className=r==='pass'?'ok':r==='manual'?'manual':'warn';div.append(label,el('small','',t.detail));box.append(div);});notice('Checks complete. Cloud-console-only tasks remain unverified until you provide evidence.'); autoReport('ecs_app_ready','passed','Application responded to self-test API');}catch(e){box.textContent=plainError(e);}}
function formRDS(){return {host:$('dbHost').value.trim(),port:Number($('dbPort').value),db_name:$('dbName').value.trim(),user:$('dbUser').value.trim(),password:$('dbPass').value,tls:$('dbTls').value,ca:$('dbCa').value,initialize:$('dbInit').checked};}
async function loadRDS(){try{const c=await api('/api/rds/config');if(c.configured){$('dbHost').value=c.host;$('dbPort').value=c.port;$('dbName').value=c.db_name;$('dbUser').value=c.user;$('dbTls').value=c.tls;$('caHolder').classList.toggle('hidden',c.tls!=='verify');}const v=await api('/api/rds/verify');$('rdsChip').textContent=v.mode==='mysql'?(v.connected?'CONNECTED':'DISCONNECTED'):'LOCAL';$('rdsMode').textContent=v.mode.toUpperCase();$('rdsHost').textContent=c.configured?c.host:'Not connected';$('rdsPing').textContent=v.connected?'PASS':'FAIL';$('rdsTLS').textContent=v.tls.encrypted?'Encrypted':v.mode==='sqlite'?'Not applicable':'Not encrypted / unknown';}catch(e){feedback('rdsFeedback',plainError(e),true);}}
async function testRDS(save){const input=formRDS();const btn=$(save?'dbSave':'dbTestBtn');if(btn)btn.disabled=true;feedback('rdsFeedback','Contacting RDS private address; this may take several seconds…');try{const r=await api(save?'/api/rds/save':'/api/rds/test',{method:'POST',body:JSON.stringify(input)});feedback('rdsFeedback',`${r.message}\nTLS: ${r.tls_encrypted?'ENCRYPTED':'NOT ENCRYPTED'} | Cipher: ${r.tls_cipher}${save?'\nConfiguration saved on this ECS.':''}`);if(save)autoReport('rds_connected','passed','RDS connection tested and configuration saved successfully');if(save){$('dbPass').value='';await loadRDS();await loadMessages();notice('RDS configured. Test shared messages before creating the ECS image.');}}catch(e){feedback('rdsFeedback',plainError(e),true);autoReport('rds_connected','failed','RDS configuration or connection test failed (inspect ECS app feedback)');}finally{if(btn)btn.disabled=false;}}
async function clearRDS(){if(!confirm('Disconnect RDS and return to local SQLite? This does not delete the Huawei RDS database.'))return;try{await api('/api/rds/config',{method:'DELETE'});$('dbPass').value='';await loadRDS();await loadMessages();notice('Application switched to local SQLite.');}catch(e){notice(plainError(e),true);}}
async function loadMessages(){const box=$('messages');box.textContent='Loading…';try{const data=await api('/api/messages');box.replaceChildren();if(!data.items.length){box.textContent='No messages yet. Insert one to test SQL reads and writes.';return;}data.items.forEach(m=>{const div=el('div','message');const body=el('p','',m.body);const meta=el('small','',m.node+' · '+m.created_at);div.append(body,meta);box.append(div);});}catch(e){box.textContent='SQL error: '+plainError(e);}}
async function postMessage(){const body=$('messageInput').value.trim();if(!body){notice('Enter a message before inserting a record.',true);return;}try{await api('/api/messages',{method:'POST',body:JSON.stringify({body})});$('messageInput').value='';await loadMessages();notice('Record inserted. Reload through a second ECS to verify shared RDS.'); autoReport('rds_write_read','evidence','Inserted a message and refreshed SQL records on node '+(lastStatus?.node||'unknown'));}catch(e){notice(plainError(e),true);autoReport('rds_write_read','failed','SQL record insert/readback failed; see lab diagnostics');}}
async function runELB(){const total=Number($('elbCount').value);const btn=$('elbRun');btn.disabled=true;$('elbBusy').textContent='Sampling nodes…';let errors=0;const nodes={};let done=0;try{for(let i=0;i<total;i+=5){const n=Math.min(5,total-i);const results=await Promise.allSettled(Array.from({length:n},(_,j)=>api('/api/identity?nonce='+Date.now()+'.'+i+'.'+j)));results.forEach(r=>{if(r.status==='fulfilled'){nodes[r.value.node]=(nodes[r.value.node]||0)+1;done++;}else errors++;});$('elbBusy').textContent=`${done+errors}/${total} checked`;}
 $('elbTotal').textContent=done;$('elbNodes').textContent=Object.keys(nodes).length;$('elbFail').textContent=errors;const bar=$('elbBars');bar.replaceChildren();Object.entries(nodes).forEach(([host,count])=>{const row=el('div','bar-row');row.append(el('span','mono',host));const bg=el('div','bar-bg');const fill=el('div','bar-fill');fill.style.width=(count/Math.max(done,1)*100)+'%';bg.append(fill);row.append(bg,el('b','',String(count)));bar.append(row);});$('elbVerdict').textContent=Object.keys(nodes).length>1?'Multiple Docker replicas observed. This verifies Nginx distribution only; it does not prove a real Huawei ELB or multi-ECS topology.':'Only one node observed. It may mean one backend, connection reuse, a sticky policy or direct ECS access. This result alone cannot prove a load balancer is misconfigured.';
 if(done>0)autoReport('elb_distribution','evidence',`ELB sampling: ${done} responses, ${Object.keys(nodes).length} distinct nodes, ${errors} errors. Instructor must inspect ELB console.`);
 }catch(e){notice(plainError(e),true);}finally{btn.disabled=false;$('elbBusy').textContent='';}}
async function targetStress(path,options={}){
 const full=path+(stressTarget?('?target_node='+encodeURIComponent(stressTarget)):'');
 let last;
 for(let attempt=0;attempt<12;attempt++){
  try{return await api(full,options);}catch(e){last=e;if(!plainError(e).includes('409')&&!plainError(e).includes('different backend')&&!plainError(e).includes('looking for'))break;}
  await new Promise(r=>setTimeout(r,150));
 }
 throw Error('Could not reach the original ECS node through ELB. Use that node’s authorized private-IP URL for direct management. '+plainError(last));
}
async function loadStress(){try{const s=await targetStress('/api/stress/status');$('stressState').textContent=s.running?'RUNNING on '+s.node:'IDLE on '+s.node;$('stressRemaining').textContent=s.running?fmtTime(s.remaining):'—';$('stressFill').style.width=s.running?(Math.min(100,s.elapsed/Math.max(1,s.duration)*100)+'%'):'0%';$('statLoad').textContent=s.running?'ACTIVE':'IDLE';if(!s.running && stressTarget){stressTarget='';sessionStorage.removeItem('koolab_stress_target');}}catch(e){if(currentPage==='scaling')feedback('stressFeedback',plainError(e),true);}}
async function runStress(){if(!confirm('Start a real CPU load on the responding ECS for the selected duration? Use only your authorized Huawei lab instance.'))return;try{const s=await api('/api/stress/start',{method:'POST',body:JSON.stringify({seconds:Number($('stressSeconds').value),workers:Number($('stressWorkers').value)})});stressTarget=s.node;sessionStorage.setItem('koolab_stress_target',stressTarget);feedback('stressFeedback',`Started ${s.workers} CPU worker(s) for ${s.duration} seconds on ${s.node}. Monitor Cloud Eye / AS group events.`,false);await loadStress();autoReport('scaling_test','evidence','CPU stress initiated on '+s.node+'; scaling action not yet verified in Huawei console');}catch(e){feedback('stressFeedback',plainError(e),true);}}
async function stopStress(){try{await targetStress('/api/stress/stop',{method:'POST'});notice('CPU stop signal sent to targeted backend '+(stressTarget||'(current node)'));setTimeout(loadStress,900);}catch(e){notice(plainError(e),true);}}
function prettyBytes(n){return (n/1024/1024).toFixed(2)+' MB';}
async function probeBandwidth(){const count=Number($('bwCount').value),kb=Number($('bwKB').value),direction=$('bwDirection').value;bwCancelled=false;$('bwStart').disabled=true;$('bwDone').textContent='0';$('bwBytes').textContent='0 MB';$('bwRate').textContent='—';feedback('bwFeedback','Running bounded '+direction+' tests…');let bytes=0,done=0;const start=performance.now();try{for(let i=0;i<count&&!bwCancelled;i++){if(direction==='upload'){const body=new Uint8Array(kb*1024);const r=await api('/api/probe/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body});bytes+=r.received_bytes;}else{const response=await fetch('/api/probe/download?kb='+kb+'&n='+i,{cache:'no-store'});if(!response.ok)throw Error(`HTTP ${response.status}`);const body=await response.arrayBuffer();bytes+=body.byteLength;}
 done++;$('bwDone').textContent=done;$('bwBytes').textContent=prettyBytes(bytes);$('bwRate').textContent=((bytes*8/1000000)/Math.max((performance.now()-start)/1000,.01)).toFixed(2)+' Mbit/s';await new Promise(r=>setTimeout(r,180));}
 feedback('bwFeedback',`${bwCancelled?'Stopped':'Completed'}: ${done}/${count} ${direction} requests (${prettyBytes(bytes)}). Check actual EIP Cloud Eye ${direction==='upload'?'INBOUND':'OUTBOUND'} metric for the period. This alone does not prove bandwidth scaling.`,false);
 if(done>0)autoReport('bandwidth_test','evidence',`Bounded ${direction} bandwidth probe: ${done} samples, ${bytes} bytes. Cloud Eye verification required.`);
 }catch(e){feedback('bwFeedback','Probe interrupted: '+plainError(e),true);}finally{$('bwStart').disabled=false;}}
async function runSecurity(){const box=$('securityItems');box.textContent='Examining actual process restrictions and RDS transport…';try{const r=await api('/api/security/checks');let passed=0,warn=0,manual=0;box.replaceChildren();r.checks.forEach(x=>{if(x.result==='pass')passed++;else if(x.result==='manual')manual++;else warn++;const div=el('div','audit-item');const icon=el('div','iconpass '+(x.result==='pass'?'ok':x.result==='manual'?'manual':'warn'),x.result==='pass'?'✓':x.result==='manual'?'◇':'!');const body=el('div');const b=el('b','',x.name+' · '+x.result.toUpperCase());body.append(b,el('p','',x.evidence));div.append(icon,body);box.append(div);});$('secPassed').textContent=passed;$('secWarn').textContent=warn;$('secManual').textContent=manual;autoReport('security_checks','evidence',`Local security audit: ${passed} pass, ${warn} warn, ${manual} require manual console inspection`);}catch(e){box.textContent='Audit failed: '+plainError(e);}}
const tasks=[
 ['Cloud network','Confirm vpc-primary and subnet-web are preset','Screenshot VPC and subnet console'],
 ['Cloud network','Create subnet-db (192.168.2.0/24)','Subnet details / screenshot'],
 ['RDS','Create sg-db, restrict inbound TCP 3306 to approved ECS security group or private sources','Security group inbound rule'],
 ['RDS','Create RDS MySQL within subnet-db','RDS instance details'],
 ['RDS','Connect RDS using the RDS Connection wizard','Live SQL connection result'],
 ['RDS','Insert and retrieve a shared test record','Message ID and ECS node names'],
 ['ELB','Unbind ECS EIP and bind it to elb-web','EIP association screenshot'],
 ['ELB','Configure listener-web TCP 80 and server_group-web backend port 80','ELB listener and health screenshot'],
 ['ELB','Verify multiple ECS backends are healthy and sampling identifies multiple nodes','Node distribution counts and ELB health'],
 ['Auto Scaling','Create image-web from working Ubuntu ECS','IMS private image details'],
 ['Auto Scaling','Create as-config-web and as-group-web (min 1 / desired 2 / max 5)','Configuration details'],
 ['Auto Scaling','Set CPU >70% scale-out and CPU <30% scale-in policies','Cloud Eye alarm setup'],
 ['Auto Scaling','Generate CPU load on an AS group instance; verify actual scaling action','AS action history and instance counts'],
 ['Bandwidth','Set up EIP inbound-bandwidth alarm; verify units','Cloud Eye metric and policy screenshot'],
 ['Bandwidth','Generate and inspect bounded traffic','EIP inbound/outbound metric'],
 ['Operations','Enable instance protection and configure AS notifications','AS notifications / protection screenshot'],
 ['Security','Run web security audit; review container controls','Findings and explanations'],
 ['Security','Prove public SSH / 3306 restrictions through actual SG rules','Authorized security group screenshot'],
 ['Security','Document TLS, IAM least privilege and HTTP risks','Mitigation plan and evidence'],
 ['Report','Submit lab evidence report with timestamps and instructor review','Screenshots and instructor sign-off']
];
const assessmentKey='koolab_v2_assessment';
function assessment(){try{return JSON.parse(localStorage.getItem(assessmentKey)||'{}');}catch{return {};}}
function saveAssessment(obj){localStorage.setItem(assessmentKey,JSON.stringify(obj));}
function renderAssessment(){const state=assessment();const root=$('assessmentList');root.replaceChildren();tasks.forEach(([phase,name,proof],i)=>{const record=state[i]||{};const wrapper=el('div','assessment-item');const lab=el('label','assessment-title');const check=el('input');check.type='checkbox';check.checked=!!record.done;check.addEventListener('change',()=>{const st=assessment();st[i]={...(st[i]||{}),done:check.checked,timestamp:new Date().toISOString()};saveAssessment(st);updateCompletion();});lab.append(check,el('span','',`${String(i+1).padStart(2,'0')} · ${phase} — ${name}`));wrapper.append(lab,el('p','',`Evidence required: ${proof}`));const field=el('input');field.type='text';field.placeholder='Evidence reference / screenshot filename / notes';field.value=record.evidence||'';field.addEventListener('change',()=>{const st=assessment();st[i]={...(st[i]||{}),evidence:field.value.trim()};saveAssessment(st);});wrapper.append(field);root.append(wrapper);});updateCompletion();}
function updateCompletion(){const records=assessment();const done=tasks.filter((_,i)=>records[i] && records[i].done).length;$('completionTag').textContent=`${done} / ${tasks.length}`;$('completionFill').style.width=(done/tasks.length*100)+'%';}
function exportEvidence(){const state=assessment();const payload={application:'KooLab Distributed Lab v6',note:'Student self-reported evidence, not certified Huawei telemetry',exported_at:new Date().toISOString(),browser_access:location.href,node:lastStatus?.node||'',tasks:tasks.map(([category,name,required],i)=>({number:i+1,category,name,required,completed:!!state[i]?.done,evidence:state[i]?.evidence||'',timestamp:state[i]?.timestamp||null}))};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='KooLab_Lab_Evidence_'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);notice('Evidence JSON exported to your browser downloads.');autoReport('lab_report','evidence','Assessment JSON exported; student self-reported checklist, not verified by Huawei');}

async function loadArchitecture(){
 const root=$('archStatus');
 try{
  const d=await api('/api/architecture');
  root.replaceChildren();
  const rows=[['Model','3 Docker replicas on ONE ECS, not three ECS instances'],['Current backend',d.node],['Redis shared state',d.redis_ok?'CONNECTED':'UNAVAILABLE'],['Queued jobs',String(d.queued??'?')],['Running jobs',String(d.processing??'?')],['Completed jobs',String(d.completed??'?')],['Worker 1',d.workers?.worker1?'ACTIVE':'OFFLINE'],['Worker 2',d.workers?.worker2?'ACTIVE':'OFFLINE'],['Data layer',d.database||'Not available']];
  rows.forEach(([name,val])=>{const r=el('div','metric-row');r.append(el('span','',name),el('strong','',val));root.append(r);});
 }catch(e){root.textContent=plainError(e);}
 await loadJobs();
}
async function loadJobs(){
 const root=$('archJobs');
 try{const d=await api('/api/architecture/jobs');root.replaceChildren();
  if(!d.jobs.length){root.textContent='No jobs submitted. Enqueue a task to see workers process it.';return;}
  d.jobs.slice(0,12).forEach(j=>{const r=el('div','message');r.append(el('strong','',j.label+' · '+j.state),el('small','',j.id+' | '+(j.worker||'waiting')+' | '+j.seconds+' seconds'));root.append(r);});
 }catch(e){root.textContent=plainError(e);}
}
async function createJob(){
 try{const seconds=Number($('archSeconds').value);const label=$('archLabel').value.trim()||'student-task';
 const d=await api('/api/architecture/jobs',{method:'POST',body:JSON.stringify({seconds,label})});
 feedback('archJobFeedback','Queued '+d.id+' on '+d.submitted_by);await loadArchitecture();
 }catch(e){feedback('archJobFeedback',plainError(e),true);}
}
async function runCache(){
 try{const key=$('archCacheKey').value.trim()||'lesson-1';
 const d=await api('/api/architecture/cache?key='+encodeURIComponent(key));
 feedback('archCacheFeedback',d.result+' · '+d.latency_ms+'ms · TTL '+d.ttl_seconds+' sec · Backend '+d.served_by);}
 catch(e){feedback('archCacheFeedback',plainError(e),true);}
}

function wire(){document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>goto(b.dataset.page)));document.querySelectorAll('[data-goto]').forEach(b=>b.addEventListener('click',()=>goto(b.dataset.goto)));
$('refreshStatus').addEventListener('click',refresh);$('runAll').addEventListener('click',allTests);$('retest').addEventListener('click',allTests);
 $('archRefresh').addEventListener('click',loadArchitecture);$('archSendJob').addEventListener('click',createJob);$('archRunCache').addEventListener('click',runCache);$('archSample').addEventListener('click',()=>goto('elb'));
 $('dbTls').addEventListener('change',()=>{$('caHolder').classList.toggle('hidden',$('dbTls').value!=='verify');});$('dbTestBtn').addEventListener('click',()=>testRDS(false));$('rdsForm').addEventListener('submit',e=>{e.preventDefault();testRDS(true);});$('rdsVerify').addEventListener('click',loadRDS);$('rdsClear').addEventListener('click',clearRDS);$('postMsg').addEventListener('click',postMessage);$('reloadMsgs').addEventListener('click',loadMessages);$('elbRun').addEventListener('click',runELB);$('stressStart').addEventListener('click',runStress);$('stressStop').addEventListener('click',stopStress);$('bwStart').addEventListener('click',probeBandwidth);$('bwStop').addEventListener('click',()=>{bwCancelled=true;});$('secRun').addEventListener('click',runSecurity);$('exportEvidence').addEventListener('click',exportEvidence);$('resetEvidence').addEventListener('click',()=>{if(confirm('Clear this browser’s recorded task checklist?')){localStorage.removeItem(assessmentKey);renderAssessment();}});
 wireTracker(); $('clock').textContent=new Date().toLocaleString();setInterval(()=>{$('clock').textContent=new Date().toLocaleString();},30000);
 refresh();
 setInterval(()=>{if(currentPage==='scaling')loadStress();else if(currentPage==='architecture')loadArchitecture();else refresh();},12000);
}

// Classroom-only HTTP/HTTPS student reporter. Student token stays in tab memory.
// WARNING: direct HTTP browsers send this credential in cleartext to the ECS.
const trackerTokenKey='koolab_v3_tracker_token';
let trackerToken=sessionStorage.getItem(trackerTokenKey)||'';
let trackerSettings=null;
const trackerHistory=[];
const trackerSecure=location.protocol==='https:'; // advisory only; NOT a block
function newTrackerEventId(){
 const a=new Uint8Array(16);
 if(window.crypto && window.crypto.getRandomValues)window.crypto.getRandomValues(a);
 else for(let i=0;i<16;i++)a[i]=Math.floor(Math.random()*256);
 a[6]=(a[6]&15)|64;a[8]=(a[8]&63)|128;
 const h=Array.from(a,x=>x.toString(16).padStart(2,'0')).join('');
 return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}
function trackerLog(message,ok=true){
 trackerHistory.unshift({message,time:new Date().toLocaleTimeString(),ok});
 trackerHistory.length=Math.min(trackerHistory.length,12);
 const root=$('trackerRecent');root.replaceChildren();
 trackerHistory.forEach(x=>{const div=el('div','test-row');const title=el('strong',x.ok?'ok':'warn',(x.ok?'✓ ':'! ')+x.time+' — '+x.message);div.append(title);root.append(div);});
}
function trackerPage(){
 $('trackerTransport').textContent=trackerSecure
   ? 'HTTPS connection: student tokens are protected in transit to this ECS. Reports are sent onward to the instructor tracker over HTTPS.'
   : 'CLASSROOM HTTP MODE: Token linking is enabled. This browser-to-ECS connection is not encrypted; use only disposable classroom tokens and an authorized training ECS. The ECS-to-instructor connection is HTTPS.';
 $('trackerConnect').disabled=false;$('trackerSync').disabled=false;
 $('trackerEvidenceSubmit').disabled=false;$('trackerToken').disabled=false;
 if(trackerToken)$('trackerState').textContent='SESSION LINKED';
 else $('trackerState').textContent='NOT CONNECTED';
}
async function trackerRequest(path,body){
 if(!trackerToken)throw Error('First connect your private student token in the Student Progress tab.');
 return api(path,{method:'POST',body:JSON.stringify({student_token:trackerToken,...body})});
}
async function trackerProbe(){
 try{
  const r=await api('/api/tracker/diagnostics');
  const status=r.reachable?'REACHABLE':'ERROR';
  trackerLog('Central tracker '+status+' (health HTTP '+String(r.upstream_status??'network failure')+'): '+r.detail,r.reachable);
  feedback('trackerFeedback',r.reachable?'Central tracker is reachable. Now connect your student token; note that this does not verify the student API.':'Tracker health check failed: '+r.detail,!r.reachable);
 }catch(err){trackerLog('Health diagnostic failed: '+plainError(err),false);feedback('trackerFeedback',plainError(err),true);}
}
async function trackerLoad(){
 const response=await trackerRequest('/api/tracker/me',{});
 const student=response.student||{},lab=response.lab||{},state=lab.state||{};
 $('trackerStudent').textContent=student.name||student.student_id||'Student';
 $('trackerLab').textContent=lab.code||'—';
 $('trackerReported').textContent=state.reported??'—';
 $('trackerApproved').textContent=state.approved??'—';
 const root=$('trackerMilestones');root.replaceChildren();
 (state.milestones||[]).forEach(m=>{
   const div=el('div','test-row');div.append(el('strong','',m.title||m.key||'Milestone'));
   const status=m.approved?'Instructor approved':(m.latest==='passed'||m.latest==='evidence')?'Reported — pending instructor':m.latest==='failed'?'Failed — needs help':'Not yet reported';
   div.append(el('small','',status));root.append(div);
 });
 if(!(state.milestones||[]).length)root.textContent='Lab created, but instructor milestones have not yet been configured.';
 $('trackerState').textContent='LINKED';
}
async function trackerLink(){
 const input=$('trackerToken').value.trim();
 if(input){trackerToken=input;sessionStorage.setItem(trackerTokenKey,input);$('trackerToken').value='';}
 try{
   await trackerLoad();
   await trackerRequest('/api/tracker/start',{event_id:newTrackerEventId()});
   feedback('trackerFeedback','Connected! STARTED received by instructor tracker. Subsequent test results and live heartbeat report automatically.');
   trackerLog('Lab started; instructor tracker received event');
   await trackerLoad();
 }catch(err){
   feedback('trackerFeedback',plainError(err),true);
   trackerLog('Connection failed: '+plainError(err),false);
   // When link fails, discard the submitted key to avoid retaining invalid credentials.
   trackerToken='';sessionStorage.removeItem(trackerTokenKey);
   $('trackerState').textContent='NOT CONNECTED';
 }
}
async function trackerSync(){try{await trackerLoad();feedback('trackerFeedback','LIVE · Central tracker status retrieved at '+new Date().toLocaleTimeString());}catch(err){feedback('trackerFeedback',plainError(err),true);}}
function trackerUnlink(){trackerPending.length=0;trackerToken='';sessionStorage.removeItem(trackerTokenKey);$('trackerToken').value='';$('trackerState').textContent='NOT CONNECTED';$('trackerStudent').textContent='—';$('trackerReported').textContent='—';$('trackerApproved').textContent='—';$('trackerRecent').textContent='Token disconnected from this browser tab.';trackerHistory.length=0;feedback('trackerFeedback','Token disconnected. Existing instructor records are preserved.');}
const trackerPending=[];
let trackerRetryRunning=false;
async function reportTracker(milestone,event,detail){
 return trackerRequest('/api/tracker/event',{milestone_key:milestone,event,detail:String(detail||'').slice(0,380),event_id:newTrackerEventId()});
}
async function trackerFlush(){
 if(trackerRetryRunning||!trackerToken||!token||!trackerPending.length)return;
 trackerRetryRunning=true;
 try{
   while(trackerPending.length){
     const next=trackerPending[0];
     try{
       await trackerRequest('/api/tracker/event',next);
       trackerPending.shift();
       trackerLog(next.milestone_key+' '+next.event.toUpperCase()+' delivered to instructor');
       if(currentPage==='tracker')trackerLoad().catch(()=>{});
     }catch(err){
       trackerLog('Reporting delayed: '+plainError(err),false);
       // Authentication or configuration errors need student intervention;
       // transient connectivity problems are automatically retried.
       break;
     }
   }
 }finally{trackerRetryRunning=false;}
}
function autoReport(milestone,event,detail){
 if(!trackerToken)return;
 const entry={milestone_key:milestone,event,detail:String(detail||'').slice(0,380),event_id:newTrackerEventId()};
 if(trackerPending.length>=60){trackerLog('Reporting queue full; use Refresh to check your progress',false);return;}
 trackerPending.push(entry);
 trackerFlush();
}
async function trackerSubmitEvidence(){
 const key=$('trackerEvidenceType').value;
 const detail=$('trackerEvidenceNote').value.trim();
 if(detail.length<5){feedback('trackerFeedback','Please enter a screenshot filename or meaningful evidence note.',true);return;}
 try{await reportTracker(key,'evidence',detail);trackerLog(key+': evidence submitted (not approved)');$('trackerEvidenceNote').value='';feedback('trackerFeedback','Evidence recorded. Instructor must verify it.');await trackerLoad();}
 catch(err){feedback('trackerFeedback',plainError(err),true);trackerLog(plainError(err),false);}
}
function wireTracker(){
 $('trackerConnect').addEventListener('click',trackerLink);
 $('trackerProbe').addEventListener('click',trackerProbe);
 $('trackerSync').addEventListener('click',trackerSync);
 $('trackerUnlink').addEventListener('click',trackerUnlink);
 $('trackerEvidenceSubmit').addEventListener('click',trackerSubmitEvidence);
 trackerPage();
 // Keep instructor last-seen fresh, without flooding the tracker.
 // Browser background suspension is expected; no false "online" claims.
 setInterval(()=>{
   if(!trackerToken||!token||document.visibilityState!=='visible')return;
   trackerRequest('/api/tracker/heartbeat',{event_id:newTrackerEventId()})
     .then(()=>{if(currentPage==='tracker')trackerLog('LIVE · heartbeat acknowledged by instructor tracker');})
     .catch(e=>{if(currentPage==='tracker')trackerLog('Heartbeat delayed: '+plainError(e),false);});
 },75000);
 setInterval(trackerFlush,25000);
 setInterval(()=>{
   if(currentPage==='tracker'&&trackerToken&&token&&document.visibilityState==='visible')
     trackerLoad().catch(()=>{});
 },45000);
}
wire();

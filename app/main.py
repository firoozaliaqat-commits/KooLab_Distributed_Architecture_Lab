"""KooLab passwordless classroom lab. No privileged Huawei API access or remote shell."""
import json, os, secrets, signal, socket, subprocess, sys, threading, time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app import storage, tracker
from app import distributed

START=time.monotonic()
RATES={}
LOCK=threading.Lock()
STRESS={'proc':None,'started':0,'seconds':0,'workers':0}
COUNTER=0
app=FastAPI(title='KooLab Elastic and Security Lab',docs_url=None,redoc_url=None,openapi_url=None)
STATIC=Path(__file__).resolve().parent/'static'
app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')

def node():
    if os.getenv('LAB_NODE_ID'):return os.environ['LAB_NODE_ID'][:64]
    try:return Path('/host_hostname').read_text().strip()[:64]
    except OSError:return socket.gethostname()[:64]

def rate(request, group, max_count, window):
    peer=request.client.host if request.client else 'unknown'
    # Never trust user-supplied X-Forwarded-For headers for security-sensitive limits.
    now=time.monotonic()
    with LOCK:
        if len(RATES)>500:RATES.clear()
        k=(peer,group)
        times=[t for t in RATES.get(k,[]) if t>=now-window]
        if len(times)>=max_count:raise HTTPException(429,'Rate limit exceeded. Try again later.')
        times.append(now)
        RATES[k]=times

def require_auth(request):
    # Deliberately open classroom app. Restrict ECS security group to trainer/student IP ranges.
    return True

@app.middleware('http')
async def headers(request, call_next):
    request.state.request_begin=time.monotonic()
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
        'Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()',
        'Content-Security-Policy':"default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; connect-src 'self'",
        'Cache-Control':'no-store','X-KooLab-Node':node()})
    distributed.observe(request,response)
    return response

@app.get('/')
def index():return FileResponse(STATIC/'index.html')

@app.get('/healthz')
def health():return PlainTextResponse('OK')

@app.get('/readyz')
def ready():
    ok,details=storage.ping()
    return Response(json.dumps({'ready':ok,'details':details}),media_type='application/json',status_code=200 if ok else 503)

@app.get('/api/status')
def status():
    ok,details=storage.ping()
    c=storage.public_config()
    return {'live':True,'node':node(),'container':socket.gethostname()[:12],
        'uptime_seconds':int(time.monotonic()-START),'database_ok':ok,'database_note':details,
        'database_mode':c['mode'], 'shared_rds':bool(c['configured'] and ok),
        'public_host':False,'http_port':80,'version':'6.0','stress_running':stress_status()['running']}


@app.get('/api/identity')
def identity():
    global COUNTER
    with LOCK:
        COUNTER+=1
        n=COUNTER
    return {'node':node(), 'instance_id':socket.gethostname()[:12],
            'counter':n,'request_id':secrets.token_hex(5),'timestamp':int(time.time())}

@app.get('/api/messages')
def messages():
    try:return {'items':storage.messages(), 'shared':storage.cfg() is not None}
    except Exception as ex:raise HTTPException(503,'Database query failed: '+str(ex)[:160])

class Message(BaseModel):
    body:str=Field(min_length=1,max_length=250)

@app.post('/api/messages')
def create_message(item:Message,request:Request):
    require_auth(request)
    rate(request,'messages',15,60)
    body=item.body.strip()
    if not body:raise HTTPException(422,'Message must not be empty')
    try:return {'id':storage.write_message(node(),body),'node':node()}
    except Exception as ex:raise HTTPException(503,'Database write failed: '+str(ex)[:160])

class RDS(BaseModel):
    host:str=Field(min_length=1,max_length=253)
    port:int=Field(default=3306,ge=1,le=65535)
    db_name:str=Field(default='koolab_lab',max_length=48)
    user:str=Field(default='root',max_length=64)
    password:str=Field(min_length=1,max_length=256)
    tls:str='required'
    ca:str=Field(default='',max_length=16000)
    initialize:bool=False

@app.get('/api/rds/config')
def rds_config(request:Request):
    require_auth(request)
    return storage.public_config()

@app.post('/api/rds/test')
def rds_test(payload:RDS,request:Request):
    require_auth(request)
    rate(request,'rds-test',10,120)
    try:return storage.test_config(payload.model_dump(),init=False)
    except Exception as ex:raise HTTPException(422,'RDS connection failed: '+str(ex)[:240])

@app.post('/api/rds/save')
def rds_save(payload:RDS,request:Request):
    require_auth(request)
    rate(request,'rds-save',5,120)
    try:
        candidate=payload.model_dump()
        result=storage.test_config(candidate,init=payload.initialize)
        storage.save_config(candidate)
        return {'saved':True, **result, 'note':'RDS configuration is saved on this ECS disk. Create the IMS image only after validating this setup.'}
    except Exception as ex:raise HTTPException(422,'Unable to save RDS settings: '+str(ex)[:240])

@app.delete('/api/rds/config')
def rds_delete(request:Request):
    require_auth(request)
    storage.remove_config()
    return {'cleared':True,'mode':'sqlite'}

@app.get('/api/rds/verify')
def rds_verify(request:Request):
    require_auth(request)
    c=storage.public_config()
    ok,details=storage.ping()
    tls=storage.tls_info()
    try:count=len(storage.messages())
    except Exception:count=None
    return {'connected':ok,'mode':c['mode'],'details':details,'tls':tls,
            'message_sample_count':count,'shared':bool(c['configured'] and ok)}

def stress_status():
    p=STRESS['proc']
    running=bool(p and p.poll() is None)
    elapsed=int(time.monotonic()-STRESS['started']) if STRESS['started'] else 0
    return {'running':running,'elapsed':elapsed,'duration':STRESS['seconds'],
            'remaining':max(0,STRESS['seconds']-elapsed) if running else 0,
            'workers':STRESS['workers'],'node':node()}

class Stress(BaseModel):
    seconds:int=Field(ge=15,le=900,default=900)
    workers:int=Field(ge=1,le=2,default=2)

@app.get('/api/stress/status')
def stress_get(request:Request, target_node:Optional[str]=None):
    require_auth(request)
    if target_node and target_node!=node():
        raise HTTPException(409,'Request reached '+node()+'; looking for '+target_node)
    return stress_status()

@app.post('/api/stress/start')
def stress_start(payload:Stress,request:Request):
    require_auth(request)
    rate(request,'stress',3,3600)
    with LOCK:
        if stress_status()['running']:raise HTTPException(409,'Stress test already running on this ECS')
        p=subprocess.Popen([sys.executable,'-m','app.stress_worker',str(payload.seconds),str(payload.workers)],
                           cwd=str(Path(__file__).resolve().parent.parent),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           start_new_session=True)
        STRESS.update(proc=p,started=time.monotonic(),seconds=payload.seconds,workers=payload.workers)
    return {'started':True,**stress_status(),
            'note':'CPU load is inside this Docker container; monitor actual ECS CPU and Huawei AS scaling in Cloud Eye.'}

@app.post('/api/stress/stop')
def stress_stop(request:Request,target_node:Optional[str]=None):
    require_auth(request)
    if target_node and target_node!=node():
        raise HTTPException(409,'This request reached a different backend ECS. Retry the target node.')

    with LOCK:
        p=STRESS['proc']
        if p and p.poll() is None:
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    return {'stop_requested':True}

@app.get('/api/probe/download')
def download(request:Request,kb:int=64):
    require_auth(request)
    if not 1<=kb<=512:raise HTTPException(422,'Payload must be between 1 and 512 KiB')
    rate(request,'download',60,60)
    return Response(b'K'*(kb*1024),media_type='application/octet-stream',
                    headers={'X-Payload-KiB':str(kb)})

@app.post('/api/probe/upload')
async def upload(request:Request):
    require_auth(request)
    rate(request,'upload',60,60)
    size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>512*1024:raise HTTPException(413,'Maximum 512 KiB per request')
    return {'received_bytes':size,'node':node()}

@app.get('/api/security/checks')
def security_checks(request:Request):
    require_auth(request)
    def proc_status(tag):
        try:
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith(tag+':'):return line.split(':',1)[1].strip()
        except OSError:pass
        return 'unknown'
    uid=os.geteuid()
    nonew=proc_status('NoNewPrivs')
    cape=proc_status('CapEff')
    seccomp=proc_status('Seccomp')
    cfg=storage.public_config()
    tls=storage.tls_info()
    return {'node':node(),'checks':[
        {'id':'uid','name':'Non-root process','result':'pass' if uid!=0 else 'fail','evidence':f'Effective UID: {uid}'},
        {'id':'nnp','name':'No new privileges','result':'pass' if nonew=='1' else 'warn','evidence':'NoNewPrivs: '+nonew},
        {'id':'caps','name':'Linux capabilities dropped','result':'pass' if cape=='0000000000000000' else 'warn','evidence':'CapEff: '+cape},
        {'id':'seccomp','name':'Seccomp filtering','result':'pass' if seccomp=='2' else 'warn','evidence':'Seccomp: '+seccomp},
        {'id':'auth','name':'Passwordless classroom mode','result':'warn','evidence':'Application actions are intentionally unauthenticated. Restrict ECS security group inbound TCP 80 to training IPs; use temporary RDS credentials only.'},
        {'id':'headers','name':'Browser security headers','result':'pass','evidence':'CSP, X-Frame-Options, nosniff, referrer and permissions policies configured'},
        {'id':'https','name':'Public HTTPS encryption','result':'warn','evidence':'Port 80 is HTTP. Use HTTPS at a supported load balancer for credentials outside isolated training'},
        {'id':'database','name':'RDS database connectivity','result':'pass' if cfg['configured'] and storage.ping()[0] else 'warn','evidence':'Real RDS required; local SQLite is not shared across ECS nodes'},
        {'id':'dbtls','name':'RDS transport encryption','result':'pass' if tls['encrypted'] else 'warn','evidence':tls['detail']},
        {'id':'password','name':'RDS credentials storage','result':'warn' if cfg['configured'] else 'info','evidence':'Saved to /data/rds.json restricted to UID 10001; use dedicated least-privilege account; disk encryption and image access controlled by cloud'},
        {'id':'sg','name':'Huawei VPC security groups','result':'manual','evidence':'Inspect ECS inbound 80/SSH and RDS inbound 3306 in Huawei console; container cannot read SG policies'},
        {'id':'elb','name':'ELB backend health & AS events','result':'manual','evidence':'Collect actual backend/Cloud Eye/AS evidence from Huawei console'}]}

@app.get('/api/self-test')
def self_test(request:Request):
    require_auth(request)
    ok,note=storage.ping()
    return {'tests':[
      {'name':'HTTP liveness','passed':True,'detail':'/healthz responds'},
      {'name':'Instance identification','passed':bool(node()),'detail':node()},
      {'name':'Database query','passed':ok,'detail':note},
      {'name':'RDS configured for shared storage','passed':bool(storage.cfg()) and ok,'detail':'RDS required for shared application data'},
      {'name':'No application password','passed':True,'detail':'Classroom access is intentionally passwordless; restrict ingress in Huawei Security Groups'},
      {'name':'ELB configured','passed':None,'detail':'Requires ELB console evidence and multiple distinct nodes seen through ELB EIP'},
      {'name':'Auto Scaling triggered','passed':None,'detail':'Requires Huawei AS scaling action and Cloud Eye evidence'},
      {'name':'Bandwidth scaling applied','passed':None,'detail':'Requires EIP bandwidth history in Huawei console'},
      {'name':'Public SG and RDS rules','passed':None,'detail':'Requires Huawei security group configuration review'}]}


# Student integration with the separate HTTPS KICS progress tracker.
# Does not change RDS, ELB, scaling, bandwidth or security practical endpoints.
class TrackerAuth(BaseModel):
    student_token: str = Field(min_length=30, max_length=200)

class TrackerEvent(TrackerAuth):
    milestone_key: str = Field(pattern=r'^[a-z][a-z0-9_]{2,39}$')
    event: str = Field(pattern=r'^(passed|failed|evidence)$')
    detail: str = Field(default='', max_length=400)
    event_id: str = Field(min_length=16, max_length=100)

def secure_student_origin(req: Request):
    """Classroom mode: permit same-origin HTTP or HTTPS to report through an HTTPS relay.

    IMPORTANT: The hop from a remote browser to an ECS EIP is plaintext in HTTP mode.
    Do not use real accounts or reuse personal tokens outside this disposable lab.
    Keep browser Origin validation; the classroom web app has no login.
    """
    from urllib.parse import urlsplit
    origin=req.headers.get('origin','')
    if not origin:
        raise HTTPException(403,'Browser Origin required for student event reporting')
    try:
        u=urlsplit(origin)
        if (u.scheme not in ('http','https') or not u.hostname or u.username
                or u.password or u.path not in ('','/') or u.query or u.fragment):
            raise ValueError('Malformed origin')
        # Normal browser requests to this lab are same-origin; do not permit
        # third-party pages to relay token-bearing requests to this server.
        origin_host=u.netloc.lower()
        request_host=req.headers.get('host','').lower()
        if origin_host != request_host:
            raise ValueError('Cross-origin request')
    except ValueError:
        raise HTTPException(403,'Student reporting must originate from this KooLab application')
    rate(req,'tracker-relay',35,60)

@app.get('/api/tracker/settings')
def tracker_settings(req: Request):
    require_auth(req)
    return {'url':tracker.TRACKER_URL,'lab_code':tracker.LAB_CODE,'milestones':tracker.MILESTONES,
            'transport_policy':'Classroom HTTP or HTTPS enabled; outbound connection to instructor remains HTTPS.'}

@app.get('/api/tracker/diagnostics')
def tracker_diagnostics(req:Request):
    require_auth(req)
    rate(req,'tracker-health',6,60)
    return tracker.probe_health()

@app.post('/api/tracker/me')
def tracker_me(payload:TrackerAuth, req: Request):
    require_auth(req)
    secure_student_origin(req)
    result=tracker.request_tracker('GET','/api/v1/me',payload.student_token)
    match=next((lab for lab in result.get('labs',[]) if lab.get('code','').upper()==tracker.LAB_CODE),None)
    if not match:
        raise HTTPException(404,'Instructor must create lab '+tracker.LAB_CODE+' in the central tracker')
    return {'student':result.get('student',{}),'lab':match,'configured_milestones':tracker.MILESTONES}

@app.post('/api/tracker/event')
def tracker_event(payload:TrackerEvent, req: Request):
    require_auth(req)
    secure_student_origin(req)
    expected=tracker.MILESTONES.get(payload.milestone_key)
    if expected is None: raise HTTPException(422,'Unsupported milestone')
    if payload.event not in (expected,'failed'):
        raise HTTPException(422,'This milestone is evidence only; Huawei console review is required')
    if payload.event=='passed':
        if payload.milestone_key=='rds_connected':
            if not storage.cfg() or not storage.ping()[0]:
                raise HTTPException(409,'No live RDS connection: cannot report RDS milestone as passed')
        elif payload.milestone_key=='ecs_app_ready':
            ok, _ = storage.ping()
            if not ok:raise HTTPException(409,'Application storage check failed')
    # Instructor tracker treats all lab-agent reports as UNVERIFIED until approval.
    detail='KooLab v6 | '+payload.detail.strip()[:380]
    event={'lab_code':tracker.LAB_CODE,'event':payload.event,
           'milestone_key':payload.milestone_key,'detail':detail,
           'source':'lab-agent','event_id':payload.event_id}
    return tracker.request_tracker('POST','/api/v1/events',payload.student_token,event)

class TrackerHeartbeat(TrackerAuth):
    event_id: str = Field(min_length=16, max_length=100)

@app.post('/api/tracker/heartbeat')
def tracker_heartbeat(payload:TrackerHeartbeat,req:Request):
    require_auth(req)
    secure_student_origin(req)
    rate(req,'tracker-heartbeat',3,150)
    return tracker.request_tracker('POST','/api/v1/events',payload.student_token,
        {'lab_code':tracker.LAB_CODE,'event':'heartbeat',
         'detail':'KooLab v6 passwordless classroom application active',
         'source':'lab-agent','event_id':payload.event_id})

class TrackerStart(TrackerAuth):
    event_id: str = Field(min_length=16, max_length=100)

@app.post('/api/tracker/start')
def tracker_start(payload:TrackerStart, req:Request):
    require_auth(req)
    secure_student_origin(req)
    return tracker.request_tracker('POST','/api/v1/events',payload.student_token,
        {'lab_code':tracker.LAB_CODE,'event':'started','detail':'KooLab v6 classroom application linked and started',
         'source':'lab-agent','event_id':payload.event_id})


# Distributed simulation: Redis queue + cache + Prometheus metrics.
@app.get('/metrics')
def metrics_endpoint():
    return distributed.metrics_response(node())

@app.get('/api/architecture')
def architecture(request:Request):
    return distributed.architecture(node())

class QueueJob(BaseModel):
    seconds: int = Field(default=2,ge=1,le=5)
    label: str = Field(default='demo',min_length=1,max_length=50)

@app.post('/api/architecture/jobs')
def submit_job(payload:QueueJob,request:Request):
    rate(request,'jobs',25,60)
    return distributed.submit_job(payload.seconds,payload.label,node())

@app.get('/api/architecture/jobs')
def list_jobs(request:Request):
    return distributed.job_status()

@app.get('/api/architecture/cache')
def cache_demo(request:Request,key:str='lesson-1'):
    if not 1<=len(key)<=48 or not all(ch.isalnum() or ch in '-_' for ch in key):
        raise HTTPException(422,'Use a 1–48 character alphanumeric cache key')
    rate(request,'cache-demo',70,60)
    return distributed.cache_demo(key,node())

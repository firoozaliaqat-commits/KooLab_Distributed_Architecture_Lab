"""Safe demo counters, Redis queue/cache, live topology. No Docker socket or cloud credentials."""
import os, time, secrets, resource
import redis
from fastapi import HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

URI=os.getenv('REDIS_URL','redis://redis:6379/0')
_http=Counter('koolab_http_requests_total','Requests to application replicas',['node','route','method','status'])
_latency=Histogram('koolab_http_request_duration_seconds','Request latency',['node','route'])
_cache=Counter('koolab_cache_requests_total','Cache outcomes',['result'])
_pending=Gauge('koolab_queue_pending','Jobs awaiting workers')
_completed=Gauge('koolab_queue_completed','Jobs completed by workers')
_failed=Gauge('koolab_queue_failed','Failed async jobs')
_mem=Gauge('koolab_process_resident_memory_bytes','Memory of each Python API process')

def conn():
    return redis.Redis.from_url(URI,decode_responses=True,socket_connect_timeout=1,socket_timeout=2)

def observe(req, resp):
    if req.url.path=='/metrics':return
    from app.main import node
    path=req.scope.get('route').path if req.scope.get('route') else req.url.path
    # Avoid unbounded label cardinality from arbitrary URLs.
    if not path.startswith(('/api/','/healthz','/readyz','/static/')) and path!='/':path='other'
    if path.startswith('/static/'):path='/static/*'
    _http.labels(node(),path,req.method,str(resp.status_code)).inc()
    begin=getattr(req.state,'request_begin',None)
    if begin is not None:_latency.labels(node(),path).observe(max(0,time.monotonic()-begin))

def metrics_response(node):
    try:
        r=conn()
        _pending.set(r.llen('koolab:queue'))
        _completed.set(int(r.get('koolab:completed') or 0))
        _failed.set(int(r.get('koolab:failed') or 0))
    except (redis.RedisError,ValueError):pass
    # Linux maxrss is KiB; classroom containers are Linux.
    _mem.set(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

def architecture(node):
    try:
        r=conn()
        r.ping()
        workers={n: bool(r.exists('koolab:worker:'+n)) for n in ('worker1','worker2')}
        return {'node':node,'mode':'single-ecs-docker-simulation','replicas':['app1','app2','app3'],
                'redis_ok':True,'workers':workers,'queued':r.llen('koolab:queue'),
                'processing':r.llen('koolab:processing'),'completed':int(r.get('koolab:completed') or 0),
                'failed':int(r.get('koolab:failed') or 0),
                'database':'MySQL RDS' if __import__('app.storage',fromlist=['cfg']).cfg() else 'SQLite (same ECS bind-mount only)'}
    except (redis.RedisError,ValueError) as exc:
        return {'node':node,'mode':'single-ecs-docker-simulation','replicas':['app1','app2','app3'],
                'redis_ok':False,'error':type(exc).__name__,'workers':{},'queued':None,'processing':None,'completed':None,'failed':None}

def submit_job(seconds,label,node):
    try:
        r=conn()
        # Bound outstanding jobs to protect classroom resources.
        if r.llen('koolab:queue')>=75:raise HTTPException(429,'Job queue full (75); allow workers to catch up')
        job_id=secrets.token_hex(8)
        key='koolab:job:'+job_id
        pipe=r.pipeline()
        pipe.hset(key,mapping={'id':job_id,'label':label,'seconds':seconds,'node':node,'state':'queued','created':int(time.time())})
        pipe.expire(key,3600)
        pipe.lpush('koolab:recent',job_id)
        pipe.ltrim('koolab:recent',0,19)
        pipe.lpush('koolab:queue',job_id)
        pipe.execute()
        return {'id':job_id,'state':'queued','submitted_by':node}
    except redis.RedisError as exc:raise HTTPException(503,'Redis queue is unavailable') from exc

def job_status():
    try:
        r=conn()
        ids=r.lrange('koolab:recent',0,19)
        jobs=[r.hgetall('koolab:job:'+job_id) for job_id in ids]
        return {'jobs':[job for job in jobs if job], 'queued':r.llen('koolab:queue'), 'processing':r.llen('koolab:processing')}
    except redis.RedisError as exc:raise HTTPException(503,'Redis queue is unavailable') from exc

def cache_demo(key,node):
    try:
        r=conn();cache_key='koolab:cache:'+key
        start=time.monotonic()
        value=r.get(cache_key)
        hit=value is not None
        if not hit:
            # The service simulates an expensive calculation; there is no external API.
            time.sleep(.18)
            value='computed-example-'+key
            r.set(cache_key,value,ex=60)
        _cache.labels('hit' if hit else 'miss').inc()
        return {'key':key,'result':'HIT' if hit else 'MISS','data':value,'served_by':node,
                'latency_ms':round((time.monotonic()-start)*1000,1),'ttl_seconds':r.ttl(cache_key)}
    except redis.RedisError as exc:raise HTTPException(503,'Redis cache unavailable') from exc

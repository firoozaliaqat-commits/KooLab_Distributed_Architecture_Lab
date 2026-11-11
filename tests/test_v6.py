import json
from fastapi.testclient import TestClient
from app import main, distributed, tracker
import pytest

client=TestClient(main.app)

def setup_function():
    main.RATES.clear()

def test_passwordless_dashboard_and_status():
    response=client.get('/')
    assert response.status_code==200
    assert 'Distributed Architecture Simulator' in response.text
    assert 'loginOverlay' not in response.text
    assert client.get('/api/status').status_code==200
    assert client.get('/healthz').text=='OK'
    assert client.get('/api/identity').status_code==200
    assert client.get('/api/auth/login').status_code==404
    assert client.get('/api/auth/me').status_code==404

def test_original_lab_functions_work_without_password():
    assert client.get('/api/rds/config').status_code==200
    assert client.get('/api/rds/verify').json()['mode']=='sqlite'
    payload={'body':'cross replica test '+"'; DROP TABLE lab_messages; --"}
    assert client.post('/api/messages',json=payload).status_code==200
    assert any(x['body']==payload['body'] for x in client.get('/api/messages').json()['items'])
    assert client.get('/api/security/checks').status_code==200
    assert client.get('/api/self-test').status_code==200
    assert client.get('/api/probe/download?kb=1').status_code==200
    assert client.post('/api/probe/upload',content=b'Hello').json()['received_bytes']==5
    assert client.post('/api/messages',json={'body':'x'*251}).status_code==422
    assert client.get('/api/probe/download?kb=513').status_code==422
    assert client.post('/api/rds/test',json={'host':'8.8.8.8','password':'example'}).status_code==422

def test_metrics_and_architecture_no_redis():
    m=client.get('/metrics')
    assert m.status_code==200
    assert 'koolab_http_requests_total' in m.text
    d=client.get('/api/architecture').json()
    assert len(d['replicas'])==3
    assert d['mode']=='single-ecs-docker-simulation'
    assert d['redis_ok'] is False
    assert client.post('/api/architecture/jobs',json={'seconds':9,'label':'too long'}).status_code==422
    assert client.get('/api/architecture/cache?key=invalid%20key').status_code==422

class FakePipeline:
    def __init__(self,r): self.r=r;self.steps=[]
    def __getattr__(self,name):
        def op(*args,**kwargs):
            self.steps.append((name,args,kwargs));return self
        return op
    def execute(self):
        for name,args,kwargs in self.steps:getattr(self.r,name)(*args,**kwargs)

class FakeRedis:
    def __init__(self):self.lists={};self.hashes={};self.values={};self.ttls={}
    def ping(self):return True
    def exists(self,key):return int(key in self.values)
    def llen(self,key):return len(self.lists.get(key,[]))
    def get(self,key):return self.values.get(key)
    def set(self,key,val,ex=None):self.values[key]=str(val);self.ttls[key]=ex
    def incr(self,key):self.values[key]=str(int(self.values.get(key,0))+1)
    def ttl(self,key):return self.ttls.get(key,-1)
    def hgetall(self,key):return self.hashes.get(key,{}).copy()
    def hset(self,key,mapping):self.hashes.setdefault(key,{}).update({k:str(v) for k,v in mapping.items()})
    def expire(self,key,n):self.ttls[key]=n
    def lpush(self,key,v):self.lists.setdefault(key,[]).insert(0,v)
    def ltrim(self,key,a,b):self.lists[key]=self.lists[key][a:b+1]
    def lrange(self,key,a,b):return self.lists.get(key,[])[a:b+1]
    def pipeline(self):return FakePipeline(self)

def test_queue_cache_and_metrics_with_fake_redis(monkeypatch):
    fake=FakeRedis()
    monkeypatch.setattr(distributed,'conn',lambda:fake)
    d=client.get('/api/architecture').json()
    assert d['redis_ok'] is True and d['queued']==0
    j=client.post('/api/architecture/jobs',json={'seconds':1,'label':'demo'})
    assert j.status_code==200 and j.json()['state']=='queued'
    assert client.get('/api/architecture/jobs').json()['queued']==1
    first=client.get('/api/architecture/cache?key=lesson')
    second=client.get('/api/architecture/cache?key=lesson')
    assert first.json()['result']=='MISS' and second.json()['result']=='HIT'
    assert 'koolab_queue_pending' in client.get('/metrics').text
    assert client.get('/api/architecture').json()['queued']==1

def test_tracker_requires_student_token_and_same_origin(monkeypatch):
    tok='classroom-unique-token-'+('x'*40)
    def fake(method,endpoint,student_token,data=None):
        if endpoint.endswith('/me'):
            return {'student':{'name':'Student 1'},'labs':[{'code':tracker.LAB_CODE}]}
        return {'ok':True}
    monkeypatch.setattr(tracker,'request_tracker',fake)
    assert client.post('/api/tracker/me',json={'student_token':tok}).status_code==403
    assert client.post('/api/tracker/me',headers={'Origin':'http://evil.example'},json={'student_token':tok}).status_code==403
    r=client.post('/api/tracker/me',headers={'Origin':'http://testserver'},json={'student_token':tok})
    assert r.status_code==200 and tok not in r.text
    assert client.post('/api/tracker/event',headers={'Origin':'http://testserver'},json={'student_token':tok,'milestone_key':'scaling_test','event':'passed','event_id':'a'*32}).status_code==422

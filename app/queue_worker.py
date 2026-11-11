"""Redis-backed at-least-once queue worker for isolated classroom exercises."""
import os, signal, time, json
import redis

WORKER=os.getenv('WORKER_ID','worker')
REDIS=os.getenv('REDIS_URL','redis://redis:6379/0')
active=True

def shutdown(_sig, _frame):
    global active
    active=False

signal.signal(signal.SIGTERM,shutdown)
signal.signal(signal.SIGINT,shutdown)

def main():
    r=redis.Redis.from_url(REDIS,decode_responses=True,socket_connect_timeout=2,socket_timeout=5)
    while active:
        try:
            r.set('koolab:worker:'+WORKER,int(time.time()),ex=15)
            job_id=r.brpoplpush('koolab:queue','koolab:processing',timeout=2)
            if not job_id:continue
            key='koolab:job:'+job_id
            try:
                entry=r.hgetall(key)
                if not entry:
                    r.lrem('koolab:processing',1,job_id)
                    continue
                duration=max(1,min(5,int(entry.get('seconds','2'))))
                r.hset(key,mapping={'state':'running','worker':WORKER,'started':int(time.time())})
                time.sleep(duration)
                r.hset(key,mapping={'state':'complete','completed':int(time.time())})
                r.incr('koolab:completed')
            except Exception as exc:
                r.hset(key,mapping={'state':'failed','error':type(exc).__name__})
                r.incr('koolab:failed')
            finally:
                r.expire(key,3600)
                r.lrem('koolab:processing',1,job_id)
        except (redis.RedisError, OSError) as exc:
            print(f'{WORKER}: redis unavailable: {type(exc).__name__}',flush=True)
            time.sleep(2)

if __name__=='__main__':main()

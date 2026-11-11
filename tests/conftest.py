"""Permit offline API tests without pip Redis; production Docker installs real redis client."""
import sys, types, importlib.util, tempfile, os
os.environ['LAB_DATA']=tempfile.mkdtemp(prefix='koolab-v6-test-')
if importlib.util.find_spec('redis') is None:
    fake=types.ModuleType('redis')
    fake.RedisError=type('RedisError',(Exception,),{})
    fake.Redis=type('Redis',(),{'from_url':staticmethod(lambda *a,**kw: (_ for _ in ()).throw(fake.RedisError('offline mocked Redis')))})
    sys.modules['redis']=fake

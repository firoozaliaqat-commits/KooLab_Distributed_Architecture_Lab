"""Student-scoped outbound reporter to the existing KICS v1 instructor tracker.

No credentials are persisted on ECS. Tracker tokens remain in browser sessionStorage;
student-to-ECS HTTP transport is plaintext in this disposable classroom release.
The relay sends requests only to the configured HTTPS instructor tracker.
This relay always communicates with its fixed, configured HTTPS origin.
All results remain pending independent instructor verification.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import ssl
from fastapi import HTTPException

TRACKER_URL = os.getenv('TRACKER_URL', 'https://huawei.stackcrm.online').rstrip('/')
LAB_CODE = os.getenv('TRACKER_LAB_CODE', 'KOOLAB_ELASTIC_SEC')

MILESTONES = {
    'ecs_app_ready': 'passed',
    'rds_connected': 'passed',
    'rds_write_read': 'evidence',
    'elb_distribution': 'evidence',
    'scaling_test': 'evidence',
    'bandwidth_test': 'evidence',
    'security_checks': 'evidence',
    'cloud_security': 'evidence',
    'lab_report': 'evidence',
}

class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPException(502, 'Tracker attempted an unexpected redirect')

_OPENER = urllib.request.build_opener(NoRedirects, urllib.request.HTTPSHandler(context=ssl.create_default_context()))

def _base():
    u = urllib.parse.urlsplit(TRACKER_URL)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
        raise HTTPException(503, 'Tracker must be configured with an HTTPS origin without a path')
    return TRACKER_URL

def probe_health():
    """Check outbound Cloudflare/tracker health without sending student credentials."""
    req=urllib.request.Request(_base()+'/healthz',headers={'Accept':'application/json'},method='GET')
    try:
        with _OPENER.open(req,timeout=6) as resp:
            payload=resp.read(2000)
            try: body=json.loads(payload)
            except ValueError: body={}
            return {'reachable':resp.status==200 and body.get('status')=='ok',
                    'upstream_status':resp.status,'tracker':TRACKER_URL,'detail':'Health endpoint returned normally; token linking additionally requires a valid student token and configured lab.'}
    except urllib.error.HTTPError as e:
        return {'reachable':False,'upstream_status':e.code,'tracker':TRACKER_URL,'detail':'Cloudflare or instructor service returned an HTTP error.'}
    except (urllib.error.URLError,TimeoutError,OSError,ValueError):
        return {'reachable':False,'upstream_status':None,'tracker':TRACKER_URL,'detail':'Outbound DNS/TLS/network path to instructor service failed.'}

def request_tracker(method, endpoint, student_token, data=None):
    if not isinstance(student_token, str) or not 30 <= len(student_token) <= 200 or '\n' in student_token or '\r' in student_token:
        raise HTTPException(422,'Invalid student tracker token')
    target = _base() + endpoint
    body = None if data is None else json.dumps(data, separators=(',', ':')).encode('utf-8')
    req = urllib.request.Request(target, data=body, method=method,
        headers={'Authorization': 'Bearer '+student_token, 'Accept': 'application/json',
                 **({'Content-Type':'application/json'} if body is not None else {})})
    try:
        with _OPENER.open(req, timeout=6) as resp:
            if resp.status not in (200,201):raise HTTPException(502, 'Tracker responded unexpectedly')
            return json.loads(resp.read(50000))
    except urllib.error.HTTPError as e:
        # Never forward raw upstream error responses, which may contain credentials.
        if e.code == 401: raise HTTPException(401,'Tracker token invalid or revoked')
        if e.code == 404: raise HTTPException(404,'Tracker lab or milestone is missing. Ask your instructor to configure it')
        if e.code == 429: raise HTTPException(429,'Tracker is rate-limiting requests')
        if e.code == 403: raise HTTPException(403,'Tracker API refused access (check Cloudflare Access/WAF rules for /api/v1/me and /api/v1/events)')
        if e.code in (500,502,503,504): raise HTTPException(502,f'Central tracker API returned HTTP {e.code}. Its /healthz may still be healthy; check API and Cloudflare Tunnel logs.')
        raise HTTPException(502,f'Instructor tracker API returned HTTP {e.code} (this is upstream; check central tracker API/logs, not the student lab HTTP/HTTPS setting)')
    except (TimeoutError, urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        raise HTTPException(503, 'Cannot reach the HTTPS instructor tracker; use manual portal and retry later')

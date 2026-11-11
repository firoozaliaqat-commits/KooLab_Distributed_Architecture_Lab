"""Locally persisted configuration; real MySQL is used only after user configures RDS."""
import json, os, re, sqlite3
from pathlib import Path
from contextlib import contextmanager

DATA = Path(os.getenv('LAB_DATA','/data'))
CONFIG = DATA/'rds.json'
LOCAL = DATA/'lab.sqlite3'
SCHEMA = '''CREATE TABLE IF NOT EXISTS lab_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, node TEXT NOT NULL, body TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
)'''
MYSQL_SCHEMA = '''CREATE TABLE IF NOT EXISTS lab_messages (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, node VARCHAR(96) NOT NULL, body VARCHAR(250) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'''

def cfg():
    try:
        data=json.loads(CONFIG.read_text())
        return data if data.get('host') else None
    except (OSError, ValueError):
        return None

def public_config():
    c=cfg()
    if not c:
        return {'configured':False, 'mode':'sqlite', 'host':'', 'db_name':'koolab_lab', 'user':'', 'tls':'off'}
    return {'configured':True,'mode':'mysql','host':c['host'],'port':c['port'],
            'db_name':c['db_name'],'user':c['user'],'tls':c['tls']}

def validate(c):
    import ipaddress
    import socket
    private_nets = [ipaddress.ip_network('10.0.0.0/8'),ipaddress.ip_network('172.16.0.0/12'),ipaddress.ip_network('192.168.0.0/16')]
    host=str(c.get('host','')).strip()
    if not host or len(host)>253 or not re.fullmatch(r'[a-zA-Z0-9_.:-]+',host):
        raise ValueError('Provide a valid private RDS IP or hostname')
    try:
        ip = ipaddress.ip_address(host)
        if ip.version != 4 or not any(ip in net for net in private_nets): raise ValueError('RDS must use a private RFC1918 IPv4 address')
    except ValueError as ex:
        if re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}',host):
            raise ValueError('Invalid or public RDS IP') from ex
        if '.' not in host or host in {'localhost', '127.0.0.1'}:
            raise ValueError('Use the RDS private IP or internal DNS name')
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)}
        except socket.gaierror as ex:
            raise ValueError('Unable to resolve RDS hostname') from ex
        if not addresses or not all(ip.version==4 and any(ip in net for net in private_nets) for ip in addresses):
            raise ValueError('RDS hostname must resolve only to private RFC1918 addresses')
    port=int(c.get('port',3306))
    if port<1 or port>65535: raise ValueError('Invalid RDS port')
    name=str(c.get('db_name','koolab_lab')).strip()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}',name):
        raise ValueError('DB name: letters, digits and underscore, beginning with a letter')
    user=str(c.get('user','root')).strip()
    if not user or len(user)>64: raise ValueError('Invalid DB username')
    pw=str(c.get('password',''))
    if not pw: raise ValueError('Database password is required')
    tls=str(c.get('tls','required'))
    if tls not in {'off','required','verify'}: raise ValueError('TLS must be off, required or verify')
    ca=str(c.get('ca',''))
    if tls=='verify' and ('BEGIN CERTIFICATE' not in ca or len(ca)>16000):
        raise ValueError('Paste the Huawei RDS CA PEM certificate for TLS verification')
    return {'host':host,'port':port,'db_name':name,'user':user,'password':pw,'tls':tls,'ca':ca}

def mysql_connect(c, with_db=True):
    import pymysql
    kwargs={'host':c['host'],'port':c['port'],'user':c['user'], 'password':c['password'],
            'charset':'utf8mb4','connect_timeout':4,'read_timeout':4,'write_timeout':4,
            'autocommit':False}
    if with_db: kwargs['database']=c['db_name']
    if c['tls']=='required': kwargs['ssl']={'check_hostname':False}
    if c['tls']=='verify':
        import ssl
        context=ssl.create_default_context(cadata=c['ca'])
        context.check_hostname=True
        kwargs['ssl']=context
    return pymysql.connect(**kwargs)

def test_config(c, init=False):
    c=validate(c)
    import pymysql
    con=mysql_connect(c,with_db=False)
    try:
        with con.cursor() as cur:
            cur.execute('SELECT 1')
            cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row=cur.fetchone()
            cipher=row[1] if row else ''
            if c['tls'] != 'off' and not cipher:
                raise RuntimeError('The database did not negotiate TLS')
            if init:
                cur.execute(f'CREATE DATABASE IF NOT EXISTS `{c["db_name"]}` CHARACTER SET utf8mb4')
                con.commit()
        con.close()
        try:
            con=mysql_connect(c,with_db=True)
        except pymysql.err.OperationalError as ex:
            if not init and ex.args and ex.args[0] == 1049:
                return {'connected':True,'tls_encrypted':bool(cipher),'tls_cipher':cipher or 'none',
                        'schema_initialized':False, 'message':'Server login successful, but database is not created yet. Use Save & connect with Initialize checked.'}
            raise
        with con.cursor() as cur:
            if init: cur.execute(MYSQL_SCHEMA)
            else: cur.execute('SELECT 1')
        con.commit()
        return {'connected':True,'tls_encrypted':bool(cipher), 'tls_cipher':cipher or 'none',
                'schema_initialized':bool(init), 'message':'Real MySQL connection and authentication succeeded'}
    finally:
        con.close()

def save_config(c):
    c=validate(c)
    DATA.mkdir(parents=True,exist_ok=True)
    temp=CONFIG.with_suffix('.tmp')
    temp.write_text(json.dumps(c,indent=2))
    os.chmod(temp,0o600)
    temp.replace(CONFIG)

def remove_config():
    CONFIG.unlink(missing_ok=True)

@contextmanager
def connect():
    c=cfg()
    if c: conn=mysql_connect(c)
    else:
        DATA.mkdir(parents=True,exist_ok=True)
        conn=sqlite3.connect(str(LOCAL),timeout=20)
        conn.execute('PRAGMA busy_timeout=20000')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute(SCHEMA)
        conn.commit()
    try:
        yield conn, bool(c)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()

def ping():
    try:
        with connect() as (con,_):
            cur=con.cursor()
            cur.execute('SELECT 1')
        return True,'Connected'
    except Exception as ex:
        return False, f'{type(ex).__name__}: {str(ex)[:160]}'

def tls_info():
    c=cfg()
    if not c:return {'encrypted':False,'detail':'SQLite local only'}
    try:
        with connect() as (con,_):
            cur=con.cursor()
            cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row=cur.fetchone()
        return {'encrypted':bool(row and row[1]),'detail':row[1] if row and row[1] else 'Unencrypted'}
    except Exception as ex:return {'encrypted':None, 'detail':f'{type(ex).__name__}: {str(ex)[:90]}'}

def messages():
    with connect() as (con,_):
        cur=con.cursor()
        cur.execute('SELECT id,node,body,created_at FROM lab_messages ORDER BY id DESC LIMIT 30')
        return [{'id':r[0], 'node':r[1], 'body':r[2], 'created_at':str(r[3])} for r in cur.fetchall()]

def write_message(node,body):
    with connect() as (con,mysql):
        cur=con.cursor()
        cur.execute('INSERT INTO lab_messages (node,body) VALUES (%s,%s)' if mysql else 'INSERT INTO lab_messages (node,body) VALUES (?,?)',(node,body))
        return cur.lastrowid

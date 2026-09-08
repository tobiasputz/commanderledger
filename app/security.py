"""Single-owner hosted authentication. Credentials never enter game backups."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from fastapi import Request
from app.db import DB_PATH

COOKIE='ledger_session'
LOGIN_COOKIE='ledger_login_csrf'

@dataclass(frozen=True)
class SecurityConfig:
    hosted: bool
    password_hash: str
    origin: str
    auth_path: Path
    @property
    def enabled(self) -> bool:
        return self.hosted or bool(self.password_hash)
    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.password_hash.encode()).hexdigest()

def config() -> SecurityConfig:
    hosted=os.getenv('COMMANDER_MODE','local')=='hosted' or bool(os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('RENDER'))
    return SecurityConfig(hosted,os.getenv('COMMANDER_PASSWORD_HASH',''),os.getenv('COMMANDER_PUBLIC_URL','').rstrip('/'),DB_PATH.with_name('auth.sqlite3'))

def hash_password(password: str) -> str:
    if not 12<=len(password)<=1024: raise ValueError('Use a password or passphrase of 12–1024 characters.')
    salt=secrets.token_bytes(16)
    derived=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return 'scrypt$'+salt.hex()+'$'+derived.hex()

def valid_hash(value: str) -> bool:
    try:
        method,salt,key=value.split('$')
        return method=='scrypt' and len(bytes.fromhex(salt))==16 and len(bytes.fromhex(key))==32
    except (ValueError,TypeError): return False

def verify_password(password: str,encoded: str) -> bool:
    if len(password)>1024 or not valid_hash(encoded): return False
    _,salt,key=encoded.split('$')
    candidate=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32)
    return hmac.compare_digest(candidate,bytes.fromhex(key))

def validate_configuration(cfg: SecurityConfig) -> None:
    from urllib.parse import urlsplit
    if cfg.enabled and not valid_hash(cfg.password_hash):
        raise RuntimeError('Authentication requires COMMANDER_PASSWORD_HASH. Run python -m app.cli password.')
    if cfg.hosted:
        parsed=urlsplit(cfg.origin)
        if parsed.scheme!='https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise RuntimeError('Set COMMANDER_PUBLIC_URL to the exact public HTTPS origin, without a path.')
        if os.getenv('COMMANDER_REQUIRE_MOUNT','false').lower()=='true' and not os.path.ismount(DB_PATH.parent):
            raise RuntimeError('Persistent volume is missing. Mount a volume at '+str(DB_PATH.parent)+' before starting.')
        if not os.getenv('COMMANDER_DB') or not os.getenv('COMMANDER_BACKUPS'):
            raise RuntimeError('Hosted mode requires explicit persistent COMMANDER_DB and COMMANDER_BACKUPS paths.')

def connect(cfg: SecurityConfig) -> sqlite3.Connection:
    cfg.auth_path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(cfg.auth_path,timeout=10)
    con.row_factory=sqlite3.Row
    con.executescript('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, fingerprint TEXT NOT NULL); CREATE TABLE IF NOT EXISTS attempts (ip TEXT NOT NULL, attempted REAL NOT NULL); CREATE INDEX IF NOT EXISTS attempts_time ON attempts(attempted);')
    con.executescript('CREATE TABLE IF NOT EXISTS accounts (username TEXT PRIMARY KEY, player_id TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0); CREATE TABLE IF NOT EXISTS invitations (token TEXT PRIMARY KEY, player_id TEXT NOT NULL, expires REAL NOT NULL); CREATE TABLE IF NOT EXISTS session_accounts (token TEXT PRIMARY KEY, username TEXT NOT NULL, fingerprint TEXT NOT NULL);')
    return con

def session(request: Request,cfg: SecurityConfig) -> dict | None:
    token=request.cookies.get(COOKIE,'')
    if not token or len(token)>200: return None
    with connect(cfg) as con:
        row=con.execute('SELECT * FROM sessions WHERE token=? AND expires>? AND fingerprint=?',(hashlib.sha256(token.encode()).hexdigest(),time.time(),cfg.fingerprint)).fetchone()
        if not row:return None
        linked=con.execute('SELECT a.*, s.fingerprint AS session_fingerprint FROM session_accounts s JOIN accounts a ON a.username=s.username WHERE s.token=?',(row['token'],)).fetchone()
        mapping=con.execute('SELECT 1 FROM session_accounts WHERE token=?',(row['token'],)).fetchone()
        if mapping and not linked:return None
        if linked:
            if linked['disabled'] or linked['session_fingerprint']!=hashlib.sha256(linked['password_hash'].encode()).hexdigest():return None
            return {**dict(row),'role':'member','username':linked['username'],'player_id':linked['player_id']}
    return {**dict(row),'role':'owner','username':'owner','player_id':None}

def login_attempt(cfg: SecurityConfig,ip: str) -> bool:
    # Count attempts atomically before expensive password verification; one app worker.
    with connect(cfg) as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM attempts WHERE attempted<?',(time.time()-600,))
        total=con.execute('SELECT count(*) FROM attempts').fetchone()[0]
        own=con.execute('SELECT count(*) FROM attempts WHERE ip=?',(ip,)).fetchone()[0]
        if total>=50 or own>=10: return False
        con.execute('INSERT INTO attempts VALUES (?,?)',(ip,time.time()))
    return True

def create_session(cfg: SecurityConfig, username: str='') -> str:
    token=secrets.token_urlsafe(32)
    with connect(cfg) as con:
        con.execute('DELETE FROM sessions WHERE expires<? OR fingerprint!=?',(time.time(),cfg.fingerprint))
        con.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),secrets.token_urlsafe(32),time.time()+7*86400,cfg.fingerprint))
        if username:
            account=con.execute('SELECT * FROM accounts WHERE username=? AND disabled=0',(username,)).fetchone()
            if not account:raise ValueError('Account unavailable')
            con.execute('INSERT INTO session_accounts VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),username,hashlib.sha256(account['password_hash'].encode()).hexdigest()))
    return token

def revoke(cfg: SecurityConfig,token: str) -> None:
    with connect(cfg) as con: con.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))

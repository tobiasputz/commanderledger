import hashlib,secrets,time,re
from app.security import connect,hash_password

def issue(cfg,player_id):
    token=secrets.token_urlsafe(32)
    with connect(cfg) as con:
        con.execute('DELETE FROM invitations WHERE player_id=? OR expires<?',(player_id,time.time()))
        con.execute('INSERT INTO invitations VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),player_id,time.time()+48*3600))
    return token

def accept(cfg,token,username,password):
    username=username.strip().lower()
    if username=='owner' or not re.fullmatch('[a-z0-9_.-]{3,40}',username):raise ValueError('Choose a username of 3–40 letters, numbers, dots, hyphens or underscores; owner is reserved.')
    encoded=hash_password(password)
    with connect(cfg) as con:
        con.execute('BEGIN IMMEDIATE')
        invitation=con.execute('SELECT * FROM invitations WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not invitation:raise ValueError('Invitation expired or was already used. Ask the administrator for a new link.')
        old=con.execute('SELECT * FROM accounts WHERE player_id=?',(invitation['player_id'],)).fetchone()
        taken=con.execute('SELECT * FROM accounts WHERE username=?',(username,)).fetchone()
        if taken and (not old or old['username']!=username):raise ValueError('Username unavailable.')
        if old:
            con.execute('DELETE FROM sessions WHERE token IN (SELECT token FROM session_accounts WHERE username=?)',(old['username'],))
            con.execute('DELETE FROM session_accounts WHERE username=?',(old['username'],))
            con.execute('DELETE FROM accounts WHERE player_id=?',(invitation['player_id'],))
        con.execute('INSERT INTO accounts VALUES (?,?,?,0)',(username,invitation['player_id'],encoded))
        con.execute('DELETE FROM invitations WHERE token=?',(invitation['token'],))
    return username

def list_accounts(cfg):
    with connect(cfg) as con:return [dict(r) for r in con.execute('SELECT username,player_id,disabled FROM accounts ORDER BY username')]

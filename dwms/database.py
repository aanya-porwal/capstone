from pathlib import Path
import sqlite3, hashlib, os, hmac, json
DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'dwms_users.db'

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, profile_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, goal_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, result_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS chat_history(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')

def _hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310000)

def register(email, password):
    email=email.strip().lower()
    if '@' not in email or len(password)<10: raise ValueError('Use a valid email and a password of at least 10 characters.')
    salt=os.urandom(16); digest=_hash(password,salt)
    try:
        with connect() as c: cur=c.execute('INSERT INTO users(email,salt,password_hash) VALUES(?,?,?)',(email,salt,digest))
        return cur.lastrowid
    except sqlite3.IntegrityError: raise ValueError('An account with this email already exists.')

def authenticate(email,password):
    with connect() as c: row=c.execute('SELECT * FROM users WHERE email=?',(email.strip().lower(),)).fetchone()
    if not row or not hmac.compare_digest(_hash(password,row['salt']),row['password_hash']): return None
    return {'id':row['id'],'email':row['email']}

def save_profile(uid, profile):
    with connect() as c: c.execute('INSERT INTO profiles(user_id,profile_json) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=CURRENT_TIMESTAMP',(uid,json.dumps(profile)))

def load_profile(uid):
    with connect() as c: row=c.execute('SELECT profile_json FROM profiles WHERE user_id=?',(uid,)).fetchone()
    return json.loads(row['profile_json']) if row else None

def save_recommendation(uid,result):
    with connect() as c: c.execute('INSERT INTO recommendations(user_id,result_json) VALUES(?,?)',(uid,json.dumps(result,default=float)))

def load_latest_recommendation(uid):
    with connect() as c: row=c.execute('SELECT result_json FROM recommendations WHERE user_id=? ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
    return json.loads(row['result_json']) if row else None

def save_chat(uid,role,content):
    with connect() as c: c.execute('INSERT INTO chat_history(user_id,role,content) VALUES(?,?,?)',(uid,role,content))

def load_chat(uid,limit=30):
    with connect() as c: rows=c.execute('SELECT role,content FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT ?',(uid,limit)).fetchall()
    return [dict(r) for r in reversed(rows)]

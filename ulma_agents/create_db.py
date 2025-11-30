import os
import sqlite3
from dotenv import load_dotenv
import datetime
import json


def get_db_path():
    load_dotenv()
    db_name = os.getenv("DATABASE_NAME", "local_addb")
    if not os.path.isabs(db_name):
        base_dir = os.path.dirname(__file__)
        db_name = os.path.join(base_dir, db_name)
    return db_name


def connect_db(db_path=None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    return conn


def create_db():
    '''
    clears existing dbs and create a mock table
    '''
    conn = connect_db()
    cursor=conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    role TEXT NOT NULL,
    groups TEXT,
    apps                  
    )
    ''')
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS agent_memory (
            session_id TEXT PRIMARY KEY,
            state_json TEXT,
            updated_at TEXT
        )
        '''
    )
    conn.commit()
    conn.close()
    print('New Table(user) created...')

def populate_db():
    '''
    creates some mock data
    '''
    conn = connect_db()
    cursor=conn.cursor()
    cursor.execute('INSERT INTO users (user_name,role,groups) VALUES (?,?,?)',('Adam','admin','sic_mundus'))
    cursor.execute('INSERT INTO users (user_name,role,groups) VALUES (?,?,?)',('Mikkel Nielson','employee','level1'))
    conn.commit()
    conn.close()
    print('A first record inserted...')


def ensure_memory_table(conn=None):
    """
    Ensures the agent_memory table exists.
    """
    owns_conn = conn is None
    conn = conn or connect_db()
    cursor = conn.cursor()
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS agent_memory (
            session_id TEXT PRIMARY KEY,
            state_json TEXT,
            updated_at TEXT
        )
        '''
    )
    conn.commit()
    if owns_conn:
        conn.close()


def save_memory_state(session_id: str, state: dict) -> None:
    """
    Persists the session state as JSON for durable memory.
    """
    ensure_memory_table()
    conn = connect_db()
    cursor = conn.cursor()
    payload = json.dumps(state or {})
    updated_at = datetime.datetime.utcnow().isoformat()
    cursor.execute(
        """
        INSERT INTO agent_memory (session_id, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
        """,
        (session_id, payload, updated_at),
    )
    conn.commit()
    conn.close()


def load_memory_state(session_id: str) -> dict:
    """
    Loads the persisted session state if present.
    """
    ensure_memory_table()
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state_json FROM agent_memory WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


if __name__=='__main__':
    create_db()
    populate_db()


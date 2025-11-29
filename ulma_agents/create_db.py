import os
import sqlite3
from dotenv import load_dotenv


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


if __name__=='__main__':
    create_db()
    populate_db()


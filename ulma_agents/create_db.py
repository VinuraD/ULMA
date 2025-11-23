import sqlite3
from dotenv import load_dotenv
import os


def connect_db():
    conn = sqlite3.connect(DATABASE+'db')
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
    cursor.commit()
    conn.close()
    print('New Table(user) created...')

def populate_db():
    '''
    creates some mock data
    '''
    conn = connect_db()
    cursor=conn.cursor()
    cursor.execute('INSERT INTO users ((user_name,role,groups) VALUES (?,?,?)',('Adam','admin','sic_mundus'))
    cursor.execute('INSERT INTO users ((user_name,role,groups) VALUES (?,?,?)',('Mikkel Nielson','employee','level1'))
    cursor.commit()
    conn.close()
    print('A first record inserted...')


if __name__=='__main__':
    load_dotenv()
    DATABASE = os.getenv("DATABASE_NAME")
    connect_db()
    create_db()
    populate_db()


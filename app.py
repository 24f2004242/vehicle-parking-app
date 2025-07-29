import sqlite3
import hashlib
from datetime import datetime
import os

DB_PATH = "parking_app.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIAMRY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_has TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Admin table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hard TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Parking Lots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prime_location_name TEXT NOT NULL,
            address TEXT NOT NULL,
            pin_code TEXT NOT NULL,
            price_per_hour REAL NOT NULL,
            maximum_spots INTEGER NOT NUL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Parking Spots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            status TEXT DEFAULT 'A' CHECK (status IN ('A', 'O')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id) ON DELETE CASCADE
        )
    ''')

    # Reservations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            parking_timestamp TIMESTAMP,
            leaving_timestamp TIMESTAMP,
            parking_cost REAL DEFAULT 0.0,
            status TEXT DEFAULT 'reserved' CHECK (status IN ('reserved', 'occupied', 'completed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (spot_id) REFERENCES parking_spots (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()
    print("Database tables created successfully")

def insert_default_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin WHERE username = ?", ('admin', ))
    if cursor.fetchone() is None:
        admin_password = hash_password('admin123')
        cursor.execute('''
            INSERT INTO admin (username, password_hash)
            VALUES (?,?)
        ''', ('admin', admin_password))
        conn.commit()
        print("Default admin created - Username: admin, Password: admin123")

def get_user_by_credentials(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)
    cursor.execute('''
        SELECT * FROM users
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))

    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_admin_by_credentials(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)
    cursor.execute('''
        SELECT * FROM admin
        WHERE username = ? AND password_hash = ?
    ''', (username, password_hash))

    admin = cursor.fetchone()
    conn.close()
    return dict(admin) if admin else None

def create_user(username, email, full_name, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO (username, email, full_name, password_hash)
            VALUES (?,?,?,?)
        ''', (username, email, full_name, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None
    


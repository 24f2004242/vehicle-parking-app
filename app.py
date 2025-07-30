from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
from datetime import datetime, timedelta
import os
from collections import defaultdict

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
    
DB_PATH = "parking_app.db"
if not os.path.exists(DB_PATH):
    create_database()
    insert_default_admin()

app = Flask(__name__)
app.secret_key = 'this_is_a_very_secret_key' 

def is_logged_in():
    return 'user_id' in session or 'admin_id' in session

def is_admin():
    return 'admin_id' in session

def is_user():
    return 'user_id' in session

def require_login():
    if not is_logged_in():
        return redirect(url_for('login'))
    return None

def require_admin():
    if not is_admin():
        return redirect(url_for('login'))
    return None

def require_user():
    if not is_user():
        return redirect(url_for('login'))
    return None

def create_parking_lot(location_name, address, pin_code, price_per_hour, max_spots):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO parking_lots (prime_location_name, address, pin_code, price_per_hour, maximum_spots)
            VALUES (?,?,?,?,?)
        ''', (location_name, address, pin_code, price_per_hour, max_spots))

        lot_id = cursor.lastrowid

        for i in range(max_spots):
            cursor.execute('''
                ISNERT INTO parking_spots (lot_id, status)
                VALUES (?, 'A')
            ''', (lot_id, ))

        conn.commit()
        conn.close()
        return lot_id
    except Exception as e:
        conn.close()
        return None
    
def update_parking_lot(lot_id, location_name, address, pin_code, price_per_hour, max_spots):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT COUNT(*) FROM parking_spots
            WHERE lot_id = ?
        ''', (lot_id, ))
        current_spots = cursor.fetchone()[0]

        cursor.execute('''
            UPDATE parking_lots
            SET prime_location_name = ?, address = ?, pin_code = ?, price_per_hour = ?, maximum_spots = ?
            WHERE id = ?
        ''', (location_name, address, pin_code, price_per_hour, max_spots, lot_id))

        if max_spots > current_spots:
            for i in range(max_spots - current_spots):
                cursor.execute('''
                    INSERT INTO parking_spots (lot_id, status)
                    VALUES (?, 'A')
                ''', (lot_id, ))
        elif max_spots < current_spots:
            cursor.execute('''
                DELETE FROM parking_spots
                WHERE lot_id = ? AND status = 'A'
                LIMIT ?
            ''', (lot_id, current_spots - max_spots))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False
    
def delete_parking_lot(lot_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT COUNT(*) FROM parking_spots
            WHERE lot_id = ? AND status = '0'          
        ''', (lot_id, ))
        occupied_spots = cursor.fetchone()[0]

        if occupied_spots >0:
            conn.close()
            return False, "Cannot delete lot with occupied spots"
        
        cursor.execute('''
            DELETE FROM parking_spots
            WHERE lot_id = ?
        ''', (lot_id, ))

        conn.commit()
        conn.close()
        return True, "Parking lot deleted success"
    except Exception as e:
        conn.close()
        return False, f"Error deleting parking lot: {str(e)}"
    
def get_available_parking_lots():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT pl.*,
            COUNT(ps.id) as total spots,
            SUM(CASE WHEN ps.status = 'A' THEN 1 ELSE 0 END) as available_spots,
            SUM(CASE WHEN ps.status = 'O' THEN 1 ELSE 0 END) as occupied_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots on pl.id = ps.lot_id
        GROUP BY pl.id
        HAVING available_spots > 0
        ORDER BY available_spots DESC, pl.price_per_hour ASC
    ''')
    
    lots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return lots

def reserve_parking_spot(user_id, lot_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT id FROM parking_spots
            WHERE lot_id = ? AND status = 'A'
            ORDER BY id ASC
            LIMIT 1
        ''', (lot_id, ))

        spot = cursor.fetchone()
        if not spot:
            conn.close()
            return None, "No available spots in this parking lot"
        
        spot_id = spot[0]

        cursor.execute('''
            SELECT COUNT(*) FROM reservations
            WHERE user_id = ? AND status IN ('reserved', 'occupied')
        ''', (user_id, ))

        active_count = cursor.fetchone()[0]
        if active_count > 0:
            conn.close()
            return None, "You already have an active reservation"
        
        cursor.execute('''
            INSERT INTO reservations (spot_id, user_id, status, created_at)
            VALUES (?, ?, 'reserved', CURRENT_TIMESTAMP)
        ''', (spot_id, user_id))

        reservation_id = cursor.lastrowid

        cursor.execute('''
            UPDATE parking_spots SET status = '0' WHERE id = ?
        ''', (spot_id, ))

        conn.commit()
        conn.close()

        return reservation_id, "Parking spot reserved successfully"
    except Exception as e:
        conn.close()
        return None, f"Error reserved spot: {str(e)}"
    
def start_parking(reservation_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT * FROM reservations
            WHERE id = ? AND user_id = ? AND status = 'reserved'
        ''', (reservation_id, user_id))

        reservation = cursor.fetchone()
        if not reservation:
            conn.close()
            return False, "invalid reservation or already started"
        
        cursor.execute('''
            UPDATE reservations
            SET status = 'occupied', parking_timestamp = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reservation_id, ))

        conn.commit()
        conn.close()
        return True, "Parking staretd successfully"
    
    except Exception as e:
        conn.close()
        return False, f"Error starting parking: {str(e)}"

def end_parking(reservation_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT r.*, pl.price_per_hour, ps.lot_id
            FROM reservations r
            JOIN parking_spots ps ON r.spot_id = ps.id
            JOIN parking_lots pl on ps.lot_id = pl.id
            WHERE r.id = ? AND r.user_id = ? AND r.status = 'occupied'
        ''', (reservation_id, user_id))

        reservation = cursor.fetchone()
        if not reservation:
            conn.close()
            return False, "Invalid reservation or not currently parked", 0
        
        reservation = dict(reservation)

        parking_start = datetime.fromisofformat(reservation['parking_timestamp'])
        parking_end = datetime.now()
        duration_hours = (parking_end - parking_start).total_seconds() / 3600

        if duration_hours < 1:
            billable_hours = 1
        else:
            billable_hours = int(duration_hours) + (1 if duration_hours %1 >0 else 0)

        parking_cost = billable_hours * reservation['price_per_hour']

        cursor.execute('''
            UPDATE reservations
            SET status = 'completed',
                leaving_timestamp = CURRENT_TIMESTAMP,
                parking_cost= ?
            WHERE id = ?
        ''', (parking_cost, reservation_id))

        cursor.execute('''
            UPDATE parking_spots SET status = 'A' WHERE id = ?    
        ''', (reservation['spot_id']))

        conn.commit()
        conn.close()

        return True, f"Parking ended. Duration: {duration_hours:.2f} hours, Cost: ₹{parking_cost:.2f}", parking_cost

    except Exception as e:
        conn.close()
        return False, f"Error ending parking: {str(e)}"
    
def get_user_reservations(user_id, include_completed = False):
    conn = get_db_connection()
    cursor = conn.cursor()

    if include_completed:
        status_filter = ""
    else:
        status_filter = "AND r.status IN ('reserved', 'occupied')"

    cursor.execute(f'''
        SELECT r.*, pl.id as spot_number, pl.prime_location_name, pl.address, pl.price_per_hour
        FROM reservations r
        JOIN parking_spots ps ON r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ? {status_filter}
        ORDER BY r.created_at DESC
    ''', (user_id, ))

    reservations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reservations

def cancel_reservation(reservation_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT spot_id from reservations
            WHERE id = ? AND user_id = ? AND status = 'reserved'
        ''', (reservation_id, user_id))

        reservation = cursor.fetchone()
        if not reservation:
            conn.close()
            return False, "Cannot cancel - reservation not found or already in use"

        spot_id = reservation[0]

        cursor.execute('''
            DELETE FROM reservations
            WHERE id = ?
        ''', (reservation_id, ))

        cursor.execute('''
            UPDATE parking_spots
            SET status = 'A'
            WHERE id = ?
        ''', (spot_id, ))

        conn.commit()
        conn.close()
        return True, "Reservation cancelled successfully"
    
    except Exception as e:
        conn.close()
        return False, f"Error cancelling reservation: {str(e)}"
    

def get_all_parking_lots():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT pl.*,
            COUNT(ps.id) as total_spots,
            SUM(CASE WHEN ps.status = 'A' THEN 1 ELSE 0 END) as available_spots,
            SUM(CASE WHEN ps.status = 'O' THEN 1 ELSE 0 END) as occupied_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        GROUP BY pl.id
        ORDER BY pl.created_at DESC
    ''')

    lots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return lots

def get_parking_lot_details(lot_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM parking_lots
        WHERE id = ?
    ''', (lot_id, ))
    lot = cursor.fetchone()

    if not lot:
        conn.close()
        return None, []
    
    cursor.execute('''
        SELECT ps.*, r.user_id, u.username, u.full_name, r.parking_timestamp, r.status as reservation_status
        FROM parking_spots ps
        LEFT JOIN reservations r ON ps.id = r.spot_id AND r.status IN ('reserved', 'occupied')
        LEFT JOIN users u on r.user_id = u.id
        WHERE ps.lot_id = ?
        ORDER BY ps.id
    ''', (lot_id, ))

    spots = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return dict(lot), spots

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT u.*, 
            COUNT(r.id) as total_reservations,
            COUNT(CASE WHEN r.status IN ('reserved', 'occupied') THEN 1 END) as active_reservations
        FROM users u
        LEFT JOIN reservations r ON u.id = r.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''')

    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def get_user_parking_summary(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT r.*, ps.id as spot_number, pl.prime_location_name, pl.address, pl.price_per_hour,
            CASE
                WHEN r.parking_timestamp IS NOT NULL AND r.leaving_timestamp IS NOT NULL
                THEN (julianday(r.leaving_timestamp)-julianday(r.parking_timestamp)) * 24
                ELSE 0
            END as duration_hours
        FROM reservations r
        JOIN parking_spots ps on r.spot_id = ps.id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    ''', (user_id, ))

    all_reservations = [dict(row) for row in cursor.fetchall()]

    total_reservations = len(all_reservations)
    completed_sessions = [r for r in all_reservations if r['status'] == 'completed']
    active_sessions = [r for r in all_reservations if r['status'] in ['reserved', 'occupied']]
    cancelled_sessions = [r for r in all_reservations if r['status'] == 'cancelled']

    total_cost = sum(r['parking_cost'] or 0 for r in completed_sessions)
    total_hours = sum(r['duration_hours'] or 0 for r in completed_sessions)

    monthly_data = defaultdict(lambda: {'count':0, 'cost':0, 'hours':0})
    for reservation in completed_sessions:
        if reservation['created_at']:
            month_key = reservation['created_at'][:7]
            monthly_data[month_key]['count'] += 1
            monthly_data[month_key]['cost'] += reservation['parking_cost'] or 0
            monthly_data[month_key]['hours'] += reservation['duration_hours'] or 0

    location_stats = defaultdict(lambda: {'count':0, 'cost':0, 'hours':0})
    for reservation in completed_sessions:
        location = reservation['prime_location_name']
        location_stats[location]['count'] += 1
        location_stats[location]['cost'] += reservation['parking_cost'] or 0
        location_stats[location]['hours'] += reservation['duration_hours'] or 0

    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    recent_sessions = [r for r in completed_sessions if r['created_at'] and r['created_at']>=thirty_days_ago]
    conn.close()

    summary = {
        'total_reservations': total_reservations,
        'completed_sessions': len(completed_sessions),
        'active_sessions': len(active_sessions),
        'cancelled_sessions': len(cancelled_sessions),
        'total_cost': total_cost,
        'total_hours': total_hours,
        'average_cost_per_sessions': total_cost / len(completed_sessions) if completed_sessions else 0,
        'average_duration': total_hours/ len(completed_sessions) if completed_sessions else 0,
        'monthly_data': dict(monthly_data),
        'location_stats': dict(location_stats),
        'recent_activity_30days': len(recent_sessions),
        'recent_cost_30days': sum(r['parking_cost'] or 0 for r in recent_sessions),
        'all_reservations': all_reservations,
        'completed_reservations': completed_sessions,
        'active_reservations': active_sessions
    }

    return summary

def get_admin_parking_summary():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(*) FROM users
    ''')
    total_users = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM parking_lots
    ''')
    total_lots = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM parking_spots
    ''')
    total_spots = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM parking_spots WHERE status = 'O'
    ''')
    occupied_spots = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM reservations WHERE status IN ('reserved', 'occupied')
    ''')
    active_reservations = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM reservations WHERE status = 'completed'
    ''')
    completed_reservations = cursor.fetchone()[0]

    cursor.execute('''
        SELECT SUM(parking_cost) FROM reservations WHERE status = 'completed'
    ''')
    total_revenue = cursor.fetchone()[0] or 0

    cursor.execute('''
        SELECT r.*, ps.id as spot_number, pl.prime_location_name, pl.price_per_hour, u.username, u.full_name,
            CASE 
                WHEN r.parking_timestamp IS NOT NULL AND r.leaving_timestamp IS NOT NULL
                THEN (julianday(r.leaving_timestamp)-julianday(r.parking_timestamp)) * 24
                ELSE 0
            END as duration_hours
        FROM reservations r
        JOIN parking_spots as ps ON ps.id = r.spot_id
        JOIN parking_lots pl ON ps.lot_id = pl.id
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    ''')

    all_reservations = [dict(row) for row in cursor.fetchall()]

    monthly_stats = defaultdict(lambda: {'reservations': 0, 'revenue': 0, 'hours':0})
    for reservation in all_reservations:
        if reservation['created_at'] and reservation['status'] =='completed':
            month_key = reservation['created_at'][:7]
            monthly_stats[month_key]['reservations'] += 1
            monthly_stats[month_key]['revenue'] += reservation['parking_cost'] or 0
            monthly_stats[month_key]['hours'] += reservation['duration_hours'] or 0

    cursor.execute('''
        SELECT pl.prime_location_name, pl.id, 
            COUNT(r.id) as total_reservations,
            COUNT(CASE WHEN r.status = 'completed' THEN 1 END) as completed_session,
            SUM(CASE WHEN r.status = 'completed' THEN r.parking_cost ELSE 0 END) as revenue,
            AVG(CASE WHEN r.status = 'completed' AND r.parking_timestamp IS NOT NULL and r.leaving_timestamp IS NOT NULL
                THEN (julianday(r.leaving_timestamp)-julianday(r.parking_timestamp)) * 24 ELSE NULL END) as avg_duration,
            COUNT(ps.id) as total_spots,
            SUM(CASE WHEN ps.status = 'O' THEN 1 ELSE 0 END) as occupied_spots
        FROM parking_lots pl
        LEFT JOIN parking_spots ps ON pl.id = ps.lot_id
        LEFT JOIN reservations r ON ps.id = r.spot_id
        GROUP BY pl.id, pl.prime_location_name
        ORDER BY revenue DESC
    ''')

    lot_performance = [dict(row) for row in cursor.fetchall()]

    cursor.execute('''
        SELECT u.username, u.full_name,
            COUNT(r.id) as total_reservations,
            COUNT(CASE WHEN r.status = 'completed' THEN 1 END) as completed_sessions,
            SUM(CASE WHEN r.status = 'completed' THEN r.parking_cost ELSE 0 END) as total_spent,
            COUNT(CASE WHEN r.status IN ('reserved', 'occupied') THEN 1 END) as active_sessions
        FROM users u
        LEFT JOIN reservations r ON u.id = r.user_id
        GROUP BY u.id, u.username, u.full_name
        HAVING total_reservations > 0
        ORDER BY total_spent DESC
    ''')

    user_activity = [dict(row) for row in cursor.fetchall()]

    seven_days_ago = (datetime.now() - timedelta(days = 7).strftime('%Y-%m-%d'))
    recent_reservations = [r for r in all_reservations if r['created_at'] and r['created_at']>=seven_days_ago]

    conn.close()

    summary = {
        'basic_stats': {
            'total_users': total_users,
            'total_lots': total_lots,
            'total_spots': total_spots,
            'occupied_spots': occupied_spots,
            'available_spots': total_spots - occupied_spots,
            'active_reservations': completed_reservations,
            'total_revenue': total_revenue,
            'occupancy_rate': (occupied_spots / total_spots *100) if total_spots > 0 else 0
        },
        'monthly_stats': dict(monthly_stats),
        'lot_performance': lot_performance,
        'user_activity': user_activity,
        'recent_activity_7days': len(recent_reservations),
        'recent_revenue_7days': sum(r['parking_cost'] or 0 for r in recent_reservations if r['status'] == 'completed'),
        'all_reservations': all_reservations[:50]
    }

    return summary


# Routes
@app.route('/')
def index():
    if is_admin():
        return redirect(url_for('admin_dashboard'))
    elif is_user():
        return redirect(url_for('user_dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']

        if user_type == 'admin':
            admin = get_admin_by_credentials(username, password)
            if admin:
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                flash('Admin login successful', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
        elif user_type == 'user':
            user = get_user_by_credentials(username, password)
            if user:
                session['user_id'] = user['id']
                session['user_username'] = user['username']
                session['user_fullname'] = user['full_name']
                flash('User login successful', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Invalid user credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['full_name']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

    if password != confirm_password:
        flash('Passwords do not match', 'error')
    elif len(password) < 6:
        flash('Password must be at least 6 characters long', 'error')
    else:
        user_id = create_user(username, email, full_name, password)
        if user_id:
            flash('Registration successful, Please login now', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists', 'error')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/admin_dashboard')
def admin_dashboard():
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    summary = get_admin_parking_summary()
    return render_template('admin_dashboard.html', stats=summary['basic_stats'], recent_lots=get_all_parking_lots()[:5], summary=summary)

@app.route('/admin/lots')
def admin_lots():
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    lots = get_all_parking_lots()
    return render_template('admin_lots.html', lots=lots)

@app.route('/admin/lots/add', methods=['GET', 'POST'])
def admin_add_lot():
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price_per_hour = float(request.form['price_per_hour'])
        max_spots = int(request.form['max_spots'])
        
        if max_spots <= 0:
            flash('Maximum spots must be greater than 0!', 'error')
        elif price_per_hour <= 0:
            flash('Price per hour must be greater than 0!', 'error')
        else:
            lot_id = create_parking_lot(location_name, address, pin_code, price_per_hour, max_spots)
            if lot_id:
                flash(f'Parking lot created successfully with {max_spots} spots!', 'success')
                return redirect(url_for('admin_lots'))
            else:
                flash('Error creating parking lot!', 'error')

    return render_template('admin_add_lot.html')

@app.route('/admin/lots/edit/<int:lot_id>', methods=['GET', 'POST'])
def admin_edit_lot(lot_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    if request.method == 'POST':
        location_name = request.form['location_name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price_per_hour = float(request.form['price_per_hour'])
        max_spots = int(request.form['max_spots'])
        
        if max_spots <= 0:
            flash('Maximum spots must be greater than 0!', 'error')
        elif price_per_hour <= 0:
            flash('Price per hour must be greater than 0!', 'error')
        else:
            if update_parking_lot(lot_id, location_name, address, pin_code, price_per_hour, max_spots):
                flash('Parking lot updated successfully!', 'success')
                return redirect(url_for('admin_lots'))
            else:
                flash('Error updating parking lot!', 'error')
    
    # Get current lot details
    lot, spots = get_parking_lot_details(lot_id)
    if not lot:
        flash('Parking lot not found!', 'error')
        return redirect(url_for('admin_lots'))
    
    return render_template('admin_edit_lot.html', lot=lot)

@app.route('/admin/lots/delete/<int:lot_id>')
def admin_delete_lot(lot_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    success, message = delete_parking_lot(lot_id)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('admin_lots'))

@app.route('/admin/lots/view/<int:lot_id>')
def admin_view_lot(lot_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    lot, spots = get_parking_lot_details(lot_id)
    if not lot:
        flash('Parking lot not found!', 'error')
        return redirect(url_for('admin_lots'))
    
@app.route('/admin/users')
def admin_users():
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    users = get_all_users()
    return render_template('admin_users.html', users=users)

@app.route('/admin/summary')
def admin_summary():
    auth_check = require_admin()
    if auth_check:
        return auth_check
    
    summary = get_admin_parking_summary()
    return render_template('admin_summary.html', summary = summary)


@app.route('/user_dashboard')
def user_dashboard():
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    active_reservations = get_user_reservations(session['user_id'], include_completed=False)
    
    available_lots = get_available_parking_lots()

    return render_template('user_dashboard.html', active_reservations=active_reservations, available_lots=available_lots)

@app.route('/user/reserve/<int:lot_id>')
def user_reserve_spot(lot_id):
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    reservation_id, message = reserve_parking_spot(session['user_id'], lot_id)

    if reservation_id:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('user_dashboard'))

@app.route('/user/start_parking/<int:reservation_id>')
def user_start_parking(reservation_id):
    auth_check = require_user()
    if auth_check:
        return auth_check

    success, message = start_parking(reservation_id, session['user_id'])

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('user_dashboard'))

@app.route('/user/end_parking/<int:reservation_id>')
def user_end_parking(reservation_id):
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    success, message, cost = end_parking(reservation_id, session['user_id'])

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('user_dashboard'))

@app.route('/user/cancel/<int:reservation_id>')
def user_cancel_reservation(reservation_id):
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    success, message = cancel_reservation(reservation_id, session['user_id'])

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('user_dashboard'))

@app.route('/user/history')
def user_history():
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    reservations = get_user_reservations(session['user_id'], include_completed=True)

    return render_template(url_for('user_history.html', reservations=reservations))

@app.route('/user/summary')
def user_summary():
    auth_check = require_user()
    if auth_check:
        return auth_check
    
    summary = get_user_parking_summary(session['user_id'])
    return render_template('user_summary.html', summary=summary)



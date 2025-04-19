from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = '30ddbf88f037b9d62a8c1633d6be3de1'  # for session management

def init_db():
    con = sqlite3.connect('hotel.db')
    cur = con.cursor()

    # Ensure 'users' table has the 'role' column
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cur.fetchone():
        cur.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cur.fetchall()]
        if 'role' not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user')''')

    cur.execute('''CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY,
        type TEXT,
        status TEXT)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        room_id INTEGER,
        date TEXT)''')

    # Clear previous data and insert demo
    cur.execute("DELETE FROM bookings")
    cur.execute("DELETE FROM rooms")
    demo_rooms = [
        ('Single', 'booked'),
        ('Double', 'available'),
        ('Suite', 'available'),
        ('Deluxe', 'available'),
        ('Deluxe', 'available')
    ]
    cur.executemany("INSERT INTO rooms (type, status) VALUES (?, ?)", demo_rooms)

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', 'admin', 'admin'))

    # Assign first room as booked by user_id=1
    cur.execute("INSERT INTO bookings (user_id, room_id, date) VALUES (?, ?, DATE('now'))", (1, 1))

    con.commit()
    con.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        con = sqlite3.connect('hotel.db')
        cur = con.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        con.commit()
        con.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        con = sqlite3.connect('hotel.db')
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        con.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3] if len(user) > 3 else 'user'
            return redirect(url_for('dashboard'))
        return "Login Failed"
    return render_template('login.html')

# New vulnerable login route
@app.route('/vulnerable_login', methods=['GET', 'POST'])
def vulnerable_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('hotel.db')
        c = conn.cursor()
        # UNSAFE: String concatenation (SQLi vulnerable)
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        c.execute(query)
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        return "Login Failed"
    return render_template('login.html', vulnerable=True)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    con = sqlite3.connect('hotel.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM rooms")
    rooms = cur.fetchall()
    cur.execute("SELECT room_id FROM bookings WHERE user_id=?", (session['user_id'],))
    user_booked = [row[0] for row in cur.fetchall()]
    con.close()
    return render_template('dashboard.html', rooms=rooms, user_booked_room_ids=user_booked)

@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
def book_page(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    con = sqlite3.connect('hotel.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM rooms WHERE id=?", (room_id,))
    room = cur.fetchone()

    if request.method == 'POST':
        session['booking'] = {
            'room_id': room_id,
            'people': request.form['people'],
            'num_rooms': request.form['num_rooms'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date']
        }
        return redirect(url_for('payment'))

    con.close()
    return render_template('book.html', room=room)

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'user_id' not in session or 'booking' not in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        room_id = session['booking']['room_id']
        user_id = session['user_id']
        con = sqlite3.connect('hotel.db')
        cur = con.cursor()
        cur.execute("INSERT INTO bookings (user_id, room_id, date) VALUES (?, ?, DATE('now'))", (user_id, room_id))
        cur.execute("UPDATE rooms SET status='booked' WHERE id=?", (room_id,))
        con.commit()
        con.close()
        session.pop('booking')
        return redirect(url_for('dashboard'))

    return render_template('payment.html')

@app.route('/unbook', methods=['POST'])
def unbook_room():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    room_id = request.form['room_id']

    con = sqlite3.connect('hotel.db')
    cur = con.cursor()
    cur.execute("DELETE FROM bookings WHERE user_id=? AND room_id=?", (user_id, room_id))
    cur.execute("UPDATE rooms SET status='available' WHERE id=?", (room_id,))
    con.commit()
    con.close()

    return redirect(url_for('dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session or session.get('role') != 'admin':
        return "Access Denied"
    con = sqlite3.connect('hotel.db')
    cur = con.cursor()
    if request.method == 'POST':
        room_type = request.form['type']
        status = request.form['status']
        cur.execute("INSERT INTO rooms (type, status) VALUES (?, ?)", (room_type, status))
        con.commit()
    cur.execute("SELECT * FROM rooms")
    rooms = cur.fetchall()
    con.close()
    return render_template('admin.html', rooms=rooms)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Insecure XSS route
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    return render_template('search.html', query=query)

# Secure XSS route
@app.route('/search_secure', methods=['GET'])
def search_secure():
    query = request.args.get('q', '')
    return render_template('search_secure.html', query=query)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

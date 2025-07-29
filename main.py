
import os
import psycopg2
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from datetime import datetime
import uuid
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create events table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            schedule TIMESTAMP NOT NULL,
            location VARCHAR(255) NOT NULL,
            creator VARCHAR(255) NOT NULL,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            invite_token VARCHAR(255) UNIQUE NOT NULL
        )
    ''')
    
    # Create RSVPs table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rsvps (
            id SERIAL PRIMARY KEY,
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            invitee_name VARCHAR(255) NOT NULL,
            invitee_email VARCHAR(255) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            response_date TIMESTAMP,
            message TEXT,
            invite_token VARCHAR(255) NOT NULL
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        schedule = request.form['schedule']
        location = request.form['location']
        creator = request.form['creator']
        
        invite_token = str(uuid.uuid4())
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO events (name, description, schedule, location, creator, invite_token)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        ''', (name, description, schedule, location, creator, invite_token))
        
        event_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        flash(f'Event created successfully! Event ID: {event_id}', 'success')
        return redirect(url_for('event_details', event_id=event_id))
    
    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
def event_details(event_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('SELECT * FROM events WHERE id = %s', (event_id,))
    event = cur.fetchone()
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    cur.execute('''
        SELECT * FROM rsvps WHERE event_id = %s ORDER BY response_date DESC
    ''', (event_id,))
    rsvps = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('event_details.html', event=event, rsvps=rsvps)

@app.route('/invite/<int:event_id>', methods=['GET', 'POST'])
def invite_people(event_id):
    if request.method == 'POST':
        invitee_name = request.form['invitee_name']
        invitee_email = request.form['invitee_email']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get event invite token
        cur.execute('SELECT invite_token FROM events WHERE id = %s', (event_id,))
        result = cur.fetchone()
        if not result:
            flash('Event not found', 'error')
            return redirect(url_for('index'))
        
        invite_token = result[0]
        
        cur.execute('''
            INSERT INTO rsvps (event_id, invitee_name, invitee_email, invite_token)
            VALUES (%s, %s, %s, %s)
        ''', (event_id, invitee_name, invitee_email, invite_token))
        
        conn.commit()
        cur.close()
        conn.close()
        
        invite_url = request.url_root + f'rsvp/{invite_token}?email={invitee_email}'
        flash(f'Invitation created! Send this URL: {invite_url}', 'success')
        
        return redirect(url_for('event_details', event_id=event_id))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM events WHERE id = %s', (event_id,))
    event = cur.fetchone()
    cur.close()
    conn.close()
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('invite.html', event=event)

@app.route('/rsvp/<invite_token>')
def rsvp_form(invite_token):
    email = request.args.get('email')
    if not email:
        flash('Invalid invitation link', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('''
        SELECT e.*, r.id as rsvp_id, r.invitee_name, r.status
        FROM events e
        JOIN rsvps r ON e.id = r.event_id
        WHERE r.invite_token = %s AND r.invitee_email = %s
    ''', (invite_token, email))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if not result:
        flash('Invalid invitation', 'error')
        return redirect(url_for('index'))
    
    return render_template('rsvp.html', event=result, email=email)

@app.route('/submit_rsvp/<invite_token>', methods=['POST'])
def submit_rsvp(invite_token):
    email = request.form['email']
    status = request.form['status']
    message = request.form.get('message', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        UPDATE rsvps 
        SET status = %s, message = %s, response_date = CURRENT_TIMESTAMP
        WHERE invite_token = %s AND invitee_email = %s
    ''', (status, message, invite_token, email))
    
    conn.commit()
    cur.close()
    conn.close()
    
    flash('RSVP submitted successfully!', 'success')
    return render_template('rsvp_success.html')

@app.route('/events')
def list_events():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('SELECT * FROM events ORDER BY creation_date DESC')
    events = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('events_list.html', events=events)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)

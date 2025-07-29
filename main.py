import os
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

def get_db_connection():
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # Create events table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            schedule TEXT NOT NULL,
            location TEXT NOT NULL,
            creator TEXT NOT NULL,
            creation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            invite_token TEXT UNIQUE NOT NULL
        )
    ''')

    # Create RSVPs table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS rsvps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            invitee_name TEXT NOT NULL,
            invitee_email TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            response_date TEXT,
            message TEXT,
            invite_token TEXT NOT NULL
        )
    ''')

    conn.commit()
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

        cursor = conn.execute('''
            INSERT INTO events (name, description, schedule, location, creator, invite_token)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, schedule, location, creator, invite_token))

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        flash(f'Event created successfully! Event ID: {event_id}', 'success')
        return redirect(url_for('event_details', event_id=event_id))

    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
def event_details(event_id):
    conn = get_db_connection()

    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()

    if not event:
        flash('Event not found', 'error')
        conn.close()
        return redirect(url_for('index'))

    rsvps = conn.execute('''
        SELECT * FROM rsvps WHERE event_id = ? ORDER BY response_date DESC
    ''', (event_id,)).fetchall()

    conn.close()

    # Convert event to dict and parse datetime strings
    event_dict = dict(event)
    event_dict['schedule'] = datetime.fromisoformat(event_dict['schedule'])
    event_dict['creation_date'] = datetime.fromisoformat(event_dict['creation_date'])

    # Convert rsvps to list of dicts and parse datetime strings
    rsvps_list = []
    for rsvp in rsvps:
        rsvp_dict = dict(rsvp)
        if rsvp_dict['response_date']:
            rsvp_dict['response_date'] = datetime.fromisoformat(rsvp_dict['response_date'])
        rsvps_list.append(rsvp_dict)

    return render_template('event_details.html', event=event_dict, rsvps=rsvps_list)

@app.route('/invite/<int:event_id>', methods=['GET', 'POST'])
def invite_people(event_id):
    if request.method == 'POST':
        invitee_name = request.form['invitee_name']
        invitee_email = request.form['invitee_email']

        conn = get_db_connection()

        # Get event invite token
        result = conn.execute('SELECT invite_token FROM events WHERE id = ?', (event_id,)).fetchone()
        if not result:
            flash('Event not found', 'error')
            conn.close()
            return redirect(url_for('index'))

        invite_token = result['invite_token']

        conn.execute('''
            INSERT INTO rsvps (event_id, invitee_name, invitee_email, invite_token)
            VALUES (?, ?, ?, ?)
        ''', (event_id, invitee_name, invitee_email, invite_token))

        conn.commit()
        conn.close()

        invite_url = request.url_root + f'rsvp/{invite_token}?email={invitee_email}'
        flash(f'Invitation created! Send this URL: {invite_url}', 'success')

        return redirect(url_for('event_details', event_id=event_id))

    conn = get_db_connection()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    conn.close()

    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('index'))

    # Convert event to dict and parse datetime
    event_dict = dict(event)
    event_dict['schedule'] = datetime.fromisoformat(event_dict['schedule'])

    return render_template('invite.html', event=event_dict)

@app.route('/rsvp/<invite_token>')
def rsvp_form(invite_token):
    email = request.args.get('email')
    if not email:
        flash('Invalid invitation link', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()

    result = conn.execute('''
        SELECT e.*, r.id as rsvp_id, r.invitee_name, r.status, r.message
        FROM events e
        JOIN rsvps r ON e.id = r.event_id
        WHERE r.invite_token = ? AND r.invitee_email = ?
    ''', (invite_token, email)).fetchone()

    conn.close()

    if not result:
        flash('Invalid invitation', 'error')
        return redirect(url_for('index'))

    # Convert result to dict and parse datetime
    event_dict = dict(result)
    event_dict['schedule'] = datetime.fromisoformat(event_dict['schedule'])

    return render_template('rsvp.html', event=event_dict, email=email)

@app.route('/submit_rsvp/<invite_token>', methods=['POST'])
def submit_rsvp(invite_token):
    email = request.form['email']
    status = request.form['status']
    message = request.form.get('message', '')

    conn = get_db_connection()

    conn.execute('''
        UPDATE rsvps 
        SET status = ?, message = ?, response_date = datetime('now')
        WHERE invite_token = ? AND invitee_email = ?
    ''', (status, message, invite_token, email))

    conn.commit()
    conn.close()

    flash('RSVP submitted successfully!', 'success')
    return render_template('rsvp_success.html')

@app.route('/events')
def list_events():
    conn = get_db_connection()

    events = conn.execute('SELECT * FROM events ORDER BY creation_date DESC').fetchall()

    conn.close()

    # Convert events to list of dicts and parse datetime strings
    events_list = []
    for event in events:
        event_dict = dict(event)
        event_dict['schedule'] = datetime.fromisoformat(event_dict['schedule'])
        event_dict['creation_date'] = datetime.fromisoformat(event_dict['creation_date'])
        events_list.append(event_dict)

    return render_template('events_list.html', events=events_list)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
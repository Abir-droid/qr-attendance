import os
import json
import hashlib
import time
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, redirect, url_for, session, render_template, request
from authlib.integrations.flask_client import OAuth
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-this")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # Set your password here or in Render

# --- CONFIGURATION ---
VARSITY_DOMAIN = "diu.edu.bd"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SPREADSHEET_NAME = "Attendance Register"

BATCHES = [str(b) for b in range(40, 79)]
SECTIONS = [chr(s) for s in range(ord('A'), ord('P') + 1)]
DURATIONS = [
    {"label": "1 Minute", "value": 1},
    {"label": "3 Minutes", "value": 3},
    {"label": "5 Minutes", "value": 5},
    {"label": "10 Minutes", "value": 10},
    {"label": "Unlimited", "value": 0}
]

# Setup OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Setup Google Sheets API Connection
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

service_account_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if service_account_env:
    info = json.loads(service_account_env)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
else:
    creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)

gc = gspread.authorize(creds)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_today_key(batch, section, expires_at):
    today_str = datetime.now().strftime("%Y-%m-%d")
    return hashlib.md5(f"SALT_KEY_{today_str}_{batch}_{section}_{expires_at}".encode()).hexdigest()[:8]

# --- ADMIN ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('teacher_display'))
        else:
            error = "Invalid password. Access denied."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def teacher_display():
    selected_batch = request.args.get('batch', '45')
    selected_section = request.args.get('section', 'A')
    try:
        duration_minutes = int(request.args.get('duration', 3))
    except ValueError:
        duration_minutes = 3

    if selected_batch not in BATCHES:
        selected_batch = '45'
    if selected_section not in SECTIONS:
        selected_section = 'A'

    now_ts = int(time.time())
    expires_at = now_ts + (duration_minutes * 60) if duration_minutes > 0 else 0

    today_key = get_today_key(selected_batch, selected_section, expires_at)
    qr_target_url = url_for(
        'student_login', 
        batch=selected_batch, 
        section=selected_section, 
        expires_at=expires_at, 
        key=today_key, 
        _external=True
    )
    
    return render_template(
        'teacher.html',
        url=qr_target_url,
        batches=BATCHES,
        sections=SECTIONS,
        durations=DURATIONS,
        current_batch=selected_batch,
        current_section=selected_section,
        current_duration=duration_minutes,
        expires_at=expires_at
    )

# --- STUDENT ATTENDANCE ROUTES ---

@app.route('/scan/<batch>/<section>/<int:expires_at>/<key>')
def student_login(batch, section, expires_at, key):
    now_ts = int(time.time())
    
    if expires_at != 0 and now_ts > expires_at:
        return render_template('error.html', message="This QR code has expired.", detail="Attendance submission is closed for this session."), 400

    if batch not in BATCHES or section not in SECTIONS or key != get_today_key(batch, section, expires_at):
        return render_template('error.html', message="Invalid QR code.", detail="The link is corrupted or invalid."), 400
    
    session['attendance_key'] = key
    session['batch'] = batch
    session['section'] = section
    session['expires_at'] = expires_at
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri, hd=VARSITY_DOMAIN, prompt='select_account')

@app.route('/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return render_template('error.html', message="Authentication Failed.", detail="Failed to fetch user profile from Google."), 400
        
    user_email = user_info.get('email', '')
    
    if not user_email.lower().endswith(f"@{VARSITY_DOMAIN}"):
        return render_template('error.html', message="Access Denied.", detail=f"You logged in as {user_email}. You must use an @{VARSITY_DOMAIN} email address."), 403

    batch = session.get('batch')
    section = session.get('section')
    expires_at = session.get('expires_at', 0)
    current_key = session.get('attendance_key')
    
    now_ts = int(time.time())
    if expires_at != 0 and now_ts > expires_at:
        return render_template('error.html', message="Session Expired.", detail="Your login took too long and the session closed."), 400

    if not batch or not section or current_key != get_today_key(batch, section, expires_at):
        return render_template('error.html', message="Invalid Session.", detail="Please scan the active QR code again."), 400

    student_id = user_email.split('@')[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    sheet_tab_name = f"{today_str}_B{batch}_Sec{section}"
    now_time = datetime.now().strftime("%H:%M:%S")

    sh = gc.open(SPREADSHEET_NAME)
    
    try:
        worksheet = sh.worksheet(sheet_tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_tab_name, rows="100", cols="10")
        worksheet.append_row(["Timestamp", "Student ID", "Batch", "Section", "Varsity Email", "Status"])

    records = worksheet.get_all_records()
    for row in records:
        if str(row.get("Student ID", "")).lower() == student_id.lower():
            return render_template('error.html', message="Already Logged", detail=f"Attendance for ID {student_id} in Batch {batch} ({section}) has already been recorded today.")

    worksheet.append_row([now_time, student_id, batch, section, user_email, "Present"])

    return render_template(
        'success.html',
        title="Attendance Success",
        message="Attendance Marked!",
        email=user_email,
        student_id=student_id,
        batch=batch,
        section=section
    )
@app.route('/api/attendance-count')
def attendance_count():
    batch = request.args.get('batch')
    section = request.args.get('section')

    if not batch or not section:
        return jsonify({"count": 0})

    today_str = datetime.now().strftime("%Y-%m-%d")
    sheet_tab_name = f"{today_str}_B{batch}_Sec{section}"

    sh = gc.open(SPREADSHEET_NAME)

    try:
        worksheet = sh.worksheet(sheet_tab_name)
        # Get row count minus header row
        records = worksheet.get_all_values()
        count = max(0, len(records) - 1)
    except gspread.exceptions.WorksheetNotFound:
        count = 0

    return jsonify({"count": count})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
import os
import json
import hashlib
from datetime import datetime
from flask import Flask, redirect, url_for, session, render_template_string, jsonify
from authlib.integrations.flask_client import OAuth
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-this")

# --- CONFIGURATION ---
VARSITY_DOMAIN = "diu.edu.bd"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SPREADSHEET_NAME = "Attendance Register"

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

# Check if service account JSON is passed via Environment Variable (for Render deployment)
service_account_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

if service_account_env:
    # Load credentials directly from environment variable on Render
    info = json.loads(service_account_env)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
else:
    # Fallback to local file for local testing
    creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)

gc = gspread.authorize(creds)

def get_today_key():
    today_str = datetime.now().strftime("%Y-%m-%d")
    return hashlib.md5(f"SALT_KEY_{today_str}".encode()).hexdigest()[:8]

# --- ROUTES ---

@app.route('/')
def teacher_display():
    # Classroom screen displays today's QR
    today_key = get_today_key()
    qr_target_url = url_for('student_login', key=today_key, _external=True)
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Attendance QR</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body { font-family: sans-serif; text-align: center; background: #1e1e2e; color: #cdd6f4; padding: 40px; }
            .card { background: #313244; display: inline-block; padding: 30px; border-radius: 16px; }
            #qrcode { background: white; padding: 15px; border-radius: 8px; margin: 20px auto; display: flex; justify-content: center; }
        </style>
    </head>
    <body>
        <h1>Today's Attendance QR</h1>
        <p>Scan with your phone camera and sign in with @diu.edu.bd</p>
        <div class="card">
            <div id="qrcode"></div>
            <p><strong>Valid for today only</strong></p>
        </div>
        <script>
            new QRCode(document.getElementById("qrcode"), { text: "{{ url }}", width: 260, height: 260 });
        </script>
    </body>
    </html>
    """
    return render_template_string(html, url=qr_target_url)

@app.route('/scan/<key>')
def student_login(key):
    if key != get_today_key():
        return "<h3>This QR code has expired or is invalid for today.</h3>", 400
    
    session['attendance_key'] = key
    redirect_uri = url_for('auth_callback', _external=True)
    # hd=diu.edu.bd forces Google to prompt for @diu.edu.bd emails directly
    return google.authorize_redirect(redirect_uri, hd=VARSITY_DOMAIN, prompt='select_account')

@app.route('/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return "Failed to fetch user information from Google.", 400
        
    user_email = user_info.get('email', '')
    
    # Enforce domain check
    if not user_email.lower().endswith(f"@{VARSITY_DOMAIN}"):
        html = f"""
        <div style="font-family:sans-serif; text-align:center; padding:30px;">
            <h2 style="color:red;">Access Denied</h2>
            <p>You logged in as: <b>{user_email}</b></p>
            <p>You must use an <b>@{VARSITY_DOMAIN}</b> account to mark attendance.</p>
            <a href="/scan/{session.get('attendance_key', '')}">Try Again with Varsity Account</a>
        </div>
        """
        return html, 403

    # Check key validity
    current_key = session.get('attendance_key')
    if current_key != get_today_key():
        return "Session expired. Please scan the QR code again.", 400

    # Record attendance in Google Sheet
    student_id = user_email.split('@')[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    sh = gc.open(SPREADSHEET_NAME)
    
    # Get or create today's worksheet tab
    try:
        worksheet = sh.worksheet(today_str)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=today_str, rows="100", cols="10")
        worksheet.append_row(["Timestamp", "Student ID", "Varsity Email", "Status"])

    # Prevent duplicates
    records = worksheet.get_all_records()
    for row in records:
        if str(row.get("Student ID", "")).lower() == student_id.lower():
            return f"""
            <div style="font-family:sans-serif; text-align:center; padding:30px;">
                <h2 style="color:#b45309;">Already Logged</h2>
                <p>Attendance for <b>{student_id}</b> has already been submitted today!</p>
            </div>
            """

    # Append entry
    worksheet.append_row([now_time, student_id, user_email, "Present"])

    return f"""
    <div style="font-family:sans-serif; text-align:center; padding:30px;">
        <h2 style="color:green;">Attendance Marked!</h2>
        <p>Logged as: <b>{user_email}</b></p>
        <p>Student ID: <b>{student_id}</b></p>
    </div>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
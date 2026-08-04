import os
import json
import hashlib
from datetime import datetime
from flask import Flask, redirect, url_for, session, render_template_string, request
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

# Generate choices
BATCHES = [str(b) for b in range(40, 79)]  # 40 through 78
SECTIONS = [chr(s) for s in range(ord('A'), ord('P') + 1)]  # A through P

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

def get_today_key(batch, section):
    today_str = datetime.now().strftime("%Y-%m-%d")
    return hashlib.md5(f"SALT_KEY_{today_str}_{batch}_{section}".encode()).hexdigest()[:8]

# --- ROUTES ---

@app.route('/')
def teacher_display():
    selected_batch = request.args.get('batch', '45')
    selected_section = request.args.get('section', 'A')

    # Basic fallback checks
    if selected_batch not in BATCHES:
        selected_batch = '45'
    if selected_section not in SECTIONS:
        selected_section = 'A'

    today_key = get_today_key(selected_batch, selected_section)
    qr_target_url = url_for('student_login', batch=selected_batch, section=selected_section, key=today_key, _external=True)
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Attendance QR</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body { font-family: sans-serif; text-align: center; background: #1e1e2e; color: #cdd6f4; padding: 30px; }
            .card { background: #313244; display: inline-block; padding: 30px; border-radius: 16px; min-width: 320px; }
            #qrcode { background: white; padding: 15px; border-radius: 8px; margin: 20px auto; display: flex; justify-content: center; }
            .controls { margin-bottom: 25px; display: flex; justify-content: center; gap: 15px; align-items: center; }
            select { padding: 10px 15px; font-size: 16px; border-radius: 8px; border: none; background: #45475a; color: white; cursor: pointer; }
            label { font-size: 16px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Today's Attendance QR</h1>
        
        <form method="GET" action="/" class="controls">
            <div>
                <label for="batch">Batch: </label>
                <select id="batch" name="batch" onchange="this.form.submit()">
                    {% for b in batches %}
                        <option value="{{ b }}" {% if b == current_batch %}selected{% endif %}>
                            Batch {{ b }}
                        </option>
                    {% endfor %}
                </select>
            </div>

            <div>
                <label for="section">Section: </label>
                <select id="section" name="section" onchange="this.form.submit()">
                    {% for s in sections %}
                        <option value="{{ s }}" {% if s == current_section %}selected{% endif %}>
                            Section {{ s }}
                        </option>
                    {% endfor %}
                </select>
            </div>
        </form>

        <div class="card">
            <h2>Batch {{ current_batch }} - Section {{ current_section }}</h2>
            <div id="qrcode"></div>
            <p>Scan with phone camera & sign in with <b>@diu.edu.bd</b></p>
            <p><small>Valid for today only</small></p>
        </div>

        <script>
            new QRCode(document.getElementById("qrcode"), { text: "{{ url }}", width: 260, height: 260 });
        </script>
    </body>
    </html>
    """
    return render_template_string(
        html, 
        url=qr_target_url, 
        batches=BATCHES,
        sections=SECTIONS, 
        current_batch=selected_batch,
        current_section=selected_section
    )

@app.route('/scan/<batch>/<section>/<key>')
def student_login(batch, section, key):
    if batch not in BATCHES or section not in SECTIONS or key != get_today_key(batch, section):
        return "<h3>This QR code has expired or is invalid.</h3>", 400
    
    session['attendance_key'] = key
    session['batch'] = batch
    session['section'] = section
    redirect_uri = url_for('auth_callback', _external=True)
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
        </div>
        """
        return html, 403

    batch = session.get('batch')
    section = session.get('section')
    current_key = session.get('attendance_key')
    
    if not batch or not section or current_key != get_today_key(batch, section):
        return "Session expired. Please scan the QR code again.", 400

    # Record attendance in Google Sheet
    student_id = user_email.split('@')[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    sheet_tab_name = f"{today_str}_B{batch}_Sec{section}"
    now_time = datetime.now().strftime("%H:%M:%S")

    sh = gc.open(SPREADSHEET_NAME)
    
    # Get or create worksheet tab for today's batch & section
    try:
        worksheet = sh.worksheet(sheet_tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_tab_name, rows="100", cols="10")
        worksheet.append_row(["Timestamp", "Student ID", "Batch", "Section", "Varsity Email", "Status"])

    # Prevent duplicates
    records = worksheet.get_all_records()
    for row in records:
        if str(row.get("Student ID", "")).lower() == student_id.lower():
            return f"""
            <div style="font-family:sans-serif; text-align:center; padding:30px;">
                <h2 style="color:#b45309;">Already Logged</h2>
                <p>Attendance for <b>{student_id}</b> in Batch <b>{batch}</b> (Section <b>{section}</b>) has already been submitted today!</p>
            </div>
            """

    # Append entry
    worksheet.append_row([now_time, student_id, batch, section, user_email, "Present"])

    return f"""
    <div style="font-family:sans-serif; text-align:center; padding:30px;">
        <h2 style="color:green;">Attendance Marked!</h2>
        <p>Logged as: <b>{user_email}</b></p>
        <p>Student ID: <b>{student_id}</b></p>
        <p>Batch: <b>{batch}</b> | Section: <b>{section}</b></p>
    </div>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
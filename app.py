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
SECTIONS = ["45A", "45B", "45C-(L)"]

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

def get_today_key(section):
    today_str = datetime.now().strftime("%Y-%m-%d")
    return hashlib.md5(f"SALT_KEY_{today_str}_{section}".encode()).hexdigest()[:8]

# --- ROUTES ---

@app.route('/')
def teacher_display():
    selected_section = request.args.get('section', SECTIONS[0])
    if selected_section not in SECTIONS:
        selected_section = SECTIONS[0]

    today_key = get_today_key(selected_section)
    qr_target_url = url_for('student_login', section=selected_section, key=today_key, _external=True)
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Attendance QR</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <style>
            body { font-family: sans-serif; text-align: center; background: #1e1e2e; color: #cdd6f4; padding: 30px; }
            .card { background: #313244; display: inline-block; padding: 30px; border-radius: 16px; min-width: 300px; }
            #qrcode { background: white; padding: 15px; border-radius: 8px; margin: 20px auto; display: flex; justify-content: center; }
            select { padding: 10px 15px; font-size: 16px; border-radius: 8px; border: none; background: #45475a; color: white; cursor: pointer; margin-bottom: 20px; }
            label { font-size: 18px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <h1>Today's Attendance QR</h1>
        
        <div>
            <label for="section-select"><b>Select Section:</b></label>
            <select id="section-select" onchange="location = this.value;">
                {% for sec in sections %}
                    <option value="/?section={{ sec }}" {% if sec == current_section %}selected{% endif %}>
                        Section {{ sec }}
                    </option>
                {% endfor %}
            </select>
        </div>

        <div class="card">
            <h2>Section: {{ current_section }}</h2>
            <div id="qrcode"></div>
            <p>Scan with your phone camera & sign in with <b>@diu.edu.bd</b></p>
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
        sections=SECTIONS, 
        current_section=selected_section
    )

@app.route('/scan/<section>/<key>')
def student_login(section, key):
    if section not in SECTIONS or key != get_today_key(section):
        return "<h3>This QR code has expired or is invalid.</h3>", 400
    
    session['attendance_key'] = key
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

    section = session.get('section')
    current_key = session.get('attendance_key')
    
    if not section or current_key != get_today_key(section):
        return "Session expired. Please scan the QR code again.", 400

    # Record attendance in Google Sheet
    student_id = user_email.split('@')[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    sheet_tab_name = f"{today_str}_{section}"
    now_time = datetime.now().strftime("%H:%M:%S")

    sh = gc.open(SPREADSHEET_NAME)
    
    # Get or create worksheet tab for today's section
    try:
        worksheet = sh.worksheet(sheet_tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_tab_name, rows="100", cols="10")
        worksheet.append_row(["Timestamp", "Student ID", "Section", "Varsity Email", "Status"])

    # Prevent duplicates
    records = worksheet.get_all_records()
    for row in records:
        if str(row.get("Student ID", "")).lower() == student_id.lower():
            return f"""
            <div style="font-family:sans-serif; text-align:center; padding:30px;">
                <h2 style="color:#b45309;">Already Logged</h2>
                <p>Attendance for <b>{student_id}</b> in section <b>{section}</b> has already been submitted today!</p>
            </div>
            """

    # Append entry
    worksheet.append_row([now_time, student_id, section, user_email, "Present"])

    return f"""
    <div style="font-family:sans-serif; text-align:center; padding:30px;">
        <h2 style="color:green;">Attendance Marked!</h2>
        <p>Logged as: <b>{user_email}</b></p>
        <p>Student ID: <b>{student_id}</b></p>
        <p>Section: <b>{section}</b></p>
    </div>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
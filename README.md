# 🎓 QR Code Attendance System with Google OAuth

A secure, real-time classroom attendance tracking system built with Python (Flask) and Google Cloud APIs. Designed specifically for university environments to streamline attendance recording, eliminate proxy attendance, and log data directly into organized Google Sheets.

---

## ✨ Key Features

* **🔒 Admin Authentication Panel:** Protected login dashboard for instructors/admins to generate QR codes and manage sessions securely.
* **⚡ Live Dynamic QR Generation:** Generates unique, encrypted QR links for specific **Batch** (40–78) and **Section** (A–P) combinations on demand.
* **⏱️ Configurable Session Timers:** Choose active duration (1 min, 3 mins, 5 mins, 10 mins, or Unlimited) with live countdowns on the classroom projector.
* **🚫 Anti-Proxy & Expiration Protection:** Server-side timestamp hashing ensures QR codes expire automatically to prevent link sharing outside class hours.
* **📧 Domain-Restricted Google OAuth:** Forces student login through official institutional email addresses (`@diu.edu.bd`) using Google OpenID Connect.
* **📊 Automatic Google Sheets Sync:** Creates organized, date-stamped worksheet tabs (e.g., `2026-08-04_B45_SecA`) automatically and logs timestamps, student IDs, emails, and attendance status.
* **🛑 Duplicate Entry Prevention:** Blocks students from submitting attendance more than once per class session.
* **📱 Responsive & Clean UI:** Works seamlessly on both desktop screens (classroom projectors) and student mobile devices.

---

## 🛠️ Tech Stack

* **Backend:** Python 3, Flask, Authlib
* **Database / Storage:** Google Sheets API (`gspread`), Google Drive API
* **Authentication:** Google OAuth 2.0 (OpenID Connect)
* **Production Deployment:** Gunicorn, Render
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

---

##Screenshots

<img width="2558" height="1373" alt="Screenshot 2026-08-04 224551" src="https://github.com/user-attachments/assets/5ceabc9a-0f2c-47b6-8bf8-7dc1cb1b2d22" />

<img width="2546" height="1242" alt="Screenshot 2026-08-04 224236" src="https://github.com/user-attachments/assets/41028b6a-6c43-4b77-b4bf-d232094f30ef" />

<img width="2558" height="1249" alt="Screenshot 2026-08-04 224529" src="https://github.com/user-attachments/assets/cdf7c0b9-4045-488f-82ce-655d948bc899" />

<img width="1038" height="2306" alt="Screenshot_20260804-224436_Chrome" src="https://github.com/user-attachments/assets/2037e0d4-c67f-4206-b341-f24aba908633" />

<img width="1080" height="2400" alt="Screenshot_20260804-224501_Chrome" src="https://github.com/user-attachments/assets/91ad98a1-297b-4af2-8617-13575b83e637" />



<img width="1080" height="2400" alt="Screenshot_20260804-225107_Chrome" src="https://github.com/user-attachments/assets/5176ceef-1cd2-433f-a7b2-fd73124812a5" />






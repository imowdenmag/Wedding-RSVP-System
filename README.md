# 💍 Wedding RSVP & Check-In System

A modern web application for managing RSVPs and check-ins at weddings and events. This system is optimized for speed, usability, and elegance, making guest handling seamless both before and during the event.

---

## ✨ Features

### 📝 RSVP Portal
- Guests can enter a unique code to RSVP.
- Real-time verification from Google Sheets.
- Dynamic update of RSVP status.

### ✅ Check-In System
- Guests are verified at entry with their unique codes.
- Live guest search with auto-fill and editable fields.
- Check-in timestamps logged.
- Writes checked-in data to a separate sheet.

### 🔒 Authentication
- Separate login portals for Admin and Check-In staff.
- Firestore (Firebase) is used for secure credential storage.

### 📊 Admin Dashboard
- Card summaries: Confirmed, Declined, Checked-In, Total.
- View RSVP responses and check-in data in real-time.
- Live data animations (green ▲ increase, red ▼ decrease).
- Edit, delete, and manually add check-ins.
- Export data as CSV, XLS, or PDF.

### 🌐 Tech Stack
| Frontend        | Backend          | Database          | Deployment       |
|-----------------|------------------|-------------------|------------------|
| HTML, CSS, JS   | Python, Flask    | Google Sheets, MySQL, Firestore | Google Cloud Run |

---

## 🛠️ Setup Instructions

### 🔧 Prerequisites
- Python 3.10+
- Node.js (for optional frontend tooling)
- Firebase Project (for Firestore)
- Google Cloud Project (with Sheets API enabled)
- MySQL Server (optional for advanced logging)
- Git

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-username/wedding-rsvp-checkin.git
cd wedding-rsvp-checkin


## Set Up Python Environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt


## Configure Environment Variables
Create a .env file

GOOGLE_SHEETS_CREDENTIALS_JSON=credentials.json
SHEET_ID=your_google_sheet_id
FIREBASE_CREDENTIALS=firebase-adminsdk.json
FLASK_SECRET_KEY=your_secret_key

🔐 Ensure .env and credential files are added to .gitignore.


### Set Up Google Sheets
Sheet 1: RSVP List

Sheet 2: Check-In Log

Make sure column headers match exactly:

RSVP Sheet: GUEST CODE, RSVP STATUS, SEATING ZONE, etc.

Check-In Sheet: TimeStamp, GuestCode, GuestName, etc.

### 5️⃣ Configure Firestore (Firebase)
Create a Firebase project.

Enable Firestore in test mode.

Create a collection for check-in and admin users.

### 6️⃣ Run the Application

## Features In Progress
QR code scanning for check-in.

Dashboard analytics (graphs).

Guest tag printing.

SMS/email RSVP confirmations.

## Deployment
This app is ready for cloud deployment via Google Cloud Run:

gcloud run deploy \
  --source . \
  --platform managed \
  --region YOUR_REGION \
  --allow-unauthenticated \
  --project YOUR_PROJECT_ID

Make sure to:

Add secrets to GCP environment variables.

Use Secret Manager for JSON credentials.

##  Project Structure
wedding-rsvp-checkin/
│
├── static/                  # JS, CSS, assets
├── templates/               # HTML templates
├── auth/                    # Firestore login logic
├── routes/                  # Flask route definitions
├── sheets/                  # Google Sheets logic
├── checkin/                 # Check-in logic & views
├── admin/                   # Admin dashboard features
├── app.py                   # Entry point
├── requirements.txt
└── .env.example


## Contributors
Owden Magnusen – Lead Developer

👩🏽‍💻 Owden Magnusen - Visual Designer

📊 Owden Magnusen - Data Management

🎨 Rachael Gapkey - Graphics and Assests for the project

## Client
iamadinkra. (iamadinkra.com)


## License
This project is licensed under the MIT License. See LICENSE file for more info.

## 💡 Inspiration
Built to simplify guest coordination at a high-scale, elegant wedding. Designed with speed, clarity, and a touch of flair.

## 📬 Contact
Have questions or want to collaborate?

📧 Email: me@owdenmagnusen.com
📸 Instagram: @imowdenmag
🌍 Portfolio: owdenmagnusen.com
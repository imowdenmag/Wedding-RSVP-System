# 💍 Wedding RSVP & Check-In System

A modern web application for managing RSVPs and check-ins at weddings and events. This system is optimized for speed, usability, and elegance, making guest handling seamless both before and during the event.

---

## Features

### RSVP Portal
- Guests can enter a unique code to RSVP.
- Real-time verification from Google Sheets.
- Dynamic update of RSVP status.

### Check-In System
- Guests are verified at entry with their unique codes.
- Live guest search with auto-fill and editable fields.
- Check-in timestamps logged.
- Writes checked-in data to a separate sheet.

### Authentication
- Separate login portals for Admin and Check-In staff.
- Firestore (Firebase) is used for secure credential storage.

### Admin Dashboard
- Card summaries: Confirmed, Declined, Checked-In, Total.
- View RSVP responses and check-in data in real-time.
- Live data animations (green ▲ increase, red ▼ decrease).
- Edit, delete, and manually add check-ins.
- Export data as CSV, XLS, or PDF.

### 🌐 Tech Stack

| Frontend        | Backend       | Database                          | Deployment         |
|-----------------|---------------|-----------------------------------|--------------------|
| HTML, CSS, JS   | Python, Flask | Google Sheets, MySQL, Firestore  | Google Cloud Run   |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js (for optional frontend tooling)
- Firebase Project (for Firestore)
- Google Cloud Project (with Sheets API enabled)
- MySQL Server (optional for advanced logging)
- Git

### 1 Clone the Repository
```bash
git clone https://github.com/imowdenmag/Wedding-RSVP-System
cd wedding-rsvp-checkin

### 2 Set Up Python Environment

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt

### 3 Configure Environment Variables
Create a .env file with the following keys:
GOOGLE_SHEETS_CREDENTIALS_JSON=credentials.json
SHEET_ID=your_google_sheet_id
FIREBASE_CREDENTIALS=firebase-adminsdk.json
FLASK_SECRET_KEY=your_secret_key

Ensure .env and credential files are added to .gitignore.

### 4 Set Up Google Sheets
-Sheet 1: RSVP List
-Sheet 2: Check-In Log
-Headers should match exactly:

RSVP Sheet:
-GUEST CODE, RSVP STATUS, SEATING ZONE, etc.

Check-In Sheet:
-TimeStamp, GuestCode, GuestName, etc.

### 5 Configure Firestore (Firebase)
-Create a Firebase project.
-Enable Firestore in test mode.
-Create collections for check-in data and admin users.

### 6 Run the application
-python app.py

### Features In Progress
-QR code scanning for Check-In
-Dashboard analytics (graphs)
-Guest tag printing
-SMS/Email Rsvp confirmations.

### Deployment
Deployed using Google Cloud Run

### Project Structure

wedding-rsvp-system/
├── static/            # JS, CSS, assets
├── templates/         # HTML templates
├── gitignore             # gitignore
├── app.py             # Entry point
├── Dockerfile          # Configuration
├── requirements.txt   # Dependencies
└── test.py


### Contributors
- Owden Magnusen - Lead Developer
- Rachael Gapkey - UI/UX Designer
- Owden Magnusen - Backend Developer

### Client 
-iamadinkra

### License
This project is licensed under the MIT License

### Contact
Email: me@owdenmagnusen.com
Portfoilio: owdenmagnusen.com
LinkedIn: https://www.linkedin.com/in/imowdenmag/

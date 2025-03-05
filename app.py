from flask import Flask, request, jsonify, render_template, redirect, session, url_for
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import mysql.connector
from functools import wraps
from datetime import datetime  # Import datetime for timestamps
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing from the .env file!")
app.secret_key = SECRET_KEY 

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("iamadinkra-ff3a4-b7ff7fb9d6ba.json", scope) 
client = gspread.authorize(creds)
sheet1 = client.open("J&O Wedding Guest Data 2025").worksheet("Master Guest Sheet")  # Sheet 1
sheet2 = client.open("J&O Wedding Guest Data 2025").worksheet("Guest Check-In ")  # Sheet 2
sheet3 = client.open("J&O Wedding Guest Data 2025").worksheet("RSVP Logging")  # Sheet 3 for RSVP logs


# MySQL setup
db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = db.cursor(dictionary=True)

# Admin login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/rsvp')
def rsvp():
    return render_template('rsvp.html')

@app.route('/check-code', methods=['POST'])
def check_code():
    data = request.get_json()
    code = data['code'].strip().upper()
    records = sheet1.get_all_records()

    for record in records:
        if record['GUEST CODE'] == code:
            # Redirect to the confirmation page with guest details
            return jsonify({
                "status": "success",
                "redirect_url": url_for('confirm', 
                                       code=code,
                                       guest_name=record['GUEST FULL NAME'],
                                       seating_zone=record['SEATING ZONE'],
                                       table_assigned=record['Table Assigned'],
                                       designation=record['Designation'])
            })
    return jsonify({"status": "error", "message": "Code not found"}), 404

@app.route('/confirm')
def confirm():
    # Fetch guest details from URL parameters
    code = request.args.get('code')
    guest_name = request.args.get('guest_name')
    seating_zone = request.args.get('seating_zone')
    table_assigned = request.args.get('table_assigned')
    designation = request.args.get('designation')

    # Render the confirmation page with guest details
    return render_template('confirm.html', 
                          code=code,
                          guest_name=guest_name,
                          seating_zone=seating_zone,
                          table_assigned=table_assigned,
                          designation=designation)

@app.route('/confirm-attendance', methods=['POST'])
def confirm_attendance():
    # Get form data
    code = request.form.get('code')
    attendance = request.form.get('attendance')

    # Debugging: Print the received form data
    print(f"Received code: {code}, attendance: {attendance}")

    # Find the guest in Sheet 1 and update their RSVP status
    records = sheet1.get_all_records()
    for i, record in enumerate(records):
        if record['GUEST CODE'] == code:
            print(f"Updating guest: {record['GUEST FULL NAME']} with attendance: {attendance}")
            sheet1.update_cell(i + 2, 10, attendance)  # Update RSVP STATUS column (10th column in Sheet 1)
            
            # Log RSVP attempt in 'RSVP Logging' sheet
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = [timestamp, code, record['GUEST FULL NAME'], attendance]
            sheet3.append_row(log_entry)
            
            return jsonify({"status": "success", "message": "Attendance updated and logged successfully"})
    
    print("Guest not found")
    return jsonify({"status": "error", "message": "Guest not found"}), 404



@app.route('/checkin')
def checkin():
    return render_template('checkin.html')


@app.route('/check-in', methods=['POST'])
def check_in():
    data = request.get_json()
    code = data['code']
    records = sheet1.get_all_records()

    # Find guest in Sheet 1
    guest_data = None
    for record in records:
        if record['GUEST CODE'] == code:
            guest_data = record
            break

    if not guest_data:
        return jsonify({"status": "error", "message": "Guest not found"}), 404

    # Prepare data for Sheet 2
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current timestamp
    new_row = [
        timestamp,  # TimeStamp
        guest_data['GUEST CODE'],  # GuestCode
        guest_data['GUEST FULL NAME'],  # GuestName
        guest_data['Table Assigned'],  # Seating (leave blank for now)
        guest_data['Designation'],  # EmergencyContact (leave blank for now)
        "",  # NumberofDevices (leave blank for now)
        "",  # DeviceDetails (leave blank for now)
        "",  # CollectionPassword (leave blank for now)
        "",  # LockerID (leave blank for now)
        "",  # CollectionStatus (leave blank for now)
        "",  # PouchCollected (leave blank for now)
        "",  # PouchReturned (leave blank for now)
        "",  # NumberofAides (leave blank for now)
        ""   # AidesDetails (leave blank for now)
    ]

    # Append new row to Sheet 2
    sheet2.append_row(new_row)
    return jsonify({"status": "success", "message": "Check-in successful"})

@app.route('/confirmed')
def confirmed():
    return render_template('Yes.html')

@app.route('/declined')
def declined():
    return render_template('No.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        if admin and admin['password'] == password:  # In production, use bcrypt for password hashing
            session['admin_id'] = admin['id']
            return redirect('/admin/dashboard')
        return "Invalid credentials", 401
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    cursor.execute("SELECT name FROM admins WHERE id = %s", (session['admin_id'],))
    admin_name = cursor.fetchone()['name']
    records = sheet2.get_all_records()
    print(records)
    return render_template('admin_dashboard.html', name_of_admin=admin_name, records=records)

if __name__ == '__main__':
    app.run(debug=True)
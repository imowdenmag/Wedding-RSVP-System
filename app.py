from flask import Flask, request, jsonify, render_template, redirect, session, url_for, flash
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
from functools import wraps 

# Load environment variables
load_dotenv()

# Load Google credentials
with open("iamadinkra-ff3a4-864ca2842b01.json", "r") as file:
    creds_dict = json.load(file)

print("✅ Google credentials loaded successfully!")

app = Flask(__name__)

# Ensure SECRET_KEY exists
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing from the .env file!")
app.secret_key = SECRET_KEY 

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

# Open Google Sheets
try:
    sheet1 = client.open("J&O Wedding Guest Data 2025").worksheet("Master Guest Sheet")  # Sheet 1
    sheet2 = client.open("J&O Wedding Guest Data 2025").worksheet("Guest Check-In")  # ✅ Fixed extra space in name
    sheet3 = client.open("J&O Wedding Guest Data 2025").worksheet("RSVP Logging")  # Sheet 3 for RSVP logs
    print("✅ Connected to Google Sheets successfully!")
except Exception as e:
    print(f"❌ Error connecting to Google Sheets: {e}")

# MySQL setup with error handling
try:
    
    db = mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE")
    )
    cursor = db.cursor(dictionary=True)
    print("✅ Connected to VM MySQL successfully!")

except mysql.connector.Error as err:
    print(f"❌ Error connecting to VM MySQL: {err}")
    db = None  # Avoid crashes if connection fails

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
            return jsonify({
                "status": "success",
                "redirect_url": url_for('confirm', 
                                       code=code,
                                       guest_name=record['GUEST FULL NAME'],
                                       seating_zone=record['SEATING ZONE'],
                                       table_assigned=record['TABLE ASSIGNED'],
                                       designation=record['DESIGNATION'])
            })
    return jsonify({"status": "error", "message": "Code not found"}), 404

@app.route('/confirm')
def confirm():
    return render_template('confirm.html', 
                          code=request.args.get('code'),
                          guest_name=request.args.get('guest_name'),
                          seating_zone=request.args.get('seating_zone'),
                          table_assigned=request.args.get('table_assigned'),
                          designation=request.args.get('designation'))

@app.route('/confirm-attendance', methods=['POST'])
def confirm_attendance():
    code = request.form.get('code')
    attendance = request.form.get('attendance')

    print(f"Received code: {code}, attendance: {attendance}")

    records = sheet1.get_all_records()
    for i, record in enumerate(records):
        if record['GUEST CODE'] == code:
            print(f"Updating guest: {record['GUEST FULL NAME']} with attendance: {attendance}")
            sheet1.update_cell(i + 2, 10, attendance)  # Update RSVP STATUS column (10th column)

            # Log RSVP attempt
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = [timestamp, code, record['GUEST FULL NAME'], attendance]
            sheet3.append_row(log_entry)
            
            return jsonify({"status": "success", "message": "Attendance updated and logged successfully"})
    
    print("Guest not found")
    return jsonify({"status": "error", "message": "Guest not found"}), 404


# --- CHECK-IN ROUTES ---

@app.route('/checkin')
def checkin():
    return render_template('checkin.html')

@app.route('/search-guest', methods=['GET'])
def search_guest():
    query = request.args.get('query', '').strip().upper()
    if not query:
        return jsonify([])

    records = sheet1.get_all_records()
    results = []

    for record in records:
        guest_code = record['GUEST CODE']
        guest_name = record['GUEST FULL NAME']

        if query in guest_code or query in guest_name:
            results.append({
                "code": guest_code,
                "name": guest_name,
                "table": record.get('TABLE ASSIGNED', 'Unknown'),
                "seating": record.get('SEATING ZONE', 'Unknown'),
                "designation": record.get('DESIGNATION', 'Unknown')
            })

        if len(results) >= 10:
            break

    return jsonify(sorted(results, key=lambda x: x['name']))

@app.route('/check-in', methods=['POST'])
def check_in():
    data = request.get_json()
    code = data['code'].strip().upper()
    
    records = sheet1.get_all_records()
    guest_data = next((record for record in records if record['GUEST CODE'] == code), None)

    if not guest_data:
        return jsonify({"status": "error", "message": "Guest not found"}), 404

    # Capture details
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guest_name = data.get('name', guest_data['GUEST FULL NAME'])
    seating = data.get('seating', guest_data['SEATING ZONE'])
    table = data.get('table', guest_data['TABLE ASSIGNED'])
    designation = data.get('designation', guest_data['DESIGNATION'])

    # ✅ Include designation and table when saving to Sheet 2
    new_row = [
        timestamp, code, guest_name, seating, table, designation
    ]
    sheet2.append_row(new_row)

    return jsonify({"status": "success", "message": "Check-in successful"})

@app.route('/summary')
def summary():
    guest_code = request.args.get('code', '').strip().upper()

    if not guest_code:
        return "Guest code not provided", 400

    # Fetch all guest records from Sheet 1 (Master Guest Sheet)
    records = sheet1.get_all_records()
    guest_details = next((record for record in records if record['GUEST CODE'] == guest_code), {})

    if not guest_details:
        return "Guest not found", 404

    # Fetch check-in data from Sheet 2
    checkin_records = sheet2.get_all_records()
    checkin_details = next((rec for rec in checkin_records if rec['GuestCode'] == guest_code), None)

    return render_template('summary.html',
                           code=guest_code,
                           guest_name=checkin_details.get('GuestName', guest_details.get('GUEST FULL NAME', 'Unknown')) if checkin_details else guest_details.get('GUEST FULL NAME', 'Unknown'),
                           seating_zone=guest_details.get('SEATING ZONE', 'Unknown'),
                           table_assigned=guest_details.get('TABLE ASSIGNED', 'Unknown'),
                           designation=guest_details.get('DESIGNATION', 'Unknown'),
                           checkin_status="Checked In" if checkin_details else "Not Checked In")


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
        
        # Create a new cursor for this function
        db_cursor = db.cursor(dictionary=True)
        db_cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = db_cursor.fetchone()
        db_cursor.close()  # Close the cursor after query execution

        if admin and admin['password'] == password:  # Use bcrypt in production
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
    return render_template('admin_dashboard.html', name_of_admin=admin_name, records=records)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    flash("Logged Out Successfully", "info")
    return redirect('/admin/login')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
    # app.run(debug=True)
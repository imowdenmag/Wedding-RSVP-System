from flask import Flask, request, jsonify, render_template, redirect, session, url_for, flash
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
from functools import wraps 
import csv
import pandas as pd
from flask_wtf .csrf import generate_csrf

# Load environment variables
load_dotenv()

# Load Google credentials
with open("iamadinkra-ff3a4-864ca2842b01.json", "r") as file:
    creds_dict = json.load(file)

print("✅ Google credentials loaded successfully!")

app = Flask(__name__)
app.jinja_env.filters['escapejs'] = generate_csrf

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
    sheet = client.open("J&O Wedding Guest Data 2025")
    sheet1 = sheet.worksheet("Master Guest Sheet")
    sheet2 = sheet.worksheet("Guest Check-In")
    sheet3 = sheet.worksheet("RSVP Logging")
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
    print("✅ Connected to MySQL successfully!")
except mysql.connector.Error as err:
    print(f"❌ Error connecting to MySQL: {err}")
    db = None  # Avoid crashes if connection fails

# --- Preload Guest Data ---
def load_guest_data():
    global guest_data_dict
    records = sheet1.get_values()
    headers = records[0]
    guest_data_dict = {row[1]: dict(zip(headers, row)) for row in records[1:] if len(row) > 1}
    print(f"✅ Loaded {len(guest_data_dict)} guest records into memory.")

load_guest_data()

# --- Admin login required decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/rsvp')
def rsvp():
    return render_template('rsvp.html')

def find_guest_by_code(code):
    """Fetch guest details dynamically from Google Sheets."""
    records = sheet1.get_all_records()  # Fetch latest data
    for guest in records:
        if guest['GUEST CODE'].strip().upper() == code:
            return guest  # Return guest details if found
    return None  # Return None if not found

@app.route('/check-code', methods=['POST'])
def check_code():
    data = request.get_json()
    code = data['code'].strip().upper()

    guest = find_guest_by_code(code)
    if guest:
        return jsonify({
            "status": "success",
            "redirect_url": url_for('confirm',
                code=code,
                guest_name=guest['GUEST FULL NAME'],
                seating_zone=guest.get('SEATING ZONE', 'Unknown'),
                table_assigned=guest.get('TABLE ASSIGNED', 'Unknown'),
                designation=guest.get('DESIGNATION', 'Unknown')
            )
        })
    
    return jsonify({"status": "error", "message": "Code not found"}), 404

@app.route('/confirm')
def confirm():
    return render_template('confirm.html', 
        code=request.args.get('code'),
        guest_name=request.args.get('guest_name'),
        seating_zone=request.args.get('seating_zone'),
        table_assigned=request.args.get('table_assigned'),
        designation=request.args.get('designation')
    )

@app.route('/confirm-attendance', methods=['POST'])
def confirm_attendance():
    code = request.form.get('code')
    attendance = request.form.get('attendance')

    print(f"Received code: {code}, attendance: {attendance}")

    guest = guest_data_dict.get(code)
    if guest:
        row_number = list(guest_data_dict.keys()).index(code) + 2
        sheet1.batch_update([{
            'range': f'J{row_number}',
            'values': [[attendance]]
        }])

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = [timestamp, code, guest['GUEST FULL NAME'], attendance]
        sheet3.append_row(log_entry)

        return jsonify({"status": "success", "message": "Attendance updated and logged successfully"})
    
    return jsonify({"status": "error", "message": "Guest not found"}), 404

@app.route('/confirmed')
def confirmed():
    return render_template('Yes.html')


@app.route('/declined')
def declined():
    return render_template('No.html')

# --- CHECK-IN ROUTES ---
@app.route('/checkin')
def checkin():
    return render_template('checkin.html')

@app.route('/search-guest', methods=['GET'])
def search_guest():
    query = request.args.get('query', '').strip().upper()
    if not query:
        return jsonify([])

    records = sheet1.get_all_records()  # Fetch latest guest data

    results = [
        {
            "code": guest['GUEST CODE'],
            "name": guest['GUEST FULL NAME'],
            "table": guest.get('TABLE ASSIGNED', 'Unknown'),
            "seating": guest.get('SEATING ZONE', 'Unknown'),
            "designation": guest.get('DESIGNATION', 'Unknown')
        }
        for guest in records if query in guest['GUEST CODE'].upper() or query in guest['GUEST FULL NAME'].upper()
    ][:10]

    return jsonify(sorted(results, key=lambda x: x['name']))

@app.route('/check-in', methods=['POST'])
def check_in():
    data = request.get_json()
    code = data['code'].strip().upper()
    
    guest = find_guest_by_code(code)

    if not guest:
        return jsonify({"status": "error", "message": "Guest not found"}), 404

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = [timestamp, code, guest['GUEST FULL NAME'], guest.get('SEATING ZONE', 'Unknown'), guest.get('TABLE ASSIGNED', 'Unknown'), guest.get('DESIGNATION', 'Unknown')]
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

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()

        if admin and admin['password'] == password:
            session['admin_id'] = admin['id']
            return redirect('/admin/dashboard')

        return "Invalid credentials", 401
    return render_template('admin_login.html')

@app.route('/admin/logout')
def logout():
    session.pop('admin_id', None)
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect('/admin/login')

    # Fetch admin name
    cursor.execute("SELECT name FROM admins WHERE id = %s", (session['admin_id'],))
    admin_name = cursor.fetchone()['name']

    # Get RSVP and Check-in Data
    rsvp_data = sheet1.get_all_records()
    checkin_data = sheet2.get_all_records()

    # Calculate summary stats
    total_rsvp = len([guest for guest in rsvp_data if guest['RSVP STATUS'] == 'Yes'])
    total_checked_in = len(checkin_data)
    total_guests = len(rsvp_data)

    return render_template('admin_dashboard.html', 
                           name_of_admin=admin_name, 
                           total_rsvp=total_rsvp, 
                           total_checked_in=total_checked_in,
                           total_guests=total_guests,
                           checkin_data=checkin_data)

# --- SEARCH FUNCTIONALITY ---
@app.route('/admin/search', methods=['POST'])
def search_guest_admin():
    search_query = request.form['search_query'].lower()
    rsvp_data = sheet1.get_all_records()
    
    results = [guest for guest in rsvp_data if search_query in guest['Guest FULL NAME'].lower() or search_query in guest['GUEST CODE'].lower()]
    
    return jsonify(results)

# --- MANUAL CHECK-IN ---
@app.route('/admin/checkin', methods=['POST'])
def manual_checkin():
    guest_code = request.form['guest_code']
    
    # Check if guest exists in RSVP
    rsvp_data = sheet1.get_all_records()
    guest = next((g for g in rsvp_data if g['GUEST CODE'] == guest_code), None)

    if guest:
        # Add to check-in sheet
        sheet2.append_row([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
            guest['GUEST CODE'],
            guest['GUEST FULL NAME'],
            guest['SEATING ZONE'],
            # # guest.get('Emergency Contact', ''),
            # '0',  # Devices
            # '',   # Device Details
            # '',   # Collection Password
            # '',   # Locker ID
            # 'Not Collected',  # Collection Status
            # 'No',  # Pouch Collected
            # 'No',  # Pouch Returned
            # '0',  # Number of Aides
            # ''    # Aides Details
        ])
        return jsonify({'status': 'success', 'message': 'Guest checked in successfully!'})
    else:
        return jsonify({'status': 'error', 'message': 'Guest not found!'})

# --- EDIT GUEST DETAILS ---
@app.route('/admin/edit', methods=['POST'])
def edit_guest():
    guest_code = request.form['guest_code']
    new_name = request.form['new_name']
    new_seating = request.form['new_seating']
    
    data = sheet1.get_all_records()
    row_index = next((i for i, g in enumerate(data, start=2) if g['GUEST CODE'] == guest_code), None)

    if row_index:
        sheet1.update(f"C{row_index}", new_name)  # Update Name
        sheet1.update(f"K{row_index}", new_seating)  # Update Seating Zone
        return jsonify({'status': 'success', 'message': 'Guest details updated!'})
    return jsonify({'status': 'error', 'message': 'Guest not found!'})

# --- DELETE GUEST RECORD ---
@app.route('/admin/delete', methods=['POST'])
def delete_guest():
    guest_code = request.form['guest_code']

    data = sheet1.get_all_records()
    row_index = next((i for i, g in enumerate(data, start=2) if g['GUEST CODE'] == guest_code), None)

    if row_index:
        sheet1.delete_row(row_index)
        return jsonify({'status': 'success', 'message': 'Guest record deleted!'})
    return jsonify({'status': 'error', 'message': 'Guest not found!'})

# --- EXPORT TO CSV ---
@app.route('/admin/export/csv')
def export_csv():
    data = sheet2.get_all_records()
    df = pd.DataFrame(data)
    df.to_csv('checked_in_guests.csv', index=False)
    return jsonify({'status': 'success', 'message': 'CSV exported!'})

if __name__ == '__main__':
    # port = int(os.environ.get("PORT", 8080))
    # app.run(host="0.0.0.0", port=port)
    app.run(debug=True)
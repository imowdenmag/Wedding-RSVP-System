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

        # Check if query matches code or name
        if query in guest_code or query in guest_name:
            results.append({
                "code": guest_code,
                "name": guest_name,
                "table": record.get('Table Assigned', 'Unknown'),
                "seating": record.get('SEATING ZONE', 'Unknown'),
                "designation": record.get('Designation', 'Unknown')
            })

        if len(results) >= 10:
            break  # Limit results for efficiency

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
    table = data.get('table', guest_data['Table Assigned'])
    designation = data.get('designation', guest_data['Designation'])
    emergency_contact = data.get('emergency_contact', '')
    num_devices = data.get('num_devices', '')
    device_details = data.get('device_details', '')

    # ✅ Include designation and table when saving to Sheet 2
    new_row = [
        timestamp, code, guest_name, seating, table, designation, emergency_contact,
        num_devices, device_details, "", "", "", "", "", ""
    ]
    sheet2.append_row(new_row)

    return jsonify({"status": "success", "message": "Check-in successful"})

@app.route('/summary')
def summary():
    guest_code = request.args.get('code', '').strip().upper()

    if not guest_code:
        return "Guest code not provided", 400

    # Fetch check-in data from Sheet 2
    checkin_records = sheet2.get_all_records()
    checkin_details = next((rec for rec in checkin_records if rec['GuestCode'] == guest_code), None)

    # If checked in, ensure we pull seating, table, and designation correctly
    if checkin_details:
        records = sheet1.get_all_records()
        guest_details = next((record for record in records if record['GUEST CODE'] == guest_code), {})

        return render_template('summary.html',
                               code=guest_code,
                               guest_name=checkin_details.get('GuestName', 'Unknown'),
                               seating_zone=checkin_details.get('Seating', guest_details.get('SEATING ZONE', 'Unknown')),
                               table_assigned=checkin_details.get('Table Assigned', guest_details.get('Table Assigned', 'Unknown')),
                               designation=checkin_details.get('Designation', guest_details.get('Designation', 'Unknown')),
                               checkin_status="Checked In")

    # If not checked in, pull from Sheet 1
    records = sheet1.get_all_records()
    guest_details = next((record for record in records if record['GUEST CODE'] == guest_code), None)

    if not guest_details:
        return "Guest not found", 404

    return render_template('summary.html',
                           code=guest_code,
                           guest_name=guest_details.get('GUEST FULL NAME', 'Unknown'),
                           seating_zone=guest_details.get('SEATING ZONE', 'Unknown'),
                           table_assigned=guest_details.get('Table Assigned', 'Unknown'),
                           designation=guest_details.get('Designation', 'Unknown'),
                           checkin_status="Not Checked In")

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    cursor.execute("SELECT name FROM admins WHERE id = %s", (session['admin_id'],))
    admin_name = cursor.fetchone()['name']
    records = sheet2.get_all_records()
    return render_template('admin_dashboard.html', name_of_admin=admin_name, records=records)

if __name__ == '__main__':
    # port = int(os.environ.get("PORT", 8080))
    # app.run(host="0.0.0.0", port=port)
    app.run(debug=True)

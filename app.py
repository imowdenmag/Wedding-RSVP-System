from flask import Flask, request, jsonify, render_template, redirect, session, url_for, flash, Response
from flask import send_file
import io
import gspread
from google.oauth2.service_account import Credentials
import firebase_admin
from firebase_admin import credentials, firestore
from markupsafe import Markup
import json
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
from functools import wraps 
import csv
import pandas as pd
from flask_wtf.csrf import generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import functools
import google.cloud.exceptions

logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app with enhanced security
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400000  # 24 hours
)

# Custom escapejs filter
@app.template_filter('escapejs')
def escapejs(value):
    return Markup(json.dumps(value))

# Load environment variables
load_dotenv()

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize Firebase Admin SDK with custom database
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("iamadinkra-ff3a4-firebase-adminsdk-zt74q-eacb9796ce.json")
        firebase_admin.initialize_app(cred, {
            'projectId': 'iamadinkra-ff3a4',
            'storageBucket': 'iamadinkra-ff3a4.appspot.com',
            'databaseURL': 'https://iamadinkra-ff3a4.firebaseio.com'
        })
        logging.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logging.error(f"Firebase initialization failed: {str(e)}")
        raise

# Connect to specific Firestore database
db = firestore.client()

# Security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# Load Google Sheets credentials
try:
    with open("iamadinkra-ff3a4-864ca2842b01.json", "r") as file:
        creds_dict = json.load(file)
    
    # Google Sheets setup
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

    read_credentials = Credentials.from_service_account_file("iamadinkra-ff3a4-864ca2842b01.json", scopes=SCOPES)
    write_credentials = Credentials.from_service_account_file("iamadinkra-ff3a4-65cdad8107d1.json", scopes=SCOPES)

    gc_read = gspread.authorize(read_credentials)
    gc_write = gspread.authorize(write_credentials)

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    logging.info("Google Sheets credentials loaded successfully")
except Exception as e:
    logging.error(f"Failed to load Google Sheets credentials: {str(e)}")
    raise


# Open Google Sheets with separate read and write clients
try:
    # READ client sheets
    sheet_read = gc_read.open("J&O Wedding Guest Data 2025")
    sheet1_read = sheet_read.worksheet("Master Guest Sheet")
    sheet4_read = sheet_read.worksheet("Reference Sheet")

    # WRITE client sheets
    sheet_write = gc_write.open("J&O Wedding Guest Data 2025")
    sheet1_write = sheet_write.worksheet("Master Guest Sheet")
    sheet2_write = sheet_write.worksheet("Guest Check-In")
    sheet3_write = sheet_write.worksheet("RSVP Logging")

    logging.info("✅ Connected to Google Sheets (read/write) successfully!")
except Exception as e:
    logging.error(f"❌ Error connecting to Google Sheets: {e}")
    raise

demOdata = sheet4_read.get('D2:H2')

first_row = next((row for row in demOdata if any(cell.strip() for cell in row)), None)

print("First Confirmed Rsvp Row:", first_row)

# --- Preload Guest Data ---
def load_guest_data():
    global guest_data_dict
    try:
        records = sheet1_read.get_values()
        headers = records[0]
        guest_data_dict = {row[1]: dict(zip(headers, row)) for row in records[1:] if len(row) > 1}
        logging.info(f"✅ Loaded {len(guest_data_dict)} guest records into memory.")
    except Exception as e:
        logging.error(f"Failed to load guest data: {str(e)}")
        guest_data_dict = {}


load_guest_data()

# --- Database Health Check ---
def check_firestore_connection():
    try:
        db.collection('admin').document('admin001').get()
        print("✅Firestore connected suscessfully")
        return True
    except Exception as e:
        logging.error(f"🚫Firestore connection error: {e}")
        return False

# --- Admin login required decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("Please login to access this page", "warning")
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# --- Check-in login required decorator ---
def authcheckIn_required(view_func):
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if 'checkin_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('authCheckin'))
        return view_func(*args, **kwargs)
    return wrapped_view

# --- Routes ---
@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/rsvp')
def rsvp():
    return render_template('rsvp.html')

def find_guest_by_code(code):
    try:
        records = sheet1_read.get_all_records()
        for guest in records:
            if guest['GUEST CODE'].strip().upper() == code:
                return guest
        return None
    except Exception as e:
        logging.error(f"Error finding guest by code: {str(e)}")
        return None

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

    logging.info(f"🎟️ Received RSVP - Code: {code}, Attendance: {attendance}")

    try:
        data = sheet1_read.get_all_records()
        refreshed_guest_dict = {row.get("GUEST CODE", ""): row for row in data}
        guest = refreshed_guest_dict.get(code)

        if guest:
            row_number = list(refreshed_guest_dict.keys()).index(code) + 2

            logging.info(f"📝 Updating RSVP at row {row_number} for guest: {guest.get('GUEST FULL NAME')}")

            sheet1_write.batch_update([{
                'range': f'J{row_number}',
                'majorDimension': 'ROWS',
                'values': [[attendance]]
            }])

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = [timestamp, code, guest.get("GUEST FULL NAME", ""), attendance]
            sheet3_write.append_row(log_entry)

            logging.info(f"✅ RSVP updated & logged for {code}")
            return jsonify({"status": "success", "message": "Attendance updated and logged successfully"})
        else:
            logging.warning(f"⚠️ Guest code not found after refresh: {code}")
            return jsonify({"status": "error", "message": "Guest not found"}), 404

    except Exception as e:
        logging.error(f"❌ Error updating attendance: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to update attendance"}), 500


@app.route('/confirmed')
def confirmed():
    return render_template('Yes.html')

@app.route('/declined')
def declined():
    return render_template('No.html')

# --- CHECK-IN ROUTES ---
@app.route('/auth/checkin', methods=['GET', 'POST'])
def authCheckin():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Invalid Credentials. Try again", "error")
            return render_template('authCheckin.html'), 400 
        
        try:
            checkin_doc_id = [
                'admins001', 'admins002', 'admins003', 'admins004',
                'checkIn001', 'checkIn002', 'checkIn003', 'checkIn004',
                'checkIn005', 'checkIn006', 'checkIn007', 'checkIn008'
            ]

            for doc_id in checkin_doc_id:
                checkin_doc = db.collection('admins').document(doc_id).get()

                if checkin_doc.exists:
                    data = checkin_doc.to_dict()
                    logging.info(f"🔍 Checking '{doc_id}' for username: {username}")

                    if data.get('username', '').strip().lower() == username.lower():
                        logging.info(f"✅ Username matched in '{doc_id}'")

                        if data.get('password', '').strip() == password:
                            session['checkin_id'] = doc_id
                            session['checkin_name'] = data.get('name', username)
                            logging.info(f"✅ Admin logged in: {username} (from {doc_id})")
                            return redirect('/checkin')
                        else:
                            logging.warning(f"❌ Password mismatch for {username}")
                            break
                    
            error1 = 'Incorrect username or password. Please try again.'
            return render_template('authCheckin.html', error=error1), 401
        
        except Exception as e:
            logging.error(f"🚨 Login error: {str(e)}")
            flash("An error occurred. Please try again.", "error")
            return render_template('authCheckin.html'), 500

    return render_template('authCheckin.html')

@app.route('/checkin/logout')
@authcheckIn_required
def checkin_logout():
    session.pop('checkin_id', None)
    session.pop('checkin_name', None)
    flash("You've been logged out.", "info")
    return redirect(url_for('authCheckin'))

@app.route('/checkin')
@authcheckIn_required
def checkin():
        
# Fetch admin name from Firestore using document ID
        logging.debug(f"Session data: {session}")
        checkin_adminDoc = db.collection('admins').document(session['checkin_id']).get()
        if not checkin_adminDoc.exists:
            flash("Admin account not found", "error")
            return redirect('/checkin/logout')
        
        checkin_adminData = checkin_adminDoc.to_dict()
        checkin_admin_name = checkin_adminData.get('name', 'Admin')
        checkin_admin_id = session['checkin_id']
        logging.info(f"Admin ID: {checkin_admin_id}")
        logging.info(f"Admin Name: {checkin_admin_name}")
        # Pass admin name to the template
        return render_template('checkin.html', 
                               admin_name=checkin_admin_name, 
                               admin_id=checkin_admin_id)

@app.route('/search-guest', methods=['GET'])
def search_guest():
    query = request.args.get('query', '').strip().upper()
    if not query:
        return jsonify([])

    try:
        records = sheet1_read.get_all_records()

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
    except Exception as e:
        logging.error(f"Error searching guest: {str(e)}")
        return jsonify([])

@app.route('/check-in', methods=['POST'])
def check_in():
    data = request.get_json()
    code = data['code'].strip().upper()
    attendedby = data.get('attendedby', 'Unknown')

    guest = find_guest_by_code(code)

    if not guest:
        return jsonify({"status": "error", "message": "Guest not found"}), 404

    try:
        # ✅ Check if the code has already been used
        existing_codes = sheet2_write.col_values(2)  # Column 2 holds the GuestCode
        if code in existing_codes:
            return jsonify({"status": "error", "message": "Guest has already checked in"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [
            timestamp,
            code,
            guest['GUEST FULL NAME'],
            guest.get('TABLE ASSIGNED', 'Unknown'),
            attendedby
        ]
        sheet2_write.append_row(new_row)

        return jsonify({"status": "success", "message": "Check-in successful"})

    except Exception as e:
        logging.error(f"Error during check-in: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to check-in guest"}), 500

@app.route('/summary')
def summary():
    guest_code = request.args.get('code', '').strip().upper()

    if not guest_code:
        return "Guest code not provided", 400

    try:
        records = sheet1_read.get_all_records()
        guest_details = next((record for record in records if record['GUEST CODE'] == guest_code), {})

        if not guest_details:
            return "Guest not found", 404

        checkin_records = sheet2_write.get_all_records()
        checkin_details = next((rec for rec in checkin_records if rec['GuestCode'] == guest_code), None)

        return render_template('summary.html',
            code=guest_code,
            guest_name=checkin_details.get('GuestName', guest_details.get('GUEST FULL NAME', 'Unknown')) if checkin_details else guest_details.get('GUEST FULL NAME', 'Unknown'),
            seating_zone=guest_details.get('SEATING ZONE', 'Unknown'),
            table_assigned=guest_details.get('TABLE ASSIGNED', 'Unknown'),
            designation=guest_details.get('DESIGNATION', 'Unknown'),
            checkin_status="Checked In" if checkin_details else "Not Checked In")
    except Exception as e:
        logging.error(f"Error generating summary: {str(e)}")
        return "Error generating summary", 500

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Username and password are required", "error")
            return render_template('admin_login.html'), 400

        try:
            # List of Firestore admin document IDs
            admin_docs_to_check = ['admins001', 'admins002', 'admins003', 'admins004']

            for doc_id in admin_docs_to_check:
                admin_doc = db.collection('admins').document(doc_id).get()

                if admin_doc.exists:
                    data = admin_doc.to_dict()
                    logging.info(f"🔍 Checking '{doc_id}' for username: {username}")

                    if data.get('username', '').strip().lower() == username.lower():
                        logging.info(f"✅ Username matched in '{doc_id}'")

                        if data.get('password', '').strip() == password:
                            session['admin_id'] = doc_id
                            session['admin_name'] = data.get('name', username)
                            logging.info(f"✅ Admin logged in: {username} (from {doc_id})")
                            return redirect('/admin/dashboard')
                        else:
                            logging.warning(f"❌ Password mismatch for {username}")
                            break  # stop checking after username match

            error = 'Incorrect username or password. Please try again.'
            return render_template('admin_login.html', error=error), 401

        except Exception as e:
            logging.error(f"🚨 Login error: {str(e)}")
            flash("An error occurred. Please try again.", "error")
            return render_template('admin_login.html'), 500

    return render_template('admin_login.html')

@app.route('/admin/logout')
def logout():
    session.pop('admin_id', None)
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    try:
        # Fetch admin ID safely
        admin_id = session.get('admin_id')
        if not admin_id:
            flash("Session expired. Please log in again.", "warning")
            return redirect('/admin/login')

        # Fetch admin name from Firestore
        admin_doc = db.collection('admins').document(admin_id).get()
        if not admin_doc.exists:
            flash("Admin account not found", "error")
            return redirect('/admin/logout')

        admin_data = admin_doc.to_dict()
        admin_name = admin_data.get('name', 'Admin')

        # Use sheet4 for Reference Sheet
        reference_sheet = sheet4_read

       # Fetch stats from Reference Sheet (row 2, cols D to H)
        stats_cells = reference_sheet.range('D2:H2')
        seating_cells = reference_sheet.range('J2:AG2')

        if len(seating_cells) != 24:
            logging.error(f"Expected 24 cells in range J2:AH2, got {len(seating_cells)}")
            raise ValueError("Reference sheet format error.")

        # Extract and safely parse each value
        try:
            kyebi = int(seating_cells[0].value or 0),
            inkorodu = int(seating_cells[1].value or 0)
            osu = int(seating_cells[2].value or 0)
            konongo = int(seating_cells[3].value or 0)
            jo_squad = int(seating_cells[4].value or 0)
            table_1 = int(seating_cells[5].value or 0)
            table_2 = int(seating_cells[6].value or 0)
            table_3 = int(seating_cells[7].value or 0)
            table_4 = int(seating_cells[8].value or 0)
            table_5 = int(seating_cells[9].value or 0)
            table_6 = int(seating_cells[10].value or 0)
            table_7 = int(seating_cells[11].value or 0)
            table_8 = int(seating_cells[12].value or 0)
            table_9 = int(seating_cells[13].value or 0)
            table_10 = int(seating_cells[14].value or 0)
            table_11 = int(seating_cells[15].value or 0)
            table_12 = int(seating_cells[16].value or 0)
            table_13 = int(seating_cells[17].value or 0)
            table_14 = int(seating_cells[18].value or 0)
            table_15 = int(seating_cells[19].value or 0)
            table_16 = int(seating_cells[20].value or 0)
            table_17 = int(seating_cells[21].value or 0)
            table_18 = int(seating_cells[22].value or 0)
            high_table = int(seating_cells[23].value or 0)
        except ValueError as e:
            logging.error(f"Invalid numeric value in Reference Sheet: {e}")
            raise


        if len(stats_cells) != 5:
            logging.error(f"🔥Expected 5 cells in range D2:H2, got {len(stats_cells)}")
            raise ValueError("Reference sheet format error.")

        # Extract and safely parse each value
        try:
            total_confirmed_rsvp = int(stats_cells[0].value or 0)
            total_declined_rsvp = int(stats_cells[1].value or 0)
            total_rsvp = int(stats_cells[2].value or 0)
            total_guests = int(stats_cells[3].value or 0)
            total_checked_in = int(stats_cells[4].value or 0)
        except ValueError as e:
            logging.error(f"Invalid numeric value in Reference Sheet: {e}")
            raise

        # Fetch check-in data from sheet2 (Check-in Sheet)
        checkin_data = sorted(sheet2_write.get_all_records(), key=lambda x: x.get('TimeStamp', ''), reverse=False)

        return render_template(
            'admin_dashboard.html', 
            name_of_admin=admin_name, 
            confirmed_rsvp=total_confirmed_rsvp,
            declined_rsvp=total_declined_rsvp,
            total_rsvp=total_rsvp,
            total_checked_in=total_checked_in,
            total_guests=total_guests,
            checkin_data=checkin_data,
            kyebi=kyebi,
            inkorodu=inkorodu,
            osu=osu,
            konongo=konongo,
            jo_squad=jo_squad,
            table_1=table_1,
            table_2=table_2,
            table_3=table_3,
            table_4=table_4,
            table_5=table_5,
            table_6=table_6,
            table_7=table_7,
            table_8=table_8,
            table_9=table_9,
            table_10=table_10,
            table_11=table_11,
            table_12=table_12,
            table_13=table_13,
            table_14=table_14,
            table_15=table_15,
            table_16=table_16,
            table_17=table_17,
            table_18=table_18,
            high_table=high_table
        )

    except Exception as e:
        logging.error(f"Dashboard error: {str(e)}")
        flash("Error loading dashboard", "error")
        return redirect('/admin/login')
    
    # -- Ajax call to update the check-in status -- 
@app.route('/admin/fetch-checkin-data')
@login_required
def fetch_checkin_data():
    try:
        checkin_data = sorted(sheet2_write.get_all_records(), key=lambda x: x.get('TimeStamp', ''), reverse=False)
        return jsonify({'status': 'success', 'data': checkin_data})
    except Exception as e:
        logging.error(f"Error fetching check-in data: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to fetch check-in data.'})
    
@app.route('/admin/fetch-dashboard-stats')
@login_required
def fetch_dashboard_stats():
    try:
        stats_cells = sheet4_read.range('D2:H2')
        seating_cells = sheet4_read.range('J2:AG2')

        if len(seating_cells) != 24:
            return jsonify({'status': 'error', 'message': 'Invalid seating format'})

        if len(stats_cells) != 5:
            return jsonify({'status': 'error', 'message': 'Invalid stats format'})

        data = {
            'confirmed_rsvp': int(stats_cells[0].value or 0),
            'declined_rsvp': int(stats_cells[1].value or 0),
            'total_rsvp': int(stats_cells[2].value or 0),
            'total_guests': int(stats_cells[3].value or 0),
            'total_checked_in': int(stats_cells[4].value or 0),
            'kyebi': int(seating_cells[0].value or 0),
            'inkorodu': int(seating_cells[1].value or 0),
            'osu': int(seating_cells[2].value or 0),
            'konongo': int(seating_cells[3].value or 0),
            'jo_squad': int(seating_cells[4].value or 0),
            'table_1': int(seating_cells[5].value or 0),
            'table_2': int(seating_cells[6].value or 0),
            'table_3': int(seating_cells[7].value or 0),
            'table_4': int(seating_cells[8].value or 0),
            'table_5': int(seating_cells[9].value or 0),
            'table_6': int(seating_cells[10].value or 0),
            'table_7': int(seating_cells[11].value or 0),
            'table_8': int(seating_cells[12].value or 0),
            'table_9': int(seating_cells[13].value or 0),
            'table_10': int(seating_cells[14].value or 0),
            'table_11': int(seating_cells[15].value or 0),
            'table_12': int(seating_cells[16].value or 0),
            'table_13': int(seating_cells[17].value or 0),
            'table_14': int(seating_cells[18].value or 0),
            'table_15': int(seating_cells[19].value or 0),
            'table_16': int(seating_cells[20].value or 0),
            'table_17': int(seating_cells[21].value or 0),
            'table_18': int(seating_cells[22].value or 0),
            'high_table': int(seating_cells[23].value or 0)
        }

        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        logging.error(f"Error fetching dashboard stats: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to fetch stats.'})

# --- SEARCH FUNCTIONALITY ---
@app.route('/admin/search', methods=['POST'])
@login_required
def search_guest_admin():
    search_query = request.form.get('search_query', '').lower()
    if not search_query:
        return jsonify([])
    
    try:
        rsvp_data = sheet1_read.get_all_records()
        results = [guest for guest in rsvp_data if search_query in guest['Guest FULL NAME'].lower() or search_query in guest['GUEST CODE'].lower()]
        return jsonify(results)
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        return jsonify([])

# --- MANUAL CHECK-IN ---
@app.route('/admin/checkin', methods=['POST'])
@login_required
def manual_checkin():
    guest_code = request.form.get('guest_code', '').strip()
    if not guest_code:
        return jsonify({'status': 'error', 'message': 'Guest code required'}), 400
    
    try:
        rsvp_data = sheet1_read.get_all_records()
        guest = next((g for g in rsvp_data if g['GUEST CODE'] == guest_code), None)

        if guest:
            sheet2_write.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                guest['GUEST CODE'],
                guest['GUEST FULL NAME'],
                guest['SEATING ZONE'],
                guest.get('TABLE ASSIGNED', 'Unknown'),
                guest.get('DESIGNATION', 'Unknown')
            ])
            return jsonify({'status': 'success', 'message': 'Guest checked in successfully!'})
        
        return jsonify({'status': 'error', 'message': 'Guest not found!'}), 404
    except Exception as e:
        logging.error(f"Manual check-in error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to check in guest'}), 500

# --- EDIT GUEST DETAILS ---
@app.route('/admin/edit', methods=['POST'])
@login_required
def edit_guest():
    guest_code = request.form.get('guest_code', '').strip()
    new_name = request.form.get('new_name', '').strip()
    new_seating = request.form.get('new_seating', '').strip()

    if not guest_code or not new_name:
        return jsonify({'status': 'error', 'message': 'Guest code and name are required'}), 400

    try:
        data = sheet1_read.get_all_records()
        row_index = next((i for i, g in enumerate(data, start=2) if g['GUEST CODE'] == guest_code), None)

        if row_index:
            sheet1_write.update(f"C{row_index}", new_name)  # Update Name
            if new_seating:
                sheet1_write.update(f"K{row_index}", new_seating)  # Update Seating Zone
            return jsonify({'status': 'success', 'message': 'Guest details updated!'})
        
        return jsonify({'status': 'error', 'message': 'Guest not found!'}), 404
    except Exception as e:
        logging.error(f"Edit guest error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to update guest'}), 500

# --- DELETE GUEST RECORD ---
@app.route('/admin/delete', methods=['POST'])
@login_required
def delete_guest():
    guest_code = request.form.get('guest_code', '').strip()
    if not guest_code:
        return jsonify({'status': 'error', 'message': 'Guest code required'}), 400

    try:
        data = sheet1_read.get_all_records()
        row_index = next((i for i, g in enumerate(data, start=2) if g['GUEST CODE'] == guest_code), None)

        if row_index:
            sheet1_write.delete_row(row_index)
            return jsonify({'status': 'success', 'message': 'Guest record deleted!'})
        
        return jsonify({'status': 'error', 'message': 'Guest not found!'}), 404
    except Exception as e:
        logging.error(f"Delete guest error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to delete guest'}), 500

# --- EXPORT TO CSV ---
@app.route('/admin/export/csv')
@login_required
def export_csv():
    try:
        # Get data from Google Sheet
        data = sheet2_write.get_all_records()
        df = pd.DataFrame(data)

        # Create in-memory file-like object
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # Create response with proper headers
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=checked_in_guests.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )

        return response

    except Exception as e:
        logging.error(f"Export CSV error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to export CSV'}), 500
    
@app.errorhandler(404)
def handle_404(e):
    return render_template('404error.html'), 404


# Health check endpoint
@app.route('/health')
def health_check():
    if check_firestore_connection():
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'sheets': 'connected' if sheet1_read else 'disconnected'
        }), 200
    return jsonify({
        'status': 'unhealthy',
        'database': 'disconnected',
        'sheets': 'connected' if sheet1_read else 'disconnected'
    }), 503

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
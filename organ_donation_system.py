# organ_donation_system.py
"""
Smart Organ Donation Management System
Single-file Flask app (Flask 3+ compatible) with:
- Donor + Recipient modules
- Admin auth (session)
- Advanced search (organ, blood, city)
- Dashboard (Chart.js)
- CSV export
- Bootstrap 5 UI
- Donor lifecycle (Registered → Verified → Harvested)
- Admin approval before donor visibility
- Auto recipient matching on harvest
- WhatsApp alert integration (Twilio) + stubs
"""

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from flask import render_template, request, redirect, url_for, session, flash
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
import requests
from sqlalchemy import text
import csv
import io
import os
from werkzeug.security import generate_password_hash, check_password_hash
from twilio.rest import Client
from random import randint
from itsdangerous import URLSafeTimedSerializer


# ------------------ Helper: Check if mobile already registered ------------------


def mobile_exists(mobile):
    donor = Donor.query.filter_by(mobile=mobile).first()
    recipient = RecipientRequest.query.filter_by(mobile=mobile).first()
    return donor or recipient

# ----------------------- App setup -----------------------


app = Flask(__name__)
SECRET_KEY = os.environ.get("FODS_SECRET_KEY", "fods-dev-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///organ_donation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.secret_key = SECRET_KEY

db = SQLAlchemy(app)
s = URLSafeTimedSerializer(app.secret_key)

# 🔐 Twilio configuration (use environment variables in production)
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE")

client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# ------------------------- ✅ WhatsApp Utility Functions -------------------------


def send_whatsapp_message(mobile, message):
    """Generic WhatsApp message sender via Twilio Business API"""
    try:
        formatted_mobile = mobile if mobile.startswith(
            "+") else f"+91{mobile}"  # Default India code
        msg = client.messages.create(
            from_="whatsapp:+14155238886",  # Replace with your approved number
            to=f"whatsapp:{formatted_mobile}",
            body=message
        )
        print(f"[WhatsApp Sent ✅] To: {formatted_mobile}, SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"[WhatsApp Error ❌] Failed to send message to {mobile}: {e}")
        return False


def send_whatsapp_otp(mobile):
    """Sends OTP with expiry via WhatsApp"""
    otp = str(randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    session['otp'] = otp
    session['otp_mobile'] = mobile
    session['otp_expires'] = expires_at.isoformat()

    msg = f"Your LifeBridge verification code is {otp}. It expires in 5 minutes. Please do not share this with anyone."
    if send_whatsapp_message(mobile, msg):
        print(f"[OTP Sent via WhatsApp] {mobile}: {otp}")
        return True
    return False


def send_allocation_notification(donor, recipient):
    """
    Sends WhatsApp notifications after successful organ allocation.
    - Donor: Appreciation message
    - Recipient: ONLY hospital details (no donor identity)
    """

    # 🫀 Donor message (allowed)
    donor_msg = (
        f"🫀  Organ Donation Update\n\n"
        f"Dear {donor.name},\n\n"
        f"You have been successfully matched for a {recipient.organ_needed} donation.\n"
        f"Thank you for your life-saving contribution.\n\n"
        f"— Smart Organ Donation System"
    )

    donor_sent = send_whatsapp_message(donor.mobile, donor_msg)

    # 💚 Recipient message (hospital details ONLY)
    if getattr(donor, 'hospital', None):
        h = donor.hospital
        recipient_msg = (
            f"💚  Organ Transplant Update\n\n"
            f"Dear {recipient.patient_name},\n\n"
            f"A suitable organ for your {recipient.organ_needed} transplant has been allocated.\n\n"
            f"🏥 Hospital Details:\n"
            f"Hospital Name: {h.hospital_name}\n"
            f"City: {h.city}\n"
            f"Contact Number: {h.mobile}\n"
            f"Email: {h.email}\n\n"
            f"Please contact the hospital immediately for further medical procedures.\n\n"
            f"⚠️ This message is confidential.\n\n"
            f"— Smart Organ Donation System"
        )
    else:
        # Fallback without donor identity
        recipient_msg = (
            f"💚  Organ Transplant Update\n\n"
            f"Dear {recipient.patient_name},\n\n"
            f"A suitable organ for your {recipient.organ_needed} transplant has been allocated.\n"
            f"Please contact the system administrator or registered hospital for next steps.\n\n"
            f"— Smart Organ Donation System"
        )

    recipient_sent = send_whatsapp_message(recipient.mobile, recipient_msg)

    print(
        f"[Allocation WhatsApp] Donor sent: {donor_sent}, Recipient sent: {recipient_sent}"
    )
    return donor_sent and recipient_sent

# ----------------------- Config: admin credentials -----------------------


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@aaa"

# ----------------------- Models -----------------------


class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)   # ✅ UNIQUE
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    blood_group = db.Column(db.String(10))
    organs = db.Column(db.String(200))  # comma separated
    contact = db.Column(db.String(120))
    city = db.Column(db.String(120))
    # Associate donor record with a hospital when registered/reported by a hospital
    hospital_id = db.Column(
        db.Integer, db.ForeignKey('hospital.id'), nullable=True)
    hospital = db.relationship('Hospital', foreign_keys=[hospital_id])
    available = db.Column(db.Boolean, default=True)
    # Registered → Verified → Harvested
    status = db.Column(db.String(20), default="Registered")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    password = db.Column(db.String(200), nullable=False)

    def organs_list(self):
        return [o.strip().lower() for o in (self.organs or "").split(",") if o.strip()]


class RecipientRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)   # ✅ UNIQUE
    age = db.Column(db.Integer)
    organ_needed = db.Column(db.String(80), nullable=False)
    blood_group = db.Column(db.String(10))
    city = db.Column(db.String(120))
    notes = db.Column(db.Text)
    status = db.Column(db.String(40), default='Pending')  # Pending → Allocated
    matched_donor_id = db.Column(
        db.Integer, db.ForeignKey('donor.id'), nullable=True)
    matched_donor = db.relationship('Donor', foreign_keys=[matched_donor_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    password = db.Column(db.String(200), nullable=False)
    emergency_level = db.Column(db.String(20), default="Medium")


class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hospital_name = db.Column(db.String(150), nullable=False, unique=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    license_verified = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DeathReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donor.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey(
        'hospital.id'), nullable=False)
    donor = db.relationship('Donor', foreign_keys=[donor_id])
    hospital = db.relationship('Hospital', foreign_keys=[hospital_id])
    death_time = db.Column(db.DateTime, nullable=False)
    cause_of_death = db.Column(db.String(200))
    medical_cert_number = db.Column(db.String(100))
    # Reported, Verified, Organs-Ready, Completed
    status = db.Column(db.String(50), default='Reported')
    next_of_kin_name = db.Column(db.String(120))
    next_of_kin_mobile = db.Column(db.String(15))
    next_of_kin_relation = db.Column(db.String(50))
    organs_harvested = db.Column(db.String(300))  # comma separated
    harvested_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    reported_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20))  # 'donor', 'recipient', 'hospital'
    user_id = db.Column(db.Integer)
    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------------- Runtime migrations -----------------------


with app.app_context():
    db.create_all()

    def _has_column(table, column):
        res = db.session.execute(
            text(f"PRAGMA table_info('{table}')")).fetchall()
        return any(r[1] == column for r in res)

    migrations = [
        ('donor', 'available', "INTEGER DEFAULT 1"),
        ('donor', 'hospital_id', "INTEGER"),
        ('recipient_request', 'matched_donor_id', "INTEGER"),
        ('donor', 'created_at', "DATETIME"),
        ('donor', 'status', "TEXT DEFAULT 'Registered'"),
        ('recipient_request', 'emergency_level', "TEXT DEFAULT 'Medium'"),
    ]

    for table, column, definition in migrations:
        try:
            if not _has_column(table, column):
                db.session.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                db.session.commit()
                print(f"[migrate] Added column {column} to {table}")
        except Exception as e:
            print(f"[migrate] Failed to add column {column} to {table}: {e}")

    # Backfill donor.hospital_id from latest DeathReport where available
    try:
        backfilled = 0
        for d in Donor.query.filter(Donor.hospital_id == None).all():
            rpt = DeathReport.query.filter_by(donor_id=d.id).order_by(
                DeathReport.reported_at.desc()).first()
            if rpt:
                d.hospital_id = rpt.hospital_id
                db.session.add(d)
                backfilled += 1
        if backfilled:
            db.session.commit()
            print(
                f"[backfill] Set hospital_id for {backfilled} donor(s) from DeathReport")
    except Exception as e:
        print(f"[backfill] Failed to backfill donor.hospital_id: {e}")

# ----------------------- Helper utilities -----------------------


def require_admin():
    if not session.get('admin_logged_in'):
        flash('Please login as admin to access that page.')
        return False
    return True


def donor_to_row(d):
    return [d.id, d.name, d.age, d.gender, d.blood_group, d.organs, d.contact, d.city, 'Yes' if d.available else 'No', d.status]


def request_to_row(r):
    return [r.id, r.patient_name, r.age, r.organ_needed, r.blood_group, r.city, r.status, r.matched_donor.name if r.matched_donor else '']


def create_notification(user_type, user_id, message):
    n = Notification(user_type=user_type, user_id=user_id, message=message)
    db.session.add(n)
    db.session.commit()

# ------------------------- OTP via Textbelt -------------------------


def send_otp_textbelt(mobile, otp):
    """
    Sends OTP via Textbelt free API. If it fails, prints OTP in console.
    Works for local testing without sending real SMS.
    """
    url = "https://textbelt.com/text"
    payload = {
        "phone": mobile,
        "message": f"Your OTP for FODS is {otp}",
        "key": "textbelt"  # free tier key
    }

    try:
        resp = requests.post(url, data=payload)
        result = resp.json()
        if result.get('success'):
            print(f"[OTP-Sent] OTP for {mobile}: {otp}")
            return True
        else:
            raise Exception(result.get('error', 'Unknown error'))
    except Exception as e:
        print(
            f"[OTP-Fallback] OTP for {mobile} is {otp} (Textbelt failed: {e})")
        return True

# ----------------------- Auto-matching helper -----------------------


def auto_match(donor):
    """
    Auto-match ONE harvested donor to ONE pending recipient.
    Priority:
    - Organ match
    - Blood group match (if available)
    """

    donor_organs = donor.organs_list()
    donor_blood = (donor.blood_group or '').strip().lower()

    recipients = RecipientRequest.query.filter(
        RecipientRequest.status == "Pending"
    ).order_by(RecipientRequest.created_at.asc()).all()

    for r in recipients:
        need = (r.organ_needed or '').strip().lower()
        r_blood = (r.blood_group or '').strip().lower()

        organ_match = any(need in o or o in need for o in donor_organs)
        blood_match = (
            donor_blood == r_blood) if donor_blood and r_blood else True

        if organ_match and blood_match:
            # ✅ Allocate ONE recipient
            r.status = "Allocated"
            r.matched_donor_id = donor.id

            donor.available = False
            donor.status = "Harvested"

            db.session.add(r)
            db.session.add(donor)
            db.session.commit()

            # Notifications
            create_notification(
                'recipient',
                r.id,
                f"A {r.organ_needed} has been allocated to you."
            )
            create_notification(
                'donor',
                donor.id,
                f"You have been matched for {r.organ_needed} donation."
            )

            try:
                send_allocation_notification(donor, r)
            except Exception as e:
                print(f"[auto_match] WhatsApp failed: {e}")

            print(
                f"[auto_match] Donor {donor.id} allocated to recipient {r.id}")
            return True  # 🔴 STOP AFTER FIRST MATCH


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

# ----------------------- Public routes -----------------------


@app.route('/')
def index():
    total_donors = Donor.query.count()
    total_requests = RecipientRequest.query.count()
    available_donors = Donor.query.filter_by(available=True).count()
    return render_template('index.html', total_donors=total_donors, total_requests=total_requests, available_donors=available_donors)


@app.route('/how_it_works')
def how_it_works():
    """Renders the How It Works / Process Flow page"""
    total_donors = Donor.query.count()
    total_requests = RecipientRequest.query.count()
    available_donors = Donor.query.filter_by(available=True).count()
    return render_template('how_it_works.html', total_donors=total_donors, total_requests=total_requests, available_donors=available_donors)

# ----------------------- Donor & Recipient: Auth + Dashboards -----------------------


@app.route('/donor/register', methods=['GET', 'POST'])
def donor_register():
    if request.method == 'POST':
        if not session.get('hospital_id'):
            flash('Donor registration is allowed only from a registered hospital. Please login as hospital.', 'warning')
            return redirect(url_for('hospital_login'))
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        age = request.form.get('age')
        gender = request.form.get('gender')
        blood_group = request.form.get('blood_group')
        organs = request.form.get('organs')
        contact = request.form.get('contact')
        city = request.form.get('city')
        password = request.form.get('password')

        if mobile_exists(mobile):
            flash("⚠️ This mobile number is already registered.", "warning")
            return render_template('donor_register.html', name=name, mobile=mobile)

        hashed_password = generate_password_hash(password or "")

        donor = Donor(
            name=name,
            mobile=mobile,
            age=int(age) if age else None,
            gender=gender,
            blood_group=blood_group,
            organs=organs,
            contact=contact,
            city=city,
            password=hashed_password,
            hospital_id=session.get('hospital_id') if session.get(
                'hospital_id') else None,
            available=False,
            status="Registered"
        )

        db.session.add(donor)
        db.session.commit()
        flash("✅ Donor registered successfully! Awaiting admin approval.", "success")
        return redirect(url_for('hospital_dashboard'))

    return render_template('donor_register.html')


@app.route('/donor/logout')
def donor_logout():
    session.pop('donor_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('hospital_dashboard'))


@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        donor = Donor.query.filter_by(mobile=mobile).first()

        if donor and password and check_password_hash(donor.password, password):
            session['donor_id'] = donor.id
            session['donor_name'] = donor.name
            flash("✅ Login successful", "success")
            return redirect(url_for('donor_dashboard'))

        flash("❌ Invalid mobile or password", "danger")

    return render_template('donor_login.html')


@app.route('/donor/dashboard')
def donor_dashboard():
    donor_id = session.get('donor_id')
    if not donor_id:
        flash('Please log in to access your dashboard.', 'warning')
        return redirect(url_for('hospital_dashboard'))

    donor = Donor.query.get_or_404(donor_id)
    notifications = Notification.query.filter_by(
        user_type='donor', user_id=donor.id).order_by(Notification.created_at.desc()).all()

    return render_template('donor_dashboard.html', donor=donor, notifications=notifications)


@app.route('/donor/profile/edit', methods=['GET', 'POST'])
def donor_edit_profile():
    donor_id = session.get('donor_id')
    if not donor_id:
        flash('Please log in to edit your profile.', 'warning')
        return redirect(url_for('hospital_dashboard'))

    donor = Donor.query.get_or_404(donor_id)

    if request.method == 'POST':
        donor.name = request.form.get('name')
        donor.age = request.form.get('age')
        donor.gender = request.form.get('gender')
        donor.blood_group = request.form.get('blood_group')
        donor.organs = request.form.get('organs')
        donor.city = request.form.get('city')
        donor.available = True if request.form.get('available') else False
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            donor.password = generate_password_hash(new_password.strip())

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('donor_dashboard'))

    return render_template('donor_edit_profile.html', donor=donor)

# ----------------------- Recipient: Auth + Dashboard -----------------------


@app.route('/recipient/register', methods=['GET', 'POST'])
def recipient_register():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        organ_needed = request.form.get('organ_needed')
        blood_group = request.form.get('blood_group')
        city = request.form.get('city')

        if mobile_exists(mobile):
            flash(
                "⚠️ This mobile number is already registered with another account.",
                "warning"
            )
            return render_template(
                'recipient_register.html',
                patient_name=patient_name,
                mobile=mobile
            )

        hashed_password = generate_password_hash(password or "")

        # ✅ ALWAYS register recipient as Pending
        recipient = RecipientRequest(
            patient_name=patient_name,
            mobile=mobile,
            password=hashed_password,
            organ_needed=organ_needed,
            blood_group=blood_group,
            city=city,
            status="Pending"
        )

        db.session.add(recipient)
        db.session.commit()

        flash(
            "✅ Recipient registered successfully. Your request is pending and will be matched once a suitable donor is available.",
            "success"
        )
        return redirect(url_for('recipient_login'))

    return render_template('recipient_register.html')


@app.route('/recipient/login', methods=['GET', 'POST'])
def recipient_login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        recipient = RecipientRequest.query.filter_by(mobile=mobile).first()

        if recipient and password and check_password_hash(recipient.password, password):
            session['recipient_id'] = recipient.id
            session['recipient_name'] = recipient.patient_name
            flash("✅ Login successful!", "success")
            return redirect(url_for('recipient_dashboard'))
        else:
            flash("❌ Invalid mobile number or password", "danger")

    return render_template('recipient_login.html')


@app.route('/recipient/logout')
def recipient_logout():
    session.pop('recipient_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


@app.route('/recipient/dashboard')
def recipient_dashboard():
    recipient_id = session.get('recipient_id')
    if not recipient_id:
        flash('Please log in to access your dashboard.', 'warning')
        return redirect(url_for('get_started'))

    recipient = RecipientRequest.query.get_or_404(recipient_id)
    notifications = Notification.query.filter_by(
        user_type='recipient', user_id=recipient.id).order_by(Notification.created_at.desc()).all()

    matched_donor = None
    if recipient.matched_donor_id and recipient.status == 'Allocated':
        matched_donor = Donor.query.get(recipient.matched_donor_id)
        if matched_donor and not any(n.message.startswith("Good news!") for n in notifications):
            match_msg = f"Good news! Donor has been matched for your {recipient.organ_needed} request"
            create_notification('recipient', recipient.id, match_msg)
            notifications = Notification.query.filter_by(
                user_type='recipient', user_id=recipient.id).order_by(Notification.created_at.desc()).all()

    return render_template('recipient_dashboard.html',
                           recipient=recipient,
                           matched_donor=matched_donor,
                           notifications=notifications)


@app.route('/recipient/profile/edit', methods=['GET', 'POST'])
def recipient_edit_profile():
    recipient_id = session.get('recipient_id')
    if not recipient_id:
        flash('Please log in to edit your profile.', 'warning')
        return redirect(url_for('recipient_login'))

    recipient = RecipientRequest.query.get_or_404(recipient_id)

    if request.method == 'POST':
        recipient.patient_name = request.form.get('patient_name')
        recipient.age = request.form.get('age')
        recipient.organ_needed = request.form.get('organ_needed')
        recipient.blood_group = request.form.get('blood_group')
        recipient.city = request.form.get('city')
        recipient.notes = request.form.get('notes')

        new_password = request.form.get('password')
        if new_password and new_password.strip():
            recipient.password = generate_password_hash(new_password.strip())

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('recipient_dashboard'))

    return render_template('recipient_edit_profile.html', recipient=recipient)

# ----------------------- Notifications -----------------------


@app.route('/notifications/mark_read/<int:notification_id>')
def mark_notification_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    n.is_read = True
    db.session.commit()
    flash('Notification marked as read.', 'info')
    ref = request.referrer or url_for('index')
    return redirect(ref)

# ----------------------- Admin: auth + dashboard -----------------------


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login successful.')
            return redirect(url_for('admin'))
        flash('Invalid credentials.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out.')
    return redirect(url_for('index'))


@app.route('/admin')
def admin():
    if not require_admin():
        return redirect(url_for('login'))
    donors = Donor.query.order_by(Donor.created_at.asc()).all()
    requests = RecipientRequest.query.order_by(
        RecipientRequest.created_at.asc()).all()

    death_reports = DeathReport.query.order_by(
        DeathReport.reported_at.desc()).all()

    hospitals = Hospital.query.order_by(Hospital.created_at.desc()).all()

    organ_counts = {}
    for d in Donor.query.all():
        for o in d.organs_list():
            organ_counts[o] = organ_counts.get(o, 0) + 1

    city_counts = {}
    for d in Donor.query.all():
        c = (d.city or '').strip().title()
        if c:
            city_counts[c] = city_counts.get(c, 0) + 1

    status_counts = {}
    for r in RecipientRequest.query.all():
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    organs_labels = list(organ_counts.keys())
    organs_counts = [organ_counts[k] for k in organs_labels]
    city_labels = list(city_counts.keys())
    city_counts_list = [city_counts[k] for k in city_labels]
    status_labels = list(status_counts.keys())
    status_counts_list = [status_counts[k] for k in status_labels]

    total_death_reports = len(death_reports)
    organs_harvested_count = len(
        [r for r in death_reports if r.organs_harvested])

    return render_template('admin.html',
                           donors=donors,
                           requests=requests,
                           death_reports=death_reports,
                           hospitals=hospitals,
                           total_death_reports=total_death_reports,
                           organs_harvested_count=organs_harvested_count,
                           organs_labels=organs_labels,
                           organs_counts=organs_counts,
                           city_labels=city_labels,
                           city_counts=city_counts_list,
                           status_labels=status_labels,
                           status_counts=status_counts_list)


@app.route('/delete/donor/<int:donor_id>')
def delete_donor(donor_id):
    if not require_admin():
        return redirect(url_for('login'))
    d = Donor.query.get_or_404(donor_id)
    db.session.delete(d)
    db.session.commit()
    flash('Donor deleted.')
    return redirect(url_for('admin'))


@app.route('/toggle/donor/<int:donor_id>')
def toggle_availability(donor_id):
    if not require_admin():
        return redirect(url_for('login'))
    d = Donor.query.get_or_404(donor_id)
    d.available = not bool(d.available)
    db.session.commit()
    flash(f"Donor availability set to {'Yes' if d.available else 'No'}.")
    return redirect(url_for('admin'))


@app.route('/delete/request/<int:request_id>')
def delete_request(request_id):
    if not require_admin():
        return redirect(url_for('login'))
    r = RecipientRequest.query.get_or_404(request_id)
    db.session.delete(r)
    db.session.commit()
    flash('Request deleted.')
    return redirect(url_for('admin'))


@app.route('/view-matches/<int:request_id>')
def view_matches(request_id):
    if not require_admin():
        return redirect(url_for('login'))

    # Get recipient request
    req = RecipientRequest.query.get_or_404(request_id)

    # -------------------------------
    # CASE 1: Already Allocated
    # -------------------------------
    if req.status == "Allocated" and req.matched_donor_id:
        donor = Donor.query.get_or_404(req.matched_donor_id)
        hospital = donor.hospital  # may be None

        return render_template(
            'view_matches.html',
            req=req,
            donor=donor,
            hospital=hospital,
            matches=[]
        )

    # -------------------------------
    # CASE 2: Not Allocated → show matches
    # -------------------------------
    organ = (req.organ_needed or '').strip().lower()
    blood = (req.blood_group or '').strip().lower()
    city = (req.city or '').strip().lower()

    candidates = Donor.query.filter_by(
        available=True,
        status="Verified"
    ).all()

    def _match_score(donor):
        score = 0
        # organ match highest weight
        donor_organs = donor.organs_list()
        if organ and any(organ in o or o in organ for o in donor_organs):
            score += 70
        # blood match medium
        d_blood = (donor.blood_group or '').strip().lower()
        if blood and d_blood and d_blood == blood:
            score += 20
        # city match small boost
        if city and (donor.city or '').strip().lower() == city:
            score += 10
        return score

    matches = []
    for d in candidates:
        s = _match_score(d)
        if s == 0:
            # skip donors with no relevance
            continue
        matches.append({'donor': d, 'score': s})

    # sort by score desc
    matches.sort(key=lambda x: x['score'], reverse=True)

    return render_template(
        'view_matches.html',
        req=req,
        donor=None,
        hospital=None,
        matches=matches
    )


@app.route('/allocate_donor/<int:donor_id>/<int:recipient_id>', methods=['GET', 'POST'])
def allocate_donor(donor_id, recipient_id):
    donor = Donor.query.get_or_404(donor_id)
    recipient = RecipientRequest.query.get_or_404(recipient_id)
    # Use shared allocation helper
    try:
        _perform_allocation(donor, recipient)
        flash(
            f"✅ Donor {donor.name} allocated to {recipient.patient_name} and both notified via WhatsApp!", "success")
    except Exception as e:
        print(f"[allocate_donor] Allocation failed: {e}")
        flash("⚠️ Allocation failed. See server logs.", "danger")
    return redirect(url_for('admin'))


def _perform_allocation(donor, recipient):
    """Helper: persist allocation, create notifications and send WhatsApp messages."""
    recipient.status = 'Allocated'
    recipient.matched_donor_id = donor.id
    donor.available = False
    donor.status = donor.status or 'Harvested'

    db.session.add(recipient)
    db.session.add(donor)
    db.session.commit()

    create_notification('donor', donor.id,
                        f"You have been matched with {recipient.patient_name} for {recipient.organ_needed} donation.")

    if getattr(donor, 'hospital', None):
        h = donor.hospital
        create_notification('recipient', recipient.id,
                            f"An organ for your {recipient.organ_needed} is available at {h.hospital_name} (Contact: {h.mobile}). Please contact the hospital for next steps.")
    else:
        create_notification('recipient', recipient.id,
                            f"Donor {donor.name} has been matched for your {recipient.organ_needed} request.")

    try:
        send_allocation_notification(donor, recipient)
    except Exception as e:
        print(f"[_perform_allocation] WhatsApp failed: {e}")


@app.route('/set-request-status/<int:request_id>/<status>')
def set_request_status(request_id, status):
    if not require_admin():
        return redirect(url_for('login'))
    r = RecipientRequest.query.get_or_404(request_id)
    r.status = status
    db.session.commit()
    flash(f"Request status set to {status}.")
    return redirect(url_for('admin'))

# ----------------------- Admin: approve donor (new) -----------------------


@app.route('/admin/approve/<int:donor_id>')
def approve_donor(donor_id):
    if not require_admin():
        return redirect(url_for('login'))
    donor = Donor.query.get_or_404(donor_id)
    donor.status = "Verified"
    donor.available = True
    db.session.commit()
    # Attempt to auto-match any pending recipient now that donor is verified and available
    try:
        matched = auto_match(donor)
        if matched:
            flash(
                f"✅ Donor {donor.name} verified and matched to a recipient.", "success")
        else:
            flash(
                f"✅ Donor {donor.name} verified successfully. No matching recipient found yet.", "success")
    except Exception as e:
        print(f"[approve_donor] auto_match failed: {e}")
        flash(f"✅ Donor {donor.name} verified successfully.", "success")
    return redirect(url_for('admin'))


@app.route('/admin/approve_hospital/<int:hospital_id>')
def approve_hospital(hospital_id):
    if not require_admin():
        return redirect(url_for('login'))
    h = Hospital.query.get_or_404(hospital_id)
    h.license_verified = True
    db.session.commit()

    # Create notification for hospital and send WhatsApp message
    try:
        create_notification(
            'hospital', h.id, f"Your hospital account '{h.hospital_name}' has been approved by admin.")
    except Exception:
        pass

    try:
        send_whatsapp_message(
            h.mobile, f"✅ Your hospital '{h.hospital_name}' has been approved. You can now log in and report cases.")
    except Exception as e:
        print(f"[approve_hospital] WhatsApp send failed: {e}")

    flash(f"✅ Hospital {h.hospital_name} approved and notified.", "success")
    return redirect(url_for('admin'))

# ----------------------- Hospital: Registration & Login -----------------------


@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():
    if request.method == 'POST':
        hospital_name = request.form.get('hospital_name')
        registration_number = request.form.get('registration_number')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if Hospital.query.filter_by(mobile=mobile).first():
            flash("⚠️ This mobile number is already registered.", "warning")
            return render_template('hospital_register.html')

        if Hospital.query.filter_by(email=email).first():
            flash("⚠️ This email is already registered.", "warning")
            return render_template('hospital_register.html')

        if Hospital.query.filter_by(registration_number=registration_number).first():
            flash("⚠️ This registration number is already registered.", "warning")
            return render_template('hospital_register.html')

        if password != confirm_password:
            flash("⚠️ Passwords do not match.", "warning")
            return render_template('hospital_register.html')

        hashed_password = generate_password_hash(password or "")
        hospital = Hospital(
            hospital_name=hospital_name,
            registration_number=registration_number,
            mobile=mobile,
            email=email,
            address=address,
            city=city,
            state=state,
            password=hashed_password
        )
        db.session.add(hospital)
        db.session.commit()

        flash("✅ Hospital registered successfully! Please log in.", "success")
        return redirect(url_for('hospital_login'))

    return render_template('hospital_register.html')


@app.route('/hospital/login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        hospital = Hospital.query.filter_by(mobile=mobile).first()
        if hospital and check_password_hash(hospital.password, password or ""):
            # If hospital not yet approved, block login
            if not hospital.license_verified:
                flash("⚠️ Your hospital account is pending admin approval. You cannot log in until an admin approves your account.", "warning")
                return render_template('hospital_login.html')

            session['hospital_id'] = hospital.id
            session['hospital_name'] = hospital.hospital_name
            flash(f"✅ Welcome, {hospital.hospital_name}!", "success")
            return redirect(url_for('hospital_dashboard'))

        flash("❌ Invalid mobile number or password.", "danger")

    return render_template('hospital_login.html')


@app.route('/hospital/logout')
def hospital_logout():
    session.pop('hospital_id', None)
    session.pop('hospital_name', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


@app.route('/hospital/dashboard')
def hospital_dashboard():
    hospital_id = session.get('hospital_id')
    if not hospital_id:
        flash('Please log in to access hospital dashboard.', 'warning')
        return redirect(url_for('hospital_login'))

    hospital = Hospital.query.get_or_404(hospital_id)
    death_reports = DeathReport.query.filter_by(
        hospital_id=hospital_id).order_by(DeathReport.reported_at.desc()).all()

    total_reports = len(death_reports)
    verified_reports = len([r for r in death_reports if r.status in [
                           'Verified', 'Organs-Ready', 'Completed']])
    organs_harvested = len([r for r in death_reports if r.organs_harvested])
    pending_reports = len([r for r in death_reports if r.status == 'Reported'])

    # Donor list for hospital, showing lifecycle state
    donors = Donor.query.filter(Donor.hospital_id == hospital_id).order_by(
        Donor.created_at.desc()).all()

    return render_template('hospital_dashboard.html',
                           hospital=hospital,
                           donors=donors,
                           death_reports=death_reports,
                           total_reports=total_reports,
                           verified_reports=verified_reports,
                           organs_harvested=organs_harvested,
                           pending_reports=pending_reports)

# ----------------------- Hospital: death reporting + verification -----------------------


@app.route('/hospital/report_death', methods=['GET', 'POST'])
def hospital_report_death():
    hospital_id = session.get('hospital_id')
    if not hospital_id:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('hospital_login'))
    # Ensure hospital is approved by admin before allowing death reporting
    hospital = Hospital.query.get(hospital_id)
    if hospital and not hospital.license_verified:
        flash('Your hospital account is pending admin approval. You cannot report deaths until approved.', 'warning')
        return redirect(url_for('hospital_dashboard'))

    if request.method == 'POST':
        donor_mobile = request.form.get('donor_mobile')
        donor = Donor.query.filter_by(mobile=donor_mobile).first()

        if not donor:
            flash("❌ Donor not found with this mobile number.", "danger")
            return render_template('hospital_report_death.html')

        death_time = request.form.get('death_time')
        cause_of_death = request.form.get('cause_of_death')
        medical_cert_number = request.form.get('medical_cert_number')
        next_of_kin_name = request.form.get('next_of_kin_name')
        next_of_kin_mobile = request.form.get('next_of_kin_mobile')
        next_of_kin_relation = request.form.get('next_of_kin_relation')

        if not donor.hospital_id:
            donor.hospital_id = hospital_id

        death_report = DeathReport(
            donor_id=donor.id,
            hospital_id=hospital_id,
            death_time=datetime.fromisoformat(
                death_time) if death_time else datetime.utcnow(),
            cause_of_death=cause_of_death,
            medical_cert_number=medical_cert_number,
            next_of_kin_name=next_of_kin_name,
            next_of_kin_mobile=next_of_kin_mobile,
            next_of_kin_relation=next_of_kin_relation,
            status='Reported'
        )
        donor.available = True
        db.session.add(death_report)
        db.session.commit()

        message = f"Donor {donor.name} has been reported as deceased at {session.get('hospital_name')}. Please confirm organ donation consent."
        send_whatsapp_message(next_of_kin_mobile, message)

        create_notification('hospital', hospital_id,
                            f"Death report filed for donor {donor.name}")

        flash(
            f"✅ Death report submitted for {donor.name}. Next of kin notified.", "success")
        return redirect(url_for('hospital_dashboard'))

    return render_template('hospital_report_death.html')


@app.route('/hospital/verify_death/<int:report_id>', methods=['GET', 'POST'])
def verify_death(report_id):
    hospital_id = session.get('hospital_id')
    if not hospital_id:
        flash('Please log in.', 'warning')
        return redirect(url_for('hospital_login'))

    report = DeathReport.query.get_or_404(report_id)

    if report.hospital_id != hospital_id:
        flash('❌ Unauthorized access.', 'danger')
        return redirect(url_for('hospital_dashboard'))

    if request.method == 'POST':
        report.status = 'Verified'
        report.verified_at = datetime.utcnow()
        report.notes = request.form.get('notes')
        db.session.commit()

        flash("✅ Death report verified.", "success")
        return redirect(url_for('hospital_dashboard'))

    return render_template('verify_death.html', report=report)


@app.route('/hospital/harvest_organs/<int:report_id>', methods=['GET', 'POST'])
def harvest_organs(report_id):
    hospital_id = session.get('hospital_id')
    if not hospital_id:
        flash('Please log in.', 'warning')
        return redirect(url_for('hospital_login'))

    report = DeathReport.query.get_or_404(report_id)

    if report.hospital_id != hospital_id:
        flash('❌ Unauthorized access.', 'danger')
        return redirect(url_for('hospital_dashboard'))

    if request.method == 'POST':
        organs_list = request.form.getlist('organs')
        organs_str = ', '.join(organs_list)

        # Update death report
        report.organs_harvested = organs_str
        report.harvested_at = datetime.utcnow()
        report.status = 'Organs-Ready'

        donor = report.donor
        donor.status = "Harvested"
        donor.available = False

        db.session.add(report)
        db.session.add(donor)
        db.session.commit()

        # 🔥 AUTO-ALLOCATE RECIPIENT (CRITICAL FIX)
        allocated = auto_match(donor)

        if allocated:
            flash("✅ Organs harvested and recipient successfully allocated.", "success")
        else:
            flash("⚠️ Organs harvested, but no matching recipient found.", "warning")

        return redirect(url_for('hospital_dashboard'))

    return render_template('harvest_organs.html', report=report)


# ----------------------- Hospital: simple donor harvest (lifecycle) -----------------------


@app.route('/hospital/harvest/<int:donor_id>', methods=['GET', 'POST'])
def hospital_harvest_donor(donor_id):
    """
    Simpler harvest path that updates donor lifecycle and auto-matches recipients,
    independent of DeathReport form.
    """
    hospital_id = session.get('hospital_id')
    if not hospital_id:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('hospital_login'))

    donor = Donor.query.get_or_404(donor_id)
    if donor.hospital_id and donor.hospital_id != hospital_id:
        flash('❌ Unauthorized access to this donor.', 'danger')
        return redirect(url_for('hospital_dashboard'))

    if donor.status != "Verified":
        flash("Donor must be verified by admin before harvest.", "warning")
        return redirect(url_for('hospital_dashboard'))

    if request.method == 'POST':
        donor.status = "Harvested"
        donor.available = False
        db.session.commit()
        auto_match(donor)
        flash(
            f"✅ Donor {donor.name} harvested and recipients auto-matched.", "success")
        return redirect(url_for('hospital_dashboard'))

    return render_template('harvest_donor.html', donor=donor)

# ---------------------- 🔑 FORGOT PASSWORD (Unified for Donor & Recipient) ----------------------


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    stage = session.get('reset_stage', 'mobile')
    mobile = session.get('reset_mobile')
    otp = session.get('reset_otp')

    if request.method == 'GET':
        session.pop('reset_stage', None)
        session.pop('reset_mobile', None)
        session.pop('reset_otp', None)
        stage = 'mobile'

    if request.method == 'POST':
        if stage == 'mobile':
            mobile = request.form.get('mobile')
            donor = Donor.query.filter_by(mobile=mobile).first()
            recipient = RecipientRequest.query.filter_by(mobile=mobile).first()

            if not donor and not recipient:
                flash("❌ Mobile number not found.", "danger")
                return render_template('forgot_password.html', stage='mobile')

            generated_otp = str(randint(100000, 999999))
            session['reset_otp'] = generated_otp
            session['reset_mobile'] = mobile
            session['reset_stage'] = 'otp'

            flash(f"💡 OTP (for testing): {generated_otp}", "info")
            if send_otp_textbelt(mobile, generated_otp):
                flash("✅ OTP sent successfully. Check console if SMS fails.", "success")
            else:
                flash("⚠️ Failed to send OTP. Using console fallback.", "warning")

            return render_template('forgot_password.html', stage='otp', mobile=mobile)

        elif stage == 'otp':
            entered_otp = request.form.get('otp')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if entered_otp != otp:
                flash("❌ Invalid OTP.", "danger")
                return render_template('forgot_password.html', stage='otp', mobile=mobile)

            if new_password != confirm_password:
                flash("⚠️ Passwords do not match.", "danger")
                return render_template('forgot_password.html', stage='otp', mobile=mobile)

            user = Donor.query.filter_by(mobile=mobile).first() or \
                RecipientRequest.query.filter_by(mobile=mobile).first()

            if user:
                user.password = generate_password_hash(new_password or "")
                db.session.commit()
                flash("✅ Password reset successful! Please log in.", "success")
                return redirect(url_for('get_started'))
            else:
                flash("❌ User not found.", "danger")

            session.pop('reset_stage', None)
            session.pop('reset_mobile', None)
            session.pop('reset_otp', None)
            return redirect(url_for('index'))

    return render_template('forgot_password.html', stage=stage)


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if entered_otp != session.get('otp'):
            flash("Invalid OTP!", "danger")
        elif not new_password.strip():
            flash("New password cannot be empty.", "warning")
        elif new_password != confirm_password:
            flash("Passwords do not match!", "warning")
        else:
            donor = Donor.query.filter_by(mobile=session.get('mobile')).first()
            if donor:
                donor.password = generate_password_hash(new_password)
                db.session.commit()
                session.pop('otp', None)
                session.pop('mobile', None)
                flash("Password reset successful! Please log in.", "success")
                return redirect(url_for('get_started'))
            else:
                flash("User not found.", "danger")

    return render_template('verify_otp.html')

# =========================== 🌐 UNIFIED REGISTRATION & LOGIN ===========================


@app.route('/get_started', methods=['GET'])
def get_started():
    return render_template('get_started.html')


@app.route('/unified_login', methods=['POST'])
def unified_login():
    """Login for both Donor and Recipient."""
    mobile = request.form.get('mobile')
    password = request.form.get('password')

    donor = Donor.query.filter_by(mobile=mobile).first()
    if donor and check_password_hash(donor.password, password or ""):
        session['donor_id'] = donor.id
        flash(f"Welcome back, {donor.name}!", "success")
        return redirect(url_for('donor_dashboard'))

    recipient = RecipientRequest.query.filter_by(mobile=mobile).first()
    if recipient and check_password_hash(recipient.password, password or ""):
        session['recipient_id'] = recipient.id
        flash(f"Welcome back, {recipient.patient_name}!", "success")
        return redirect(url_for('recipient_dashboard'))

    flash("❌ Invalid mobile number or password.", "danger")
    return redirect(url_for('get_started'))


@app.route('/learn_more')
def learn_more():
    return render_template('learn_more.html')

# ----------------------- Export CSV (donors or requests) -----------------------


@app.route('/export/<what>')
def export_csv(what):
    if not require_admin():
        return redirect(url_for('login'))
    output = io.StringIO()
    writer = csv.writer(output)
    if what == 'donors':
        writer.writerow(['ID', 'Name', 'Age', 'Gender', 'Blood', 'Organs',
                        'Contact', 'City', 'Hospital', 'Available', 'Status', 'CreatedAt'])
        for d in Donor.query.order_by(Donor.id).all():
            writer.writerow([d.id, d.name, d.age, d.gender, d.blood_group,
                             d.organs, d.contact, d.city, (
                                 d.hospital.hospital_name if d.hospital else ''),
                             d.available, d.status, d.created_at])
        filename = 'donors.csv'
    elif what == 'available':
        writer.writerow(['ID', 'Name', 'Age', 'Gender', 'Blood', 'Organs',
                        'Contact', 'City', 'Hospital', 'Status', 'CreatedAt'])
        for d in Donor.query.filter_by(available=True).order_by(Donor.id).all():
            writer.writerow([d.id, d.name, d.age, d.gender, d.blood_group, d.organs, d.contact,
                             d.city, (d.hospital.hospital_name if d.hospital else ''), d.status, d.created_at])
        filename = 'available_organs.csv'
    else:
        writer.writerow(['ID', 'Patient', 'Age', 'OrganNeeded', 'Blood',
                        'City', 'Notes', 'Status', 'MatchedDonor', 'CreatedAt'])
        for r in RecipientRequest.query.order_by(RecipientRequest.id).all():
            writer.writerow([r.id, r.patient_name, r.age, r.organ_needed, r.blood_group, r.city, (r.notes or ''),
                             r.status, (r.matched_donor.name if r.matched_donor else ''), r.created_at])
        filename = 'requests.csv'
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=filename)

# ----------------------- Short routes mapping -----------------------


@app.route('/delete/<int:donor_id>')
def delete_donor_short(donor_id): return delete_donor(donor_id)


@app.route('/toggle/<int:donor_id>')
def toggle_availability_short(donor_id): return toggle_availability(donor_id)


@app.route('/view-matches')
def view_matches_redirect():
    return redirect(url_for('admin'))


@app.route('/allocate_donor_short/<int:donor_id>/<int:recipient_id>')
def allocate_donor_short(donor_id, recipient_id):
    return allocate_donor(donor_id, recipient_id)


# ----------------------- MAIN -----------------------


if __name__ == '__main__':
    app.run(debug=True)

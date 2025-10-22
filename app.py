# Standard Library
import os
import secrets
from datetime import datetime, timedelta
from io import BytesIO
from sqlalchemy import case


# Flask Core
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, abort, make_response
)

# Flask Extensions
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_migrate import Migrate

# Security & Utilities
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# PDF & Reporting
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from fpdf import FPDF

# Data Handling
import pandas as pd

# SQLAlchemy Models
from models import db, User, Case, Document, ContactMessage

import pymysql
pymysql.install_as_MySQLdb()


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_strong_secret_key'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/kilifi_casess'
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('mysql://root:EqKeTBDdQnjMkXhwMSxBhJYnLLxFcrGR@mysql.railway.internal:3306/railway', 'mysql+pymysql://root:password@localhost/kilifi_casess')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('mysql://', 'mysql+pymysql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload config
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpg', 'png'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        #this is for checking password match.
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        #checking for existing username/email.
        username_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()

        if username_exists and email_exists:
            flash('Username and email already exist.', 'danger')
            return redirect(url_for('register'))
        elif username_exists:
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        elif email_exists:
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(full_name=full_name, username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    locked_user = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if not user:
            flash('Username does not exist.', 'danger')
        else:
            if user.is_locked:
                locked_user = user.username
            elif not check_password_hash(user.password_hash, password):
                flash('Incorrect password.', 'danger')
                user.failed_attempts += 1
                if user.failed_attempts >= 3:
                    user.is_locked = True
                db.session.commit()
            else:
                user.failed_attempts = 0
                user.is_locked = False
                db.session.commit()
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))

    return render_template('login.html', locked_user=locked_user)



'''
@app.route('/reset_password_locked/<username>', methods=['GET', 'POST'])
def reset_password_locked(username):
    user = User.query.filter_by(username=username).first_or_404()
    message = None
    success = False

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            message = 'Passwords do not match.'
        else:
            user.password_hash = generate_password_hash(new_password)
            user.failed_attempts = 0
            user.is_locked = False
            db.session.commit()
            message = 'Password reset successful. Please login.'
            success = True

    return render_template('reset_locked.html', username=username, message=message, success=success)
'''

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    user = User.query.filter_by(reset_token=token).first()
    message = None
    success = False
    reset_link = url_for('reset_password_token', token=token, _external=True)

    if not user or user.token_expiry < datetime.utcnow():
        message = 'Invalid or expired token.'
        return render_template('reset_token.html', message=message, success=success, reset_link=None)

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            message = 'Passwords do not match.'
        else:
            user.password_hash = generate_password_hash(new_password)
            user.reset_token = None
            user.token_expiry = None
            user.failed_attempts = 0
            user.is_locked = False
            db.session.commit()
            message = 'Password reset successful. Please login.'
            success = True

    return render_template('reset_token.html', message=message, success=success, reset_link=reset_link)


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    reset_link = None

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_link = url_for('reset_password_token', token=token, _external=True)
            flash('Reset link generated successfully.', 'info')
        else:
            flash('Email not found.', 'danger')

    return render_template('forgot_password.html', reset_link=reset_link)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    total_cases = Case.query.count()
    ongoing_cases = Case.query.filter_by(status='Ongoing').count()
    closed_cases = Case.query.filter_by(status='Closed').count()
    total_documents = Document.query.count()
    cases = Case.query.order_by(Case.date_filed.desc()).limit(5).all()

    upcoming_hearings = Case.query.filter(
        Case.next_hearing_date != None,
        Case.next_hearing_date >= datetime.utcnow()
    ).order_by(Case.next_hearing_date.asc()).limit(5).all()

    now = datetime.utcnow()  #pass this to template

    return render_template('dashboard.html', user=current_user,
                           total_cases=total_cases,
                           ongoing_cases=ongoing_cases,
                           closed_cases=closed_cases,
                           total_documents=total_documents,
                           cases=cases,
                           upcoming_hearings=upcoming_hearings,
                           now=now)



@app.route('/my-cases')
@login_required
def my_cases():
    status_filter = request.args.get('status')
    search_query = request.args.get('search')
    handled_by = request.args.get('handled_by')
    parties = request.args.get('parties')
    case_type = request.args.get('case_type')
    department = request.args.get('department')
    date_filed = request.args.get('date_filed')

    query = Case.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if search_query:
        query = query.filter(Case.case_number.like(f"%{search_query}%"))
    if handled_by:
        query = query.filter(Case.handled_by.like(f"%{handled_by}%"))
    if parties:
        query = query.filter(Case.parties.like(f"%{parties}%"))
    if case_type:
        query = query.filter(Case.case_type.like(f"%{case_type}%"))
    if department:
        query = query.filter(Case.department.like(f"%{department}%"))
    if date_filed:
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(date_filed, "%Y-%m-%d")
            query = query.filter(db.func.date(Case.date_filed) == parsed_date.date())
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")

    cases = query.order_by(Case.date_filed.desc()).all()
    return render_template('my_cases.html', cases=cases)


@app.route('/add_case', methods=['GET', 'POST'])
@login_required
def add_case():
    if request.method == 'POST':
        case_number = request.form.get('case_number')
        case_type = request.form.get('case_type')
        parties = request.form.get('parties')
        department = request.form.get('department')
        descriptions = request.form.get('descriptions')
        records = request.form.get('records')
        status = request.form.get('status')
        handled_by = request.form.get('handled_by')
        hearing_mode = request.form.get('hearing_mode')
        court_link = request.form.get('court_link') if hearing_mode == 'Virtual' else None
        link_title = request.form.get('link_title') if hearing_mode == 'Virtual' else None

        new_case = Case(
            case_number=case_number,
            case_type=case_type,
            parties=parties,
            department=department,
            descriptions=descriptions,
            records=records,
            status=status,
            handled_by=handled_by,
            hearing_mode=hearing_mode,
            court_link=court_link,
            link_title=link_title,
            date_filed=datetime.utcnow()
        )

        db.session.add(new_case)
        db.session.commit()
        flash('Case added successfully.', 'success')
        return redirect(url_for('my_cases'))

    return render_template('add_case.html')


@app.route('/edit_case/<int:case_id>', methods=['GET', 'POST'])
@login_required
def edit_case(case_id):
    case = Case.query.get_or_404(case_id)

    if request.method == 'POST':
        # Status and hearing date
        case.status = request.form.get('status')
        hearing_date = request.form.get('next_hearing_date')
        case.next_hearing_date = datetime.strptime(hearing_date, '%Y-%m-%dT%H:%M') if hearing_date else None

        # Hearing mode
        case.hearing_mode = request.form.get('hearing_mode')

        if case.hearing_mode == 'Virtual':
            case.court_link = request.form.get('court_link') or None
            case.link_title = request.form.get('link_title') or None
            case.department = None  # Clear physical venue
        else:
            case.department = request.form.get('department') or None
            case.court_link = None  # Clear virtual link
            case.link_title = None

        db.session.commit()
        flash('Case updated successfully.', 'success')
        return redirect(url_for('my_cases'))

    return render_template('edit_case.html', case=case)


@app.route('/update_case_status/<int:case_id>', methods=['POST'])
@login_required
def update_case_status(case_id):
    case = Case.query.get_or_404(case_id)
    new_status = request.form.get('status')

    if new_status == 'Closed':
        case.status = 'Closed'
        case.date_closed = datetime.utcnow()
    elif new_status == 'Paused':
        case.status = 'Paused'
        case.date_paused = datetime.utcnow()
    elif new_status == 'Resumed':
        case.status = 'Ongoing'
        case.date_resumed = datetime.utcnow()

    db.session.commit()
    flash(f'Case status updated to {new_status}.', 'success')
    return redirect(url_for('my_cases'))

@app.route('/upload_document/<int:case_id>', methods=['POST'])
@login_required
def upload_document(case_id):
    file = request.files.get('file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        new_doc = Document(filename=filename, case_id=case_id)
        db.session.add(new_doc)
        db.session.commit()
        flash('Document uploaded successfully!', 'success')
    else:
        flash('Invalid file or missing case.', 'danger')
    return redirect(url_for('my_cases'))

@app.route('/upload_document_global', methods=['POST'])
@login_required
def upload_document_global():
    file = request.files.get('file')
    case_id = request.form.get('case_id')
    if file and allowed_file(file.filename) and case_id:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        new_doc = Document(filename=filename, case_id=case_id)
        db.session.add(new_doc)
        db.session.commit()
        flash('Document uploaded successfully!', 'success')
    else:
        flash('Invalid upload.', 'danger')
    return redirect(url_for('documents'))

@app.route('/delete_document/<int:doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'info')
    return redirect(url_for('documents'))

@app.route('/download/<int:doc_id>')
@login_required
def download_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
    return send_file(filepath, as_attachment=True)

@app.route('/documents')
@login_required
def documents():
    documents = Document.query.order_by(Document.uploaded_at.desc()).all()
    cases = Case.query.order_by(Case.case_number).all()
    return render_template('documents.html', documents=documents, cases=cases)

@app.route('/profile', methods=['GET'])
@login_required
def profile():
    user = current_user
    total_cases = Case.query.filter_by(handled_by=user.full_name).count()
    closed_cases = Case.query.filter_by(handled_by=user.full_name, status='Closed').count()
    ongoing_cases = Case.query.filter_by(handled_by=user.full_name, status='Ongoing').count()
    return render_template('profile.html', user=user,
                           total_cases=total_cases,
                           closed_cases=closed_cases,
                           ongoing_cases=ongoing_cases)

@app.route('/profile', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    user.full_name = request.form.get('full_name')
    user.username = request.form.get('username')
    user.email = request.form.get('email')

    # Handle profile picture upload
    file = request.files.get('profile_picture')
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.root_path, 'static', 'profile_pics', filename)
        file.save(filepath)
        user.profile_picture = filename

    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/remove-picture', methods=['POST'])
@login_required
def remove_profile_picture():
    user = current_user

    if user.profile_picture:
        filepath = os.path.join(app.root_path, 'static', 'profile_pics', user.profile_picture)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting file: {e}")

        user.profile_picture = None
        db.session.commit()
        flash('Profile picture removed.', 'info')

    return redirect(url_for('profile'))


@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            new_msg = ContactMessage(user_id=current_user.id, message=message)
            db.session.add(new_msg)
            db.session.commit()
            flash('Message sent successfully!', 'success')
            return redirect(url_for('contact'))
        flash('Please enter a message.', 'danger')
    return render_template('contact.html')


@app.route('/export/pdf')
@login_required
def export_pdf():
    cases = Case.query.order_by(Case.date_filed.desc()).all()

    # Summary stats
    total_cases = len(cases)
    ongoing = sum(1 for c in cases if c.status == 'Ongoing')
    paused = sum(1 for c in cases if c.status == 'Paused')
    resumed = sum(1 for c in cases if c.status == 'Resumed')
    closed = sum(1 for c in cases if c.status == 'Closed')

    # Setup PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Optional logo
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=8, w=30)

    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Kilifi Legal Cases Report", ln=True, align='C')
    
    from pytz import timezone
    eat_time = datetime.now(timezone('Africa/Nairobi'))
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Generated on: {eat_time.strftime('%Y-%m-%d %H:%M EAT')}", ln=True, align='C')
    pdf.ln(10)



    # Case listings
    pdf.set_font("Arial", '', 12)
    for case in cases:
        pdf.cell(0, 8, f"Case: {case.case_number} | Status: {case.status}", ln=True)
        pdf.cell(0, 8, f"Filed: {case.date_filed.strftime('%Y-%m-%d')} | Handled By: {case.handled_by}", ln=True)
        pdf.ln(5)

    # Summary stats at bottom
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Summary Statistics", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"Total Cases: {total_cases}", ln=True)
    pdf.cell(0, 8, f"Ongoing: {ongoing}", ln=True)
    pdf.cell(0, 8, f"Paused: {paused}", ln=True)
    pdf.cell(0, 8, f"Resumed: {resumed}", ln=True)
    pdf.cell(0, 8, f"Closed: {closed}", ln=True)

    # Output safely
    pdf_bytes = pdf.output(dest='S').encode('latin1', errors='replace')
    output = BytesIO(pdf_bytes)
    return send_file(output, download_name="cases_report.pdf", as_attachment=True)

'''
@app.route('/admin/messages')
@login_required
def admin_messages():
    if current_user.role != 'admin':
        abort(403)
    messages = ContactMessage.query.order_by(ContactMessage.submitted_at.desc()).all()
    return render_template('admin_messages.html', messages=messages)

@app.route('/admin/reply/<int:message_id>', methods=['POST'])
@login_required
def reply_to_message(message_id):
    if current_user.role != 'admin':
        abort(403)
    message = ContactMessage.query.get_or_404(message_id)
    reply_text = request.form.get('reply')
    message.reply = reply_text
    message.replied_at = datetime.utcnow()
    message.replied_by = current_user.id
    db.session.commit()
    flash('Reply sent successfully', 'success')
    return redirect(url_for('admin_messages'))
'''

@app.route('/admin/messages')
@login_required
def admin_messages():
    if current_user.role != 'admin':
        abort(403)

    messages = ContactMessage.query.order_by(
        case((ContactMessage.reply == None, 1), else_=0).desc(),
        ContactMessage.submitted_at.desc()
    ).all()

    return render_template('admin_messages.html', messages=messages)



@app.route('/admin/reply/<int:msg_id>', methods=['POST'])
@login_required
def reply_message(msg_id):
    if current_user.role != 'admin':
        abort(403)

    msg = ContactMessage.query.get_or_404(msg_id)
    reply_text = request.form.get('reply')

    if reply_text:
        msg.reply = reply_text
        msg.replied_at = datetime.utcnow()
        msg.replied_by = current_user.id
        db.session.commit()
        flash('Reply sent successfully.', 'success')

    return redirect(url_for('admin_messages'))



@app.route('/export/excel')
@login_required
def export_excel():
    cases = Case.query.order_by(Case.date_filed.desc()).all()
    data = [{
        "Case Number": c.case_number,
        "Type": c.case_type,
        "Parties": c.parties,
        "Filed": c.date_filed.strftime('%Y-%m-%d'),
        "Status": c.status,
        "Handled By": c.handled_by,
        "Closed": c.date_closed.strftime('%Y-%m-%d') if c.date_closed else '',
        "Paused": c.date_paused.strftime('%Y-%m-%d') if c.date_paused else '',
        "Resumed": c.date_resumed.strftime('%Y-%m-%d') if c.date_resumed else ''
    } for c in cases]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Cases')
    output.seek(0)
    return send_file(output, download_name="cases_report.xlsx", as_attachment=True)

@app.route('/admin/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_single_message(msg_id):
    if current_user.role != 'admin':
        abort(403)

    msg = ContactMessage.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash('Message deleted successfully.', 'info')
    return redirect(url_for('admin_messages'))


@app.route('/admin/delete-multiple', methods=['POST'])
@login_required
def delete_messages():
    if current_user.role != 'admin':
        abort(403)

    ids = request.form.getlist('delete_ids')
    if ids:
        for msg_id in ids:
            msg = ContactMessage.query.get(msg_id)
            if msg:
                db.session.delete(msg)
        db.session.commit()
        flash(f'{len(ids)} message(s) deleted.', 'info')
    else:
        flash('No messages selected.', 'warning')

    return redirect(url_for('admin_messages'))

@app.route('/dashboard/delete/<int:msg_id>', methods=['POST'])
@login_required
def delete_user_message(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    if msg.user_id != current_user.id:
        abort(403)

    db.session.delete(msg)
    db.session.commit()
    flash('Message deleted successfully.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/delete-multiple', methods=['POST'])
@login_required
def delete_user_messages():
    ids = request.form.getlist('delete_ids')
    if ids:
        for msg_id in ids:
            msg = ContactMessage.query.get(msg_id)
            if msg and msg.user_id == current_user.id:
                db.session.delete(msg)
        db.session.commit()
        flash(f'{len(ids)} message(s) deleted.', 'info')
    else:
        flash('No messages selected.', 'warning')

    return redirect(url_for('dashboard'))

@app.route('/update_hearing/<int:case_id>', methods=['POST'])
@login_required
def update_hearing(case_id):
    case = Case.query.get_or_404(case_id)
    date_str = request.form.get('next_hearing_date')
    if date_str:
        case.next_hearing_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('Hearing date updated successfully.', 'success')
    return redirect(url_for('my_cases'))


@app.route('/export_hearings_pdf')
@login_required
def export_hearings_pdf():
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Logo
    logo_path = os.path.join(app.root_path, 'static', 'logo.png')
    if os.path.exists(logo_path):
        p.drawImage(logo_path, 40, height - 80, width=60, height=60, mask='auto')

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(120, height - 50, "Kilifi Legal Portal")
    p.setFont("Helvetica", 12)
    p.drawString(120, height - 70, "Upcoming Hearings Report")

    # Table headers
    y = height - 110
    p.setFont("Helvetica-Bold", 11)
    p.drawString(40, y, "Date")
    p.drawString(140, y, "Case")
    p.drawString(240, y, "Type")
    p.drawString(340, y, "Parties")
    p.drawString(500, y, "Urgency")

    hearings = Case.query.filter(
        Case.next_hearing_date != None,
        Case.next_hearing_date >= datetime.utcnow()
    ).order_by(Case.next_hearing_date.asc()).all()

    y -= 20
    p.setFont("Helvetica", 10)
    for case in hearings:
        urgency = "Urgent" if (case.next_hearing_date - datetime.utcnow()).days <= 3 else \
                  "Soon" if (case.next_hearing_date - datetime.utcnow()).days <= 7 else "Scheduled"

        p.drawString(40, y, case.next_hearing_date.strftime('%Y-%m-%d %H:%M'))
        p.drawString(140, y, case.case_number)
        p.drawString(240, y, case.case_type)
        p.drawString(340, y, case.parties[:40])  # Truncate if too long
        p.drawString(500, y, urgency)
        y -= 20
        if y < 50:
            p.showPage()
            y = height - 50

    # Footer
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(40, 30, f"Printed by: {current_user.full_name} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return make_response(buffer.read(), {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="hearings.pdf"'
    })


@app.route('/bulk_schedule', methods=['POST'])
@login_required
def bulk_schedule():
    case_ids = request.form.getlist('case_ids')
    date_str = request.form.get('bulk_date')
    if case_ids and date_str:
        hearing_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        for cid in case_ids:
            case = Case.query.get(int(cid))
            case.next_hearing_date = hearing_date
        db.session.commit()
        flash('Hearings scheduled successfully.', 'success')
    else:
        flash('Please select cases and a date.', 'danger')
    return redirect(url_for('my_cases'))



# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

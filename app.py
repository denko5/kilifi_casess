import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Case, Document, ContactMessage
from flask_migrate import Migrate
from io import BytesIO
from fpdf import FPDF
import pandas as pd

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_strong_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:password@localhost/kilifi_cases'
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

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.', 'danger')
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
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    cases = Case.query.order_by(Case.date_filed.desc()).all()
    total_cases = len(cases)
    ongoing_cases = Case.query.filter_by(status='Ongoing').count()
    closed_cases = Case.query.filter_by(status='Closed').count()
    total_documents = Document.query.count()
    return render_template('dashboard.html',
                           cases=cases,
                           total_cases=total_cases,
                           ongoing_cases=ongoing_cases,
                           closed_cases=closed_cases,
                           total_documents=total_documents,
                           current_user=current_user)

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
        case_number = request.form['case_number']
        case_type = request.form['case_type']
        parties = request.form['parties']
        status = request.form.get('status', 'Ongoing')
        handled_by = request.form.get('handled_by', current_user.full_name)
        department = request.form.get('department')
        descriptions = request.form.get('descriptions')
        records = request.form.get('records')


        new_case = Case(
            case_number=case_number,
            case_type=case_type,
            parties=parties,
            department=department,
            descriptions=descriptions,
            records=records,
            status=status,
            handled_by=handled_by
        )
        db.session.add(new_case)
        db.session.commit()
        flash('Case added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_case.html')

@app.route('/edit_case/<int:case_id>', methods=['GET', 'POST'])
@login_required
def edit_case(case_id):
    case = Case.query.get_or_404(case_id)
    if request.method == 'POST':
        new_status = request.form.get('status')
        case.status = new_status

        if new_status == 'Closed':
            case.date_closed = datetime.utcnow()
        elif new_status == 'Paused':
            case.date_paused = datetime.utcnow()
        elif new_status == 'Resumed':
            case.date_resumed = datetime.utcnow()

        db.session.commit()
        flash('Case status updated successfully.', 'success')
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

@app.route('/profile')
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

from sqlalchemy import case

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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5001, debug=True)

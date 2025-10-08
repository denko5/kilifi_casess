import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Case, Document, ContactMessage
from flask_migrate import Migrate

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
    cases = Case.query.order_by(Case.date_filed.desc()).all()
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

        new_case = Case(
            case_number=case_number,
            case_type=case_type,
            parties=parties,
            status=status,
            handled_by=handled_by,
            date_filed=datetime.utcnow()
        )
        db.session.add(new_case)
        db.session.commit()
        flash('Case added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_case.html')

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
    return render_template('profile.html', user=current_user)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5001, debug=True)

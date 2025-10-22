from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    failed_attempts = db.Column(db.Integer, default=0)
    is_locked = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    contact_messages = db.relationship(
        'ContactMessage',
        backref='user',
        lazy=True,
        foreign_keys='ContactMessage.user_id'
    )

    replies_sent = db.relationship(
        'ContactMessage',
        back_populates='replier',
        foreign_keys='ContactMessage.replied_by'
)




class Case(db.Model):
    __tablename__ = 'casess'

    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(100), unique=True, nullable=False)
    case_type = db.Column(db.String(100), nullable=False)
    parties = db.Column(db.Text, nullable=False)
    date_filed = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Ongoing')
    handled_by = db.Column(db.String(150))

    department = db.Column(db.String(150), nullable=True)
    descriptions = db.Column(db.Text, nullable=True)
    records = db.Column(db.Text, nullable=True)

    date_closed = db.Column(db.DateTime, nullable=True)
    date_paused = db.Column(db.DateTime, nullable=True)
    date_resumed = db.Column(db.DateTime, nullable=True)

    next_hearing_date = db.Column(db.DateTime, nullable=True)  # ✅ New field

    documents = db.relationship('Document', backref='case', lazy=True)
    hearing_mode = db.Column(db.String(20))  # 'Physical' or 'Virtual'
    court_link = db.Column(db.String(255))   # actual URL
    link_title = db.Column(db.String(100))   # optional display name



'''
class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(100), unique=True, nullable=False)
    case_type = db.Column(db.String(100), nullable=False)
    parties = db.Column(db.Text, nullable=False)
    date_filed = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Ongoing')  # Ongoing, Paused, Resumed, Closed
    handled_by = db.Column(db.String(150))

    # Status history timestamps
    date_closed = db.Column(db.DateTime, nullable=True)
    date_paused = db.Column(db.DateTime, nullable=True)
    date_resumed = db.Column(db.DateTime, nullable=True)

    documents = db.relationship('Document', backref='case', lazy=True)

'''
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('casess.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

'''
class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reply = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)

'''
class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reply = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
    replied_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    replier = db.relationship('User', foreign_keys=[replied_by])


from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, flash
import os
import logging
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from templates.mongo_connect import setup_mongo_connection

# Initialize MongoDB connection (optional)
try:
    mongo_db = setup_mongo_connection()
    if mongo_db:
        logging.info("MongoDB connection established")
    else:
        logging.warning("MongoDB not available - running in SQLite-only mode")
except Exception as e:
    mongo_db = None
    logging.warning(f"MongoDB connection failed: {str(e)} - running in SQLite-only mode")
from datetime import datetime
import sqlite3
from flask_mail import Mail, Message
from dateutil.parser import parse
import json
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-password')

mail = Mail(app)

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), 'user_data')

# Initialize directories
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FIR(db.Model):
    __tablename__ = 'firs'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    anonymous = db.Column(db.Boolean, default=False)
    filename = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Received')
    case_id = db.Column(db.String(50), unique=True)
    terms_accepted = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(200))
    appointments = db.relationship('Appointment', backref='fir', lazy=True)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    fir_id = db.Column(db.Integer, db.ForeignKey('firs.id'), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='Pending')

# Initialize database
with app.app_context():
    db.create_all()

def verify_user(username, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        return False
    return check_password_hash(user.password, password)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verify_user(username, password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

import random

def generate_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    return f"{a} + {b}", str(a + b)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Validate CAPTCHA first
        user_answer = request.form.get('captcha')
        correct_answer = request.form.get('captcha_answer')
        
        if user_answer != correct_answer:
            flash('CAPTCHA verification failed. Please try again.', 'danger')
            captcha_question, captcha_answer = generate_captcha()
            return render_template('signup.html', 
                                captcha_question=captcha_question,
                                captcha_answer=captcha_answer)
        
        # Validate password match
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            captcha_question, captcha_answer = generate_captcha()
            return render_template('signup.html', 
                                captcha_question=captcha_question,
                                captcha_answer=captcha_answer)
        
        # Register user
        username = request.form['username']
        email = request.form['email']
        if register_user(username, email, password):
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists. Please choose a different one.', 'danger')
    
    # Generate new CAPTCHA for GET request
    captcha_question, captcha_answer = generate_captcha()
    return render_template('signup.html', 
                         captcha_question=captcha_question,
                         captcha_answer=captcha_answer)

def register_user(username, email, password):
    if User.query.filter_by(username=username).first():
        return False
    
    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()
    return True

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Existing FIR submission route (modified to include username)
@app.route('/submit_fir', methods=['POST'])
def submit_fir():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        data = request.form
        terms = request.form.get('terms')
        if not terms:
            flash('You must accept the terms and conditions', 'error')
            return redirect(request.referrer or url_for('index'))
            
        files = request.files.getlist('file')
        password_hash = generate_password_hash(data.get('password'))
        
        case_id = f"FIR-{datetime.now().strftime('%Y%m%d')}-{os.urandom(4).hex().upper()}"
        
        filenames = []
        for file in files:
            if not file or file.filename == '':
                continue
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                flash('Invalid file type. Only PDF, JPG, PNG allowed', 'error')
                return redirect(request.referrer or url_for('index'))
            try:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                filenames.append(filename)
            except Exception as e:
                flash(f'File upload failed: {str(e)}', 'error')
                return redirect(request.referrer or url_for('index'))
        
        new_fir = FIR(
            username=session['username'],
            name='Anonymous' if data.get('anonymous') else data.get('name'),
            email='hidden' if data.get('anonymous') else data.get('email'),
            description=data.get('description'),
            anonymous=bool(data.get('anonymous')),
            filename=','.join(filenames),
            case_id=case_id,
            terms_accepted=bool(data.get('terms')),
            password=password_hash
        )
        db.session.add(new_fir)
        db.session.commit()
        fir_id = new_fir.id
        
        # Send confirmation email
        try:
            if not data.get('anonymous'):
                msg = Message('FIR Submission Confirmation',
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[data.get('email')])
                msg.body = f"""Your FIR has been submitted successfully.
Case ID: {case_id}
Description: {data.get('description')}
"""
                mail.send(msg)
        except Exception as e:
            app.logger.error(f'Failed to send email: {str(e)}')

        flash('FIR submitted successfully!', 'success')
        session['submission_data'] = {
            'case_id': case_id,
            'name': 'Anonymous' if data.get('anonymous') else data.get('name'),
            'email': 'hidden' if data.get('anonymous') else data.get('email'),
            'description': data.get('description'),
            'files': filenames,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return redirect(url_for('success_page'))
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(request.referrer or url_for('index'))

@app.route('/submit_appointment', methods=['POST'])
def submit_appointment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        data = request.form
        fir_id = data.get('fir_id')
        date = data.get('date')
        time = data.get('time')
        
        # Validate FIR exists and belongs to user
        fir = FIR.query.filter_by(id=fir_id, username=session['username']).first()
        if not fir:
            flash('Invalid FIR case or not authorized', 'error')
            return redirect(request.referrer or url_for('dashboard'))
            
        # Validate date/time
        if not date or not time:
            flash('Date and time are required', 'error')
            return redirect(request.referrer or url_for('dashboard'))
            
        # Create new appointment
        new_appointment = Appointment(
            fir_id=fir_id,
            date=date,
            time=time,
            status='Pending'
        )
        db.session.add(new_appointment)
        db.session.commit()
        
        # Send confirmation email if not anonymous
        if not fir.anonymous:
            try:
                msg = Message('Appointment Scheduled',
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[fir.email])
                msg.body = f"""Your appointment has been scheduled successfully.
FIR Case ID: {fir.case_id}
Date: {date}
Time: {time}
Status: Pending
"""
                mail.send(msg)
            except Exception as e:
                app.logger.error(f'Failed to send email: {str(e)}')

        flash('Appointment scheduled successfully!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(request.referrer or url_for('dashboard'))

# Other existing routes...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

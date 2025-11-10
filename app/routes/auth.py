from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app import db, limiter
from app.services import UserService, EmailService
from app.models import PendingUser, EmailVerification, User
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

# Rate limiting storage
recent_resends = {}

def login_required(f):
    """Decorator to require login for protected routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def guest_protected(f):
    """Decorator to protect routes from guest access"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('is_guest'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'guest_read_only', 'message': 'Please create an account to perform this action'}), 403
            flash('Please create an account to perform this action', 'warning')
            return redirect(url_for('main.explore'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', 'other')

        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.signup'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'danger')
            return redirect(url_for('auth.signup'))

        # Check if user exists
        if User.query.filter_by(email=email).first() or PendingUser.query.filter_by(email=email).first():
            flash('Email already registered or pending verification', 'danger')
            return redirect(url_for('auth.signup'))

        if User.query.filter_by(username=username).first() or PendingUser.query.filter_by(username=username).first():
            flash('Username already taken or pending', 'danger')
            return redirect(url_for('auth.signup'))

        try:
            # Create pending user
            pending = UserService.create_pending_user(username, email, password, name, gender)
            
            # Generate and send verification code
            code = UserService.create_verification_code(pending.id)
            
            if EmailService.send_verification_email(pending.email, pending.username, code):
                session['pending_id'] = pending.id
                flash('Verification code sent to your email', 'success')
                return redirect(url_for('auth.verify_code'))
            else:
                # Clean up if email fails
                db.session.delete(pending)
                db.session.commit()
                flash('Failed to send verification email. Please check your email settings.', 'danger')
                return redirect(url_for('auth.signup'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Signup error: {e}")
            flash('An error occurred during registration', 'danger')
            return redirect(url_for('auth.signup'))

    return render_template('signup.html')

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify_code():
    if 'pending_id' not in session:
        flash('Please complete signup first', 'danger')
        return redirect(url_for('auth.signup'))

    pending = PendingUser.query.get(session['pending_id'])
    if not pending:
        flash('Invalid session. Please sign up again.', 'danger')
        session.pop('pending_id', None)
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        code = request.form['code'].strip()
        
        user, message = UserService.verify_pending_user(pending.id, code)
        
        if user:
            # Send welcome email
            EmailService.send_welcome_email(user.email, user.username)
            
            session.pop('pending_id', None)
            flash('Email verified successfully! You can now login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')
            return redirect(url_for('auth.verify_code'))

    return render_template('verify.html', email=pending.email)

@auth_bp.route('/resend-code', methods=['POST'])
@limiter.limit("3 per hour")
def resend_code():
    if 'pending_id' not in session:
        flash('Please complete signup first', 'danger')
        return redirect(url_for('auth.signup'))

    pending = PendingUser.query.get(session['pending_id'])
    if not pending:
        flash('Invalid session. Please sign up again.', 'danger')
        session.pop('pending_id', None)
        return redirect(url_for('auth.signup'))

    # Rate limiting check
    user_key = f"resend_pending_{pending.id}"
    current_time = datetime.utcnow()

    if user_key in recent_resends:
        last_resend, count = recent_resends[user_key]
        if (current_time - last_resend).total_seconds() < 3600 and count >= 3:
            flash('Too many resend attempts. Please wait before trying again.', 'danger')
            return redirect(url_for('auth.verify_code'))

    # Create new verification code
    code = UserService.create_verification_code(pending.id)

    # Update rate limiting
    if user_key in recent_resends:
        recent_resends[user_key] = (current_time, recent_resends[user_key][1] + 1)
    else:
        recent_resends[user_key] = (current_time, 1)

    if EmailService.send_verification_email(pending.email, pending.username, code):
        flash('New verification code sent', 'success')
    else:
        flash('Failed to send verification email. Please check your email settings.', 'danger')
    
    return redirect(url_for('auth.verify_code'))

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        login_input = request.form['login_input'].strip().lower()
        password = request.form['password']

        user = UserService.authenticate_user(login_input, password)

        if user:
            if not user.is_verified:
                session['pending_user_id'] = user.id
                flash('Please verify your email before logging in', 'warning')
                return redirect(url_for('auth.verify_code'))
            
            session['user_id'] = user.id
            session.pop('is_guest', None)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.landing'))
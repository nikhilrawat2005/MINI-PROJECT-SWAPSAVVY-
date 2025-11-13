# run.py - UPDATED WITH COMPLETE NETWORKING AND MESSAGING FEATURES
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail
from dotenv import load_dotenv
from functools import wraps
import os
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
import traceback
import json
import uuid
import enum
from collections import Counter

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///swapsavvy.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enhanced file upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webp', 'pdf', 'ppt', 'pptx'}

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Initialize extensions
db = SQLAlchemy()
db.init_app(app)
csrf = CSRFProtect(app)
migrate = Migrate(app, db)

# Initialize rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# Security headers
if not app.debug:
    Talisman(app, content_security_policy=None)

# Initialize mail
mail = Mail(app)

# Rate limiting storage
recent_resends = {}

# ==================== ENUMS ====================

class ProfileMode(enum.Enum):
    LEARNER = 'learner'
    TEACHER = 'teacher'
    BOTH = 'both'

class PriceType(enum.Enum):
    FIXED = 'fixed'
    HOURLY = 'hourly'
    PROJECT = 'project'
    FREE = 'free'

# ==================== MODELS ====================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    assigned_id = db.Column(db.String(16), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))
    gender = db.Column(db.String(10))
    avatar = db.Column(db.String(200), default='img/default-avatar.png')
    cover_photo = db.Column(db.String(200), default='img/default-cover.jpg')
    
    # Enhanced profile fields
    headline = db.Column(db.String(200))
    summary = db.Column(db.Text)
    location = db.Column(db.String(100))
    website = db.Column(db.String(200))
    open_to_work = db.Column(db.Boolean, default=False)
    open_to_freelance = db.Column(db.Boolean, default=False)
    
    # Profile mode and teacher fields
    profile_mode = db.Column(db.Enum(ProfileMode), default=ProfileMode.BOTH)
    hourly_rate = db.Column(db.Numeric(10, 2))
    response_time = db.Column(db.String(50))
    
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_badge = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Enhanced relationships
    posts = db.relationship("Post", back_populates="user", cascade="all, delete-orphan", lazy='dynamic')
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy='dynamic')
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy='dynamic')
    likes = db.relationship("Like", back_populates="user", cascade="all, delete-orphan")
    comments = db.relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", foreign_keys='Notification.user_id', backref='user', lazy='dynamic')
    
    # New professional relationships
    experiences = db.relationship("Experience", back_populates="user", cascade="all, delete-orphan")
    educations = db.relationship("Education", back_populates="user", cascade="all, delete-orphan")
    skills = db.relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    portfolio_items = db.relationship("PortfolioItem", back_populates="user", cascade="all, delete-orphan")
    connections = db.relationship("Connection", foreign_keys='Connection.user1_id', backref='user1', lazy='dynamic')
    messages_sent = db.relationship("Message", foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship("Message", foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    services = db.relationship("Service", back_populates="user", cascade="all, delete-orphan")
    learning_goals = db.relationship("LearningGoal", back_populates="user", cascade="all, delete-orphan")
    reviews_given = db.relationship("Review", foreign_keys='Review.reviewer_id', backref='reviewer', lazy='dynamic')
    reviews_received = db.relationship("Review", foreign_keys='Review.reviewee_id', backref='reviewee', lazy='dynamic')
    
    def get_rating_stats(self):
        """Calculate rating statistics for the user"""
        reviews = self.reviews_received.all()
        if not reviews:
            return {'count': 0, 'average': 0}
        
        total_rating = sum(review.rating for review in reviews)
        average_rating = total_rating / len(reviews)
        
        return {
            'count': len(reviews),
            'average': round(average_rating, 1)
        }

    def is_following(self, user):
        return self.following.filter_by(followed_id=user.id).first() is not None

    def is_connected(self, user):
        return Connection.query.filter(
            ((Connection.user1_id == self.id) & (Connection.user2_id == user.id)) |
            ((Connection.user1_id == user.id) & (Connection.user2_id == self.id))
        ).first() is not None

    def follow(self, user):
        if not self.is_following(user):
            follow = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(follow)
            return True
        return False

    def unfollow(self, user):
        follow = self.following.filter_by(followed_id=user.id).first()
        if follow:
            db.session.delete(follow)
            return True
        return False

    def connect(self, user):
        if not self.is_connected(user) and self.id != user.id:
            connection = Connection(user1_id=self.id, user2_id=user.id, status='pending')
            db.session.add(connection)
            return True
        return False

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"

class Experience(db.Model):
    __tablename__ = 'experiences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    current = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    
    user = db.relationship("User", back_populates="experiences")

class Education(db.Model):
    __tablename__ = 'educations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    school = db.Column(db.String(200), nullable=False)
    degree = db.Column(db.String(200))
    field_of_study = db.Column(db.String(200))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    current = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    
    user = db.relationship("User", back_populates="educations")

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class UserSkill(db.Model):
    __tablename__ = 'user_skills'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    proficiency = db.Column(db.String(20))
    years_experience = db.Column(db.Integer)
    
    user = db.relationship("User", back_populates="skills")
    skill = db.relationship("Skill")

class PortfolioItem(db.Model):
    __tablename__ = 'portfolio_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_url = db.Column(db.String(500))
    media_path = db.Column(db.String(500), default='img/portfolio-placeholder.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="portfolio_items")

class Connection(db.Model):
    __tablename__ = 'connections'
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user1_id', 'user2_id', name='unique_connection'),)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    price_type = db.Column(db.Enum(PriceType), default=PriceType.FIXED)
    price_amount = db.Column(db.Numeric(10, 2))
    duration = db.Column(db.String(100))
    tags = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="services")

class LearningGoal(db.Model):
    __tablename__ = 'learning_goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    budget_min = db.Column(db.Numeric(10, 2))
    budget_max = db.Column(db.Numeric(10, 2))
    timeline = db.Column(db.String(100))
    preferred_format = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="learning_goals")

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    service_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PendingUser(db.Model):
    __tablename__ = 'pending_users'
    id = db.Column(db.Integer, primary_key=True)
    assigned_id = db.Column(db.String(16), unique=True, nullable=False)
    username = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))
    gender = db.Column(db.String(10))
    avatar = db.Column(db.String(200), default='img/default-avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)

    def to_user(self):
        return User(
            assigned_id=self.assigned_id,
            username=self.username,
            email=self.email,
            password_hash=self.password_hash,
            name=self.name,
            gender=self.gender,
            avatar=self.avatar,
            is_verified=True
        )

    def __repr__(self):
        return f"<PendingUser {self.username} ({self.email})>"

class EmailVerification(db.Model):
    __tablename__ = 'email_verifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    pending_user_id = db.Column(db.Integer, db.ForeignKey('pending_users.id'), nullable=True)
    code = db.Column(db.String(6), nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    resend_count = db.Column(db.Integer, default=0, nullable=False)
    last_sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('verifications', cascade='all, delete-orphan'))
    pending_user = db.relationship('PendingUser', backref=db.backref('verifications', cascade='all, delete-orphan'))

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def __repr__(self):
        target = f"pending:{self.pending_user_id}" if self.pending_user_id else f"user:{self.user_id}"
        return f"<EmailVerification {target} code={self.code} attempts={self.attempts}>"

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    media_path = db.Column(db.String(500), nullable=True)
    post_type = db.Column(db.String(20), default='text')
    extra_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship("User", back_populates="posts")
    likes = db.relationship("Like", back_populates="post", cascade="all, delete-orphan")
    comments = db.relationship("Comment", back_populates="post", cascade="all, delete-orphan", order_by="Comment.created_at")

    def like_count(self):
        return len(self.likes)

    def comment_count(self):
        return len(self.comments)

    def get_extra_data(self):
        if self.extra_data:
            return json.loads(self.extra_data)
        return {}

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="likes")
    post = db.relationship("Post", back_populates="likes")

    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_like'),)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship("User", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")

class Follow(db.Model):
    __tablename__ = 'follows'
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('follower_id', 'followed_id', name='unique_follow'),)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verb = db.Column(db.String(64))
    target_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    actor = db.relationship("User", foreign_keys=[actor_id])

# ==================== DECORATORS & HELPERS ====================

def guest_protected(f):
    """Decorator to protect routes from guest access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('is_guest'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'guest_read_only', 'message': 'Please create an account to perform this action'}), 403
            flash('Please create an account to perform this action', 'warning')
            return redirect(url_for('explore'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_guest_expiry():
    """Check if guest session has expired"""
    if session.get('is_guest') and session.get('guest_expiry'):
        if datetime.utcnow() > datetime.fromisoformat(session['guest_expiry']):
            session.clear()
            flash('Your guest session has expired. Please sign up to continue.', 'info')
            return True
    return False

def generate_assigned_id(username, length_prefix=3, tries=30):
    prefix = (username.strip().lower() + "x" * length_prefix)[:length_prefix]
    for _ in range(tries):
        num = f"{random.randint(0, 9999):04d}"
        candidate = prefix + num
        if not (User.query.filter_by(assigned_id=candidate).first() or
                PendingUser.query.filter_by(assigned_id=candidate).first()):
            return candidate
    raise RuntimeError("Failed to generate unique assigned ID")

def get_avatar_path(gender):
    """Get default avatar path based on gender"""
    return 'img/default-avatar.png'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, subfolder):
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)
        return f"uploads/{subfolder}/{filename}"
    return None

# ==================== EMAIL SERVICE ====================

class EmailService:
    @staticmethod
    def send_verification_email(email, username, code):
        """Send email verification code"""
        try:
            from flask_mail import Message
            msg = Message(
                subject="SwapSavvy Pro — Email Verification Code",
                recipients=[email],
                html=render_template('email_verification.html', 
                                   username=username, 
                                   code=code,
                                   header_img=url_for('static', filename='img/email/header.png', _external=True))
            )
            mail.send(msg)
            print(f"✅ Verification email sent to {email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send email to {email}: {e}")
            return False

    @staticmethod
    def send_welcome_email(email, username):
        """Send welcome email after successful registration"""
        try:
            from flask_mail import Message
            msg = Message(
                subject="Welcome to SwapSavvy Pro!",
                recipients=[email],
                html=render_template('welcome_email.html',
                                   username=username,
                                   header_img=url_for('static', filename='img/email/header.png', _external=True))
            )
            mail.send(msg)
            print(f"✅ Welcome email sent to {email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send welcome email to {email}: {e}")
            return False

    @staticmethod
    def send_password_reset_email(email, username, reset_link):
        """Send password reset email"""
        try:
            from flask_mail import Message
            msg = Message(
                subject="SwapSavvy Pro — Password Reset",
                recipients=[email],
                html=render_template('password_reset_email.html',
                                   username=username,
                                   reset_link=reset_link,
                                   header_img=url_for('static', filename='img/email/header.png', _external=True))
            )
            mail.send(msg)
            print(f"✅ Password reset email sent to {email}")
            return True
        except Exception as e:
            print(f"❌ Failed to send password reset email to {email}: {e}")
            return False

# ==================== IMAGE HELPER FUNCTIONS ====================

def get_user_avatar(user):
    """Safe function to get user avatar with fallback"""
    if hasattr(user, 'avatar') and user.avatar:
        return user.avatar
    return 'img/default-avatar.png'

def get_user_cover(user):
    """Safe function to get user cover with fallback"""
    if hasattr(user, 'cover_photo') and user.cover_photo:
        return user.cover_photo
    return 'img/default-cover.jpg'

def get_portfolio_image(portfolio_item):
    """Safe function to get portfolio image with fallback"""
    if hasattr(portfolio_item, 'media_path') and portfolio_item.media_path:
        return portfolio_item.media_path
    return 'img/portfolio-placeholder.png'

# ==================== PROFILE MANAGEMENT FUNCTIONS ====================

def update_user_skills(user, request):
    """Update user skills from form data"""
    UserSkill.query.filter_by(user_id=user.id).delete()
    
    skill_names = request.form.getlist('skill_names[]')
    proficiencies = request.form.getlist('skill_proficiencies[]')
    years_list = request.form.getlist('skill_years[]')
    
    for i, skill_name in enumerate(skill_names):
        if skill_name.strip():
            skill = Skill.query.filter_by(name=skill_name.strip().lower()).first()
            if not skill:
                skill = Skill(name=skill_name.strip().lower())
                db.session.add(skill)
                db.session.flush()
            
            user_skill = UserSkill(
                user_id=user.id,
                skill_id=skill.id,
                proficiency=proficiencies[i] if i < len(proficiencies) else 'beginner',
                years_experience=int(years_list[i]) if i < len(years_list) and years_list[i] else None
            )
            db.session.add(user_skill)

# ==================== GUEST ROUTES ====================

@app.route('/browse-as-guest')
def browse_as_guest():
    """Start guest browsing session"""
    session.clear()
    session['is_guest'] = True
    session['guest_expiry'] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    session['guest_id'] = str(uuid.uuid4())[:8]
    flash('You are now browsing as a guest. Some features are limited.', 'info')
    return redirect(url_for('explore'))

@app.route('/upgrade-from-guest')
def upgrade_from_guest():
    """Redirect to signup from guest session"""
    if session.get('is_guest'):
        session['guest_upgrade'] = True
        return redirect(url_for('signup'))
    return redirect(url_for('signup'))

@app.route('/end-guest-session')
def end_guest_session():
    """End guest session"""
    session.clear()
    flash('Guest session ended.', 'info')
    return redirect(url_for('landing'))

@app.route('/guest', endpoint='guest_mode')
def guest_mode():
    """Alias for guest mode"""
    return redirect(url_for('browse_as_guest'))

# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_verified:
            return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', 'other')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('signup'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'danger')
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first() or PendingUser.query.filter_by(email=email).first():
            flash('Email already registered or pending verification', 'danger')
            return redirect(url_for('signup'))

        if User.query.filter_by(username=username).first() or PendingUser.query.filter_by(username=username).first():
            flash('Username already taken or pending', 'danger')
            return redirect(url_for('signup'))

        try:
            assigned_id = generate_assigned_id(username)
            avatar = get_avatar_path(gender)
            password_hash = generate_password_hash(password)

            pending = PendingUser(
                username=username,
                email=email,
                password_hash=password_hash,
                name=name,
                gender=gender,
                avatar=avatar,
                assigned_id=assigned_id
            )
            db.session.add(pending)
            db.session.commit()

            code = f"{random.randint(0, 999999):06d}"
            expires_at = datetime.utcnow() + timedelta(minutes=10)

            EmailVerification.query.filter_by(pending_user_id=pending.id).delete()

            verification = EmailVerification(
                pending_user_id=pending.id,
                code=code,
                expires_at=expires_at,
                last_sent_at=datetime.utcnow()
            )
            db.session.add(verification)
            db.session.commit()

            email_service = EmailService()
            if email_service.send_verification_email(pending.email, pending.username, code):
                session['pending_id'] = pending.id
                flash('Verification code sent to your email', 'success')
                return redirect(url_for('verify_code'))
            else:
                db.session.delete(verification)
                db.session.delete(pending)
                db.session.commit()
                flash('Failed to send verification email. Please check SMTP settings and try again.', 'danger')
                return redirect(url_for('signup'))

        except Exception as e:
            db.session.rollback()
            print("Signup error:", e)
            flash('An error occurred during registration', 'danger')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify_code():
    if 'pending_id' not in session:
        flash('Please complete signup first', 'danger')
        return redirect(url_for('signup'))

    pending = PendingUser.query.get(session['pending_id'])
    if not pending:
        flash('Invalid session. Please sign up again.', 'danger')
        session.pop('pending_id', None)
        return redirect(url_for('signup'))

    verification = EmailVerification.query.filter_by(
        pending_user_id=pending.id
    ).order_by(EmailVerification.created_at.desc()).first()

    if request.method == 'POST':
        code = request.form['code'].strip()

        if not verification or verification.expires_at < datetime.utcnow():
            flash('Verification code expired. Please request a new one.', 'danger')
            return redirect(url_for('verify_code'))

        if verification.attempts >= 5:
            flash('Too many attempts. Please request a new code.', 'danger')
            return redirect(url_for('verify_code'))

        if verification.code == code:
            if User.query.filter_by(email=pending.email).first() or User.query.filter_by(username=pending.username).first():
                db.session.delete(verification)
                pending.status = 'expired'
                db.session.commit()
                session.pop('pending_id', None)
                flash('A user with same email/username already exists. Please try logging in.', 'danger')
                return redirect(url_for('login'))

            user = pending.to_user()
            user.is_verified = True
            
            email_service = EmailService()
            email_service.send_welcome_email(user.email, user.username)
            
            try:
                db.session.add(user)
                db.session.delete(verification)
                db.session.delete(pending)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print("Error creating user from pending:", e)
                flash('An error occurred finalizing registration. Please try again.', 'danger')
                return redirect(url_for('signup'))

            session.pop('pending_id', None)
            flash('Email verified successfully! You can now login.', 'success')
            return redirect(url_for('login'))
        else:
            verification.attempts += 1
            db.session.commit()
            flash('Invalid verification code', 'danger')
            return redirect(url_for('verify_code'))

    debug_code = verification.code if verification else "No code found"
    
    return render_template('verify.html', 
                         email=pending.email,
                         debug_code=debug_code if app.debug else None)

@app.route('/resend-code', methods=['POST'])
@limiter.limit("3 per hour")
def resend_code():
    if 'pending_id' not in session:
        flash('Please complete signup first', 'danger')
        return redirect(url_for('signup'))

    pending = PendingUser.query.get(session['pending_id'])
    if not pending:
        flash('Invalid session. Please sign up again.', 'danger')
        session.pop('pending_id', None)
        return redirect(url_for('signup'))

    user_key = f"resend_pending_{pending.id}"
    current_time = datetime.utcnow()

    if user_key in recent_resends:
        last_resend, count = recent_resends[user_key]
        if current_time - last_resend < timedelta(hours=1) and count >= 3:
            flash('Too many resend attempts. Please wait before trying again.', 'danger')
            return redirect(url_for('verify_code'))

    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    EmailVerification.query.filter_by(pending_user_id=pending.id).delete()

    verification = EmailVerification(
        pending_user_id=pending.id,
        code=code,
        expires_at=expires_at,
        last_sent_at=datetime.utcnow()
    )
    db.session.add(verification)
    db.session.commit()

    if user_key in recent_resends:
        recent_resends[user_key] = (current_time, recent_resends[user_key][1] + 1)
    else:
        recent_resends[user_key] = (current_time, 1)

    email_service = EmailService()
    if email_service.send_verification_email(pending.email, pending.username, code):
        flash('New verification code sent', 'success')
    else:
        flash('Failed to send verification email. Please check SMTP settings.', 'danger')
    return redirect(url_for('verify_code'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        login_input = request.form['login_input'].strip().lower()
        password = request.form['password']

        user = User.query.filter(
            (User.email == login_input) | (User.username == login_input)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_verified:
                session['pending_user_id'] = user.id
                flash('Please verify your email before logging in', 'warning')
                return redirect(url_for('verify_code'))
            session['user_id'] = user.id
            session.pop('is_guest', None)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('landing'))

# ==================== PROFILE MANAGEMENT ROUTES ====================

@app.route('/update_profile', methods=['POST'])
@guest_protected
@login_required
def update_profile():
    """Update user profile with Learn/Teach mode data"""
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('login'))
    
    try:
        user.username = request.form.get('username')
        user.name = request.form.get('name')
        user.location = request.form.get('location')
        user.website = request.form.get('website')
        user.headline = request.form.get('headline')
        user.summary = request.form.get('summary')
        
        profile_mode = request.form.get('profile_mode', 'both')
        user.profile_mode = ProfileMode(profile_mode)
        
        user.open_to_work = 'open_to_work' in request.form
        user.open_to_freelance = 'open_to_freelance' in request.form
        
        if profile_mode in ['teacher', 'both']:
            hourly_rate = request.form.get('hourly_rate')
            user.hourly_rate = Decimal(hourly_rate) if hourly_rate else None
            user.response_time = request.form.get('response_time')
        
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                avatar_path = save_uploaded_file(file, 'avatars')
                if avatar_path:
                    user.avatar = avatar_path
        
        if 'cover_photo' in request.files:
            file = request.files['cover_photo']
            if file and file.filename:
                cover_path = save_uploaded_file(file, 'covers')
                if cover_path:
                    user.cover_photo = cover_path
        
        update_user_skills(user, request)
        
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        if current_password and new_password:
            if check_password_hash(user.password_hash, current_password):
                user.password_hash = generate_password_hash(new_password)
                flash('Password updated successfully', 'success')
            else:
                flash('Current password is incorrect', 'error')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating profile: {str(e)}', 'error')
    
    return redirect(url_for('profile', username=user.username))

# ==================== PORTFOLIO MANAGEMENT ROUTES ====================

@app.route('/manage-portfolio')
@guest_protected
@login_required
def manage_portfolio():
    """Manage user portfolio items"""
    user = User.query.get(session['user_id'])
    portfolio_items = user.portfolio_items.order_by(PortfolioItem.created_at.desc()).all()
    return render_template('manage_portfolio.html', portfolio_items=portfolio_items)

@app.route('/portfolio/add', methods=['POST'])
@guest_protected
@login_required
def add_portfolio_item():
    """Add new portfolio item"""
    user = User.query.get(session['user_id'])
    
    title = request.form.get('title')
    description = request.form.get('description')
    project_url = request.form.get('project_url')
    media_file = request.files.get('media')
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('manage_portfolio'))
    
    try:
        media_path = None
        if media_file and media_file.filename:
            media_path = save_uploaded_file(media_file, 'portfolio')
        
        portfolio_item = PortfolioItem(
            user_id=user.id,
            title=title,
            description=description,
            project_url=project_url,
            media_path=media_path
        )
        
        db.session.add(portfolio_item)
        db.session.commit()
        flash('Portfolio item added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding portfolio item: {str(e)}', 'error')
    
    return redirect(url_for('manage_portfolio'))

@app.route('/portfolio/<int:item_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_portfolio_item(item_id):
    """Edit portfolio item"""
    portfolio_item = PortfolioItem.query.get_or_404(item_id)
    
    if portfolio_item.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_portfolio'))
    
    try:
        portfolio_item.title = request.form.get('title')
        portfolio_item.description = request.form.get('description')
        portfolio_item.project_url = request.form.get('project_url')
        
        media_file = request.files.get('media')
        if media_file and media_file.filename:
            media_path = save_uploaded_file(media_file, 'portfolio')
            if media_path:
                portfolio_item.media_path = media_path
        
        db.session.commit()
        flash('Portfolio item updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating portfolio item: {str(e)}', 'error')
    
    return redirect(url_for('manage_portfolio'))

@app.route('/portfolio/<int:item_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_portfolio_item(item_id):
    """Delete portfolio item"""
    portfolio_item = PortfolioItem.query.get_or_404(item_id)
    
    if portfolio_item.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_portfolio'))
    
    try:
        db.session.delete(portfolio_item)
        db.session.commit()
        flash('Portfolio item deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting portfolio item: {str(e)}', 'error')
    
    return redirect(url_for('manage_portfolio'))

# ==================== EXPERIENCE MANAGEMENT ROUTES ====================

@app.route('/manage-experience')
@guest_protected
@login_required
def manage_experience():
    """Manage user experience"""
    user = User.query.get(session['user_id'])
    experiences = user.experiences.order_by(Experience.start_date.desc()).all()
    return render_template('manage_experience.html', experiences=experiences)

@app.route('/experience/add', methods=['POST'])
@guest_protected
@login_required
def add_experience():
    """Add new experience"""
    user = User.query.get(session['user_id'])
    
    title = request.form.get('title')
    company = request.form.get('company')
    location = request.form.get('location')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    current = request.form.get('current') == 'on'
    description = request.form.get('description')
    
    if not title or not company or not start_date_str:
        flash('Title, company, and start date are required', 'error')
        return redirect(url_for('manage_experience'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str and not current else None
        
        experience = Experience(
            user_id=user.id,
            title=title,
            company=company,
            location=location,
            start_date=start_date,
            end_date=end_date,
            current=current,
            description=description
        )
        
        db.session.add(experience)
        db.session.commit()
        flash('Experience added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding experience: {str(e)}', 'error')
    
    return redirect(url_for('manage_experience'))

@app.route('/experience/<int:exp_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_experience(exp_id):
    """Edit experience"""
    experience = Experience.query.get_or_404(exp_id)
    
    if experience.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_experience'))
    
    try:
        experience.title = request.form.get('title')
        experience.company = request.form.get('company')
        experience.location = request.form.get('location')
        experience.description = request.form.get('description')
        experience.current = request.form.get('current') == 'on'
        
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if start_date_str:
            experience.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if end_date_str and not experience.current:
            experience.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            experience.end_date = None
        
        db.session.commit()
        flash('Experience updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating experience: {str(e)}', 'error')
    
    return redirect(url_for('manage_experience'))

@app.route('/experience/<int:exp_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_experience(exp_id):
    """Delete experience"""
    experience = Experience.query.get_or_404(exp_id)
    
    if experience.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_experience'))
    
    try:
        db.session.delete(experience)
        db.session.commit()
        flash('Experience deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting experience: {str(e)}', 'error')
    
    return redirect(url_for('manage_experience'))

# ==================== EDUCATION MANAGEMENT ROUTES ====================

@app.route('/manage-education')
@guest_protected
@login_required
def manage_education():
    """Manage user education"""
    user = User.query.get(session['user_id'])
    educations = user.educations.order_by(Education.start_date.desc()).all()
    return render_template('manage_education.html', educations=educations)

@app.route('/education/add', methods=['POST'])
@guest_protected
@login_required
def add_education():
    """Add new education"""
    user = User.query.get(session['user_id'])
    
    school = request.form.get('school')
    degree = request.form.get('degree')
    field_of_study = request.form.get('field_of_study')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    current = request.form.get('current') == 'on'
    description = request.form.get('description')
    
    if not school:
        flash('School is required', 'error')
        return redirect(url_for('manage_education'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str and not current else None
        
        education = Education(
            user_id=user.id,
            school=school,
            degree=degree,
            field_of_study=field_of_study,
            start_date=start_date,
            end_date=end_date,
            current=current,
            description=description
        )
        
        db.session.add(education)
        db.session.commit()
        flash('Education added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding education: {str(e)}', 'error')
    
    return redirect(url_for('manage_education'))

@app.route('/education/<int:edu_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_education(edu_id):
    """Edit education"""
    education = Education.query.get_or_404(edu_id)
    
    if education.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_education'))
    
    try:
        education.school = request.form.get('school')
        education.degree = request.form.get('degree')
        education.field_of_study = request.form.get('field_of_study')
        education.description = request.form.get('description')
        education.current = request.form.get('current') == 'on'
        
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if start_date_str:
            education.start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if end_date_str and not education.current:
            education.end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            education.end_date = None
        
        db.session.commit()
        flash('Education updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating education: {str(e)}', 'error')
    
    return redirect(url_for('manage_education'))

@app.route('/education/<int:edu_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_education(edu_id):
    """Delete education"""
    education = Education.query.get_or_404(edu_id)
    
    if education.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('manage_education'))
    
    try:
        db.session.delete(education)
        db.session.commit()
        flash('Education deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting education: {str(e)}', 'error')
    
    return redirect(url_for('manage_education'))

# ==================== SOCIAL FEATURES ROUTES ====================

@app.route('/user/<int:user_id>/follow', methods=['POST'])
@guest_protected
@login_required
def follow_user(user_id):
    """Follow/unfollow a user"""
    current_user = User.query.get(session['user_id'])
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    if current_user.id == target_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    if current_user.is_following(target_user):
        current_user.unfollow(target_user)
        action = 'unfollowed'
    else:
        current_user.follow(target_user)
        action = 'followed'
    
    db.session.commit()
    
    return jsonify({
        'action': action,
        'followers_count': target_user.followers.count()
    })

@app.route('/user/<int:user_id>/connect', methods=['POST'])
@guest_protected
@login_required
def connect_user(user_id):
    """Send connection request to a user"""
    current_user = User.query.get(session['user_id'])
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    if current_user.id == target_user.id:
        return jsonify({'error': 'Cannot connect with yourself'}), 400
    
    if current_user.is_connected(target_user):
        return jsonify({'error': 'Already connected'}), 400
    
    if current_user.connect(target_user):
        notification = Notification(
            user_id=target_user.id,
            actor_id=current_user.id,
            verb='connection_request',
            target_user_id=current_user.id
        )
        db.session.add(notification)
        db.session.commit()
        return jsonify({'message': 'Connection request sent'})
    else:
        return jsonify({'error': 'Connection request already pending'}), 400

@app.route('/connections')
@guest_protected
@login_required
def connections():
    """View user connections"""
    user = User.query.get(session['user_id'])
    
    pending_connections = Connection.query.filter(
        ((Connection.user1_id == user.id) | (Connection.user2_id == user.id)) &
        (Connection.status == 'pending')
    ).all()
    
    accepted_connections = Connection.query.filter(
        ((Connection.user1_id == user.id) | (Connection.user2_id == user.id)) &
        (Connection.status == 'accepted')
    ).all()
    
    pending_users = []
    for conn in pending_connections:
        other_user = User.query.get(conn.user2_id if conn.user1_id == user.id else conn.user1_id)
        if other_user:
            pending_users.append({
                'user': other_user,
                'connection': conn,
                'is_sent_by_me': conn.user1_id == user.id
            })
    
    accepted_users = []
    for conn in accepted_connections:
        other_user = User.query.get(conn.user2_id if conn.user1_id == user.id else conn.user1_id)
        if other_user:
            accepted_users.append(other_user)
    
    return render_template('connections.html', 
                         pending_users=pending_users,
                         accepted_users=accepted_users)

@app.route('/connection/<int:conn_id>/accept', methods=['POST'])
@guest_protected
@login_required
def accept_connection(conn_id):
    """Accept connection request"""
    connection = Connection.query.get_or_404(conn_id)
    
    if connection.user2_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('connections'))
    
    connection.status = 'accepted'
    
    notification = Notification(
        user_id=connection.user1_id,
        actor_id=session['user_id'],
        verb='connection_accepted',
        target_user_id=session['user_id']
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Connection request accepted!', 'success')
    return redirect(url_for('connections'))

@app.route('/connection/<int:conn_id>/reject', methods=['POST'])
@guest_protected
@login_required
def reject_connection(conn_id):
    """Reject connection request"""
    connection = Connection.query.get_or_404(conn_id)
    
    if connection.user2_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('connections'))
    
    db.session.delete(connection)
    db.session.commit()
    
    flash('Connection request rejected', 'info')
    return redirect(url_for('connections'))

# ==================== MESSAGING ROUTES ====================

@app.route('/messages')
@guest_protected
@login_required
def messages():
    """View messages"""
    user = User.query.get(session['user_id'])
    
    sent_conversations = db.session.query(Message.receiver_id).filter_by(sender_id=user.id).distinct()
    received_conversations = db.session.query(Message.sender_id).filter_by(receiver_id=user.id).distinct()
    
    all_conversation_ids = set([id for (id,) in sent_conversations] + [id for (id,) in received_conversations])
    
    conversations = []
    for user_id in all_conversation_ids:
        other_user = User.query.get(user_id)
        if other_user:
            last_message = Message.query.filter(
                ((Message.sender_id == user.id) & (Message.receiver_id == user_id)) |
                ((Message.sender_id == user_id) & (Message.receiver_id == user.id))
            ).order_by(Message.created_at.desc()).first()
            
            unread_count = Message.query.filter_by(sender_id=user_id, receiver_id=user.id, is_read=False).count()
            
            conversations.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
    
    conversations.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min, reverse=True)
    
    return render_template('messages.html', conversations=conversations)

# Updated view_conversation route in run.py
@app.route('/messages/<int:user_id>')
@guest_protected
@login_required
def view_conversation(user_id):
    """View conversation with specific user - can be accessed directly from profiles"""
    current_user_obj = User.query.get(session['user_id'])
    other_user = User.query.get(user_id)
    
    if not other_user:
        flash('User not found', 'error')
        return redirect(url_for('messages'))
    
    # Mark messages as read when viewing conversation
    Message.query.filter_by(sender_id=user_id, receiver_id=current_user_obj.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    # Get all messages for this conversation
    messages = Message.query.filter(
        ((Message.sender_id == current_user_obj.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_obj.id))
    ).order_by(Message.created_at.asc()).all()
    
    # Get conversations list for the sidebar
    sent_conversations = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_obj.id).distinct()
    received_conversations = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_obj.id).distinct()
    
    all_conversation_ids = set([id for (id,) in sent_conversations] + [id for (id,) in received_conversations])
    
    conversations = []
    for conv_user_id in all_conversation_ids:
        conv_user = User.query.get(conv_user_id)
        if conv_user:
            last_message = Message.query.filter(
                ((Message.sender_id == current_user_obj.id) & (Message.receiver_id == conv_user_id)) |
                ((Message.sender_id == conv_user_id) & (Message.receiver_id == current_user_obj.id))
            ).order_by(Message.created_at.desc()).first()
            
            unread_count = Message.query.filter_by(sender_id=conv_user_id, receiver_id=current_user_obj.id, is_read=False).count()
            
            conversations.append({
                'user': conv_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
    
    conversations.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min, reverse=True)
    
    return render_template('conversation.html', 
                         messages=messages, 
                         other_user=other_user,
                         current_user=current_user_obj,
                         conversations=conversations)

@app.route('/messages/send', methods=['POST'])
@guest_protected
@login_required
def send_message():
    """Send a message"""
    current_user = User.query.get(session['user_id'])
    receiver_id = request.form.get('receiver_id')
    content = request.form.get('content')
    
    if not content or not receiver_id:
        return jsonify({'error': 'Message content and receiver are required'}), 400
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404
    
    try:
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        
        notification = Notification(
            user_id=receiver_id,
            actor_id=current_user.id,
            verb='new_message',
            target_user_id=current_user.id
        )
        
        db.session.add(message)
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message_id': message.id,
            'created_at': message.created_at.strftime('%b %d, %Y at %H:%M')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error sending message: {str(e)}'}), 500

# ==================== NOTIFICATION ROUTES ====================

@app.route('/notifications')
@guest_protected
@login_required
def notifications():
    """View notifications"""
    user = User.query.get(session['user_id'])
    notifications = user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/read-all', methods=['POST'])
@guest_protected
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user = User.query.get(session['user_id'])
    
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error marking notifications as read: {str(e)}'}), 500

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@guest_protected
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error marking notification as read: {str(e)}'}), 500

@app.route('/api/notifications/count')
@login_required
def get_notification_count():
    """Get unread notification count for API"""
    user = User.query.get(session['user_id'])
    unread_count = user.notifications.filter_by(is_read=False).count()
    return jsonify({'count': unread_count})

# ==================== POST AND CONTENT ROUTES ====================

@app.route('/post/<int:post_id>/like', methods=['POST'])
@guest_protected
@login_required
def like_post(post_id):
    """Like/unlike a post"""
    user = User.query.get(session['user_id'])
    post = Post.query.get_or_404(post_id)
    
    existing_like = Like.query.filter_by(user_id=user.id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        action = 'unliked'
        
        Notification.query.filter_by(
            user_id=post.user_id,
            actor_id=user.id,
            verb='like',
            target_post_id=post_id
        ).delete()
    else:
        like = Like(user_id=user.id, post_id=post_id)
        db.session.add(like)
        action = 'liked'
        
        if post.user_id != user.id:
            notification = Notification(
                user_id=post.user_id,
                actor_id=user.id,
                verb='like',
                target_post_id=post_id
            )
            db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'action': action,
        'likes_count': post.like_count()
    })

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@guest_protected
@login_required
def comment_post(post_id):
    """Comment on a post"""
    user = User.query.get(session['user_id'])
    post = Post.query.get_or_404(post_id)
    comment_content = request.form.get('comment', '').strip()
    
    if not comment_content:
        flash('Comment cannot be empty', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        comment = Comment(
            user_id=user.id,
            post_id=post_id,
            content=comment_content
        )
        
        db.session.add(comment)
        
        if post.user_id != user.id:
            notification = Notification(
                user_id=post.user_id,
                actor_id=user.id,
                verb='comment',
                target_post_id=post_id
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('Comment added!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error adding comment', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/create-post', methods=['POST'])
@guest_protected
@login_required
def create_post():
    """Create a new post"""
    user = User.query.get(session['user_id'])
    
    content = request.form.get('content', '').strip()
    media_file = request.files.get('media')
    
    if not content and not media_file:
        flash('Post cannot be empty', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        media_path = None
        if media_file and media_file.filename:
            media_path = save_uploaded_file(media_file, 'posts')
        
        post = Post(
            user_id=user.id,
            content=content,
            media_path=media_path
        )
        
        db.session.add(post)
        db.session.commit()
        flash('Post created successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error creating post', 'danger')
    
    return redirect(url_for('dashboard'))

# ==================== DASHBOARD & PUBLIC ROUTES ====================

@app.route('/dashboard')
def dashboard():
    """Dashboard - available to both users and guests"""
    if check_guest_expiry():
        return redirect(url_for('landing'))
    
    if session.get('is_guest'):
        posts = Post.query.join(User).filter(User.is_verified==True).order_by(Post.created_at.desc()).limit(10).all()
        return render_template('dashboard.html', posts=posts, is_guest=True, suggestions=[])
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_verified:
        return redirect(url_for('login'))
    
    following_ids = [f.followed_id for f in user.following.all()]
    following_ids.append(user.id)
    
    posts = Post.query.filter(Post.user_id.in_(following_ids)).order_by(Post.created_at.desc()).all()
    
    # Get suggestions - users not followed by current user
    suggestions = User.query.filter(
        User.id != user.id,
        User.is_verified == True
    ).filter(~User.id.in_(following_ids)).limit(5).all()
    
    # Precompute counts for template
    posts_count = user.posts.count() if hasattr(user.posts, 'count') else len(user.posts)
    followers_count = user.followers.count() if hasattr(user.followers, 'count') else len(user.followers)
    following_count = user.following.count() if hasattr(user.following, 'count') else len(user.following)
    
    return render_template('dashboard.html', 
                         posts=posts, 
                         is_guest=False,
                         suggestions=suggestions,
                         posts_count=posts_count,
                         followers_count=followers_count,
                         following_count=following_count)

@app.route('/explore')
def explore():
    """Explore page - available to guests"""
    if check_guest_expiry():
        return redirect(url_for('landing'))
    
    query = request.args.get('q', '')
    filter_type = request.args.get('type', 'all')
    
    users = []
    posts = []
    
    if query:
        if filter_type in ['all', 'people']:
            users = User.query.filter(
                (User.username.ilike(f'%{query}%')) | 
                (User.name.ilike(f'%{query}%')) |
                (User.headline.ilike(f'%{query}%'))
            ).filter_by(is_verified=True).limit(20).all()
        
        if filter_type in ['all', 'posts']:
            posts = Post.query.join(User).filter(
                Post.content.ilike(f'%{query}%')
            ).filter(User.is_verified==True).order_by(Post.created_at.desc()).limit(20).all()
    else:
        users = User.query.filter_by(is_verified=True).order_by(db.func.random()).limit(6).all()
        posts = Post.query.join(User).filter(User.is_verified==True).order_by(Post.created_at.desc()).limit(10).all()
    
    trending_skills = Skill.query.join(UserSkill).group_by(Skill.id).order_by(db.func.count(UserSkill.id).desc()).limit(10).all()
    
    return render_template('explore.html', 
                         users=users, 
                         posts=posts, 
                         query=query, 
                         filter_type=filter_type,
                         trending_skills=trending_skills)

@app.route('/search')
def search():
    """Search for users"""
    query = request.args.get('q', '')
    users = []
    
    if query:
        users = User.query.filter(
            (User.username.ilike(f'%{query}%')) | 
            (User.name.ilike(f'%{query}%')) |
            (User.headline.ilike(f'%{query}%'))
        ).filter_by(is_verified=True).all()
    
    return render_template('search.html', users=users, query=query)

@app.route('/profile/<username>')
def profile(username):
    """Profile page - available to guests (read-only)"""
    if check_guest_expiry():
        return redirect(url_for('landing'))
    
    user = User.query.filter_by(username=username, is_verified=True).first_or_404()
    posts = user.posts.order_by(Post.created_at.desc()).all()
    
    is_owner = False
    is_following = False
    is_connected = False
    
    if not session.get('is_guest') and 'user_id' in session:
        current_user_obj = User.query.get(session['user_id'])
        if current_user_obj:
            is_owner = current_user_obj.id == user.id
            is_following = current_user_obj.is_following(user)
            is_connected = current_user_obj.is_connected(user)
    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts,
                         is_owner=is_owner,
                         is_following=is_following,
                         is_connected=is_connected)

@app.route('/edit-profile')
@guest_protected
def edit_profile():
    """Edit profile - protected from guests"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    return render_template('edit_profile.html', user=user)

# ==================== REVIEW AND RATING ROUTES ====================

@app.route('/user/<int:user_id>/review', methods=['POST'])
@guest_protected
@login_required
def add_review(user_id):
    """Add review for a user"""
    current_user = User.query.get(session['user_id'])
    target_user = User.query.get(user_id)
    
    if not target_user:
        flash('User not found', 'error')
        return redirect(request.referrer or url_for('explore'))
    
    if current_user.id == target_user.id:
        flash('Cannot review yourself', 'error')
        return redirect(request.referrer or url_for('explore'))
    
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    service_type = request.form.get('service_type')
    
    if not rating or not service_type:
        flash('Rating and service type are required', 'error')
        return redirect(request.referrer or url_for('explore'))
    
    try:
        existing_review = Review.query.filter_by(
            reviewer_id=current_user.id,
            reviewee_id=target_user.id,
            service_type=service_type
        ).first()
        
        if existing_review:
            flash('You have already reviewed this user for this service type', 'error')
            return redirect(request.referrer or url_for('explore'))
        
        review = Review(
            reviewer_id=current_user.id,
            reviewee_id=target_user.id,
            rating=int(rating),
            comment=comment,
            service_type=service_type
        )
        
        notification = Notification(
            user_id=target_user.id,
            actor_id=current_user.id,
            verb='review',
            target_user_id=current_user.id
        )
        
        db.session.add(review)
        db.session.add(notification)
        db.session.commit()
        
        flash('Review submitted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting review: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('profile', username=target_user.username))

# ==================== API ROUTES ====================

@app.route('/api/user/<username>')
def api_get_user(username):
    """Get user data for API"""
    user = User.query.filter_by(username=username, is_verified=True).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'avatar': get_user_avatar(user),
        'headline': user.headline,
        'location': user.location,
        'profile_mode': user.profile_mode.value,
        'open_to_work': user.open_to_work,
        'open_to_freelance': user.open_to_freelance
    }
    
    return jsonify(user_data)

@app.route('/api/posts')
def api_get_posts():
    """Get posts for API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    posts = Post.query.join(User).filter(User.is_verified==True)\
        .order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    posts_data = []
    for post in posts.items:
        posts_data.append({
            'id': post.id,
            'content': post.content,
            'media_path': post.media_path,
            'created_at': post.created_at.isoformat(),
            'user': {
                'id': post.user.id,
                'username': post.user.username,
                'name': post.user.name,
                'avatar': get_user_avatar(post.user)
            },
            'like_count': post.like_count(),
            'comment_count': post.comment_count()
        })
    
    return jsonify({
        'posts': posts_data,
        'total': posts.total,
        'pages': posts.pages,
        'current_page': page
    })

# ==================== CONTEXT PROCESSOR ====================

@app.context_processor
def inject_template_vars():
    """Inject variables into all templates (safe if User model lacks is_guest)."""
    user = None
    # session-level guest flag (e.g., temporary guest sessions)
    session_is_guest = bool(session.get('is_guest', False))

    # Try to load user if session contains user_id and session not explicitly guest
    if not session_is_guest and 'user_id' in session:
        try:
            user = User.query.get(session['user_id'])
        except Exception:
            # If anything goes wrong while fetching user, clear session to avoid stale state
            session.clear()
            user = None

    # If session indicates guest or we couldn't load a real user, create GuestUser
    if (session_is_guest or not user):
        class GuestUser:
            def __init__(self):
                self.id = None
                self.username = "guest"
                self.name = "Guest User"
                self.avatar = "img/default-avatar.png"
                self.cover_photo = "img/default-cover.jpg"
                # keep attribute so templates/code expecting it won't fail
                self.is_guest = True
                self.is_verified = False

            def is_following(self, other_user):
                return False

            def is_connected(self, other_user):
                return False

        # If we actually loaded a real user earlier, prefer that (unless session says guest)
        if user and not session_is_guest:
            # keep loaded user
            pass
        else:
            user = GuestUser()

    # Determine final is_guest flag safely:
    # - session flag OR user's attribute if present (use getattr to avoid AttributeError)
    user_is_guest = bool(getattr(user, "is_guest", False))
    is_guest = session_is_guest or user_is_guest

    # Initialize counts / lists
    unread_messages_count = 0
    unread_notifications_count = 0
    recent_notifications = []

    # Only query counts if we have a real logged-in user (id present and not guest)
    if user and not is_guest and getattr(user, "id", None):
        try:
            unread_messages_count = Message.query.filter_by(receiver_id=user.id, is_read=False).count()
            unread_notifications_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
            recent_notifications = Notification.query.filter_by(user_id=user.id) \
                .order_by(Notification.created_at.desc()).limit(5).all()
        except Exception:
            # In case DB queries fail, don't crash templates — log if needed
            unread_messages_count = 0
            unread_notifications_count = 0
            recent_notifications = []

    return dict(
        current_user=user,
        is_guest=is_guest,
        unread_messages_count=unread_messages_count,
        unread_notifications_count=unread_notifications_count,
        recent_notifications=recent_notifications,
        get_user_avatar=get_user_avatar,
        get_user_cover=get_user_cover,
        get_portfolio_image=get_portfolio_image
    )

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', error="Internal server error"), 500

@app.errorhandler(413)
def too_large(error):
    return render_template('error.html', error="File too large"), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template('error.html', error="Rate limit exceeded. Please try again later."), 429

# ==================== INITIALIZATION ====================

def setup_database():
    """Initialize database with migrations"""
    print("🔍 Setting up database...")
    
    with app.app_context():
        try:
            db.create_all()
            
            # Create upload directories
            upload_folders = ['avatars', 'covers', 'posts', 'portfolio', 'documents']
            for folder in upload_folders:
                folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder)
                os.makedirs(folder_path, exist_ok=True)
            
            # Create image directories
            img_folders = ['img', 'img/email']
            for folder in img_folders:
                folder_path = os.path.join(app.root_path, 'static', folder)
                os.makedirs(folder_path, exist_ok=True)
            
            print("✅ Database setup completed successfully!")
            
            # Print some debug info
            user_count = User.query.count()
            post_count = Post.query.count()
            print(f"📊 Current stats - Users: {user_count}, Posts: {post_count}")
            
        except Exception as e:
            print(f"❌ Database setup error: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    print("🚀 Starting SwapSavvy Pro Application...")
    
    if not app.debug:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            REMEMBER_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax'
        )
    
    setup_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
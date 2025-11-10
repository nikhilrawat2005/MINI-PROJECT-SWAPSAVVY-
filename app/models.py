from app import db
from datetime import datetime, timedelta
from decimal import Decimal
import enum
import json

class ProfileMode(enum.Enum):
    LEARNER = 'learner'
    TEACHER = 'teacher'
    BOTH = 'both'

class PriceType(enum.Enum):
    FIXED = 'fixed'
    HOURLY = 'hourly'
    PROJECT = 'project'
    FREE = 'free'

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    assigned_id = db.Column(db.String(16), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))
    gender = db.Column(db.String(10))
    avatar = db.Column(db.String(200))
    cover_photo = db.Column(db.String(200))
    
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
    success_rate = db.Column(db.Integer)
    
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_badge = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    posts = db.relationship("Post", back_populates="user", cascade="all, delete-orphan", lazy='dynamic')
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy='dynamic')
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy='dynamic')
    likes = db.relationship("Like", back_populates="user", cascade="all, delete-orphan")
    comments = db.relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", foreign_keys='Notification.user_id', backref='user', lazy='dynamic')
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
    category = db.Column(db.String(50))

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
    media_path = db.Column(db.String(500))
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

    __table_args__ = (db.UniqueConstraint('reviewer_id', 'reviewee_id', 'service_type', name='unique_review'),)

class PendingUser(db.Model):
    __tablename__ = 'pending_users'
    id = db.Column(db.Integer, primary_key=True)
    assigned_id = db.Column(db.String(16), unique=True, nullable=False)
    username = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))
    gender = db.Column(db.String(10))
    avatar = db.Column(db.String(200))
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
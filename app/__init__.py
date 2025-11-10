from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_mail import Mail
import os

# Initialize extensions
db = SQLAlchemy()
csrf = CSRFProtect()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)
mail = Mail()

def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'development')
    
    from config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    mail.init_app(app)
    
    # Security headers
    if not app.debug:
        Talisman(app, content_security_policy=None)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.profile import profile_bp
    from app.routes.social import social_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(social_bp)
    
    # Import models to ensure they are known to SQLAlchemy
    from app import models
    
    # Context processor
    @app.context_processor
    def inject_template_vars():
        """Inject variables into all templates"""
        from app.models import User, Message, Notification, ProfileMode
        from datetime import datetime
        
        user = None
        session_is_guest = bool(session.get('is_guest', False))

        if not session_is_guest and 'user_id' in session:
            try:
                user = User.query.get(session['user_id'])
            except Exception:
                session.clear()
                user = None

        if session_is_guest or not user:
            class GuestUser:
                def __init__(self):
                    self.id = None
                    self.username = "guest"
                    self.name = "Guest User"
                    self.avatar = "avatars/guest_default.png"
                    self.is_guest = True
                    self.is_verified = False
                    self.profile_mode = ProfileMode.BOTH
                    self.headline = "Guest User"
                    self.open_to_work = False
                    self.open_to_freelance = False

                def is_following(self, other_user):
                    return False

                def is_connected(self, other_user):
                    return False

            user = GuestUser()

        user_is_guest = bool(getattr(user, "is_guest", False))
        is_guest = session_is_guest or user_is_guest

        unread_messages_count = 0
        unread_notifications_count = 0
        recent_notifications = []

        if user and not is_guest and getattr(user, "id", None):
            try:
                unread_messages_count = Message.query.filter_by(receiver_id=user.id, is_read=False).count()
                unread_notifications_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
                recent_notifications = Notification.query.filter_by(user_id=user.id)\
                    .order_by(Notification.created_at.desc()).limit(5).all()
            except Exception:
                unread_messages_count = 0
                unread_notifications_count = 0
                recent_notifications = []

        return dict(
            current_user=user,
            is_guest=is_guest,
            unread_messages_count=unread_messages_count,
            unread_notifications_count=unread_notifications_count,
            recent_notifications=recent_notifications
        )
    
    # Error handlers
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
    
    return app
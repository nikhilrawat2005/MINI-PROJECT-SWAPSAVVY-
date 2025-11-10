import random
import time
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User, PendingUser, EmailVerification, ProfileMode, UserSkill, Skill

class UserService:
    @staticmethod
    def generate_assigned_id(username, length_prefix=3, tries=30):
        prefix = (username.strip().lower() + "x" * length_prefix)[:length_prefix]
        for _ in range(tries):
            num = f"{random.randint(0, 9999):04d}"
            candidate = prefix + num
            if not (User.query.filter_by(assigned_id=candidate).first() or
                    PendingUser.query.filter_by(assigned_id=candidate).first()):
                return candidate
        raise RuntimeError("Failed to generate unique assigned ID")

    @staticmethod
    def get_avatar_path(gender):
        gender = (gender or 'other').lower()
        if gender not in ('male', 'female', 'other'):
            gender = 'other'
        return f"avatars/{gender}_default.png"

    @staticmethod
    def create_pending_user(username, email, password, name, gender):
        """Create a pending user for email verification"""
        try:
            assigned_id = UserService.generate_assigned_id(username)
            avatar = UserService.get_avatar_path(gender)
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
            return pending
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def verify_pending_user(pending_id, code):
        """Verify a pending user with code"""
        pending = PendingUser.query.get(pending_id)
        if not pending:
            return None, "Invalid session"

        verification = EmailVerification.query.filter_by(
            pending_user_id=pending.id
        ).order_by(EmailVerification.created_at.desc()).first()

        if not verification or verification.is_expired():
            return None, "Verification code expired"

        if verification.attempts >= 5:
            return None, "Too many attempts"

        if verification.code != code:
            verification.attempts += 1
            db.session.commit()
            return None, "Invalid verification code"

        # Check if user already exists
        if User.query.filter_by(email=pending.email).first() or User.query.filter_by(username=pending.username).first():
            db.session.delete(verification)
            pending.status = 'expired'
            db.session.commit()
            return None, "User already exists"

        # Convert to actual user
        user = pending.to_user()
        db.session.add(user)
        db.session.delete(verification)
        db.session.delete(pending)
        db.session.commit()

        return user, "Success"

    @staticmethod
    def authenticate_user(login_input, password):
        """Authenticate user by email or username"""
        user = User.query.filter(
            (User.email == login_input) | (User.username == login_input)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            return user
        return None

    @staticmethod
    def update_user_profile(user_id, form_data, files):
        """Update user profile with form data"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        try:
            # Basic info
            user.username = form_data.get('username')
            user.name = form_data.get('name')
            user.location = form_data.get('location')
            user.website = form_data.get('website')
            user.headline = form_data.get('headline')
            user.summary = form_data.get('summary')
            
            # Profile mode
            profile_mode = form_data.get('profile_mode', 'both')
            user.profile_mode = ProfileMode(profile_mode)
            
            # Work preferences
            user.open_to_work = 'open_to_work' in form_data
            user.open_to_freelance = 'open_to_freelance' in form_data
            
            # Teacher-specific fields
            if profile_mode in ['teacher', 'both']:
                hourly_rate = form_data.get('hourly_rate')
                user.hourly_rate = float(hourly_rate) if hourly_rate else None
                user.response_time = form_data.get('response_time')

            db.session.commit()
            return True, "Profile updated successfully"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Error updating profile: {str(e)}"

    @staticmethod
    def create_verification_code(pending_user_id):
        """Create verification code for pending user"""
        code = f"{random.randint(0, 999999):06d}"
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Delete existing verifications
        EmailVerification.query.filter_by(pending_user_id=pending_user_id).delete()

        verification = EmailVerification(
            pending_user_id=pending_user_id,
            code=code,
            expires_at=expires_at,
            last_sent_at=datetime.utcnow()
        )
        db.session.add(verification)
        db.session.commit()
        
        return code

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def get_user_by_username(username):
        return User.query.filter_by(username=username, is_verified=True).first()

    @staticmethod
    def search_users(query):
        """Search users by username, name, or headline"""
        if not query:
            return User.query.filter_by(is_verified=True).limit(20).all()
        
        return User.query.filter(
            (User.username.ilike(f'%{query}%')) | 
            (User.name.ilike(f'%{query}%')) |
            (User.headline.ilike(f'%{query}%'))
        ).filter_by(is_verified=True).all()

    @staticmethod
    def update_user_skills(user, form_data):
        """Update user skills from form data"""
        UserSkill.query.filter_by(user_id=user.id).delete()
        
        skill_names = form_data.getlist('skill_names[]')
        proficiencies = form_data.getlist('skill_proficiencies[]')
        years_list = form_data.getlist('skill_years[]')
        
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
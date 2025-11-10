from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from app.models import User, PortfolioItem, Experience, Education, UserSkill, Skill, Service, LearningGoal, Post, Notification, Review
from app.services import UserService
import logging
import os
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)
profile_bp = Blueprint('profile', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webp', 'pdf', 'ppt', 'pptx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, subfolder):
    from werkzeug.utils import secure_filename
    import time
    from flask import current_app
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)
        return f"uploads/{subfolder}/{filename}"
    return None

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

@profile_bp.route('/profile/<username>')
def profile(username):
    """Profile page - available to guests (read-only)"""
    # Check guest expiry
    if session.get('is_guest') and session.get('guest_expiry'):
        if datetime.utcnow() > datetime.fromisoformat(session['guest_expiry']):
            session.clear()
            flash('Your guest session has expired. Please sign up to continue.', 'info')
            return redirect(url_for('main.landing'))

    user = UserService.get_user_by_username(username)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('main.explore'))
    
    posts = user.posts.order_by(Post.created_at.desc()).all()
    
    is_owner = False
    is_following = False
    is_connected = False
    
    if not session.get('is_guest') and 'user_id' in session:
        current_user_obj = UserService.get_user_by_id(session['user_id'])
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

@profile_bp.route('/edit-profile')
@guest_protected
@login_required
def edit_profile():
    """Edit profile - protected from guests"""
    user = UserService.get_user_by_id(session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))
    
    return render_template('edit_profile.html', user=user)

@profile_bp.route('/update_profile', methods=['POST'])
@guest_protected
@login_required
def update_profile():
    """Update user profile with Learn/Teach mode data"""
    user = UserService.get_user_by_id(session['user_id'])
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        success, message = UserService.update_user_profile(user.id, request.form, request.files)
        
        if success:
            # Handle file uploads
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
            
            # Handle skills update
            UserService.update_user_skills(user, request.form)
            
            # Handle password change
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
        else:
            flash(message, 'error')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating profile: {str(e)}', 'error')
    
    return redirect(url_for('profile.profile', username=user.username))

# Portfolio Management Routes
@profile_bp.route('/manage-portfolio')
@guest_protected
@login_required
def manage_portfolio():
    """Manage user portfolio items"""
    user = UserService.get_user_by_id(session['user_id'])
    portfolio_items = user.portfolio_items.order_by(PortfolioItem.created_at.desc()).all()
    return render_template('manage_portfolio.html', portfolio_items=portfolio_items)

@profile_bp.route('/portfolio/add', methods=['POST'])
@guest_protected
@login_required
def add_portfolio_item():
    """Add new portfolio item"""
    user = UserService.get_user_by_id(session['user_id'])
    
    title = request.form.get('title')
    description = request.form.get('description')
    project_url = request.form.get('project_url')
    media_file = request.files.get('media')
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('profile.manage_portfolio'))
    
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
    
    return redirect(url_for('profile.manage_portfolio'))

@profile_bp.route('/portfolio/<int:item_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_portfolio_item(item_id):
    """Edit portfolio item"""
    portfolio_item = PortfolioItem.query.get_or_404(item_id)
    
    if portfolio_item.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_portfolio'))
    
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
    
    return redirect(url_for('profile.manage_portfolio'))

@profile_bp.route('/portfolio/<int:item_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_portfolio_item(item_id):
    """Delete portfolio item"""
    portfolio_item = PortfolioItem.query.get_or_404(item_id)
    
    if portfolio_item.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_portfolio'))
    
    try:
        db.session.delete(portfolio_item)
        db.session.commit()
        flash('Portfolio item deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting portfolio item: {str(e)}', 'error')
    
    return redirect(url_for('profile.manage_portfolio'))

# Experience Management Routes
@profile_bp.route('/manage-experience')
@guest_protected
@login_required
def manage_experience():
    """Manage user experience"""
    user = UserService.get_user_by_id(session['user_id'])
    experiences = user.experiences.order_by(Experience.start_date.desc()).all()
    return render_template('manage_experience.html', experiences=experiences)

@profile_bp.route('/experience/add', methods=['POST'])
@guest_protected
@login_required
def add_experience():
    """Add new experience"""
    user = UserService.get_user_by_id(session['user_id'])
    
    title = request.form.get('title')
    company = request.form.get('company')
    location = request.form.get('location')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    current = request.form.get('current') == 'on'
    description = request.form.get('description')
    
    if not title or not company or not start_date_str:
        flash('Title, company, and start date are required', 'error')
        return redirect(url_for('profile.manage_experience'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str and not current else None
        
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
    
    return redirect(url_for('profile.manage_experience'))

@profile_bp.route('/experience/<int:exp_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_experience(exp_id):
    """Edit experience"""
    experience = Experience.query.get_or_404(exp_id)
    
    if experience.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_experience'))
    
    try:
        experience.title = request.form.get('title')
        experience.company = request.form.get('company')
        experience.location = request.form.get('location')
        experience.description = request.form.get('description')
        experience.current = request.form.get('current') == 'on'
        
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if start_date_str:
            experience.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        if end_date_str and not experience.current:
            experience.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            experience.end_date = None
        
        db.session.commit()
        flash('Experience updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating experience: {str(e)}', 'error')
    
    return redirect(url_for('profile.manage_experience'))

@profile_bp.route('/experience/<int:exp_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_experience(exp_id):
    """Delete experience"""
    experience = Experience.query.get_or_404(exp_id)
    
    if experience.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_experience'))
    
    try:
        db.session.delete(experience)
        db.session.commit()
        flash('Experience deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting experience: {str(e)}', 'error')
    
    return redirect(url_for('profile.manage_experience'))

# Education Management Routes
@profile_bp.route('/manage-education')
@guest_protected
@login_required
def manage_education():
    """Manage user education"""
    user = UserService.get_user_by_id(session['user_id'])
    educations = user.educations.order_by(Education.start_date.desc()).all()
    return render_template('manage_education.html', educations=educations)

@profile_bp.route('/education/add', methods=['POST'])
@guest_protected
@login_required
def add_education():
    """Add new education"""
    user = UserService.get_user_by_id(session['user_id'])
    
    school = request.form.get('school')
    degree = request.form.get('degree')
    field_of_study = request.form.get('field_of_study')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    current = request.form.get('current') == 'on'
    description = request.form.get('description')
    
    if not school:
        flash('School is required', 'error')
        return redirect(url_for('profile.manage_education'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str and not current else None
        
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
    
    return redirect(url_for('profile.manage_education'))

@profile_bp.route('/education/<int:edu_id>/edit', methods=['POST'])
@guest_protected
@login_required
def edit_education(edu_id):
    """Edit education"""
    education = Education.query.get_or_404(edu_id)
    
    if education.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_education'))
    
    try:
        education.school = request.form.get('school')
        education.degree = request.form.get('degree')
        education.field_of_study = request.form.get('field_of_study')
        education.description = request.form.get('description')
        education.current = request.form.get('current') == 'on'
        
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if start_date_str:
            education.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        if end_date_str and not education.current:
            education.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            education.end_date = None
        
        db.session.commit()
        flash('Education updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating education: {str(e)}', 'error')
    
    return redirect(url_for('profile.manage_education'))

@profile_bp.route('/education/<int:edu_id>/delete', methods=['POST'])
@guest_protected
@login_required
def delete_education(edu_id):
    """Delete education"""
    education = Education.query.get_or_404(edu_id)
    
    if education.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('profile.manage_education'))
    
    try:
        db.session.delete(education)
        db.session.commit()
        flash('Education deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting education: {str(e)}', 'error')
    
    return redirect(url_for('profile.manage_education'))

@profile_bp.route('/user/<int:user_id>/review', methods=['POST'])
@guest_protected
@login_required
def add_review(user_id):
    """Add review for a user"""
    current_user = UserService.get_user_by_id(session['user_id'])
    target_user = UserService.get_user_by_id(user_id)
    
    if not target_user:
        flash('User not found', 'error')
        return redirect(request.referrer or url_for('main.explore'))
    
    if current_user.id == target_user.id:
        flash('Cannot review yourself', 'error')
        return redirect(request.referrer or url_for('main.explore'))
    
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    service_type = request.form.get('service_type')
    
    if not rating or not service_type:
        flash('Rating and service type are required', 'error')
        return redirect(request.referrer or url_for('main.explore'))
    
    try:
        existing_review = Review.query.filter_by(
            reviewer_id=current_user.id,
            reviewee_id=target_user.id,
            service_type=service_type
        ).first()
        
        if existing_review:
            flash('You have already reviewed this user for this service type', 'error')
            return redirect(request.referrer or url_for('main.explore'))
        
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
    
    return redirect(request.referrer or url_for('profile.profile', username=target_user.username))
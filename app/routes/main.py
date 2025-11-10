from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app import db
from app.models import User, Post, Skill, UserSkill
from app.services import UserService
import logging
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)

def check_guest_expiry():
    """Check if guest session has expired"""
    if session.get('is_guest') and session.get('guest_expiry'):
        if datetime.utcnow() > datetime.fromisoformat(session['guest_expiry']):
            session.clear()
            flash('Your guest session has expired. Please sign up to continue.', 'info')
            return True
    return False

@main_bp.route('/')
def index():
    if 'user_id' in session:
        user = UserService.get_user_by_id(session['user_id'])
        if user and user.is_verified:
            return redirect(url_for('main.dashboard'))
    return render_template('landing.html')

@main_bp.route('/landing')
def landing():
    return render_template('landing.html')

@main_bp.route('/dashboard')
def dashboard():
    """Dashboard - available to both users and guests"""
    if check_guest_expiry():
        return redirect(url_for('main.landing'))

    if session.get('is_guest'):
        posts = Post.query.join(User).filter(User.is_verified==True)\
            .order_by(Post.created_at.desc()).limit(10).all()
        return render_template('dashboard.html', posts=posts, is_guest=True)
    
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = UserService.get_user_by_id(session['user_id'])
    if not user or not user.is_verified:
        return redirect(url_for('auth.login'))
    
    # Get posts from followed users
    following_ids = [f.followed_id for f in user.following.all()]
    following_ids.append(user.id)
    
    posts = Post.query.filter(Post.user_id.in_(following_ids))\
        .order_by(Post.created_at.desc()).all()
    
    return render_template('dashboard.html', posts=posts, is_guest=False)

@main_bp.route('/explore')
def explore():
    """Explore page - available to guests"""
    if check_guest_expiry():
        return redirect(url_for('main.landing'))

    query = request.args.get('q', '')
    filter_type = request.args.get('type', 'all')
    
    users = []
    posts = []
    
    if query:
        if filter_type in ['all', 'people']:
            users = UserService.search_users(query)
        
        if filter_type in ['all', 'posts']:
            posts = Post.query.join(User).filter(
                Post.content.ilike(f'%{query}%')
            ).filter(User.is_verified==True).order_by(Post.created_at.desc()).limit(20).all()
    else:
        users = User.query.filter_by(is_verified=True).order_by(db.func.random()).limit(6).all()
        posts = Post.query.join(User).filter(User.is_verified==True)\
            .order_by(Post.created_at.desc()).limit(10).all()
    
    trending_skills = Skill.query.join(UserSkill)\
        .group_by(Skill.id)\
        .order_by(db.func.count(UserSkill.id).desc()).limit(10).all()
    
    return render_template('explore.html', 
                         users=users, 
                         posts=posts, 
                         query=query, 
                         filter_type=filter_type,
                         trending_skills=trending_skills)

@main_bp.route('/search')
def search():
    """Search for users"""
    query = request.args.get('q', '')
    users = UserService.search_users(query)
    
    return render_template('search.html', users=users, query=query)

@main_bp.route('/browse-as-guest')
def browse_as_guest():
    """Start guest browsing session"""
    session.clear()
    session['is_guest'] = True
    session['guest_expiry'] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    session['guest_id'] = str(uuid.uuid4())[:8]
    flash('You are now browsing as a guest. Some features are limited.', 'info')
    return redirect(url_for('main.explore'))

@main_bp.route('/upgrade-from-guest')
def upgrade_from_guest():
    """Redirect to signup from guest session"""
    if session.get('is_guest'):
        session['guest_upgrade'] = True
        return redirect(url_for('auth.signup'))
    return redirect(url_for('auth.signup'))

@main_bp.route('/end-guest-session')
def end_guest_session():
    """End guest session"""
    session.clear()
    flash('Guest session ended.', 'info')
    return redirect(url_for('main.landing'))

@main_bp.route('/guest')
def guest_mode():
    """Alias for guest mode"""
    return redirect(url_for('main.browse_as_guest'))

@main_bp.route('/api/user/<username>')
def api_get_user(username):
    """Get user data for API"""
    user = UserService.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'avatar': user.avatar,
        'headline': user.headline,
        'location': user.location,
        'profile_mode': user.profile_mode.value,
        'open_to_work': user.open_to_work,
        'open_to_freelance': user.open_to_freelance
    }
    
    return jsonify(user_data)

@main_bp.route('/api/posts')
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
                'avatar': post.user.avatar
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
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app import db
from app.models import User, Connection, Notification, Post, Like, Comment, Message, Review
from app.services import UserService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
social_bp = Blueprint('social', __name__)

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

def save_uploaded_file(file, subfolder):
    """Helper function to save uploaded files"""
    from werkzeug.utils import secure_filename
    import time
    import os
    from flask import current_app
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webp', 'pdf', 'ppt', 'pptx'}
    
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)
        return f"uploads/{subfolder}/{filename}"
    return None

@social_bp.route('/user/<int:user_id>/follow', methods=['POST'])
@guest_protected
@login_required
def follow_user(user_id):
    """Follow/unfollow a user"""
    current_user = UserService.get_user_by_id(session['user_id'])
    target_user = UserService.get_user_by_id(user_id)
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    if current_user.id == target_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    if current_user.is_following(target_user):
        current_user.unfollow(target_user)
        action = 'unfollowed'
        
        # Remove notification
        Notification.query.filter_by(
            user_id=target_user.id,
            actor_id=current_user.id,
            verb='follow'
        ).delete()
    else:
        current_user.follow(target_user)
        action = 'followed'
        
        # Create notification
        notification = Notification(
            user_id=target_user.id,
            actor_id=current_user.id,
            verb='follow'
        )
        db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'action': action,
        'followers_count': target_user.followers.count()
    })

@social_bp.route('/user/<int:user_id>/connect', methods=['POST'])
@guest_protected
@login_required
def connect_user(user_id):
    """Send connection request to a user"""
    current_user = UserService.get_user_by_id(session['user_id'])
    target_user = UserService.get_user_by_id(user_id)
    
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

@social_bp.route('/connections')
@guest_protected
@login_required
def connections():
    """View user connections"""
    user = UserService.get_user_by_id(session['user_id'])
    
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

@social_bp.route('/connection/<int:conn_id>/accept', methods=['POST'])
@guest_protected
@login_required
def accept_connection(conn_id):
    """Accept connection request"""
    connection = Connection.query.get_or_404(conn_id)
    
    if connection.user2_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('social.connections'))
    
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
    return redirect(url_for('social.connections'))

@social_bp.route('/connection/<int:conn_id>/reject', methods=['POST'])
@guest_protected
@login_required
def reject_connection(conn_id):
    """Reject connection request"""
    connection = Connection.query.get_or_404(conn_id)
    
    if connection.user2_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('social.connections'))
    
    db.session.delete(connection)
    db.session.commit()
    
    flash('Connection request rejected', 'info')
    return redirect(url_for('social.connections'))

@social_bp.route('/messages')
@guest_protected
@login_required
def messages():
    """View messages"""
    user = UserService.get_user_by_id(session['user_id'])
    
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

@social_bp.route('/messages/<int:user_id>')
@guest_protected
@login_required
def view_conversation(user_id):
    """View conversation with specific user"""
    current_user = UserService.get_user_by_id(session['user_id'])
    other_user = User.query.get(user_id)
    
    if not other_user:
        flash('User not found', 'error')
        return redirect(url_for('social.messages'))
    
    Message.query.filter_by(sender_id=user_id, receiver_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    return render_template('conversation.html', 
                         messages=messages, 
                         other_user=other_user,
                         current_user=current_user)

@social_bp.route('/messages/send', methods=['POST'])
@guest_protected
@login_required
def send_message():
    """Send a message"""
    current_user = UserService.get_user_by_id(session['user_id'])
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

@social_bp.route('/notifications')
@guest_protected
@login_required
def notifications():
    """View notifications"""
    user = UserService.get_user_by_id(session['user_id'])
    notifications = user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@social_bp.route('/notifications/read-all', methods=['POST'])
@guest_protected
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user = UserService.get_user_by_id(session['user_id'])
    
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error marking notifications as read: {str(e)}'}), 500

@social_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
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

@social_bp.route('/api/notifications/count')
@login_required
def get_notification_count():
    """Get unread notification count for API"""
    user = UserService.get_user_by_id(session['user_id'])
    unread_count = user.notifications.filter_by(is_read=False).count()
    return jsonify({'count': unread_count})

@social_bp.route('/post/<int:post_id>/like', methods=['POST'])
@guest_protected
@login_required
def like_post(post_id):
    """Like/unlike a post"""
    user = UserService.get_user_by_id(session['user_id'])
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

@social_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@guest_protected
@login_required
def comment_post(post_id):
    """Comment on a post"""
    user = UserService.get_user_by_id(session['user_id'])
    post = Post.query.get_or_404(post_id)
    comment_content = request.form.get('comment', '').strip()
    
    if not comment_content:
        flash('Comment cannot be empty', 'danger')
        return redirect(url_for('main.dashboard'))
    
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
    
    return redirect(url_for('main.dashboard'))

@social_bp.route('/create-post', methods=['POST'])
@guest_protected
@login_required
def create_post():
    """Create a new post"""
    user = UserService.get_user_by_id(session['user_id'])
    
    content = request.form.get('content', '').strip()
    media_file = request.files.get('media')
    
    if not content and not media_file:
        flash('Post cannot be empty', 'danger')
        return redirect(url_for('main.dashboard'))
    
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
    
    return redirect(url_for('main.dashboard'))
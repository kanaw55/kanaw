from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import random
import re
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-123')

basedir = os.path.abspath(os.path.dirname(__file__))
db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'social.db'))
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}

cloudinary.config(
    cloud_name = "hgeundkj",
    api_key = "648417333443189",
    api_secret = "JFLlaKxfpaUGKHOj_jHVRieLYpw",
    secure = True
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

likes = db.Table('likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True)
)

saves = db.Table('saves',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True)
)

blocks = db.Table('blocks',
    db.Column('blocker_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('blocked_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

comment_likes = db.Table('comment_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('comment_id', db.Integer, db.ForeignKey('comment.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    profile_pic = db.Column(db.String(500), default=None)
    bio = db.Column(db.String(200), default="مرحباً! أنا أستخدم تطبيق Kanaw.")
    is_private = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    followed = db.relationship('User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    liked_videos = db.relationship('Video', secondary=likes, backref=db.backref('liked_by', lazy='dynamic'))
    saved_videos = db.relationship('Video', secondary=saves, backref=db.backref('saved_by', lazy='dynamic'))
    blocked_users = db.relationship('User', secondary=blocks,
        primaryjoin=(blocks.c.blocker_id == id),
        secondaryjoin=(blocks.c.blocked_id == id),
        backref=db.backref('blocked_by', lazy='dynamic'), lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200), default="")
    likes_count = db.Column('likes', db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='videos')
    comments = db.relationship('Comment', backref='video', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    likes_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='comments')
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")
    liked_by = db.relationship('User', secondary=comment_likes, backref='liked_comments')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')
    reaction = db.Column(db.String(10), default=None)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.String(20))
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    reason = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class FollowRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(unread_notifications=unread_count)
    return dict(unread_notifications=0)

@app.template_filter('hashtag')
def hashtag_filter(text):
    if not text:
        return text
    return re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:#00f2ea; text-decoration:none;">#\1</a>', text)

@app.route('/hashtag/<tag>')
def hashtag_page(tag):
    videos = Video.query.filter(Video.caption.ilike(f'%#{tag}%')).order_by(Video.id.desc()).all()
    return render_template('hashtag.html', tag=tag, videos=videos)

@app.route('/api/message/delete/<int:msg_id>', methods=['POST'])
@login_required
def api_delete_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403

@app.route('/api/message/react/<int:msg_id>', methods=['POST'])
@login_required
def api_react_message(msg_id):
    data = request.get_json()
    reaction = data.get('reaction')
    msg = Message.query.get_or_404(msg_id)
    msg.reaction = None if reaction == msg.reaction else reaction
    db.session.commit()
    return jsonify({'success': True, 'reaction': msg.reaction})

@app.route('/sw.js')
def sw():
    return app.send_static_file('sw.js')

@app.route('/')
def index():
    feed_type = request.args.get('feed', 'foryou')
    blocked_ids = [u.id for u in current_user.blocked_users] if current_user.is_authenticated else []

    if current_user.is_authenticated:
        followed_ids = [u.id for u in current_user.followed]
        if feed_type == 'following':
            videos = Video.query.join(User).filter(Video.user_id.in_(followed_ids), ~Video.user_id.in_(blocked_ids)).all()
        else:
            videos = Video.query.join(User).filter(
                (User.is_private == False) | (Video.user_id == current_user.id) | (Video.user_id.in_(followed_ids)),
                ~Video.user_id.in_(blocked_ids)
            ).all()
        liked_vids = [v.id for v in current_user.liked_videos]
        saved_vids = [v.id for v in current_user.saved_videos]
        
        # جلب الحسابات المقترحة (أشخاص لا تتابعهم)
        suggested = User.query.filter(
            User.id != current_user.id, 
            ~User.id.in_(followed_ids),
            ~User.id.in_(blocked_ids)
        ).order_by(db.func.random()).limit(5).all()
    else:
        videos = Video.query.join(User).filter(User.is_private == False).all()
        liked_vids, saved_vids = [], []
        suggested = User.query.order_by(db.func.random()).limit(5).all()
        
    random.shuffle(videos)
    return render_template('index.html', videos=videos, liked_videos=liked_vids, saved_videos=saved_vids, feed_type=feed_type, suggested_users=suggested)

@app.route('/trending')
def trending():
    videos = Video.query.order_by(Video.views.desc()).limit(50).all()
    return render_template('trending.html', videos=videos)

@app.route('/api/comment/pin/<int:comment_id>', methods=['POST'])
@login_required
def api_pin_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    video = Video.query.get(comment.video_id)
    if video.user_id == current_user.id:
        comment.is_pinned = not comment.is_pinned
        db.session.commit()
        return jsonify({'success': True, 'is_pinned': comment.is_pinned})
    return jsonify({'success': False}), 403

@app.route('/api/notifications/count')
@login_required
def api_notifications_count():
    return jsonify({'count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()})

@app.route('/api/chat/audio', methods=['POST'])
@login_required
def upload_audio():
    file = request.files.get('audio')
    receiver_id = request.form.get('receiver_id')
    if file and receiver_id:
        try:
            upload_result = cloudinary.uploader.upload(file, resource_type="video")
            audio_url = upload_result.get('secure_url')
            db.session.add(Message(sender_id=current_user.id, receiver_id=receiver_id, content=audio_url, message_type='audio'))
            db.session.add(Notification(user_id=receiver_id, sender_id=current_user.id, type='message'))
            db.session.commit()
            return jsonify({'success': True})
        except Exception:
            return jsonify({'success': False}), 500
    return jsonify({'success': False}), 400

@app.route('/api/save/<int:video_id>', methods=['POST'])
@login_required
def api_save(video_id):
    video = Video.query.get_or_404(video_id)
    if current_user in video.saved_by:
        video.saved_by.remove(current_user)
        is_saved = False
    else:
        video.saved_by.append(current_user)
        is_saved = True
    db.session.commit()
    return jsonify({'success': True, 'is_saved': is_saved})

@app.route('/block/<int:user_id>')
@login_required
def block_user(user_id):
    user = User.query.get_or_404(user_id)
    if user != current_user:
        if user in current_user.blocked_users:
            current_user.blocked_users.remove(user)
        else:
            current_user.blocked_users.append(user)
            if user in current_user.followed:
                current_user.followed.remove(user)
        db.session.commit()
    return redirect(url_for('profile', username=user.username))

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'users': [], 'videos': []})
        
    blocked_ids = [u.id for u in current_user.blocked_users] if current_user.is_authenticated else []
    users = User.query.filter(User.username.ilike(f'%{query}%'), ~User.id.in_(blocked_ids)).limit(5).all()
    users_data = [{'username': u.username, 'profile_pic': u.profile_pic, 'followers': u.followers.count()} for u in users]
    
    videos_query = Video.query.join(User).filter(Video.caption.ilike(f'%{query}%'), ~Video.user_id.in_(blocked_ids))
    if current_user.is_authenticated:
        videos_query = videos_query.filter((User.is_private == False) | (Video.user_id == current_user.id))
    else:
        videos_query = videos_query.filter(User.is_private == False)
        
    videos = videos_query.limit(12).all()
    videos_data = [{'id': v.id, 'filename': v.filename, 'views': v.views, 'thumbnail': v.filename.replace('.mp4', '.jpg')} for v in videos]
    return jsonify({'users': users_data, 'videos': videos_data})

@app.route('/api/view/<int:video_id>', methods=['POST'])
def api_view(video_id):
    video = Video.query.get_or_404(video_id)
    video.views += 1
    db.session.commit()
    return jsonify({'success': True, 'views': video.views})

@app.route('/api/like/<int:video_id>', methods=['POST'])
@login_required
def api_like(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id == current_user.id: return jsonify({'success': False})
    if current_user in video.liked_by:
        video.liked_by.remove(current_user)
        video.likes_count -= 1
        is_liked = False
    else:
        video.liked_by.append(current_user)
        video.likes_count += 1
        db.session.add(Notification(user_id=video.user_id, sender_id=current_user.id, type='like'))
        is_liked = True
    db.session.commit()
    return jsonify({'success': True, 'likes': video.likes_count, 'is_liked': is_liked})

@app.route('/api/upload_direct', methods=['POST'])
@login_required
def upload_direct():
    file = request.files.get('video')
    caption = request.form.get('caption', '')
    if file and file.filename != '':
        try:
            upload_result = cloudinary.uploader.upload(file, resource_type="video")
            video_url = upload_result.get('secure_url')
            if '/video/upload/' in video_url:
                video_url = video_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            db.session.add(Video(filename=video_url, caption=caption, user=current_user))
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'No file'}), 400

@app.route('/api/comments/<int:video_id>')
def get_comments(video_id):
    comments = Comment.query.filter_by(video_id=video_id, parent_id=None).order_by(Comment.timestamp.desc()).all()
    def serialize_comment(c):
        return {'id': c.id, 'content': c.content, 'user': c.user.username, 'user_pic': c.user.profile_pic, 'likes': c.likes_count,
            'is_liked': current_user.is_authenticated and current_user in c.liked_by,
            'replies': [serialize_comment(r) for r in c.replies.order_by(Comment.timestamp.asc()).all()]}
    return jsonify([serialize_comment(c) for c in comments])

@app.route('/api/comment/<int:video_id>', methods=['POST'])
@login_required
def api_add_comment(video_id):
    data = request.get_json()
    content = data.get('content')
    parent_id = data.get('parent_id')
    if content:
        comment = Comment(content=content, user_id=current_user.id, video_id=video_id, parent_id=parent_id)
        db.session.add(comment)
        target_user_id = Comment.query.get(parent_id).user_id if parent_id else Video.query.get(video_id).user_id
        if target_user_id != current_user.id:
            db.session.add(Notification(user_id=target_user_id, sender_id=current_user.id, type='comment'))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/api/comment/like/<int:comment_id>', methods=['POST'])
@login_required
def api_like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if current_user in comment.liked_by:
        comment.liked_by.remove(current_user)
        comment.likes_count -= 1
        is_liked = False
    else:
        comment.liked_by.append(current_user)
        comment.likes_count += 1
        is_liked = True
    db.session.commit()
    return jsonify({'success': True, 'likes': comment.likes_count, 'is_liked': is_liked})



@app.route('/api/get_followed_users')
@login_required
def get_followed_users():
    users = current_user.followed.all()
    return jsonify([{'id': u.id, 'username': u.username, 'profile_pic': u.profile_pic} for u in users])

@app.route('/api/share_video/<int:video_id>', methods=['POST'])

@login_required
def api_share_video(video_id):
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    video = Video.query.get_or_404(video_id)
    if receiver_id:
        msg_content = f"شاهد هذا الفيديو: /?video_id={video_id}"
        db.session.add(Message(sender_id=current_user.id, receiver_id=receiver_id, content=msg_content))
        db.session.add(Notification(user_id=receiver_id, sender_id=current_user.id, type='message'))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/report_video/<int:video_id>', methods=['POST'])
@login_required
def api_report_video(video_id):
    data = request.get_json()
    reason = data.get('reason')
    if reason:
        db.session.add(Report(reporter_id=current_user.id, video_id=video_id, reason=reason))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/register', methods=['GET', 'POST'])

def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    accounts_created = 0
    try: accounts_created = int(request.cookies.get('accounts_created', 0))
    except ValueError: accounts_created = 0
    if request.method == 'POST':
        if accounts_created >= 2:
            flash('عذراً، لقد وصلت للحد الأقصى لإنشاء الحسابات على هذا الجهاز (حسابين فقط).')
            return redirect(url_for('register'))
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('الرجاء إدخال الاسم وكلمة المرور')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم محجوز، اختر اسماً آخر')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('accounts_created', str(accounts_created + 1), max_age=30*24*60*60)
        return resp
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('اسم المستخدم أو كلمة المرور خاطئة')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.is_private = True if request.form.get('is_private') == 'on' else False
        db.session.commit()
        flash('تم تحديث الإعدادات بنجاح')
        return redirect(url_for('settings'))
    return render_template('settings.html')

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    is_blocked = current_user.is_authenticated and user in current_user.blocked_users

    if request.method == 'POST' and current_user.is_authenticated and current_user.id == user.id:
        file = request.files.get('profile_pic')
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, resource_type="image")
            user.profile_pic = upload_result.get('secure_url')
        new_bio = request.form.get('bio')
        if new_bio is not None:
            user.bio = new_bio
        db.session.commit()
        return redirect(url_for('profile', username=user.username))

    is_following = False
    has_requested = False
    if current_user.is_authenticated:
        is_following = current_user.followed.filter(followers.c.followed_id == user.id).count() > 0
        has_requested = FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first() is not None

    can_view = False
    if not is_blocked:
        if not user.is_private or (current_user.is_authenticated and (is_following or current_user.id == user.id)):
            can_view = True

    videos = Video.query.filter_by(user_id=user.id).order_by(Video.id.desc()).all() if can_view else []
    liked_vids = Video.query.join(likes).filter(likes.c.user_id == user.id).order_by(Video.id.desc()).all() if can_view else []
    saved_vids = Video.query.join(saves).filter(saves.c.user_id == user.id).order_by(Video.id.desc()).all() if can_view and current_user.id == user.id else []
    
    total_likes = sum(v.likes_count for v in videos) if can_view else 0
    followers_count = user.followers.count()
    following_count = user.followed.count()
    
    return render_template('profile.html', user=user, videos=videos, liked_vids=liked_vids, saved_vids=saved_vids, total_likes=total_likes, is_following=is_following, has_requested=has_requested, can_view=can_view, followers_count=followers_count, following_count=following_count, is_blocked=is_blocked)

@app.route('/profile/<username>/followers')
def followers_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('follow_list.html', title="المتابعين", users=user.followers.all(), target_user=user)

@app.route('/profile/<username>/following')
def following_list(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('follow_list.html', title="يتابع", users=user.followed.all(), target_user=user)

@app.route('/toggle_follow/<int:user_id>')
@login_required
def toggle_follow(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user: return redirect(url_for('profile', username=user.username))
    if current_user.followed.filter(followers.c.followed_id == user.id).count() > 0:
        current_user.followed.remove(user)
        db.session.commit()
    else:
        if user.is_private:
            if not FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first():
                db.session.add(FollowRequest(sender_id=current_user.id, receiver_id=user.id))
                db.session.add(Notification(user_id=user.id, sender_id=current_user.id, type='follow_request'))
                db.session.commit()
        else:
            current_user.followed.append(user)
            db.session.add(Notification(user_id=user.id, sender_id=current_user.id, type='follow'))
            db.session.commit()
    return redirect(request.referrer or url_for('profile', username=user.username))

@app.route('/accept_request/<int:req_id>')
@login_required
def accept_request(req_id):
    req = FollowRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id:
        current_user.followers.append(req.sender)
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/reject_request/<int:req_id>')
@login_required
def reject_request(req_id):
    req = FollowRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id:
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('video')
        caption = request.form.get('caption')
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, resource_type="video")
            video_url = upload_result.get('secure_url')
            if '/video/upload/' in video_url:
                video_url = video_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            db.session.add(Video(filename=video_url, caption=caption, user=current_user))
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/delete_video/<int:video_id>')
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id == current_user.id:
        db.session.delete(video)
        db.session.commit()
        flash('تم حذف الفيديو بنجاح')
    return redirect(request.referrer or url_for('index'))

@app.route('/inbox')
@login_required
def inbox():
    sent = db.session.query(Message.receiver_id).filter(Message.sender_id == current_user.id)
    received = db.session.query(Message.sender_id).filter(Message.receiver_id == current_user.id)
    user_ids = set([id[0] for id in sent.all()] + [id[0] for id in received.all()])
    users = User.query.filter(User.id.in_(user_ids)).all()
    return render_template('inbox.html', users=users)

@app.route('/chat/<username>', methods=['GET', 'POST'])
@login_required
def chat(username):
    other_user = User.query.filter_by(username=username).first_or_404()
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            db.session.add(Message(sender_id=current_user.id, receiver_id=other_user.id, content=content))
            db.session.add(Notification(user_id=other_user.id, sender_id=current_user.id, type='message'))
            db.session.commit()
            return redirect(url_for('chat', username=username))
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', other_user=other_user, messages=messages)

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    for n in notifs: n.is_read = True
    db.session.commit()
    requests = FollowRequest.query.filter_by(receiver_id=current_user.id).all()
    return render_template('notifications.html', notifications=notifs, requests=requests)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

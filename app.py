from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import random
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

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_pic = db.Column(db.String(500), default=None)
    is_private = db.Column(db.Boolean, default=False)
    followed = db.relationship('User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200), default="")
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='videos')
    comments = db.relationship('Comment', backref='video', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    user = db.relationship('User', backref='comments')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
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

@app.route('/')
def index():
    if current_user.is_authenticated:
        followed_ids = [u.id for u in current_user.followed]
        videos = Video.query.join(User).filter(
            (User.is_private == False) | (Video.user_id == current_user.id) | (Video.user_id.in_(followed_ids))
        ).all()
    else:
        videos = Video.query.join(User).filter(User.is_private == False).all()
    random.shuffle(videos)
    return render_template('index.html', videos=videos)

@app.route('/api/like/<int:video_id>', methods=['POST'])
@login_required
def api_like(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id != current_user.id:
        video.likes += 1
        db.session.add(Notification(user_id=video.user_id, sender_id=current_user.id, type='like'))
        db.session.commit()
        return jsonify({'success': True, 'likes': video.likes})
    return jsonify({'success': False, 'likes': video.likes})

@app.route('/api/upload_direct', methods=['POST'])
@login_required
def upload_direct():
    file = request.files.get('video')
    if file and file.filename != '':
        try:
            upload_result = cloudinary.uploader.upload(file, resource_type="video")
            video_url = upload_result.get('secure_url')
            if '/video/upload/' in video_url:
                video_url = video_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            new_video = Video(filename=video_url, user=current_user)
            db.session.add(new_video)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'No file'}), 400

@app.route('/api/comments/<int:video_id>')
def get_comments(video_id):
    comments = Comment.query.filter_by(video_id=video_id).order_by(Comment.timestamp.desc()).all()
    return jsonify([{'id': c.id, 'content': c.content, 'user': c.user.username, 'time': c.timestamp.strftime('%Y-%m-%d %H:%M')} for c in comments])

@app.route('/api/comment/<int:video_id>', methods=['POST'])
@login_required
def api_add_comment(video_id):
    data = request.get_json()
    content = data.get('content') if data else None
    if content:
        try:
            comment = Comment(content=content, user_id=current_user.id, video_id=video_id)
            db.session.add(comment)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False, 'error': 'Empty'}), 400

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    try:
        accounts_created = int(request.cookies.get("accounts_created", 0))
    except ValueError:
        accounts_created = 0
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
    if request.method == 'POST' and current_user.is_authenticated and current_user.id == user.id:
        file = request.files.get('profile_pic')
        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, resource_type="image")
            user.profile_pic = upload_result.get('secure_url')
            db.session.commit()
            return redirect(url_for('profile', username=user.username))

    is_following = False
    has_requested = False
    if current_user.is_authenticated:
        is_following = current_user.followed.filter(followers.c.followed_id == user.id).count() > 0
        has_requested = FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first() is not None

    can_view = False
    if not user.is_private or (current_user.is_authenticated and (is_following or current_user.id == user.id)):
        can_view = True

    videos = Video.query.filter_by(user_id=user.id).order_by(Video.id.desc()).all() if can_view else []
    total_likes = sum(v.likes for v in videos) if can_view else 0
    followers_count = user.followers.count()
    return render_template('profile.html', user=user, videos=videos, total_likes=total_likes, is_following=is_following, has_requested=has_requested, can_view=can_view, followers_count=followers_count)

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
    return redirect(url_for('profile', username=user.username))

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
    try:
        db.create_all()
        print("✅ Database tables verified/created successfully!")
    except Exception as e:
        print(f"❌ Database error on startup: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

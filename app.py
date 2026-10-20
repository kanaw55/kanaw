from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# إعدادات الأمان (تدعم متغيرات البيئة في Render)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    profile_pic = db.Column(db.String(100), default=None)
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
    filename = db.Column(db.String(100), nullable=False)
    caption = db.Column(db.String(200))
    likes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='videos')

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
    type = db.Column(db.String(20)) # like, follow, message, follow_request
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
        ).order_by(Video.id.desc()).all()
    else:
        videos = Video.query.join(User).filter(User.is_private == False).order_by(Video.id.desc()).all()
    return render_template('index.html', videos=videos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
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
        return redirect(url_for('index'))
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
            filename = secure_filename(file.filename)
            filename = f"avatar_{user.id}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
            db.session.commit()
            return redirect(url_for('profile', username=user.username))

    is_following = False
    has_requested = False
    if current_user.is_authenticated:
        is_following = current_user.followed.filter(followers.c.followed_id == user.id).count() > 0
        has_requested = FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first() is not None

    can_view = False
    if not user.is_private:
        can_view = True
    elif current_user.is_authenticated and (is_following or current_user.id == user.id):
        can_view = True

    if can_view:
        videos = Video.query.filter_by(user_id=user.id).order_by(Video.id.desc()).all()
        total_likes = sum(v.likes for v in videos)
    else:
        videos = []
        total_likes = 0

    followers_count = user.followers.count()
    return render_template('profile.html', user=user, videos=videos, total_likes=total_likes, 
                           is_following=is_following, has_requested=has_requested, can_view=can_view, followers_count=followers_count)

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
                req = FollowRequest(sender_id=current_user.id, receiver_id=user.id)
                db.session.add(req)
                notif = Notification(user_id=user.id, sender_id=current_user.id, type='follow_request')
                db.session.add(notif)
                db.session.commit()
        else:
            current_user.followed.append(user)
            notif = Notification(user_id=user.id, sender_id=current_user.id, type='follow')
            db.session.add(notif)
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
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            new_video = Video(filename=filename, caption=caption, user=current_user)
            db.session.add(new_video)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/delete_video/<int:video_id>')
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id == current_user.id:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(video)
        db.session.commit()
        flash('تم حذف الفيديو بنجاح')
    return redirect(request.referrer or url_for('index'))

@app.route('/like/<int:video_id>')
@login_required
def like(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id != current_user.id:
        video.likes += 1
        notif = Notification(user_id=video.user_id, sender_id=current_user.id, type='like')
        db.session.add(notif)
        db.session.commit()
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
            msg = Message(sender_id=current_user.id, receiver_id=other_user.id, content=content)
            db.session.add(msg)
            notif = Notification(user_id=other_user.id, sender_id=current_user.id, type='message')
            db.session.add(notif)
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # التعديل الخاص بـ Render (المنفذ الديناميكي)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import uuid
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

cloudinary.config(cloud_name="hgeundkj", api_key="648417333443189", api_secret="JFLlaKxfpaUGKHOj_jHVRieLYpw", secure=True)

VALID_VIDEOS = [
    "https://www.w3schools.com/html/mov_bbb.mp4",
    "https://www.w3schools.com/html/movie.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/friday.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-tree-with-yellow-leaves-2763-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-forest-stream-in-the-sunlight-529-large.mp4"
]

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        now = datetime.utcnow()
        ls = getattr(current_user, 'last_seen', None)
        if not ls or (now - ls).total_seconds() > 60:
            try:
                current_user.last_seen = now
                db.session.commit()
            except Exception:
                db.session.rollback()


@login_manager.unauthorized_handler
def unauthorized():
    login_url = url_for('login', next=request.referrer or request.path)
    if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': False,
            'error': 'login_required',
            'login_required': True,
            'login_url': login_url
        }), 401
    return redirect(login_url)


followers = db.Table('followers', db.Column('follower_id', db.Integer, db.ForeignKey('user.id')), db.Column('followed_id', db.Integer, db.ForeignKey('user.id')))
likes = db.Table('likes', db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True), db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True))
saves = db.Table('saves', db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True), db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True))
blocks = db.Table('blocks', db.Column('blocker_id', db.Integer, db.ForeignKey('user.id'), primary_key=True), db.Column('blocked_id', db.Integer, db.ForeignKey('user.id'), primary_key=True))
comment_likes = db.Table('comment_likes', db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True), db.Column('comment_id', db.Integer, db.ForeignKey('comment.id'), primary_key=True))
group_member = db.Table('group_member', db.Column('group_id', db.Integer, db.ForeignKey('chat_group.id'), primary_key=True), db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    profile_pic = db.Column(db.String(500), default=None)
    bio = db.Column(db.String(200), default="مرحباً! أنا أستخدم تطبيق Kanaw.")
    is_private = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    followed = db.relationship('User', secondary=followers, primaryjoin=(followers.c.follower_id == id), secondaryjoin=(followers.c.followed_id == id), backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    liked_videos = db.relationship('Video', secondary=likes, backref=db.backref('liked_by', lazy='dynamic'))
    saved_videos = db.relationship('Video', secondary=saves, backref=db.backref('saved_by', lazy='dynamic'))
    blocked_users = db.relationship('User', secondary=blocks, primaryjoin=(blocks.c.blocker_id == id), secondaryjoin=(blocks.c.blocked_id == id), backref=db.backref('blocked_by', lazy='dynamic'), lazy='dynamic')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

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
    user = db.relationship('User', backref='comments')
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")
    liked_by = db.relationship('User', secondary=comment_likes, backref='liked_comments')

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('chat_group.id'), nullable=True)
    media_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='stories')


group_admin = db.Table('group_admin',
    db.Column('group_id', db.Integer, db.ForeignKey('chat_group.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class ChatGroup(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship('User', secondary=group_member, backref='chat_groups')
    admins = db.relationship('User', secondary=group_admin, backref='admin_groups')
    invite_code = db.Column(db.String(20), unique=True, default=None)
    description = db.Column(db.Text, default='مرحباً بكم في المجموعة!')
    group_pic = db.Column(db.String(500), default=None)
    join_approval = db.Column(db.Boolean, default=False)
    restrict_edit_info = db.Column(db.Boolean, default=False)
    restrict_send_messages = db.Column(db.Boolean, default=False)
    restrict_add_members = db.Column(db.Boolean, default=False)
    chat_bg = db.Column(db.String(500), default=None)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_group.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')
    reaction = db.Column(db.String(10), default=None)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    reply_to = db.relationship('Message', remote_side=[id], foreign_keys=[reply_to_id], backref='message_replies')


class TypingStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    target_id = db.Column(db.Integer)
    is_group = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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


class GroupJoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_group.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='group_join_requests')

class Report(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    reason = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    video = db.relationship('Video', backref='reports')

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.context_processor

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

def inject_notifications():
    if current_user.is_authenticated:
        return dict(unread_notifications=Notification.query.filter_by(user_id=current_user.id, is_read=False).count())
    return dict(unread_notifications=0)


@app.template_filter('linkify')
def linkify(text):
    if not text: return text
    # تحويل الروابط إلى a tags
    return re.sub(r'(https?://[^\s]+|www\.[^\s]+)', r'<a href="\1" target="_blank" style="color:#00f2fe; text-decoration:underline;">\1</a>', text)


@app.template_filter('format_text')
def format_text(text):
    if not text: return text
    from markupsafe import Markup, escape
    # 1. تحويل النص الآمن
    s = str(escape(str(text)))
    # 2. تحويل الروابط
    s = re.sub(r'(https?://[^\s]+|www\.[^\s]+)', r'<a href="\1" target="_blank" style="color:#00f2fe;text-decoration:underline;">\1</a>', s)
    # 3. تحويل الهاشتاجات
    s = re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:#00f2ea;text-decoration:none;">#\1</a>', s)
    return Markup(s)

def hashtag_filter(text):
    if not text: return text
    return re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:#00f2ea; text-decoration:none;">#\1</a>', text)




@app.route('/hashtag/<tag>')
def hashtag_page(tag):
    videos = Video.query.filter(Video.caption.ilike(f'%#{tag}%')).order_by(Video.id.desc()).all()
    return render_template('hashtag.html', tag=tag, videos=videos)

@app.route('/')
def index():
    feed_type = request.args.get('feed', 'foryou')
    blocked_ids = [u.id for u in current_user.blocked_users] if current_user.is_authenticated else []
    if current_user.is_authenticated:
        followed_ids = [u.id for u in current_user.followed]
        videos = Video.query.join(User).filter((User.is_private == False) | (Video.user_id == current_user.id) | (Video.user_id.in_(followed_ids)), ~Video.user_id.in_(blocked_ids)).order_by(db.func.random()).limit(30).all()
        liked_vids = [v.id for v in current_user.liked_videos]
        saved_vids = [v.id for v in current_user.saved_videos]
    else:
        videos = Video.query.join(User).filter(User.is_private == False).order_by(db.func.random()).limit(30).all()
        liked_vids, saved_vids = [], []
    return render_template('index.html', videos=videos, liked_videos=liked_vids, saved_videos=saved_vids, feed_type=feed_type)

@app.route('/api/load_more')
def load_more():
    blocked_ids = [u.id for u in current_user.blocked_users] if current_user.is_authenticated else []
    videos = Video.query.join(User).filter(User.is_private == False, ~Video.user_id.in_(blocked_ids)).order_by(db.func.random()).limit(30).all()
    liked_vids = [v.id for v in current_user.liked_videos] if current_user.is_authenticated else []
    saved_vids = [v.id for v in current_user.saved_videos] if current_user.is_authenticated else []
    if not videos: return ""
    return render_template('_video.html', videos=videos, liked_videos=liked_vids, saved_videos=saved_vids)

@app.route('/trending')
def trending():
    videos = Video.query.order_by(Video.views.desc()).limit(50).all()
    return render_template('trending.html', videos=videos)

@app.route('/inbox')
@login_required
def inbox():
    try:
        sent = db.session.query(Message.receiver_id).filter(Message.sender_id == current_user.id, Message.group_id == None)
        received = db.session.query(Message.sender_id).filter(Message.receiver_id == current_user.id, Message.group_id == None)
        user_ids = set([id[0] for id in sent.all()] + [id[0] for id in received.all()])
        users = User.query.filter(User.id.in_(user_ids)).all()
        groups = current_user.chat_groups
        stories = Story.query.filter(Story.created_at >= datetime.utcnow() - timedelta(days=1)).order_by(Story.created_at.desc()).all()
        stories_json = [{'url': s.media_url, 'user': s.user.username, 'pic': s.user.profile_pic or '', 'time': 'الآن'} for s in stories if s.user]
        return render_template('inbox.html', users=users, groups=groups, stories=stories, stories_json=stories_json)
    except:
        return render_template('inbox.html', users=[], groups=[], stories=[], stories_json=[])



@app.route('/group/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user.id != group.creator_id:
        return "غير مصرح", 403
    Message.query.filter_by(group_id=group.id).delete()
    GroupJoinRequest.query.filter_by(group_id=group.id).delete()
    Story.query.filter_by(group_id=group.id).delete()
    group.admins.clear()
    group.members.clear()
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('inbox'))

@app.route('/group/<int:group_id>/update_info', methods=['POST'])
@login_required
def update_group_info(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user.id != group.creator_id:
        if current_user not in group.admins or group.restrict_edit_info:
            return "غير مصرح", 403
    
    new_name = request.form.get('name')
    if new_name and current_user.id == group.creator_id:
        group.name = new_name.strip()
    
    if 'group_pic' in request.files:
        file = request.files['group_pic']
        if file and file.filename != '':
            res = cloudinary.uploader.upload(file, resource_type="image")
            group.group_pic = res.get('secure_url')
    if request.form.get('description') is not None:
        group.description = request.form.get('description')
    group.join_approval = True if request.form.get('join_approval') == 'on' else False
    db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))


@app.route('/group/<int:group_id>/add_member/<int:user_id>', methods=['POST'])
@login_required
def add_group_member(group_id, user_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user in group.admins or (not group.restrict_add_members and current_user in group.members):
        user = User.query.get(user_id)
        if user and user not in group.members:
            group.members.append(user)
            db.session.add(Message(sender_id=current_user.id, group_id=group.id,
                content=f"@{user.username} انضم للمجموعة", message_type='system'))
            db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user in group.members and current_user.id != group.creator_id:
        group.members.remove(current_user)
        if current_user in group.admins:
            group.admins.remove(current_user)
        db.session.add(Message(sender_id=current_user.id, group_id=group.id,
            content=f"@{current_user.username} غادر المجموعة", message_type='system'))
        db.session.commit()
        return redirect(url_for('inbox'))
    return redirect(url_for('group_info', group_id=group_id))


@app.route('/group/<int:group_id>/update_permissions', methods=['POST'])
@login_required
def update_group_permissions(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user.id != group.creator_id: return "غير مصرح", 403
    
    group.restrict_edit_info = True if request.form.get('restrict_edit_info') == 'on' else False
    group.restrict_send_messages = True if request.form.get('restrict_send_messages') == 'on' else False
    group.restrict_add_members = True if request.form.get('restrict_add_members') == 'on' else False
    db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/clear_chat', methods=['POST'])
@login_required
def clear_chat(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.admins: return "غير مصرح", 403
    Message.query.filter_by(group_id=group.id).delete()
    db.session.commit()
    return redirect(url_for('chat_group', group_id=group_id))

@app.route('/group/<int:group_id>/add_story', methods=['POST'])
@login_required
def add_group_story(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.members: return "غير مصرح", 403
    file = request.files.get('story')
    if file:
        res = cloudinary.uploader.upload(file, resource_type="image")
        db.session.add(Story(user_id=current_user.id, group_id=group.id, media_url=res.get('secure_url')))
        db.session.commit()
    return redirect(url_for('chat_group', group_id=group_id))

@app.route('/group/<int:group_id>/stories')
@login_required
def group_stories(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.members: return "غير مصرح", 403
    stories = Story.query.filter(
        Story.group_id == group.id,
        Story.created_at >= datetime.utcnow() - timedelta(days=1)
    ).order_by(Story.created_at.desc()).all()
    return jsonify([{'id': s.id, 'url': s.media_url, 'user': s.user.username, 'pic': s.user.profile_pic} for s in stories])

@app.route('/group/<int:group_id>/update_bg', methods=['POST'])
@login_required
def update_chat_bg(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.admins:
        return "غير مصرح", 403
    if request.form.get('clear_bg') == 'on':
        group.chat_bg = None
        db.session.commit()
        return redirect(url_for('chat_group', group_id=group_id))
    file = request.files.get('chat_bg_image')
    if file and file.filename != '':
        try:
            res = cloudinary.uploader.upload(file, resource_type="image")
            group.chat_bg = res.get('secure_url')
            db.session.commit()
        except Exception as e:
            flash(f'خطأ في رفع الصورة: {e}')
    return redirect(url_for('chat_group', group_id=group_id))

@app.route('/group_info/<int:group_id>')
@login_required
def group_info(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.members: return "غير مصرح", 403
    
    # إصلاح المجموعات القديمة تلقائياً
    changed = False
    if not group.invite_code:
        group.invite_code = str(uuid.uuid4())[:8]
        changed = True
    if group.description is None:
        group.description = 'مرحباً بكم في المجموعة!'
        changed = True
    if group.join_approval is None:
        group.join_approval = False
        changed = True
    if group.restrict_edit_info is None:
        group.restrict_edit_info = False
        changed = True
    if group.restrict_send_messages is None:
        group.restrict_send_messages = False
        changed = True
    if group.restrict_add_members is None:
        group.restrict_add_members = False
        changed = True
    
    # التأكد من أن المالك مشرف
    if current_user.id == group.creator_id and current_user not in group.admins:
        group.admins.append(current_user)
        changed = True
    
    if changed:
        db.session.commit()
    
    friends_not_in_group = [u for u in current_user.followed.all() if u not in group.members]
    join_requests = GroupJoinRequest.query.filter_by(group_id=group.id).all()
    return render_template('group_info.html', group=group, friends_not_in_group=friends_not_in_group, group_join_requests=join_requests, is_admin=(current_user in group.admins))

@app.route('/join_group/<string:code>')
@login_required
def join_group(code):
    group = ChatGroup.query.filter_by(invite_code=code).first()
    if not group: return render_template('join_preview.html', group=None, code=code), 404
    if current_user in group.members:
        return redirect(url_for('chat_group', group_id=group.id))
    # صفحة المعاينة
    return render_template('join_preview.html', group=group, code=code)

@app.route('/join_group/<string:code>/confirm', methods=['POST'])
@login_required
def join_group_confirm(code):
    group = ChatGroup.query.filter_by(invite_code=code).first()
    if not group: return "الرابط غير صالح", 404
    if current_user in group.members:
        return redirect(url_for('chat_group', group_id=group.id))
    if group.join_approval:
        existing_req = GroupJoinRequest.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if not existing_req:
            req = GroupJoinRequest(group_id=group.id, user_id=current_user.id)
            db.session.add(req)
            db.session.commit()
        return render_template('join_request_sent.html', group=group)
    else:
        group.members.append(current_user)
        db.session.commit()
        return redirect(url_for('chat_group', group_id=group.id))
        
    if group.join_approval:
        # إذا كانت المجموعة تتطلب موافقة، نرسل طلباً
        existing_req = GroupJoinRequest.query.filter_by(group_id=group.id, user_id=current_user.id).first()
        if not existing_req:
            req = GroupJoinRequest(group_id=group.id, user_id=current_user.id)
            db.session.add(req)
            db.session.commit()
        return render_template('join_request_sent.html', group=group)
    else:
        # انضمام فوري
        group.members.append(current_user)
        db.session.commit()
        return redirect(url_for('chat_group', group_id=group.id))

@app.route('/group/<int:group_id>/approve_join/<int:req_id>')
@login_required
def approve_join(group_id, req_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.admins: return "غير مصرح", 403
    req = GroupJoinRequest.query.get_or_404(req_id)
    if req.group_id == group.id:
        group.members.append(req.user)
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/reject_join/<int:req_id>')
@login_required
def reject_join(group_id, req_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.admins: return "غير مصرح", 403
    req = GroupJoinRequest.query.get_or_404(req_id)
    if req.group_id == group.id:
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/make_admin/<int:user_id>', methods=['POST'])
@login_required
def make_admin(group_id, user_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user in group.admins:
        user = User.query.get(user_id)
        if user and user in group.members and user not in group.admins:
            group.admins.append(user)
            db.session.add(Message(sender_id=current_user.id, group_id=group.id,
                content=f"@{user.username} أصبح مشرفاً", message_type='system'))
            db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/remove_admin/<int:user_id>', methods=['POST'])
@login_required
def remove_admin(group_id, user_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user in group.admins:
        user = User.query.get(user_id)
        if user and user in group.admins and user.id != group.creator_id:
            group.admins.remove(user)
            db.session.add(Message(sender_id=current_user.id, group_id=group.id,
                content=f"@{user.username} لم يعد مشرفاً", message_type='system'))
            db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/kick/<int:user_id>', methods=['POST'])
@login_required
def kick_member(group_id, user_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user in group.admins:
        user = User.query.get(user_id)
        if user and user in group.members and user.id != group.creator_id:
            if user in group.admins and current_user.id != group.creator_id:
                return "غير مصرح: فقط المالك يمكنه طرد المشرفين", 403
            group.members.remove(user)
            if user in group.admins: group.admins.remove(user)
            db.session.add(Message(sender_id=current_user.id, group_id=group.id,
                content=f"تمت إزالة @{user.username} من المجموعة", message_type='system'))
            db.session.commit()
    return redirect(url_for('group_info', group_id=group_id))

@app.route('/group/<int:group_id>/pin/<int:msg_id>', methods=['POST'])
@login_required
def pin_message(group_id, msg_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.admins:
        return "غير مصرح", 403
    msg = Message.query.get_or_404(msg_id)
    if msg.group_id == group.id:
        if msg.is_pinned:
            msg.is_pinned = False
        else:
            Message.query.filter_by(group_id=group.id).update({"is_pinned": False})
            msg.is_pinned = True
        db.session.commit()
    return redirect(url_for('chat_group', group_id=group_id))

@app.route('/chat_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def chat_group(group_id):
    group = ChatGroup.query.get_or_404(group_id)
    if current_user not in group.members: return "غير مصرح", 403
    
    is_admin = current_user in group.admins
    
    if request.method == 'POST':
        if group.restrict_send_messages and not is_admin:
            flash('المجموعة مغلقة، فقط المشرفون يمكنهم إرسال الرسائل.')
            return redirect(url_for('chat_group', group_id=group.id))
            
        content = request.form.get('content')
        if content:
            reply_to_id = request.form.get('reply_to_id')
            reply_to_id = int(reply_to_id) if reply_to_id else None
            db.session.add(Message(sender_id=current_user.id, content=content, group_id=group.id, reply_to_id=reply_to_id))
            db.session.commit()
            return redirect(url_for('chat_group', group_id=group.id))
            
    messages = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', other_user=None, group=group, messages=messages, is_admin=is_admin)

@app.route('/api/add_story', methods=['POST'])
@login_required
def add_story():
    file = request.files.get('story')
    if file:
        res = cloudinary.uploader.upload(file, resource_type="image")
        db.session.add(Story(user_id=current_user.id, media_url=res.get('secure_url')))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/api/create_group', methods=['POST'])
@login_required
def create_group():
    data = request.get_json()
    if data.get('name'):
        group = ChatGroup(name=data.get('name'), creator_id=current_user.id, invite_code=str(uuid.uuid4())[:8])
        group.members.append(current_user)
        group.admins.append(current_user) # المالك يكون مشرفاً
        db.session.add(group)
        db.session.commit()
        return jsonify({'success': True, 'group_id': group.id})
    return jsonify({'success': False}), 400

@app.route('/admin')
@login_required
def admin_panel():
    if not getattr(current_user, 'is_admin', False): return "عذراً، هذه الصفحة للمشرفين فقط.", 403
    reports = Report.query.order_by(Report.timestamp.desc()).all()
    return render_template('admin.html', reports=reports)

@app.route('/admin/delete_report/<int:report_id>')
@login_required
def admin_delete_report(report_id):
    if not getattr(current_user, 'is_admin', False): return "غير مصرح", 403
    db.session.delete(Report.query.get_or_404(report_id))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_vid/<int:video_id>')
@login_required
def admin_delete_video(video_id):
    if not getattr(current_user, 'is_admin', False): return "غير مصرح", 403
    Report.query.filter_by(video_id=video_id).delete()
    db.session.delete(Video.query.get_or_404(video_id))
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/search')
def search_page(): return render_template('search.html')

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query: return jsonify({'users': [], 'videos': []})
    blocked_ids = [u.id for u in current_user.blocked_users] if current_user.is_authenticated else []
    users = User.query.filter(User.username.ilike(f'%{query}%'), ~User.id.in_(blocked_ids)).limit(5).all()
    users_data = [{'username': u.username, 'profile_pic': u.profile_pic, 'followers': u.followers.count()} for u in users]
    videos_query = Video.query.join(User).filter(Video.caption.ilike(f'%{query}%'), ~Video.user_id.in_(blocked_ids))
    videos = videos_query.limit(12).all()
    videos_data = [{'id': v.id, 'filename': v.filename, 'views': v.views, 'thumbnail': v.filename.replace('.mp4', '.jpg')} for v in videos]
    return jsonify({'users': users_data, 'videos': videos_data})

@app.route('/api/view/<int:video_id>', methods=['POST'])
def api_view(video_id):
    video = Video.query.get_or_404(video_id); video.views += 1; db.session.commit()
    return jsonify({'success': True, 'views': video.views})

@app.route('/api/like/<int:video_id>', methods=['POST'])
@login_required
def api_like(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id == current_user.id: return jsonify({'success': False})
    if current_user in video.liked_by: video.liked_by.remove(current_user); video.likes_count -= 1; is_liked = False
    else: video.liked_by.append(current_user); video.likes_count += 1; db.session.add(Notification(user_id=video.user_id, sender_id=current_user.id, type='like')); is_liked = True
    db.session.commit()
    return jsonify({'success': True, 'likes': video.likes_count, 'is_liked': is_liked})

@app.route('/api/save/<int:video_id>', methods=['POST'])
@login_required
def api_save(video_id):
    video = Video.query.get_or_404(video_id)
    if current_user in video.saved_by: video.saved_by.remove(current_user); is_saved = False
    else: video.saved_by.append(current_user); is_saved = True
    db.session.commit()
    return jsonify({'success': True, 'is_saved': is_saved})

@app.route('/api/upload_direct', methods=['POST'])
@login_required
def upload_direct():
    file = request.files.get('video'); caption = request.form.get('caption', '')
    if file and file.filename != '':
        if is_video_too_large(file):
            return jsonify({'success': False, 'error': 'حجم الفيديو أكبر من 10 ميغابايت! يرجى اختيار فيديو أقصر.'}), 400
        try:
            upload_result = cloudinary.uploader.upload(file, resource_type="video")
            video_url = upload_result.get('secure_url')
            if '/video/upload/' in video_url: video_url = video_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            db.session.add(Video(filename=video_url, caption=caption, user=current_user))
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e: return jsonify({'success': False, 'error': str(e)}), 500
    return jsonify({'success': False}), 400

@app.route('/api/comments/<int:video_id>')
def get_comments(video_id):
    comments = Comment.query.filter_by(video_id=video_id, parent_id=None).order_by(Comment.timestamp.desc()).all()
    def serialize_comment(c):
        return {'id': c.id, 'content': c.content, 'user': c.user.username, 'user_pic': c.user.profile_pic, 'likes': c.likes_count, 'is_liked': current_user.is_authenticated and current_user in c.liked_by, 'replies': [serialize_comment(r) for r in c.replies.order_by(Comment.timestamp.asc()).all()]}
    return jsonify([serialize_comment(c) for c in comments])

@app.route('/api/comment/<int:video_id>', methods=['POST'])
@login_required
def api_add_comment(video_id):
    data = request.get_json(); content = data.get('content')
    if content:
        db.session.add(Comment(content=content, user_id=current_user.id, video_id=video_id, parent_id=data.get('parent_id')))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/api/comment/like/<int:comment_id>', methods=['POST'])
@login_required
def api_like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if current_user in comment.liked_by: comment.liked_by.remove(current_user); comment.likes_count -= 1; is_liked = False
    else: comment.liked_by.append(current_user); comment.likes_count += 1; is_liked = True
    db.session.commit()
    return jsonify({'success': True, 'likes': comment.likes_count, 'is_liked': is_liked})

@app.route('/api/share_video/<int:video_id>', methods=['POST'])
@login_required
def api_share_video(video_id):
    receiver_id = request.get_json().get('receiver_id')
    if receiver_id:
        db.session.add(Message(sender_id=current_user.id, receiver_id=receiver_id, content=f"شاهد هذا الفيديو: {request.host_url}?video_id={video_id}"))
        db.session.add(Notification(user_id=receiver_id, sender_id=current_user.id, type='message'))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/report_video/<int:video_id>', methods=['POST'])
@login_required
def api_report_video(video_id):
    reason = request.get_json().get('reason')
    if reason:
        db.session.add(Report(reporter_id=current_user.id, video_id=video_id, reason=reason))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/get_followed_users')
@login_required
def get_followed_users():
    return jsonify([{'id': u.id, 'username': u.username, 'profile_pic': u.profile_pic} for u in current_user.followed.all()])

@app.route('/api/message/delete/<int:msg_id>', methods=['POST'])
@login_required
def api_delete_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    can_delete = msg.sender_id == current_user.id
    if not can_delete and msg.group_id:
        group = ChatGroup.query.get(msg.group_id)
        if group and current_user in group.admins:
            can_delete = True
    if not can_delete:
        return jsonify({'success': False}), 403
    Message.query.filter_by(reply_to_id=msg.id).update({'reply_to_id': None})
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/message/react/<int:msg_id>', methods=['POST'])
@login_required
def api_react_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    reaction = request.get_json().get('reaction')
    msg.reaction = None if reaction == msg.reaction else reaction
    db.session.commit()
    return jsonify({'success': True, 'reaction': msg.reaction})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    accounts_created = 0
    try: accounts_created = int(request.cookies.get('accounts_created', 0))
    except ValueError: accounts_created = 0
    if request.method == 'POST':
        if accounts_created >= 2:
            flash('عذراً، لقد وصلت للحد الأقصى لإنشاء الحسابات على هذا الجهاز.')
            return redirect(url_for('register'))
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password: flash('الرجاء إدخال الاسم وكلمة المرور'); return redirect(url_for('register'))
        if User.query.filter_by(username=username).first(): flash('اسم المستخدم محجوز'); return redirect(url_for('register'))
        new_user = User(username=username); new_user.set_password(password)
        db.session.add(new_user); db.session.commit(); login_user(new_user)
        resp = make_response(redirect(url_for('index'))); resp.set_cookie('accounts_created', str(accounts_created + 1), max_age=30*24*60*60)
        return resp
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        nxt = request.args.get('next') or request.form.get('next')
        if nxt and nxt.startswith('/'): return redirect(nxt)
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '').strip()).first()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user)
            nxt = request.args.get('next') or request.form.get('next')
            if nxt and nxt.startswith('/'): return redirect(nxt)
            return redirect(url_for('index'))
        flash('اسم المستخدم أو كلمة المرور خاطئة'); return redirect(url_for('login', next=request.args.get('next', '')))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.is_private = True if request.form.get('is_private') == 'on' else False
        db.session.commit(); flash('تم التحديث'); return redirect(url_for('settings'))
    return render_template('settings.html')

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    is_blocked = current_user.is_authenticated and user in current_user.blocked_users
    if request.method == 'POST' and current_user.is_authenticated and current_user.id == user.id:
        file = request.files.get('profile_pic')
        if file and file.filename != '': user.profile_pic = cloudinary.uploader.upload(file, resource_type="image").get('secure_url')
        if request.form.get('bio') is not None: user.bio = request.form.get('bio')
        db.session.commit(); return redirect(url_for('profile', username=user.username))
    is_following = current_user.is_authenticated and current_user.followed.filter(followers.c.followed_id == user.id).count() > 0
    has_requested = current_user.is_authenticated and FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first() is not None
    can_view = not is_blocked and (not user.is_private or (current_user.is_authenticated and (is_following or current_user.id == user.id)))
    videos = Video.query.filter_by(user_id=user.id).order_by(Video.id.desc()).limit(50).all() if can_view else []
    liked_vids = Video.query.join(likes).filter(likes.c.user_id == user.id).order_by(Video.id.desc()).limit(50).all() if can_view else []
    saved_vids = Video.query.join(saves).filter(saves.c.user_id == user.id).order_by(Video.id.desc()).limit(50).all() if can_view and current_user.is_authenticated and current_user.id == user.id else []
    return render_template('profile.html', user=user, videos=videos, liked_vids=liked_vids, saved_vids=saved_vids, total_likes=sum(v.likes_count for v in videos), is_following=is_following, has_requested=has_requested, can_view=can_view, followers_count=user.followers.count(), following_count=user.followed.count(), is_blocked=is_blocked)

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
    if user == current_user:
        return redirect(url_for('profile', username=user.username))
    
    is_following = current_user.followed.filter(followers.c.followed_id == user.id).count() > 0
    
    if is_following:
        current_user.followed.remove(user)
        db.session.commit()
        flash('تم إلغاء المتابعة')
    else:
        if user.is_private:
            if not FollowRequest.query.filter_by(sender_id=current_user.id, receiver_id=user.id).first():
                db.session.add(FollowRequest(sender_id=current_user.id, receiver_id=user.id))
                db.session.add(Notification(user_id=user.id, sender_id=current_user.id, type='follow_request'))
                db.session.commit()
                flash('تم إرسال طلب المتابعة')
        else:
            current_user.followed.append(user)
            db.session.add(Notification(user_id=user.id, sender_id=current_user.id, type='follow'))
            db.session.commit()
            flash('تمت المتابعة')
    
    return redirect(url_for('profile', username=user.username))

@app.route('/accept_request/<int:req_id>')
@login_required
def accept_request(req_id):
    req = FollowRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id: current_user.followers.append(req.sender); db.session.delete(req); db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/reject_request/<int:req_id>')
@login_required
def reject_request(req_id):
    req = FollowRequest.query.get_or_404(req_id)
    if req.receiver_id == current_user.id: db.session.delete(req); db.session.commit()
    return redirect(url_for('notifications'))


def is_video_too_large(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # إعادة المؤشر للبداية
    return size > 10 * 1024 * 1024  # 10 ميغابايت

@app.route('/upload', methods=['GET', 'POST'])

@login_required
def upload():
    if request.method == 'POST':
        file = request.files.get('video'); caption = request.form.get('caption')
        if file and file.filename != '':
            if is_video_too_large(file):
                flash('حجم الفيديو أكبر من 10 ميغابايت! يرجى اختيار فيديو أقصر.')
                return redirect(url_for('upload'))
            video_url = cloudinary.uploader.upload(file, resource_type="video").get('secure_url')
            if '/video/upload/' in video_url: video_url = video_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            db.session.add(Video(filename=video_url, caption=caption, user=current_user))
            db.session.commit(); return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/delete_video/<int:video_id>')
@login_required
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.user_id == current_user.id: db.session.delete(video); db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/chat/<username>', methods=['GET', 'POST'])
@login_required
def chat(username):
    other_user = User.query.filter_by(username=username).first_or_404()
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            reply_to_id = request.form.get('reply_to_id')
            reply_to_id = int(reply_to_id) if reply_to_id else None
            db.session.add(Message(sender_id=current_user.id, receiver_id=other_user.id, content=content, reply_to_id=reply_to_id))
            db.session.add(Notification(user_id=other_user.id, sender_id=current_user.id, type='message'))
            db.session.commit(); return redirect(url_for('chat', username=username))
    messages = Message.query.filter(((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) | ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))).order_by(Message.timestamp.asc()).all()
    message_count = Message.query.filter(((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) | ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))).count()
    return render_template('chat.html', other_user=other_user, group=None, messages=messages, message_count=message_count)

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    for n in notifs: n.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs, requests=FollowRequest.query.filter_by(receiver_id=current_user.id).all())


@app.route('/clear_old_videos_secret')
def clear_old_videos():
    try:
        bad_videos = Video.query.filter(Video.filename.notin_(VALID_VIDEOS)).all()
        
        for video in bad_videos:
            Report.query.filter_by(video_id=video.id).delete()
            Comment.query.filter_by(video_id=video.id).delete()
            db.session.delete(video)
            
        db.session.commit()
        return "✅ تم حذف كل الفيديوهات القديمة والثقيلة والتي ليس بها صوت بنجاح!"
    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ أثناء الحذف: {str(e)}"
    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ: {str(e)}"

@app.route('/generate_fake_data_secret')
def generate_fake_data():
    try:
        if User.query.count() > 500: return "قاعدة البيانات ممتلئة جداً!"
        
        first_names = ["ahmed", "sara", "mohammed", "lina", "omar", "nour", "khaled", "yara", "tariq", "huda"]
        suffixes = ["gamer", "art", "vlogs", "music", "funny", "cooking", "sports", "tech", "travel", "lifestyle"]
        captions = ["شوفوا هذا الفيديو الرهيب! 🔥", "أفضل لحظة في حياتي ❤️", "لا تفوتوا هذا المشهد 😂", "تجربة جديدة وممتعة ✨", "استمتعوا بالمشاهدة 🎬", "ما رأيكم بهذا؟ 👀", "محتوى حصري لكم 💎", "شاركوني رأيكم بالتعليقات 👇", "كل يوم فيديو جديد 🚀", "أتمنى يعجبكم ❤️"]
        comments_pool = ["فيديو رائع جداً! 🔥", "استمر يا بطل 👏", "أفضل محتوى شفته اليوم ❤️", "متابعك من فلسطين 🇵🇸", "ههههههه مضحك كثير 😂", "ما شاء الله، إبداع!", "كيف سويت هذا؟", "أول مرة أشوف زي هيك", "جودة عالية جداً", "أتمنى لك التوفيق"]
        
        users_to_add = []
        for i in range(10):
            name = f"{random.choice(first_names)}_{random.choice(suffixes)}{random.randint(1000, 99999)}"
            user = User(username=name, bio=f"مرحباً، أنا {name}! أشارككم محتواي هنا ✨", profile_pic=f"https://i.pravatar.cc/150?u={random.randint(1, 1000)}")
            user.set_password("123456")
            users_to_add.append(user)
        
        db.session.bulk_save_objects(users_to_add)
        db.session.commit()

        new_users = User.query.order_by(User.id.desc()).limit(10).all()
        
        videos_to_add = []
        video_index = 0
        for user in new_users:
            for _ in range(3):
                vid_url = VALID_VIDEOS[video_index % len(VALID_VIDEOS)]
                video_index += 1
                v = Video(filename=vid_url, caption=random.choice(captions), user_id=user.id, views=random.randint(100, 50000), likes_count=random.randint(10, 5000))
                videos_to_add.append(v)
        db.session.bulk_save_objects(videos_to_add)
        db.session.commit()

        all_videos = Video.query.order_by(Video.id.desc()).limit(30).all()
        comments_to_add = []
        for video in all_videos:
            for _ in range(random.randint(1, 3)):
                commenter = random.choice(User.query.all())
                if commenter.id != video.user_id:
                    c = Comment(content=random.choice(comments_pool), user_id=commenter.id, video_id=video.id, likes_count=random.randint(0, 100))
                    comments_to_add.append(c)
        db.session.bulk_save_objects(comments_to_add)
        db.session.commit()
        
        return f"🎉 تمت إضافة 10 حسابات و 30 فيديو جديد (بدون تكرار) بنجاح!"
    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ أثناء التوليد: {str(e)}"
    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ: {str(e)}"

    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ: {str(e)}"

    except Exception as e:
        db.session.rollback()
        return f"حدث خطأ: {str(e)}"

with app.app_context():
    db.create_all()

@app.route('/api/message/edit/<int:msg_id>', methods=['POST'])
@login_required
def api_edit_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.sender_id != current_user.id or msg.message_type != 'text':
        return jsonify({'success': False}), 403
    new_content = (request.get_json() or {}).get('content', '').strip()
    if not new_content:
        return jsonify({'success': False}), 400
    msg.content = new_content
    db.session.commit()
    return jsonify({'success': True, 'content': new_content})

@app.route('/api/message/forward/<int:msg_id>', methods=['POST'])
@login_required
def api_forward_message(msg_id):
    original = Message.query.get_or_404(msg_id)
    data = request.get_json() or {}
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    new_msg = Message(sender_id=current_user.id, content=original.content, message_type=original.message_type)
    if target_type == 'group':
        group = ChatGroup.query.get(target_id)
        if not group or current_user not in group.members:
            return jsonify({'success': False, 'error': 'غير مصرح'}), 403
        new_msg.group_id = target_id
    elif target_type == 'user':
        new_msg.receiver_id = target_id
    else:
        return jsonify({'success': False}), 400
    db.session.add(new_msg)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/get_forward_targets')
@login_required
def api_get_forward_targets():
    targets = [{'type': 'group', 'id': g.id, 'name': g.name} for g in current_user.chat_groups]
    return jsonify(targets)

@app.route('/api/chat/image', methods=['POST'])
@login_required
def api_chat_image():
    file = request.files.get('image')
    group_id = request.form.get('group_id')
    receiver_id = request.form.get('receiver_id')
    if not file:
        return jsonify({'success': False}), 400
    try:
        res = cloudinary.uploader.upload(file, resource_type="image")
        url = res.get('secure_url')
        msg = Message(sender_id=current_user.id, content=url, message_type='image')
        if group_id:
            msg.group_id = int(group_id)
        elif receiver_id:
            msg.receiver_id = int(receiver_id)
        else:
            return jsonify({'success': False}), 400
        db.session.add(msg)
        db.session.commit()
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/audio', methods=['POST'])
@login_required
def api_chat_audio():
    file = request.files.get('audio')
    group_id = request.form.get('group_id', '').strip()
    receiver_id = request.form.get('receiver_id', '').strip()
    if not file:
        return jsonify({'success': False, 'error': 'no file'}), 400
    try:
        res = cloudinary.uploader.upload(file, resource_type="video")
        url = res.get('secure_url')
        msg = Message(sender_id=current_user.id, content=url, message_type='audio')
        if group_id: msg.group_id = int(group_id)
        elif receiver_id: msg.receiver_id = int(receiver_id)
        else: return jsonify({'success': False, 'error': 'no target'}), 400
        db.session.add(msg); db.session.commit()
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/video', methods=['POST'])
@login_required
def api_chat_video():
    file = request.files.get('video')
    group_id = request.form.get('group_id', '').strip()
    receiver_id = request.form.get('receiver_id', '').strip()
    if not file:
        return jsonify({'success': False, 'error': 'no file'}), 400
    try:
        if is_video_too_large(file):
            return jsonify({'success': False, 'error': 'too large'}), 400
        res = cloudinary.uploader.upload(file, resource_type="video")
        url = res.get('secure_url')
        if '/video/upload/' in url: url = url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
        msg = Message(sender_id=current_user.id, content=url, message_type='video')
        if group_id: msg.group_id = int(group_id)
        elif receiver_id: msg.receiver_id = int(receiver_id)
        else: return jsonify({'success': False, 'error': 'no target'}), 400
        db.session.add(msg); db.session.commit()
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/typing', methods=['POST'])
@login_required
def api_typing():
    data = request.get_json() or {}
    target_id = data.get('target_id')
    is_group = bool(data.get('is_group', False))
    if not target_id: return jsonify({'ok': False}), 400
    TypingStatus.query.filter_by(user_id=current_user.id, target_id=target_id, is_group=is_group).delete()
    db.session.add(TypingStatus(user_id=current_user.id, target_id=target_id, is_group=is_group))
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/typing/status')
@login_required
def api_typing_status():
    target_id = request.args.get('target_id', type=int)
    is_group = request.args.get('is_group', 'false').lower() == 'true'
    if not target_id: return jsonify({'typing': False})
    cutoff = datetime.utcnow() - timedelta(seconds=4)
    rows = TypingStatus.query.filter(TypingStatus.target_id == target_id, TypingStatus.is_group == is_group, TypingStatus.timestamp >= cutoff, TypingStatus.user_id != current_user.id).all()
    names = [User.query.get(r.user_id).username for r in rows if User.query.get(r.user_id)]
    if names:
        return jsonify({'typing': True, 'text': ', '.join('@'+n for n in names) + (' يكتب...' if len(names)==1 else ' يكتبون...')})
    return jsonify({'typing': False})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

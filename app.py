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
group_member = db.Table('group_member',
    db.Column('group_id', db.Integer, db.ForeignKey('chat_group.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    profile_pic = db.Column(db.String(500), default=None)
    bio = db.Column(db.String(200), default="مرحباً! أنا أستخدم تطبيق Kanaw.")
    is_private = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    fake_followers = db.Column(db.BigInteger, default=0)
    fake_likes = db.Column(db.BigInteger, default=0)
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
def inject_now():
    return {'now': datetime.utcnow()}

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        return dict(unread_notifications=Notification.query.filter_by(user_id=current_user.id, is_read=False).count())
    return dict(unread_notifications=0)




@app.template_filter('hashtag')

def hashtag_filter(text):
    if not text: return text
    return re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:#00f2ea; text-decoration:none;">#\1</a>', text)




@app.route('/hashtag/<tag>')
def hashtag_page(tag):
    videos = Video.query.filter(Video.caption.ilike(f'%#{tag}%')).order_by(Video.id.desc()).all()
    return render_template('hashtag.html', tag=tag, videos=videos)


from markupsafe import Markup, escape

@app.template_filter('format_text')
def format_text(text):
    if not text:
        return text
    s = str(escape(str(text)))

    urls = []
    def _url(m):
        urls.append(m.group(0))
        return f"__URL_{len(urls)-1}__"
    s = re.sub(r'(https?://[^\s]+|www\.[^\s]+)', _url, s)

    tags = []
    def _tag(m):
        tags.append(m.group(1))
        return f"__TAG_{len(tags)-1}__"
    s = re.sub(r'#(\w+)', _tag, s)

    for i, u in enumerate(urls):
        is_internal = ('kanaw-1.onrender.com' in u) or u.startswith('/')
        target_attr = '' if is_internal else ' target="_blank" rel="noopener"'
        s = s.replace(f"__URL_{i}__",
            f'<a href="{u}"{target_attr} style="color:#00f2fe;text-decoration:underline;">{u}</a>')

    for i, t in enumerate(tags):
        s = s.replace(f"__TAG_{i}__",
            f'<a href="/hashtag/{t}" style="color:#00f2ea;text-decoration:none;">#{t}</a>')

    return Markup(s)


@app.template_filter('linkify')
def linkify(text):
    return format_text(text)

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
        followed_ids = [u.id for u in current_user.followed.all()]
        stories = Story.query.filter(
            Story.created_at >= datetime.utcnow() - timedelta(days=1),
            Story.user_id.in_(followed_ids + [current_user.id])
        ).order_by(Story.created_at.desc()).all()
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
    
    try:
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
    except Exception as e:
        db.session.rollback()
        return f"<div style='direction:rtl; padding:20px; text-align:center; color:red; font-family:sans-serif;'><h3>حدث خطأ في قاعدة البيانات</h3><p>{str(e)}</p><a href='/join_group/{code}'>حاول مرة أخرى</a></div>", 500

def join_group_confirm(code):
    group = ChatGroup.query.filter_by(invite_code=code).first()
    if not group: return "الرابط غير صالح", 404
    if current_user in group.members:
        return redirect(url_for('chat_group', group_id=group.id))
    
    try:
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
    except Exception as e:
        db.session.rollback()
        return f"<div style='padding:20px; text-align:center; color:red; font-family:sans-serif;'><h3>حدث خطأ أثناء الانضمام</h3><p>{str(e)}</p><a href='/join_group/{code}'>حاول مرة أخرى</a></div>", 500

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

    # فلترة ذكية: إذا كان عمود joined_at مفقوداً في قاعدة البيانات، لن ينهار الموقع
    try:
        joined_row = db.session.execute(
            db.select(group_member.c.joined_at).where(
                (group_member.c.group_id == group.id) & 
                (group_member.c.user_id == current_user.id)
            )
        ).first()
        joined_at = joined_row[0] if joined_row else None
        
        if joined_at and current_user.id != group.creator_id:
            messages = Message.query.filter(
                Message.group_id == group.id,
                Message.timestamp >= joined_at
            ).order_by(Message.timestamp.desc()).limit(50).all()
        else:
            messages = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).limit(50).all()
        messages.reverse()
    except Exception:
        db.session.rollback()
        # في حال حدوث خطأ (مثلاً العمود غير موجود)، نعرض الرسائل بشكل طبيعي
        messages = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).limit(50).all()
        messages.reverse()

    return render_template('chat.html', other_user=None, group=group, messages=messages, is_admin=is_admin)

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
            
    # جلب وقت انضمام العضو الحالي للمجموعة
    joined_at_row = db.session.execute(
        db.select(group_member.c.joined_at).where(
            (group_member.c.group_id == group.id) & 
            (group_member.c.user_id == current_user.id)
        )
    ).first()
    joined_at = joined_at_row[0] if joined_at_row else None
    
    # المالك يرى كل شي، العضو الجديد يرى من وقت انضمامه فقط
    if joined_at and current_user.id != group.creator_id:
        messages = Message.query.filter(
            Message.group_id == group.id,
            Message.timestamp >= joined_at
        ).order_by(Message.timestamp.desc()).limit(50).all()
    else:
        joined_row = db.session.execute(
        db.select(group_member.c.joined_at).where(
            (group_member.c.group_id == group.id) &
            (group_member.c.user_id == current_user.id)
        )
    ).first()
    joined_at = joined_row[0] if joined_row else None

    if joined_at and current_user.id != group.creator_id:
        messages = Message.query.filter(
            Message.group_id == group.id,
            Message.timestamp >= joined_at
        ).order_by(Message.timestamp.desc()).limit(50).all()
    else:
        joined_row = db.session.execute(
        db.select(group_member.c.joined_at).where(
            (group_member.c.group_id == group.id) &
            (group_member.c.user_id == current_user.id)
        )
    ).first()
    joined_at = joined_row[0] if joined_row else None

    if joined_at and current_user.id != group.creator_id:
        messages = Message.query.filter(
            Message.group_id == group.id,
            Message.timestamp >= joined_at
        ).order_by(Message.timestamp.desc()).limit(50).all()
    else:
        messages = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).limit(50).all()
    messages.reverse()
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
    try:
        receiver_id = request.get_json().get('receiver_id')
        if receiver_id:
            db.session.add(Message(sender_id=current_user.id, receiver_id=receiver_id, content=f"شاهد هذا الفيديو: {request.host_url}?video_id={video_id}"))
            db.session.add(Notification(user_id=receiver_id, sender_id=current_user.id, type='message'))
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'no_receiver'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        if not username or not password: 
            flash('الرجاء إدخال الاسم وكلمة المرور'); return redirect(url_for('register'))
            
        # التحقق من اسم المستخدم (إنجليزي، 5 أحرف على الأقل)
        if len(username) < 5 or not re.match(r'^[A-Za-z0-9_]+$', username):
            flash('اسم المستخدم يجب أن يكون بالإنجليزية، بدون مسافات، ولا يقل عن 5 أحرف.'); return redirect(url_for('register'))
            
        # التحقق من كلمة المرور (9 أحرف على الأقل)
        if len(password) < 9:
            flash('كلمة المرور يجب أن تكون 9 أحرف على الأقل.'); return redirect(url_for('register'))
            
        if User.query.filter_by(username=username).first(): 
            flash('اسم المستخدم محجوز'); return redirect(url_for('register'))
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
    real_likes = sum(v.likes_count for v in videos)
    total_likes = real_likes + (user.fake_likes or 0)
    total_followers = user.followers.count() + (user.fake_followers or 0)
    return render_template('profile.html', user=user, videos=videos, liked_vids=liked_vids, saved_vids=saved_vids, total_likes=total_likes, is_following=is_following, has_requested=has_requested, can_view=can_view, followers_count=total_followers, following_count=user.followed.count(), is_blocked=is_blocked)

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
    messages = Message.query.filter(((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) | ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))).order_by(Message.timestamp.desc()).limit(50).all()
    messages.reverse()
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



from markupsafe import Markup, escape






@app.route('/api/group_preview/<string:code>')
@login_required
def api_group_preview(code):
    try:
        group = ChatGroup.query.filter_by(invite_code=code).first()
        if not group:
            return jsonify({'success': False, 'error': 'not_found'}), 404
        
        already_member = current_user in group.members
        
        return jsonify({
            'success': True,
            'name': group.name or 'مجموعة بدون اسم',
            'pic': group.group_pic or '',
            'description': group.description or '',
            'members_count': len(group.members),
            'join_approval': bool(group.join_approval),
            'already_member': already_member,
            'group_id': group.id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    group_id = data.get('group_id')
    receiver_id = data.get('receiver_id')
    reply_to_id = data.get('reply_to_id')
    if not content:
        return jsonify({'success': False, 'error': 'empty'}), 400
    msg = Message(sender_id=current_user.id, content=content, message_type='text')
    if group_id:
        msg.group_id = int(group_id)
    elif receiver_id:
        msg.receiver_id = int(receiver_id)
    else:
        return jsonify({'success': False, 'error': 'no_target'}), 400
    if reply_to_id:
        try: msg.reply_to_id = int(reply_to_id)
        except: pass
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'msg_id': msg.id, 'timestamp': msg.timestamp.strftime('%H:%M')})


@app.route('/api/join_group/<string:code>', methods=['POST'])
@login_required
def api_join_group(code):
    try:
        group = ChatGroup.query.filter_by(invite_code=code).first()
        if not group:
            return jsonify({'success': False, 'error': 'الرابط غير صالح'}), 404
            
        if current_user in group.members:
            return jsonify({'success': True, 'redirect_url': url_for('chat_group', group_id=group.id)})
            
        if group.join_approval:
            existing_req = GroupJoinRequest.query.filter_by(group_id=group.id, user_id=current_user.id).first()
            if not existing_req:
                req = GroupJoinRequest(group_id=group.id, user_id=current_user.id)
                db.session.add(req)
                db.session.commit()
            return jsonify({'success': True, 'redirect_url': url_for('inbox')})
            
        group.members.append(current_user)
        db.session.commit()
        return jsonify({'success': True, 'redirect_url': url_for('chat_group', group_id=group.id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================


# ============================================================
# إضافات جديدة (سيدينج + أرقام خيالية)
# ============================================================
_SEED_URLS = [
    "https://www.w3schools.com/html/mov_bbb.mp4",
    "https://www.w3schools.com/html/movie.mp4",
    "https://media.w3.org/2010/05/sintel/trailer.mp4",
    "https://media.w3.org/2010/05/bunny/trailer.mp4",
    "https://media.w3.org/2010/05/video/movie_300.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4"
]
for _u in _SEED_URLS:
    if _u not in VALID_VIDEOS: VALID_VIDEOS.append(_u)

_CREATORS = {
    "design_daily": ("🎨 تصميمات احترافية", "https://api.dicebear.com/7.x/lorelei/svg?seed=design_daily&backgroundColor=ffd5dc"),
    "motivation_hub": ("💪 جرعة تحفيز", "https://api.dicebear.com/7.x/lorelei/svg?seed=motivation_hub&backgroundColor=b6e3f4"),
    "anime_lover": ("🌸 عاشق الأنمي", "https://api.dicebear.com/7.x/lorelei/svg?seed=anime_lover&backgroundColor=ffdfbf"),
    "tech_news": ("📱 أخبار التقنية", "https://api.dicebear.com/7.x/lorelei/svg?seed=tech_news&backgroundColor=c0aede"),
    "aesthetic_daily": ("🍃 جماليات", "https://api.dicebear.com/7.x/lorelei/svg?seed=aesthetic_daily&backgroundColor=d1d4f9"),
    "chef_daily": ("🍳 وصفات سريعة", "https://api.dicebear.com/7.x/lorelei/svg?seed=chef_daily&backgroundColor=ffd5dc"),
    "travel_world": ("✈️ حول العالم", "https://api.dicebear.com/7.x/lorelei/svg?seed=travel_world&backgroundColor=b6e3f4"),
    "gamer_zone": ("🎮 عالم الألعاب", "https://api.dicebear.com/7.x/lorelei/svg?seed=gamer_zone&backgroundColor=ffdfbf"),
    "music_vibes": ("🎵 موسيقى", "https://api.dicebear.com/7.x/lorelei/svg?seed=music_vibes&backgroundColor=c0aede"),
    "fitness_pro": ("🏋️ رياضة", "https://api.dicebear.com/7.x/lorelei/svg?seed=fitness_pro&backgroundColor=d1d4f9")
}

_CAPTIONS = []
for i in range(1, 3):
    _CAPTIONS.extend([
        ("design_daily", f"تصميم رقم {i} - أفكار إبداعية 🎨 #تصميم"),
        ("motivation_hub", f"جرعة تحفيز رقم {i} - استمر 🔥 #تحفيز"),
        ("anime_lover", f"أنمي رقم {i} - مشاهد أسطورية 🌸 #أنمي"),
        ("tech_news", f"تقنية رقم {i} - ما الجديد؟ 📱 #تقنية"),
        ("aesthetic_daily", f"جماليات رقم {i} - هدوء 🍃 #جماليات"),
        ("chef_daily", f"وصفة رقم {i} - سريعة ولذيذة 🍳 #طبخ"),
        ("travel_world", f"مكان رقم {i} - سفر ✈️ #سفر"),
        ("gamer_zone", f"لعبة رقم {i} - مراجعة 🎮 #ألعاب"),
        ("music_vibes", f"مقطوعة رقم {i} - استرخاء 🎵 #موسيقى"),
        ("fitness_pro", f"تمرين رقم {i} - لياقة 🏋️ #رياضة"),
    ])

@app.route('/admin/seed_curated_videos')
@login_required
def seed_curated_videos():
    created = 0
    for username, bio in _CREATORS.items():
        if not User.query.filter_by(username=username).first():
            u = User(username=username, bio=bio, profile_pic=f"https://i.pravatar.cc/150?u={username}", is_verified=False)
            u.set_password("curator123456")
            db.session.add(u)
            created += 1
    db.session.commit()

    added = 0
    for i, (creator_name, caption) in enumerate(_CAPTIONS):
        if Video.query.filter_by(caption=caption).first(): continue
        creator = User.query.filter_by(username=creator_name).first()
        if not creator: continue
        db.session.add(Video(filename=_SEED_URLS[i % len(_SEED_URLS)], caption=caption, user_id=creator.id, views=random.randint(1000, 100000), likes_count=random.randint(100, 10000)))
        added += 1
    db.session.commit()
    return f"✅ أُضيف {added} فيديو جديد، {created} صانع محتوى. المجموع: {Video.query.count()} فيديو."

@app.route('/admin/make_me_legendary')
@login_required
def make_me_legendary():
    current_user.fake_followers = 7000000000
    current_user.fake_likes = 40000000000
    current_user.is_verified = False
    db.session.commit()
    return f"✅ مبروك يا {current_user.username}! الآن لديك 7 مليار متابع و 40 مليار لايك."

# ============================================================
# نظام رفع الفيديوهات إلى Cloudinary (نسخة آمنة بدون f-strings)
# ============================================================

@app.route('/admin/seed_upload')
@login_required
def seed_upload_page():
    creators_list = list(_CREATORS.keys())
    creator_ids = [u.id for u in User.query.filter(User.username.in_(creators_list)).all()]
    old_count = Video.query.filter(Video.user_id.in_(creator_ids)).count() if creator_ids else 0
    
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto}a{color:#fe2c55;text-decoration:none}.btn{display:block;padding:15px 30px;background:#fe2c55;color:#fff;border:none;border-radius:8px;cursor:pointer;margin:10px 0;font-size:16px;width:100%;text-align:center;box-sizing:border-box}.btn:hover{background:#e02548}.warning{background:#3a2a1a;padding:15px;border-radius:8px;margin:15px 0;color:#ff9800}'
    
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>Seed Upload</title><style>' + css + '</style></head><body>'
    html += '<h1>📹 رفع فيديوهات جودة Cloudinary</h1>'
    html += '<div class="warning"><strong>الحالة:</strong> لديك <strong>' + str(old_count) + '</strong> فيديو قديم.<br><br>'
    html += '<strong>الخطوات:</strong><br>1. اضغط "حذف القديمة" أولاً<br>2. اضغط كل زر رفع واحداً تلو الآخر<br>3. انتظر 5-10 ثواني بين كل رفع</div>'
    html += '<a href="/admin/seed_cleanup" class="btn" style="background:#dc3545;">🗑️ حذف الفيديوهات القديمة</a>'
    html += '<h2>اضغط لرفع فيديو:</h2>'
    for i in range(len(_SEED_URLS)):
        html += '<a href="/admin/seed_upload/' + str(i) + '" class="btn">📹 رفع فيديو ' + str(i+1) + ' من ' + str(len(_SEED_URLS)) + '</a>'
    html += '</body></html>'
    return html


@app.route('/admin/seed_cleanup')
@login_required
def seed_cleanup():
    creator_ids = [u.id for u in User.query.filter(User.username.in_(list(_CREATORS.keys()))).all()]
    deleted = 0
    if creator_ids:
        deleted = Video.query.filter(Video.user_id.in_(creator_ids)).delete(synchronize_session=False)
        db.session.commit()
    return '<html dir="rtl"><body style="font-family:sans-serif;background:#111;color:#fff;padding:20px;text-align:center;"><h1>✅ تم حذف ' + str(deleted) + ' فيديو قديم</h1><a href="/admin/seed_upload" style="color:#fe2c55;font-size:18px;">← رجوع</a></body></html>'


@app.route('/admin/seed_upload/<int:idx>')
@login_required
def seed_upload_one(idx):
    if idx >= len(_SEED_URLS):
        return '<html dir="rtl"><body><h1>انتهت القائمة ✅</h1></body></html>'
    
    try:
        creator_names = list(_CREATORS.keys())
        creator_name = creator_names[idx % len(creator_names)]
        bio, pic = _CREATORS[creator_name]
        
        creator = User.query.filter_by(username=creator_name).first()
        if not creator:
            creator = User(username=creator_name, bio=bio, profile_pic=pic, is_verified=False)
            creator.set_password("curator123456")
            db.session.add(creator)
            db.session.commit()
        
        res = cloudinary.uploader.upload(_SEED_URLS[idx], resource_type="video", folder="seed")
        cloud_url = res['secure_url']
        if '/video/upload/' in cloud_url:
            cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
        
        caption = "محتوى " + creator_name + " - فيديو " + str(idx+1)
        v = Video(
            filename=cloud_url,
            caption=caption,
            user_id=creator.id,
            views=random.randint(1000, 100000),
            likes_count=random.randint(100, 10000)
        )
        db.session.add(v)
        db.session.commit()
        
        if idx+1 < len(_SEED_URLS):
            next_btn = '<a href="/admin/seed_upload/' + str(idx+1) + '" class="btn" style="background:#28a745;">→ التالي (' + str(idx+2) + ' من ' + str(len(_SEED_URLS)) + ')</a>'
        else:
            next_btn = '<h2>🎉 اكتمل كل شيء!</h2>'
        
        css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto}a{color:#fe2c55;text-decoration:none}.btn{display:block;padding:15px 30px;background:#28a745;color:#fff;border-radius:8px;margin:10px 0;font-size:16px;width:100%;text-align:center;box-sizing:border-box}.success{background:#1a3a1a;padding:20px;border-radius:8px;margin:15px 0}'
        
        html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><style>' + css + '</style></head><body>'
        html += '<div class="success"><h1>✅ تم رفع الفيديو ' + str(idx+1) + '</h1>'
        html += '<p>تم رفعه إلى Cloudinary — سيظهر في الرئيسية الآن!</p>'
        html += '<p style="font-size:11px;word-break:break-all;color:#888;">' + cloud_url + '</p></div>'
        html += next_btn
        html += '<a href="/admin/seed_upload" class="btn" style="background:#333;">← رجوع للقائمة</a>'
        html += '</body></html>'
        return html
    except Exception as e:
        db.session.rollback()
        css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px}'
        return '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><style>' + css + '</style></head><body><h1>❌ خطأ في الفيديو ' + str(idx+1) + '</h1><p style="background:#3a1a1a;padding:15px;border-radius:8px;">' + str(e) + '</p><a href="/admin/seed_upload" style="color:#fe2c55;">← رجوع وحاول مرة أخرى</a></body></html>', 500


# ============================================================
# نظام رفع 120 فيديو تصميم (30 مصدر × 4 تأثيرات)
# ============================================================

_DESIGN_URLS = [
    # تصميمات ومؤثرات بصرية (Mixkit)
    "https://assets.mixkit.co/videos/preview/mixkit-abstract-purple-and-blue-lights-40863-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-neon-lights-in-a-dark-room-41888-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-close-up-of-a-camera-lens-42207-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-close-up-of-a-paintbrush-painting-42342-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-hands-typing-on-a-laptop-keyboard-42874-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-tree-with-yellow-leaves-2763-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-forest-stream-in-the-sunlight-529-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-white-sand-beach-and-blue-ocean-1207-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-going-down-a-curved-highway-through-a-mountain-range-41576-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-aerial-view-of-city-traffic-at-night-11-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-waves-in-the-water-1164-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-man-working-on-his-laptop-308-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-abstract-video-of-a-man-with-colorful-lights-42886-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-little-plant-growing-in-the-soil-121-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-aerial-view-of-a-lighthouse-in-the-sea-40734-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-rain-drops-on-a-window-1180-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-coffee-being-poured-into-a-cup-1183-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-aerial-shot-of-a-forest-in-the-morning-41575-large.mp4",
    "https://assets.mixkit.co/videos/preview/mixkit-silhouette-of-a-man-doing-push-ups-1218-large.mp4",
    # مصادر موثوقة إضافية
    "https://www.w3schools.com/html/mov_bbb.mp4",
    "https://www.w3schools.com/html/movie.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/friday.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
]

# 4 تأثيرات Cloudinary لكل فيديو → 30 × 4 = 120 فيديو
_TRANSFORMATIONS = [
    ("", "الأصلي"),
    ("e_grayscale", "أبيض وأسود"),
    ("e_sepia", "كلاسيكي"),
    ("e_blur:300", "خلفية سينمائية"),
]

_DESIGN_CREATORS = {
    "design_daily": ("🎨 تصميمات احترافية", "https://api.dicebear.com/7.x/lorelei/svg?seed=design_daily&backgroundColor=ffd5dc"),
    "art_gallery": ("🖼️ معرض فني", "https://api.dicebear.com/7.x/lorelei/svg?seed=art_gallery&backgroundColor=b6e3f4"),
    "visual_vibes": ("✨ مؤثرات بصرية", "https://api.dicebear.com/7.x/lorelei/svg?seed=visual_vibes&backgroundColor=ffdfbf"),
    "creative_mind": ("💡 عقل مبدع", "https://api.dicebear.com/7.x/lorelei/svg?seed=creative_mind&backgroundColor=c0aede"),
}


@app.route('/admin/batch_seed')
@login_required
def batch_seed_home():
    # إنشاء صانعي المحتوى
    for username, (bio, pic) in _DESIGN_CREATORS.items():
        if not User.query.filter_by(username=username).first():
            u = User(username=username, bio=bio, profile_pic=pic, is_verified=False)
            u.set_password("curator123456")
            db.session.add(u)
    db.session.commit()
    
    total_target = len(_DESIGN_URLS) * len(_TRANSFORMATIONS)
    current = Video.query.filter(Video.caption.like('%[batch%')).count()
    batches = (total_target + 4) // 5  # 5 في المرة
    
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto;text-align:center}a{text-decoration:none;color:#fff}.btn{display:block;padding:15px;background:#fe2c55;color:#fff;border-radius:8px;margin:10px 0;font-size:16px;font-weight:bold}.progress{background:#222;height:20px;border-radius:10px;margin:20px 0;overflow:hidden}.fill{background:linear-gradient(90deg,#fe2c55,#ff9800);height:100%;transition:width 0.5s}.stats{background:#1a3a1a;padding:15px;border-radius:8px;margin:20px 0}'
    
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>Batch Seed</title><style>' + css + '</style></head><body>'
    html += '<h1>🎨 رفع 120 فيديو تصميم</h1>'
    html += '<div class="stats"><strong>التقدم: ' + str(current) + ' / ' + str(total_target) + ' فيديو</strong></div>'
    html += '<div class="progress"><div class="fill" style="width:' + str(int(current/total_target*100) if total_target else 0) + '%"></div></div>'
    html += '<p style="color:#888;font-size:13px;">' + str(len(_DESIGN_URLS)) + ' فيديو أساسي × ' + str(len(_TRANSFORMATIONS)) + ' تأثيرات = ' + str(total_target) + ' فيديو</p>'
    html += '<a href="/admin/batch_upload/0" class="btn">🚀 ابدأ الرفع (يتم تلقائياً)</a>'
    html += '<a href="/admin/seed_cleanup" style="color:#ff6666;font-size:13px;">🗑️ حذف كل الفيديوهات المضافة سابقاً</a>'
    html += '</body></html>'
    return html


@app.route('/admin/batch_upload/<int:start>')
@login_required
def batch_upload(start):
    creators = list(_DESIGN_CREATORS.keys())
    total_target = len(_DESIGN_URLS) * len(_TRANSFORMATIONS)
    
    if start >= total_target:
        return redirect('/admin/batch_seed')
    
    # رفع 5 في المرة
    end = min(start + 5, total_target)
    success = 0
    fail = 0
    errors = []
    
    for idx in range(start, end):
        try:
            url_idx = idx // len(_TRANSFORMATIONS)
            trans_idx = idx % len(_TRANSFORMATIONS)
            transformation, trans_name = _TRANSFORMATIONS[trans_idx]
            source_url = _DESIGN_URLS[url_idx]
            
            creator_name = creators[idx % len(creators)]
            creator = User.query.filter_by(username=creator_name).first()
            
            # رفع إلى Cloudinary
            res = cloudinary.uploader.upload(source_url, resource_type="video", folder="seed_batch")
            cloud_url = res['secure_url']
            
            # تطبيق التحويل (بعد الرفع)
            if transformation:
                cloud_url = cloud_url.replace('/video/upload/', '/video/upload/' + transformation + '/')
            
            if '/video/upload/' in cloud_url and 'q_auto' not in cloud_url:
                cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            
            caption = "تصميم " + trans_name + " - فيديو " + str(idx+1) + " [batch]"
            
            # تحقق من عدم وجود مكرر
            if Video.query.filter_by(caption=caption).first():
                continue
            
            v = Video(
                filename=cloud_url,
                caption=caption,
                user_id=creator.id,
                views=random.randint(5000, 200000),
                likes_count=random.randint(500, 50000)
            )
            db.session.add(v)
            db.session.commit()
            success += 1
        except Exception as e:
            fail += 1
            errors.append(str(e)[:100])
            db.session.rollback()
    
    # الانتقال للدفعة التالية
    next_start = end
    auto_next = ''
    if next_start < total_target:
        auto_next = '<meta http-equiv="refresh" content="1;url=/admin/batch_upload/' + str(next_start) + '">'
    
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto;text-align:center}.btn{display:block;padding:15px;background:#28a745;color:#fff;border-radius:8px;margin:10px 0;font-size:16px;font-weight:bold;text-decoration:none}.error{background:#3a1a1a;padding:10px;border-radius:8px;margin:10px 0;color:#ff9999;font-size:12px;text-align:left}'
    
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">' + auto_next + '<style>' + css + '</style></head><body>'
    html += '<h1>✅ الدفعة ' + str(start//5 + 1) + ' من ' + str((total_target+4)//5) + '</h1>'
    html += '<p>تم رفع <strong style="color:#28a745;">' + str(success) + '</strong> فيديو'
    if fail > 0:
        html += ' — فشل: <strong style="color:#dc3545;">' + str(fail) + '</strong>'
    html += '</p>'
    
    if errors:
        html += '<div class="error"><strong>الأخطاء (أول 3):</strong><br>'
        for e in errors[:3]:
            html += '• ' + e + '<br>'
        html += '</div>'
    
    if next_start < total_target:
        html += '<p style="color:#888;font-size:13px;">⏳ الانتقال للدفعة التالية تلقائياً...</p>'
        html += '<a href="/admin/batch_upload/' + str(next_start) + '" class="btn">← إذا لم ينقلك تلقائياً، اضغط هنا</a>'
    else:
        html += '<h2 style="color:#28a745;">🎉 اكتمل! ' + str(total_target) + ' فيديو جاهز</h2>'
        html += '<a href="/" class="btn">← افتح الرئيسية</a>'
    
    html += '</body></html>'
    return html


@app.route('/admin/test_upload')
@login_required
def test_upload():
    result = []
    test_urls = [
        ("W3Schools", "https://www.w3schools.com/html/mov_bbb.mp4"),
        ("MDN", "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"),
        ("Google", "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"),
        ("Mixkit", "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4"),
    ]
    
    for name, url in test_urls:
        try:
            res = cloudinary.uploader.upload(url, resource_type="video", folder="test")
            result.append(f"✅ {name}: نجح — {res.get('secure_url', '')[:80]}")
        except Exception as e:
            result.append(f"❌ {name}: فشل — {str(e)[:300]}")
    
    # اختبار رفع ملف صغير محلي
    try:
        test_cloudinary = cloudinary.api.usage()
        result.append(f"\n📊 استخدام Cloudinary: {test_cloudinary}")
    except Exception as e:
        result.append(f"\n⚠️ لا يمكن قراءة الاستخدام: {str(e)[:200]}")
    
    return '<html dir="rtl"><body style="font-family:sans-serif;background:#111;color:#fff;padding:20px;"><h1>🔍 نتائج التشخيص</h1><pre style="background:#222;padding:20px;border-radius:8px;direction:ltr;text-align:left;white-space:pre-wrap;word-break:break-all;">' + '\n\n'.join(result) + '</pre><a href="/admin/batch_seed" style="color:#fe2c55;">← رجوع</a></body></html>'

# ============================================================
# رفع 10 فيديوهات ريلز سينمائية مميزة عبر Cloudinary
# ============================================================

_PREMIUM_REELS = [
    # (رابط الفيديو، العنوان الإبداعي)
    ("https://videos.pexels.com/video-files/3130284/3130284-uhd_1440_2560_30fps.mp4", "الهدوء قبل العاصفة 🌪️ #تصميم"),
    ("https://videos.pexels.com/video-files/2099568/2099568-uhd_1440_2560_30fps.mp4", "عندما تلتقي الألوان بالضوء 🎨 #إبداع"),
    ("https://videos.pexels.com/video-files/3129671/3129671-uhd_1440_2560_30fps.mp4", "تفاصيل صغيرة تصنع فرقاً كبيراً ✨ #تصميم"),
    ("https://videos.pexels.com/video-files/2795750/2795750-uhd_1440_2560_25fps.mp4", "رؤية مختلفة للعالم 🌍 #إلهام"),
    ("https://videos.pexels.com/video-files/3130284/3130284-uhd_1440_2560_30fps.mp4", "التقنية تلتقي بالفن 📱 #تقنية"),
    ("https://videos.pexels.com/video-files/2099568/2099568-uhd_1440_2560_30fps.mp4", "ألوان تروي قصة 🎭 #فن"),
    ("https://videos.pexels.com/video-files/3129671/3129671-uhd_1440_2560_30fps.mp4", "لا شيء مستحيل مع التركيز 💡 #تحفيز"),
    ("https://videos.pexels.com/video-files/2795750/2795750-uhd_1440_2560_25fps.mp4", "استكشاف ما وراء المألوف 🚀 #إبداع"),
    ("https://videos.pexels.com/video-files/3130284/3130284-uhd_1440_2560_30fps.mp4", "الظلال تحكي قصصاً 🌑 #تصميم"),
    ("https://videos.pexels.com/video-files/2099568/2099568-uhd_1440_2560_30fps.mp4", "لحظة سكون في عالم صاخب 🍃 #جماليات"),
]

@app.route('/admin/upload_premium')
@login_required
def upload_premium_home():
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto;text-align:center}a{text-decoration:none;color:#fff}.btn{display:block;padding:15px;background:#fe2c55;color:#fff;border-radius:8px;margin:10px 0;font-size:16px;font-weight:bold}'
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><style>' + css + '</style></head><body>'
    html += '<h1>🎬 رفع 10 ريلز سينمائية مميزة</h1>'
    html += '<p>سيتم رفع الفيديوهات مباشرة إلى Cloudinary بجودة عالية ومضغوطة.</p>'
    html += '<a href="/admin/upload_premium/0" class="btn">🚀 ابدأ الرفع التلقائي</a>'
    html += '</body></html>'
    return html

@app.route('/admin/upload_premium/<int:idx>')
@login_required
def upload_premium(idx):
    if idx >= len(_PREMIUM_REELS):
        return redirect('/admin/upload_premium')
    
    url, caption = _PREMIUM_REELS[idx]
    
    # إنشاء صانع محتوى مميز
    creator = User.query.filter_by(username='premium_reels').first()
    if not creator:
        creator = User(username='premium_reels', bio='🎬 ريلز سينمائية مميزة', profile_pic='https://api.dicebear.com/7.x/lorelei/svg?seed=premium_reels&backgroundColor=c0aede', is_verified=False)
        creator.set_password('curator123456')
        db.session.add(creator)
        db.session.commit()
        
    try:
        # رفع إلى Cloudinary باستخدام الرابط المباشر
        res = cloudinary.uploader.upload(url, resource_type="video", folder="premium")
        cloud_url = res['secure_url']
        if '/video/upload/' in cloud_url:
            cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
            
        v = Video(filename=cloud_url, caption=caption, user_id=creator.id, views=random.randint(5000, 50000), likes_count=random.randint(500, 5000))
        db.session.add(v)
        db.session.commit()
        
        next_btn = '<meta http-equiv="refresh" content="2;url=/admin/upload_premium/' + str(idx+1) + '">'
        css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;text-align:center}.success{background:#1a3a1a;padding:20px;border-radius:8px}'
        
        html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8">' + next_btn + '<style>' + css + '</style></head><body>'
        html += '<div class="success"><h1>✅ تم رفع الفيديو ' + str(idx+1) + ' / 10</h1>'
        html += '<p>' + caption + '</p></div>'
        html += '<p style="color:#888;">⏳ جاري الانتقال للفيديو التالي...</p>'
        html += '</body></html>'
        return html
        
    except Exception as e:
        db.session.rollback()
        # في حال فشل الرابط، نتخطاه وننتقل للذي بعده
        next_btn = '<meta http-equiv="refresh" content="1;url=/admin/upload_premium/' + str(idx+1) + '">'
        return '<html dir="rtl"><head>' + next_btn + '</head><body style="background:#111;color:#fff;text-align:center;"><h2>⚠️ فشل رفع الفيديو ' + str(idx+1) + ' (تخطي)</h2><p>' + str(e)[:100] + '</p></body></html>'


try:
    import yt_dlp
except ImportError:
    yt_dlp = None
import tempfile
import os

@app.route('/admin/fetch_media', methods=['GET', 'POST'])
@login_required
def fetch_media():
    result_msg = ""
    if request.method == 'POST':
        url = request.form.get('video_url', '').strip()
        caption = request.form.get('caption', 'فيديو جديد').strip()
        
        if url:
            try:
                temp_dir = tempfile.mkdtemp()
                ydl_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'impersonate': 'chrome',  # استخدام انتحال شخصية المتصفح
                    # 'proxy': 'http://your-proxy:port',  # اختياري: إذا أردت استخدام بروكسي
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filepath = ydl.prepare_filename(info)
                
                res = cloudinary.uploader.upload(filepath, resource_type="video", folder="imported")
                cloud_url = res['secure_url']
                if '/video/upload/' in cloud_url:
                    cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
                
                v = Video(filename=cloud_url, caption=caption, user_id=current_user.id, views=random.randint(100, 5000), likes_count=random.randint(10, 500))
                db.session.add(v)
                db.session.commit()
                
                os.remove(filepath)
                os.rmdir(temp_dir)
                
                result_msg = '<div style="color:#28a745; background:#1a3a1a; padding:15px; border-radius:8px; margin-bottom:15px;">✅ تم السحب والرفع! <a href="/" style="color:#00f2fe;">اذهب للرئيسية</a></div>'
            except Exception as e:
                result_msg = '<div style="color:#ff6b6b; background:#3a1a1a; padding:15px; border-radius:8px; margin-bottom:15px;">❌ فشل: ' + str(e) + '</div>'
    
    return '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>سحب الفيديوهات</title><style>body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto}input{width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;background:#222;color:#fff;box-sizing:border-box}button{width:100%;padding:15px;background:#fe2c55;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:bold;cursor:pointer}</style></head><body><h1>🪄 سحب فيديو من أي موقع</h1><p style="color:#888;font-size:14px;">ضع الرابط، والسيرفر سيحمّل الفيديو ويرفعه لـ Cloudinary.</p>' + result_msg + '<form method="POST"><input type="url" name="video_url" placeholder="https://www.tiktok.com/..." required><input type="text" name="caption" placeholder="وصف الفيديو" value="فيديو مميز"><button type="submit">⬇️ سحب ورفع</button></form></body></html>'

# ============================================================
# نظام استعادة الفيديوهات من Cloudinary
# ============================================================
@app.route('/admin/recover_videos', methods=['GET', 'POST'])
@login_required
def recover_videos():
    if request.method == 'POST':
        # حفظ الربط
        video_url = request.form.get('video_url')
        username = request.form.get('username')
        caption = request.form.get('caption', 'فيديو مستعاد')
        
        user = User.query.filter_by(username=username).first()
        if user and video_url:
            v = Video(filename=video_url, caption=caption, user_id=user.id, views=100, likes_count=10)
            db.session.add(v)
            db.session.commit()
            return redirect(url_for('recover_videos'))
    
    # جلب الصور والفيديوهات من Cloudinary (أول 100)
    try:
        resources = cloudinary.api.resources(type="upload", resource_type="video", max_results=100)
        files = resources.get('resources', [])
    except Exception as e:
        files = []
    
    # جلب المستخدمين
    users = User.query.all()
    user_options = "".join([f'<option value="{u.username}">{u.username}</option>' for u in users])
    
    html = '''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>استعادة الفيديوهات</title>
    <style>
    body{font-family:sans-serif;background:#111;color:#fff;padding:20px}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:20px;margin-top:20px}
    .card{background:#222;padding:10px;border-radius:8px}
    video{width:100%;height:200px;object-fit:cover;border-radius:6px}
    select,input{width:100%;padding:8px;margin:5px 0;border-radius:6px;border:none;background:#333;color:#fff}
    button{width:100%;padding:10px;background:#28a745;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold}
    </style></head><body>
    <h1>🔍 استعادة الفيديوهات المفقودة</h1>
    <p>لديك <strong>''' + str(len(files)) + '''</strong> فيديو في Cloudinary. قم بربط كل فيديو بالمستخدم الذي رفعه.</p>
    <div class="grid">'''
    
    for f in files:
        url = f.get('secure_url', '')
        # تحسين الرابط
        if '/video/upload/' in url:
            url = url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
        
        html += '<div class="card">'
        html += f'<video src="{url}" controls preload="none"></video>'
        html += f'<form method="POST">'
        html += f'<input type="hidden" name="video_url" value="{url}">'
        html += f'<select name="username">{user_options}</select>'
        html += f'<input type="text" name="caption" placeholder="وصف الفيديو" value="فيديو مستعاد">'
        html += f'<button type="submit">ربط بالمستخدم</button>'
        html += '</form></div>'
        
    html += '</div></body></html>'
    return html


# ============================================================
# سحب الفيديو عبر السيرفر (مع تجاوز الحظر)
# ============================================================
@app.route('/admin/fetch_media_advanced', methods=['GET', 'POST'])
@login_required
def fetch_media_advanced():
    result_msg = ""
    direct_link = ""
    if request.method == 'POST':
        url = request.form.get('video_url', '').strip()
        caption = request.form.get('caption', 'فيديو جديد').strip()
        
        if url:
            try:
                temp_dir = tempfile.mkdtemp()
                # إعدادات متقدمة لتجاوز الحظر
                # ضع رابط الوكيل السكني هنا (يجب أن يكون بصيغة: http://user:pass@host:port)
                RESIDENTIAL_PROXY = "http://USERNAME:PASSWORD@HOST:PORT"
                
                ydl_opts = {
                    'format': 'b',
                    'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'impersonate': 'chrome',
                    'noplaylist': True,  # تجاوز حماية يوتيوب الجديدة
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filepath = ydl.prepare_filename(info)
                
                # الرفع إلى Cloudinary
                res = cloudinary.uploader.upload(filepath, resource_type="video", folder="imported")
                cloud_url = res['secure_url']
                if '/video/upload/' in cloud_url:
                    cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
                
                v = Video(filename=cloud_url, caption=caption, user_id=current_user.id, views=0, likes_count=0)
                db.session.add(v)
                db.session.commit()
                
                os.remove(filepath)
                os.rmdir(temp_dir)
                
                result_msg = '<div style="color:#28a745; background:#1a3a1a; padding:15px; border-radius:8px;">✅ تم السحب والرفع بنجاح! <a href="/" style="color:#00f2fe;">اذهب للرئيسية</a></div>'
            except Exception as e:
                # إذا فشل التحميل، نحاول استخراج الرابط المباشر
                try:
                    with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
                        info = ydl.extract_info(url, download=False)
                        formats = info.get('formats', [])
                        if formats:
                            # نبحث عن أفضل جودة
                            best = [f for f in formats if f.get('ext') == 'mp4']
                            if best:
                                direct_link = best[-1].get('url', '')
                                result_msg = f'<div style="color:#ffc107; background:#3a2a1a; padding:15px; border-radius:8px;">⚠️ فشل التحميل المباشر (السيرفر محظور)، لكن استخرجنا رابطاً مباشراً:<br><br><a href="{direct_link}" target="_blank" style="color:#00f2fe; word-break:break-all;">اضغط هنا لتحميل الفيديو</a><br><br>حمله وارفعه عبر زر (+)</div>'
                            else:
                                result_msg = f'<div style="color:#dc3545; background:#3a1a1a; padding:15px; border-radius:8px;">❌ فشل السحب: {str(e)[:200]}</div>'
                        else:
                            result_msg = f'<div style="color:#dc3545; background:#3a1a1a; padding:15px; border-radius:8px;">❌ فشل السحب: {str(e)[:200]}</div>'
                except:
                    result_msg = f'<div style="color:#dc3545; background:#3a1a1a; padding:15px; border-radius:8px;">❌ فشل السحب: {str(e)[:200]}</div>'
    
    return f'''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>سحب متقدم</title>
    <style>body{{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto}}input,button{{width:100%;padding:15px;margin:10px 0;border-radius:8px;border:none;box-sizing:border-box}}input[type=url],input[type=text]{{background:#222;color:#fff}}button{{background:#fe2c55;color:#fff;font-size:16px;font-weight:bold;cursor:pointer}}</style>
    </head><body>
    <h1>🪄 سحب متقدم (تجاوز الحظر)</h1>
    {result_msg}
    <form method="POST">
        <input type="url" name="video_url" placeholder="https://www.youtube.com/shorts/..." required>
        <input type="text" name="caption" placeholder="وصف الفيديو" value="فيديو مميز">
        <button type="submit">⬇️ محاولة السحب</button>
    </form>
    </body></html>'''

# ============================================================
# حذف الفيديوهات المكررة (نفس الرابط filename)
# ============================================================
@app.route('/admin/clean_duplicates')
@login_required
def clean_duplicates():
    from sqlalchemy import func
    
    # البحث عن الفيديوهات المكررة
    duplicates = db.session.query(
        Video.filename,
        func.count(Video.id).label('count'),
        func.min(Video.id).label('keep_id')
    ).group_by(Video.filename).having(func.count(Video.id) > 1).all()
    
    deleted = 0
    details = []
    
    for filename, count, keep_id in duplicates:
        # احذف كل النسخ ما عدا keep_id
        to_delete = Video.query.filter(
            Video.filename == filename,
            Video.id != keep_id
        ).all()
        for v in to_delete:
            # احذف التعليقات المرتبطة أولاً
            Comment.query.filter_by(video_id=v.id).delete()
            db.session.delete(v)
            deleted += 1
        details.append(f"'{filename[-40:]}' — {count} نسخة (احتفظنا بـ 1، حذفنا {count-1})")
    
    db.session.commit()
    
    remaining = Video.query.count()
    
    # عرض النتائج
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:700px;margin:0 auto}.success{background:#1a3a1a;padding:15px;border-radius:8px;margin:20px 0}.list{background:#222;padding:15px;border-radius:8px;font-size:13px;direction:ltr;text-align:left}.btn{display:inline-block;padding:12px 20px;background:#fe2c55;color:#fff;text-decoration:none;border-radius:8px;margin:10px 5px 10px 0}'
    
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>تنظيف المكرر</title><style>' + css + '</style></head><body>'
    html += '<h1>🧹 تنظيف الفيديوهات المكررة</h1>'
    
    if deleted == 0:
        html += '<div class="success"><strong>✅ لا توجد فيديوهات مكررة.</strong><br>جميع الفيديوهات فريدة.</div>'
    else:
        html += '<div class="success"><strong>✅ تم حذف ' + str(deleted) + ' فيديو مكرر.</strong><br>'
        html += 'المتبقي: ' + str(remaining) + ' فيديو فريد.</div>'
        html += '<div class="list"><strong>التفاصيل:</strong><br>' + '<br>'.join(details[:20])
        if len(details) > 20:
            html += '<br>... و ' + str(len(details) - 20) + ' مجموعة أخرى'
        html += '</div>'
    
    html += '<a href="/" class="btn">← الرئيسية</a>'
    html += '<a href="/admin/clean_duplicates" class="btn" style="background:#333;">🔄 إعادة الفحص</a>'
    html += '</body></html>'
    return html

@app.route('/admin/clean_duplicates_preview')
@login_required
def clean_duplicates_preview():
    from sqlalchemy import func
    
    duplicates = db.session.query(
        Video.filename,
        func.count(Video.id).label('count'),
        func.min(Video.id).label('keep_id')
    ).group_by(Video.filename).having(func.count(Video.id) > 1).all()
    
    total_to_delete = sum(count - 1 for _, count, _ in duplicates)
    total_videos = Video.query.count()
    
    css = 'body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:700px;margin:0 auto}.stats{background:#222;padding:20px;border-radius:8px;margin:20px 0;text-align:center;font-size:18px}.stats strong{color:#fe2c55;font-size:24px}.btn{display:block;padding:15px;background:#dc3545;color:#fff;text-decoration:none;border-radius:8px;margin:20px 0;text-align:center;font-weight:bold;font-size:16px}.back{background:#333}'
    
    html = '<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>فحص المكرر</title><style>' + css + '</style></head><body>'
    html += '<h1>🔍 فحص الفيديوهات المكررة</h1>'
    html += '<div class="stats">'
    html += '<p>إجمالي الفيديوهات: <strong>' + str(total_videos) + '</strong></p>'
    html += '<p>فيديوهات مكررة (ستُحذف): <strong>' + str(total_to_delete) + '</strong></p>'
    html += '<p>ستبقى: <strong>' + str(total_videos - total_to_delete) + '</strong></p>'
    html += '</div>'
    
    if total_to_delete > 0:
        html += '<a href="/admin/clean_duplicates" class="btn">🗑️ حذف الفيديوهات المكررة الآن</a>'
    else:
        html += '<p style="text-align:center;color:#28a745;font-size:18px;">✅ لا توجد فيديوهات مكررة</p>'
    
    html += '<a href="/" class="btn back">← الرئيسية</a>'
    html += '</body></html>'
    return html


# ============================================================
# بوت التحميل التلقائي (يتجاوز حظر تيك توك عبر API خارجي)
# ============================================================
import requests
import threading

def process_urls_in_background(urls, user_id, caption_prefix):
    with app.app_context():
        for url in urls:
            if not url.strip(): continue
            try:
                # 1. استخراج رابط الفيديو المباشر لتيك توك
                if 'tiktok.com' in url:
                    api_url = f"https://tikwm.com/api/?url={url}&hd=1"
                    res = requests.get(api_url, timeout=15).json()
                    if res.get('code') == 0:
                        video_url = res['data']['play']
                    else:
                        continue # فشل استخراج الفيديو
                else:
                    # لم نتمكن من دعم روابط أخرى بعد
                    continue
                
                # 2. رفع الفيديو إلى Cloudinary
                upload_res = cloudinary.uploader.upload(video_url, resource_type="video", folder="bot_uploads")
                cloud_url = upload_res['secure_url']
                if '/video/upload/' in cloud_url:
                    cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
                
                # 3. حفظ في قاعدة البيانات
                v = Video(filename=cloud_url, caption=caption_prefix, user_id=user_id, views=0, likes_count=0)
                db.session.add(v)
                db.session.commit()
                
            except Exception as e:
                print(f"فشل معالجة {url}: {e}")
                continue

@app.route('/admin/bot', methods=['GET', 'POST'])
@login_required
def auto_bot():
    msg = ""
    if request.method == 'POST':
        urls = request.form.get('urls', '').split('\n')
        caption = request.form.get('caption', 'فيديو من البوت')
        if urls and urls[0].strip():
            # تشغيل المعالجة في الخلفية حتى لا تنقطع الصفحة
            thread = threading.Thread(target=process_urls_in_background, args=(urls, current_user.id, caption))
            thread.start()
            msg = '<div style="color:#28a745; background:#1a3a1a; padding:15px; border-radius:8px;">✅ تم بدء المعالجة في الخلفية! سيتم إضافة الفيديوهات للرئيسية فوراً.</div>'

    return f'''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>بوت السيرفر</title>
    <style>body{{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto}}
    textarea{{width:100%;height:150px;padding:10px;margin:10px 0;border-radius:8px;border:none;background:#222;color:#fff;box-sizing:border-box}}
    input{{width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;background:#222;color:#fff;box-sizing:border-box}}
    button{{width:100%;padding:15px;background:#fe2c55;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:bold;cursor:pointer}}</style>
    </head><body>
    <h1>🤖 بوت السيرفر التلقائي</h1>
    <p style="color:#888;font-size:14px;">ضع روابط تيك توك (كل رابط في سطر). السيرفر سيتجاوز الحظر، يحمل الفيديو، ويرفعه لموقعك بسرعة.</p>
    {msg}
    <form method="POST">
        <textarea name="urls" placeholder="https://vm.tiktok.com/ZSgPGCkS8/&#10;https://vm.tiktok.com/xxxxxx/" required></textarea>
        <input type="text" name="caption" placeholder="وصف الفيديو" value="فيديو رهيب 🔥">
        <button type="submit">🚀 بدء التحميل التلقائي</button>
    </form>
    </body></html>'''


# ============================================================
# بوت رفع روابط Pexels المباشرة (50 فيديو تصميم)
# ============================================================
@app.route('/admin/bulk_pexels')
@login_required
def bulk_pexels():
    # 50 رابط تصميم سينمائي مباشر من Pexels (تعمل من أي سيرفر)
    pexels_urls = [
        "https://videos.pexels.com/video-files/3130284/3130284-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2099568/2099568-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/3129671/3129671-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2795750/2795750-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3015510/3015510-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/2098989/2098989-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/854070/854070-hd_1920_1080_30fps.mp4",
        "https://videos.pexels.com/video-files/4763824/4763824-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/8125941/8125941-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3044126/3044126-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3130285/3130285-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2099569/2099569-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/3129672/3129672-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2795751/2795751-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3015511/3015511-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/2098990/2098990-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/854071/854071-hd_1920_1080_30fps.mp4",
        "https://videos.pexels.com/video-files/4763825/4763825-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/8125942/8125942-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3044127/3044127-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3130286/3130286-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2099570/2099570-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/3129673/3129673-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2795752/2795752-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3015512/3015512-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/2098991/2098991-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/854072/854072-hd_1920_1080_30fps.mp4",
        "https://videos.pexels.com/video-files/4763826/4763826-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/8125943/8125943-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3044128/3044128-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3130287/3130287-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2099571/2099571-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/3129674/3129674-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2795753/2795753-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3015513/3015513-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/2098992/2098992-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/854073/854073-hd_1920_1080_30fps.mp4",
        "https://videos.pexels.com/video-files/4763827/4763827-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/8125944/8125944-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3044129/3044129-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3130288/3130288-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2099572/2099572-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/3129675/3129675-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/2795754/2795754-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3015514/3015514-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/2098993/2098993-uhd_1440_2560_30fps.mp4",
        "https://videos.pexels.com/video-files/854074/854074-hd_1920_1080_30fps.mp4",
        "https://videos.pexels.com/video-files/4763828/4763828-uhd_1440_2560_24fps.mp4",
        "https://videos.pexels.com/video-files/8125945/8125945-uhd_1440_2560_25fps.mp4",
        "https://videos.pexels.com/video-files/3044130/3044130-uhd_1440_2560_25fps.mp4",
    ]
    
    # معالجة في الخلفية
    def upload_all():
        with app.app_context():
            admin = User.query.filter_by(username='kanaw').first() or current_user
            for i, url in enumerate(pexels_urls):
                try:
                    res = cloudinary.uploader.upload(url, resource_type="video", folder="pexels")
                    cloud_url = res['secure_url']
                    if '/video/upload/' in cloud_url:
                        cloud_url = cloud_url.replace('/video/upload/', '/video/upload/q_auto,f_auto/')
                    v = Video(filename=cloud_url, caption=f"تصميم سينمائي {i+1} 🎬", user_id=admin.id, views=random.randint(1000,50000), likes_count=random.randint(100,5000))
                    db.session.add(v)
                    db.session.commit()
                except Exception as e:
                    print(f"فشل {i+1}: {e}")
    
    thread = threading.Thread(target=upload_all)
    thread.start()
    
    return '''<!DOCTYPE html><html dir="rtl"><head><meta charset="UTF-8"><title>رفع Pexels</title><style>body{font-family:sans-serif;background:#111;color:#fff;padding:20px;max-width:600px;margin:0 auto;text-align:center;line-height:1.8}a{color:#fe2c55;font-size:18px;text-decoration:none}</style></head><body><h1>🎬 بدء رفع 50 فيديو تصميم</h1><p style="color:#28a745;background:#1a3a1a;padding:20px;border-radius:8px;">✅ بدأ الرفع في الخلفية! سيستغرق 3-5 دقائق.</p><p style="color:#888;">انتظر ثم افتح الرئيسية لمشاهدتها.</p><a href="/">← الرئيسية</a></body></html>'''


import os
import random
from app import app, db, User, Video, Comment

# ==========================================
# 🎛️ يمكنك تغيير هذه الأرقام لزيادة الكمية
NUM_USERS = 500         # عدد الحسابات
VIDEOS_PER_USER = 3     # عدد الفيديوهات لكل حساب
# ==========================================

# توليد أسماء مستخدمين عشوائية
first_names = ["ahmed", "sara", "mohammed", "lina", "omar", "nour", "khaled", "yara", "tariq", "huda", "adam", "maya", "ali", "fatima", "hassan", "zainab", "yousef", "layla", "majed", "dina", "sami", "reem", "anas", "salma", "zaid", "rana", "faris", "noor", "kareem", "aya"]
suffixes = ["gamer", "art", "vlogs", "music", "funny", "cooking", "sports", "tech", "travel", "lifestyle", "fitness", "beauty", "food", "comedy", "news", "photo", "diy", "gaming", "movies", "books", "cars", "fashion", "dance", "sing", "code", "life", "world", "star", "king", "queen"]

# فيديوهات حقيقية من جوجل (لا تستهلك مساحة Cloudinary)
sample_videos = [
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"
]

# منشورات
captions = [
    "شوفوا هذا الفيديو الرهيب! 🔥", "أفضل لحظة في حياتي ❤️", "لا تفوتوا هذا المشهد 😂",
    "تجربة جديدة وممتعة ✨", "استمتعوا بالمشاهدة 🎬", "ما رأيكم بهذا؟ 👀",
    "محتوى حصري لكم 💎", "شاركوني رأيكم بالتعليقات 👇", "كل يوم فيديو جديد 🚀",
    "أتمنى يعجبكم ❤️", "لا تنسوا المتابعة ✨", "جودة عالية 4K 🎥", "من تصويري الخاص 📸",
    "تحياتي لكم من فلسطين 🇵🇸", "اللهم صل على محمد ﷺ", "Happy Day ✌️", "تحدي جديد 🔥"
]

# تعليقات
comments_pool = [
    "فيديو رائع جداً! 🔥", "استمر يا بطل 👏", "أفضل محتوى شفته اليوم ❤️",
    "متابعك من فلسطين 🇵🇸", "ههههههه مضحك كثير 😂", "ما شاء الله، إبداع!",
    "كيف سويت هذا؟", "أول مرة أشوف زي هيك", "جودة عالية جداً",
    "أتمنى لك التوفيق", "أنت الأفضل!", "أضفتك للمفضلة ⭐",
    "منتظر جديدك", "شكراً على المحتوى", "الله يعطيك العافية",
    "تبارك الرحمن", "شو هذا الجمال!", "بطل والله", "عاش يا وحش 💪"
]

def generate_username(existing):
    while True:
        name = f"{random.choice(first_names)}_{random.choice(suffixes)}{random.randint(10, 9999)}"
        if name not in existing:
            return name

print("⏳ جاري إنشاء البيانات... يرجى الانتظار (قد يستغرق دقيقة).")

with app.app_context():
    # 1. جلب الأسماء الموجودة
    existing_users = {u.username for u in User.query.with_entities(User.username).all()}
    
    # 2. إنشاء الحسابات
    users_to_add = []
    for i in range(NUM_USERS):
        name = generate_username(existing_users)
        existing_users.add(name)
        user = User(
            username=name,
            bio=f"مرحباً، أنا {name}! أشارككم يومياتي ومحتواي هنا ✨",
            profile_pic=f"https://i.pravatar.cc/150?u={random.randint(1,1000)}",
            is_verified=random.choice([True, False, False, False])
        )
        user.set_password("123456")
        users_to_add.append(user)
    
    db.session.add_all(users_to_add)
    db.session.commit()
    print(f"✅ تم إنشاء {len(users_to_add)} حساب!")
    
    # 3. جلب كل الحسابات
    all_users = User.query.all()
    
    # 4. إنشاء الفيديوهات
    videos_to_add = []
    for user in all_users:
        for _ in range(VIDEOS_PER_USER):
            v = Video(
                filename=random.choice(sample_videos),
                caption=random.choice(captions),
                user_id=user.id,
                views=random.randint(100, 50000),
                likes_count=random.randint(10, 5000)
            )
            videos_to_add.append(v)
    
    db.session.add_all(videos_to_add)
    db.session.commit()
    print(f"✅ تم إنشاء {len(videos_to_add)} فيديو!")
    
    # 5. إنشاء التعليقات
    all_videos = Video.query.all()
    comments_to_add = []
    for video in all_videos:
        for _ in range(random.randint(1, 3)):
            commenter = random.choice(all_users)
            if commenter.id != video.user_id:
                c = Comment(
                    content=random.choice(comments_pool),
                    user_id=commenter.id,
                    video_id=video.id,
                    likes_count=random.randint(0, 100)
                )
                comments_to_add.append(c)
    
    db.session.add_all(comments_to_add)
    db.session.commit()
    print(f"✅ تم إنشاء {len(comments_to_add)} تعليق!")
    
    print("\n🎉 اكتمل كل شيء بنجاح! الموقع الآن مليء بالبيانات.")
    print("🔑 كلمة المرور لجميع الحسابات التجريبية هي: 123456")

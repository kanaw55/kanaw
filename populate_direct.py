import psycopg2
import random
from datetime import datetime, timedelta

# 🛑 ضع رابط قاعدة البيانات الخاص بك هنا
DATABASE_URL = "postgresql://neondb_owner:npg_V9Fkf8QbUYjq@ep-polished-cell-b544ydqc-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# إعدادات الكمية
NUM_USERS = 1000
VIDEOS_PER_USER = 3

first_names = ["ahmed", "sara", "mohammed", "lina", "omar", "nour", "khaled", "yara", "tariq", "huda", "adam", "maya", "ali", "fatima", "hassan", "zainab", "yousef", "layla", "majed", "dina", "sami", "reem", "anas", "salma", "zaid", "rana", "faris", "noor", "kareem", "aya"]
suffixes = ["gamer", "art", "vlogs", "music", "funny", "cooking", "sports", "tech", "travel", "lifestyle", "fitness", "beauty", "food", "comedy", "news", "photo", "diy", "gaming", "movies", "books", "cars", "fashion", "dance", "sing", "code", "life", "world", "star", "king", "queen"]

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

captions = [
    "شوفوا هذا الفيديو الرهيب! 🔥", "أفضل لحظة في حياتي ❤️", "لا تفوتوا هذا المشهد 😂",
    "تجربة جديدة وممتعة ✨", "استمتعوا بالمشاهدة 🎬", "ما رأيكم بهذا؟ 👀",
    "محتوى حصري لكم 💎", "شاركوني رأيكم بالتعليقات 👇", "كل يوم فيديو جديد 🚀",
    "أتمنى يعجبكم ❤️", "لا تنسوا المتابعة ✨", "جودة عالية 4K 🎥", "من تصويري الخاص 📸",
    "تحياتي لكم من فلسطين 🇵🇸", "Happy Day ✌️", "تحدي جديد 🔥"
]

comments_pool = [
    "فيديو رائع جداً! 🔥", "استمر يا بطل 👏", "أفضل محتوى شفته اليوم ❤️",
    "متابعك من فلسطين 🇵🇸", "ههههههه مضحك كثير 😂", "ما شاء الله، إبداع!",
    "كيف سويت هذا؟", "أول مرة أشوف زي هيك", "جودة عالية جداً",
    "أتمنى لك التوفيق", "أنت الأفضل!", "أضفتك للمفضلة ⭐",
    "منتظر جديدك", "شكراً على المحتوى", "الله يعطيك العافية"
]

print("⏳ جاري الاتصال بقاعدة البيانات...")
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("✅ تم الاتصال بنجاح!")
except Exception as e:
    print(f"❌ فشل الاتصال: {e}")
    exit()

# إنشاء 1000 حساب
print("⏳ جاري إنشاء 1000 حساب...")
for i in range(NUM_USERS):
    name = f"{random.choice(first_names)}_{random.choice(suffixes)}{random.randint(100, 99999)}"
    password = "scrypt:32768:8:1$dummyhash$dummyhash" # كلمة مرور وهمية
    bio = f"مرحباً، أنا {name}! أشارككم محتواي هنا ✨"
    pic = f"https://i.pravatar.cc/150?u={random.randint(1, 1000)}"
    is_ver = random.choice([True, False, False, False])
    
    cursor.execute("""
        INSERT INTO "user" (username, password_hash, bio, profile_pic, is_verified)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING
    """, (name, password, bio, pic, is_ver))

conn.commit()
print("✅ تم إنشاء الحسابات!")

# جلب الـ IDs الخاصة بالحسابات
cursor.execute('SELECT id FROM "user"')
user_ids = [row[0] for row in cursor.fetchall()]

# إنشاء الفيديوهات
print("⏳ جاري إنشاء 3000 فيديو...")
for uid in user_ids:
    for _ in range(VIDEOS_PER_USER):
        vid_url = random.choice(sample_videos)
        cap = random.choice(captions)
        views = random.randint(100, 50000)
        likes = random.randint(10, 5000)
        
        cursor.execute("""
            INSERT INTO video (filename, caption, views, likes, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (vid_url, cap, views, likes, uid))

conn.commit()
print("✅ تم إنشاء الفيديوهات!")

# جلب الـ IDs الخاصة بالفيديوهات
cursor.execute("SELECT id, user_id FROM video")
videos = cursor.fetchall()

# إنشاء التعليقات
print("⏳ جاري إنشاء التعليقات...")
for vid_id, owner_id in videos:
    for _ in range(random.randint(1, 3)):
        commenter_id = random.choice(user_ids)
        if commenter_id != owner_id:
            content = random.choice(comments_pool)
            likes = random.randint(0, 100)
            cursor.execute("""
                INSERT INTO comment (content, user_id, video_id, likes_count)
                VALUES (%s, %s, %s, %s)
            """, (content, commenter_id, vid_id, likes))

conn.commit()
cursor.close()
conn.close()

print("\n🎉 تمت العملية بنجاح! 1000 حساب و 3000 فيديو جاهزون الآن على الموقع.")
print("🔑 كلمة المرور لجميع الحسابات التجريبية: 123456")

import os
import json
import pandas as pd
import requests
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# ----------------------------
# تهيئة التطبيق واللوجينج
# ----------------------------
app = Flask(__name__)

# إعداد logging لعرض الوقت والمستوى والرسالة
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ----------------------------
# ثوابت وملفات الحالة
# ----------------------------
EXCEL_FILE = "coupons.xlsx"    # ملف الإكسل مع قائمة الكوبونات
STATE_FILE = "state.json"      # ملف JSON لحفظ آخر فهرس منشور

# المتغيران يُحمَلان من environment variables على السيرفر
PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

# ----------------------------
# دوال مساعدة
# ----------------------------

def load_coupons():
    """
    تحميل الإكسل وتحويله إلى قائمة قواميس
    """
    logging.info("🔄 Loading coupons from Excel")
    try:
        df = pd.read_excel(EXCEL_FILE)
        coupons = df.to_dict(orient="records")
        logging.info(f"✅ Loaded {len(coupons)} coupons")
        return coupons
    except Exception as e:
        logging.error(f"❌ Failed to load Excel file: {e}")
        return []

def get_next_index(total):
    """
    استرجاع الفهرس التالي من ملف الحالة، والالتفاف عند نهاية القائمة
    """
    if not os.path.exists(STATE_FILE):
        logging.info("ℹ️ State file not found, starting at index 0")
        return 0
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        last = state.get("last_index", -1)
        next_idx = (last + 1) % total
        logging.info(f"ℹ️ Next index calculated: {next_idx} (last was {last})")
        return next_idx
    except Exception as e:
        logging.error(f"❌ Error reading state file: {e}")
        return 0

def update_state(index):
    """
    تحديث ملف الحالة بالفهرس المطروح
    """
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_index": index}, f)
        logging.info(f"✅ State updated to index {index}")
    except Exception as e:
        logging.error(f"❌ Failed to update state file: {e}")

# ----------------------------
# دالة النشر الرئيسية
# ----------------------------
def post_coupon():
    logging.info("🚀 Starting post_coupon job")
    coupons = load_coupons()
    if not coupons:
        logging.warning("⚠️ No coupons to post")
        return

    idx = get_next_index(len(coupons))
    coupon = coupons[idx]
    logging.info(f"ℹ️ Posting coupon at index {idx}: {coupon.get('title')}")

    # تحضير الرسالة
    message = (
        f"🎉 {coupon['title']}\n\n"
        f"🔥 {coupon['description']}\n\n"
        f"✅ الكوبون : {coupon['code']}\n\n"
        f"🌍 صالح لـ : {coupon['countries']}\n\n"
        f"📌 ملاحظة : {coupon['note']}\n\n"
        f"🛒 رابط الشراء : {coupon['link']}\n\n"
        "💎 لمزيد من الكوبونات والخصومات:\n"
        "https://www.discountcoupon.online"
    )

    # نشر الصورة والنص عبر Facebook Graph API
    url = f"https://graph.facebook.com/{PAGE_ID}/photos"
    payload = {
        "url": coupon['image'],
        "caption": message,
        "access_token": PAGE_ACCESS_TOKEN
    }

    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.ok:
            logging.info(f"✅ Successfully posted coupon #{idx + 1}")
            update_state(idx)
        else:
            logging.error(f"❌ Facebook API error [{resp.status_code}]: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Exception during HTTP request: {e}")

# ----------------------------
# جدولة المهمة
# ----------------------------
scheduler = BackgroundScheduler()
# هنا ننشر كل دقيقة، وتنفذ أول مرة فور الإقلاع
scheduler.add_job(
    post_coupon,
    trigger='interval',
    minutes=1,
    next_run_time=datetime.now()
)
scheduler.start()
logging.info("✅ Scheduler started: posting every 1 minute")

# ----------------------------
# نقطة تحقق حالة السيرفر (لـ UptimeRobot)
# ----------------------------
@app.route("/")
def health_check():
    return "Server is alive", 200

# ----------------------------
# تشغيل التطبيق
# ----------------------------
if __name__ == "__main__":
    # قراءة منفذ Render من متغير PORT أو 10000 كافتراضي
    port = int(os.environ.get("PORT", 10000))
    logging.info(f"🔌 Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)

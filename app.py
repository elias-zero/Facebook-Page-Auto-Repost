import os
import json
import pandas as pd
import requests
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

EXCEL_FILE = "coupons.xlsx"
STATE_FILE = "state.json"

PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

def load_coupons():
    df = pd.read_excel(EXCEL_FILE)
    coupons = df.to_dict(orient="records")
    return coupons

def get_next_index(total):
    if not os.path.exists(STATE_FILE):
        return 0
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    index = state.get("last_index", 0)
    return (index + 1) % total

def update_state(index):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_index": index}, f)

def post_coupon():
    try:
        coupons = load_coupons()
        if not coupons:
            print("❌ لا يوجد كوبونات في الملف")
            return

        index = get_next_index(len(coupons))
        coupon = coupons[index]

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

        image_url = coupon['image']
        url = f"https://graph.facebook.com/{PAGE_ID}/photos"
        payload = {
            "url": image_url,
            "caption": message,
            "access_token": PAGE_ACCESS_TOKEN
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ تم نشر الكوبون رقم {index + 1}")
            update_state(index)
        else:
            print(f"❌ خطأ في النشر: {response.text}")
    except Exception as e:
        print(f"❌ خطأ في المعالجة: {e}")

# جدولة النشر كل ساعة
scheduler = BackgroundScheduler()
scheduler.add_job(post_coupon, 'interval', hours=1)
scheduler.start()

# health check ل UptimeRobot
@app.route("/")
def health_check():
    return "Server is alive", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

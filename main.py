import httpx

# ضغ الـ sessionid الخاص بك هنا (تأكد من نسخه بدقة بدون مسافات)
SESSION_ID = "73733783hshssjshshshsggsvs"
TEST_USERNAME = "instagram" # يوزر لنجرب عليه

def check_instagram_session():
    print("⏳ جاري الاتصال بسيرفرات انستقرام...")
    
    client = httpx.Client(
        http2=True,
        cookies={
            "sessionid": SESSION_ID
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "x-ig-app-id": "936619743392459",
            "accept": "application/json"
        }
    )
    
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={TEST_USERNAME}"
    
    try:
        response = client.get(url)
        print("="*40)
        print(f"📌 كود الحالة (Status Code): {response.status_code}")
        
        if response.status_code == 200:
            print("✅ النتيجة: الاتصال ناجح والـ Session ID يعمل بشكل ممتاز!")
            print("="*40)
        else:
            print("❌ النتيجة: الاتصال فشل!")
            print(f"⚠️ رسالة انستقرام الخفية: {response.text}")
            print("="*40)
            
            if "challenge_required" in response.text:
                print("💡 السبب: انستقرام يطلب منك إثبات هويتك (افتح حسابك من التطبيق وأكد أنك صاحب الدخول).")
            elif "fail" in response.text or response.status_code == 401:
                print("💡 السبب: الـ Session ID منتهي الصلاحية أو غير صحيح نهائياً. يجب استخراج واحد جديد.")
                
    except Exception as e:
        print(f"❌ حدث خطأ داخلي: {e}")

if __name__ == "__main__":
    check_instagram_session()

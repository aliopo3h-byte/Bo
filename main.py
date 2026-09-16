import httpx
import telebot

# 1. ضع توكن البوت الخاص بك من BotFather هنا
BOT_TOKEN = "8826605376:AAEqVw-OxHVxZZ8kBiqsU86KkerBCaFAUo0"
bot = telebot.TeleBot(BOT_TOKEN)

# 2. ضع sessionid الخاص بحسابك الوهمي/الأساسي هنا
SESSION_ID = "73733783hshssjshshshsggsvs"

class InstagramUserInfo:
    def __init__(self, sessionid):
        self.client = httpx.Client(
            http2=True,
            cookies={
                "sessionid": sessionid
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "x-ig-app-id": "936619743392459",
                "accept": "application/json"
            }
        )

    def get_user_info(self, username):
        url = (
            f"https://www.instagram.com/api/v1/"
            f"users/web_profile_info/?username={username}"
        )
        try:
            response = self.client.get(url)
            if response.status_code != 200:
                return f"❌ فشل الطلب: {response.status_code}\nتأكد من صلاحية الـ sessionid أو أن الحساب موجود."
            
            data = response.json()
            if "data" not in data or data["data"]["user"] is None:
                return "❌ الحساب غير موجود أو تم تقييد الطلب."

            user = data["data"]["user"]
            
            # ترتيب البيانات في رسالة نصية ليتم إرسالها في تليجرام
            info = (
                f"👤 **معلومات حساب انستقرام**\n"
                f"━━━━━━━━━━━━\n"
                f"🆔 **الآيدي:** `{user.get('id')}`\n"
                f"👤 **اليوزر:** `@{user.get('username')}`\n"
                f"📝 **الاسم:** {user.get('full_name')}\n"
                f"📖 **البايو:** {user.get('biography')}\n"
                f"👥 **المتابِعين:** {user.get('edge_followed_by', {}).get('count', 0)}\n"
                f"🗣 **المتابَعين:** {user.get('edge_follow', {}).get('count', 0)}\n"
                f"🔒 **حساب خاص:** {'نعم' if user.get('is_private') else 'لا'}\n"
                f"✅ **موثق:** {'نعم' if user.get('is_verified') else 'لا'}\n"
                f"━━━━━━━━━━━━"
            )
            return info
            
        except Exception as e:
            return f"❌ حدث خطأ أثناء جلب البيانات: {e}"

# تهيئة كلاس الانستقرام
ig_fetcher = InstagramUserInfo(SESSION_ID)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في بوت جلب معلومات انستقرام! 👋\n\n"
        "فقط أرسل يوزر أي حساب (بدون علامة @) وسأقوم بجلب بياناته."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def fetch_and_send_info(message):
    # تنظيف اليوزر من أي مسافات أو علامة @
    username = message.text.strip().replace("@", "")
    
    # إرسال رسالة انتظار للمستخدم
    msg = bot.reply_to(message, "⏳ جاري جلب المعلومات، يرجى الانتظار...")
    
    # جلب المعلومات من الكلاس
    result_text = ig_fetcher.get_user_info(username)
    
    # تعديل رسالة الانتظار وإرسال النتيجة النهائية
    bot.edit_message_text(
        chat_id=message.chat.id, 
        message_id=msg.message_id, 
        text=result_text, 
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    print("✅ البوت يعمل الآن...")
    bot.infinity_polling()

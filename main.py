import httpx
import telebot

# 1. ضع توكن البوت الخاص بك من BotFather هنا
BOT_TOKEN = "8826605376:AAEqVw-OxHVxZZ8kBiqsU86KkerBCaFAUo0"
bot = telebot.TeleBot(BOT_TOKEN)

# 2. ضع sessionid الخاص بحسابك الوهمي/الأساسي هنا
SESSION_ID = "21842597641%3AnhPoO2lBBjOvui%3A24%3AAYnu4gBEKH-kv1SEnEWlkDTGPoR6s2Wv2t2ujktxoA"

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
                return f"❌ فشل الطلب: {response.status_code}\nتأكد من صلاحية الـ sessionid أو أن الحساب موجود.", None
            
            data = response.json()
            if "data" not in data or data["data"]["user"] is None:
                return "❌ الحساب غير موجود أو تم تقييد الطلب.", None

            user = data["data"]["user"]
            
            # جلب رابط الصورة الشخصية (عالية الدقة إن وجدت، وإلا العادية)
            pic_url = user.get("profile_pic_url_hd") or user.get("profile_pic_url")
            
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
            return info, pic_url
            
        except Exception as e:
            return f"❌ حدث خطأ أثناء جلب البيانات: {e}", None

# تهيئة كلاس الانستقرام
ig_fetcher = InstagramUserInfo(SESSION_ID)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في بوت جلب معلومات انستقرام! 👋\n\n"
        "فقط أرسل يوزر أي حساب (بدون علامة @) وسأقوم بجلب بياناته مع صورته الشخصية."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def fetch_and_send_info(message):
    # تنظيف اليوزر من أي مسافات أو علامة @
    username = message.text.strip().replace("@", "")
    
    # إرسال رسالة انتظار للمستخدم
    msg = bot.reply_to(message, "⏳ جاري جلب المعلومات والصورة، يرجى الانتظار...")
    
    # جلب المعلومات من الكلاس (النص + رابط الصورة)
    result_text, pic_url = ig_fetcher.get_user_info(username)
    
    # حذف رسالة الانتظار
    try:
        bot.delete_message(chat_id=message.chat.id, message_id=msg.message_id)
    except:
        pass # تجاهل الخطأ لو لم يتمكن من حذف الرسالة لسبب ما
    
    # إرسال النتيجة (صورة + نص، أو نص فقط لو فشل جلب الصورة)
    if pic_url:
        try:
            bot.send_photo(
                chat_id=message.chat.id, 
                photo=pic_url, 
                caption=result_text, 
                parse_mode="Markdown"
            )
        except Exception as e:
            # في حال فشل إرسال الصورة (مثلاً الرابط غير صالح)، نرسل النص فقط كملاذ أخير
            bot.send_message(
                chat_id=message.chat.id, 
                text=result_text + "\n\n*(ملاحظة: تعذر إرسال الصورة الشخصية)*", 
                parse_mode="Markdown"
            )
    else:
        # إذا لم يتم العثور على صورة أو حدث خطأ
        bot.send_message(
            chat_id=message.chat.id, 
            text=result_text, 
            parse_mode="Markdown"
        )

if __name__ == "__main__":
    print("✅ البوت يعمل الآن...")
    bot.infinity_polling()

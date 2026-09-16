#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════╗
║   Instagram Profile Lookup  •  Telegram Bot                       ║
║   نسخة بدون sessionid — لا حساب، لا كوكيز، لا خطر حظر.            ║
║                                                                   ║
║   aiogram 3.x  +  httpx (async / HTTP-2)                          ║
╚═══════════════════════════════════════════════════════════════════╝

التشغيل:
    pip install "aiogram>=3.7" "httpx[http2,brotli]"
    export BOT_TOKEN="123456:ABC..."
    python instagram_bot_public.py
"""

import asyncio
import html
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ════════════════════════════════════════════════════════════════════
#   الإعدادات
# ════════════════════════════════════════════════════════════════════

def _load_dotenv(path: str = ".env") -> None:
    """
    يقرأ ملف .env المحلي إن وُجد.
    على Railway لا يوجد هذا الملف — القيم تأتي من تبويب Variables.
    """
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()

BOT_TOKEN = os.getenv("8826605376:AAEqVw-OxHVxZZ8kBiqsU86KkerBCaFAUo0", "")

CACHE_TTL = 1800          # كاش نصف ساعة — بلا جلسة الحدّ ضيّق، فالكاش أهم
NEGATIVE_TTL = 300        # كاش لنتائج "غير موجود" حتى لا تُعاد المحاولة
USER_COOLDOWN = 5.0       # تبريد لكل مستخدم
GLOBAL_GAP = 2.0          # فاصل إجباري بين أي طلبين نحو إنستغرام
REQUEST_TIMEOUT = 15.0

IG_APP_ID = "936619743392459"

# مضيفان لنفس المسار — إن فشل الأول نجرّب الثاني
ENDPOINTS: List[str] = [
    "https://i.instagram.com/api/v1/users/web_profile_info/",
    "https://www.instagram.com/api/v1/users/web_profile_info/",
]

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ig-bot")


# ════════════════════════════════════════════════════════════════════
#   الأخطاء
# ════════════════════════════════════════════════════════════════════

class IGError(Exception):
    user_message = "⚠️ حدث خطأ غير متوقع. جرّب مرة ثانية بعد قليل."


class ProfileNotFound(IGError):
    user_message = (
        "🔍 لا يوجد حساب عام بهذا الاسم.\n"
        "<i>الحسابات الخاصة غالباً لا تظهر بدون تسجيل دخول.</i>"
    )


class RateLimited(IGError):
    user_message = (
        "⏳ إنستغرام يحدّ الطلبات الآن.\n"
        "<i>انتظر دقيقة أو دقيقتين وأعد المحاولة.</i>"
    )


class Blocked(IGError):
    user_message = (
        "🚧 إنستغرام رفض الطلب من هذا الخادم.\n"
        "<i>عناوين السيرفرات تُحجب عادةً — جرّب تشغيل البوت من جهاز منزلي.</i>"
    )


# ════════════════════════════════════════════════════════════════════
#   نموذج البيانات
# ════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class Profile:
    user_id: str = ""
    username: str = ""
    full_name: str = ""
    biography: str = ""
    followers: int = 0
    following: int = 0
    posts: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    is_professional: bool = False
    category: str = ""
    external_url: str = ""
    avatar_url: str = ""

    @classmethod
    def from_api(cls, u: dict) -> "Profile":
        return cls(
            user_id=str(u.get("id") or ""),
            username=u.get("username") or "",
            full_name=u.get("full_name") or "",
            biography=u.get("biography") or "",
            followers=(u.get("edge_followed_by") or {}).get("count", 0),
            following=(u.get("edge_follow") or {}).get("count", 0),
            posts=(u.get("edge_owner_to_timeline_media") or {}).get("count", 0),
            is_private=bool(u.get("is_private")),
            is_verified=bool(u.get("is_verified")),
            is_business=bool(u.get("is_business_account")),
            is_professional=bool(u.get("is_professional_account")),
            category=u.get("category_name") or u.get("business_category_name") or "",
            external_url=u.get("external_url") or "",
            avatar_url=u.get("profile_pic_url_hd") or u.get("profile_pic_url") or "",
        )


# ════════════════════════════════════════════════════════════════════
#   العميل — بلا مصادقة
# ════════════════════════════════════════════════════════════════════

class InstagramPublicClient:
    """
    يستدعي نفس النقطة التي يستدعيها متصفّح الزائر غير المسجّل.
    لا كوكيز ولا حساب — لذلك:
      • الحسابات الخاصة قد تُرجع 404 بدل بياناتها.
      • الحدّ (429) يُضرب أسرع، فالكاش والتبريد ضروريان.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            http2=True,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
            headers={
                "x-ig-app-id": IG_APP_ID,
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "accept-encoding": "gzip, deflate, br",
                "referer": "https://www.instagram.com/",
                "sec-fetch-site": "same-origin",
            },
        )
        self._cache: Dict[str, Tuple[float, Optional[Profile]]] = {}
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    # ── الكاش ───────────────────────────────────────────────────────
    def _cached(self, key: str):
        hit = self._cache.get(key)
        if not hit:
            return False, None
        ts, profile = hit
        ttl = CACHE_TTL if profile else NEGATIVE_TTL
        if time.monotonic() - ts > ttl:
            self._cache.pop(key, None)
            return False, None
        return True, profile

    async def _pace(self) -> None:
        """يفرض فاصلاً زمنياً بين الطلبات الخارجية."""
        gap = GLOBAL_GAP - (time.monotonic() - self._last_call)
        if gap > 0:
            await asyncio.sleep(gap)
        self._last_call = time.monotonic()

    # ── الجلب ───────────────────────────────────────────────────────
    async def fetch(self, username: str, *, force: bool = False) -> Profile:
        key = username.lower()

        if not force:
            found, cached = self._cached(key)
            if found:
                log.info("cache hit → @%s", key)
                if cached is None:
                    raise ProfileNotFound
                return cached

        async with self._lock:
            last_error: IGError = IGError()

            for url in ENDPOINTS:
                await self._pace()
                try:
                    resp = await self._client.get(
                        url,
                        params={"username": key},
                        headers={"user-agent": random.choice(USER_AGENTS)},
                    )
                except httpx.TimeoutException:
                    last_error = IGError("timeout")
                    continue
                except httpx.HTTPError as exc:
                    last_error = IGError(str(exc))
                    continue

                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                    except ValueError:
                        last_error = Blocked()
                        continue

                    user = (payload.get("data") or {}).get("user")
                    if not user:
                        self._cache[key] = (time.monotonic(), None)
                        raise ProfileNotFound

                    profile = Profile.from_api(user)
                    self._cache[key] = (time.monotonic(), profile)
                    log.info("fetched → @%s", profile.username)
                    return profile

                if resp.status_code == 404:
                    self._cache[key] = (time.monotonic(), None)
                    raise ProfileNotFound
                if resp.status_code == 429:
                    last_error = RateLimited()
                    continue
                if resp.status_code in (301, 302, 401, 403):
                    last_error = Blocked()
                    continue

                last_error = IGError(f"HTTP {resp.status_code}")

            raise last_error

    async def download_avatar(self, url: str) -> Optional[bytes]:
        if not url:
            return None
        try:
            r = await self._client.get(
                url,
                timeout=10.0,
                headers={"user-agent": random.choice(USER_AGENTS)},
            )
            return r.content if r.status_code == 200 else None
        except httpx.HTTPError:
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


# ════════════════════════════════════════════════════════════════════
#   أدوات التنسيق
# ════════════════════════════════════════════════════════════════════

def fmt_number(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def ratio_bar(followers: int, following: int, width: int = 14) -> str:
    total = followers + following
    if total == 0:
        return "░" * width
    filled = max(0, min(width, round(width * followers / total)))
    return "█" * filled + "░" * (width - filled)


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def shorten(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def badges(p: Profile) -> str:
    out = []
    if p.is_verified:
        out.append("☑️ موثّق")
    out.append("🔒 خاص" if p.is_private else "🌐 عام")
    if p.is_business:
        out.append("💼 أعمال")
    elif p.is_professional:
        out.append("🎨 احترافي")
    return "  •  ".join(out)


def render_card(p: Profile) -> str:
    bio = shorten(p.biography)
    bio_block = f"<blockquote>{esc(bio)}</blockquote>" if bio else "<i>— لا يوجد وصف —</i>"

    lines = [
        f"<b>{esc(p.full_name) or esc(p.username)}</b>",
        f"<code>@{esc(p.username)}</code>",
        "",
        badges(p),
        "",
        "<code>━━━━━━━━━━━━━━━━━━━━━━</code>",
        f"👥  <b>المتابِعون</b>   <code>{fmt_number(p.followers):>10}</code>",
        f"➡️  <b>يتابِع</b>      <code>{fmt_number(p.following):>10}</code>",
        f"🖼  <b>المنشورات</b>   <code>{fmt_number(p.posts):>10}</code>",
        "<code>━━━━━━━━━━━━━━━━━━━━━━</code>",
        f"<code>{ratio_bar(p.followers, p.following)}</code>",
        "",
        bio_block,
    ]

    if p.category:
        lines.append(f"\n🏷 <b>التصنيف:</b> {esc(p.category)}")
    if p.external_url:
        lines.append(f"🔗 <b>الرابط:</b> {esc(p.external_url)}")

    lines.append(f"\n🆔 <code>{esc(p.user_id)}</code>")
    return "\n".join(lines)


def build_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 فتح الحساب",
                    url=f"https://instagram.com/{username}",
                ),
                InlineKeyboardButton(text="🔄 تحديث", callback_data=f"rf:{username}"[:64]),
            ],
            [InlineKeyboardButton(text="🔎 بحث جديد", callback_data="new")],
        ]
    )


# ════════════════════════════════════════════════════════════════════
#   منع السبام
# ════════════════════════════════════════════════════════════════════

@dataclass
class Throttle:
    last_seen: Dict[int, float] = field(default_factory=dict)

    def allow(self, user_id: int) -> Tuple[bool, float]:
        now = time.monotonic()
        wait = USER_COOLDOWN - (now - self.last_seen.get(user_id, 0.0))
        if wait > 0:
            return False, wait
        self.last_seen[user_id] = now
        return True, 0.0


throttle = Throttle()
router = Router()
ig: InstagramPublicClient


# ════════════════════════════════════════════════════════════════════
#   المعالجات
# ════════════════════════════════════════════════════════════════════

WELCOME = (
    "<b>📸  Instagram Profile Lookup</b>\n"
    "<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    "أرسل لي <b>اسم مستخدم</b> إنستغرام وسأعرض لك بطاقة الحساب.\n\n"
    "<b>أمثلة:</b>\n"
    "<code>instagram</code>\n"
    "<code>@nasa</code>\n"
    "<code>instagram.com/natgeo</code>\n\n"
    "<i>بيانات عامة فقط — نفس ما يراه زائر غير مسجّل.</i>"
)

HELP = (
    "<b>🧭 الأوامر</b>\n"
    "<code>━━━━━━━━━━━━━━━━</code>\n"
    "/start — البداية\n"
    "/help — هذه الرسالة\n\n"
    "أو أرسل اسم المستخدم مباشرة.\n\n"
    "<b>ما الذي يُعرض؟</b>\n"
    "الاسم • المعرّف • الوصف • المتابعون • المنشورات • "
    "التوثيق والخصوصية • التصنيف • الرابط\n\n"
    "<b>ملاحظة:</b> <i>بدون تسجيل دخول، الحسابات الخاصة قد لا تظهر إطلاقاً، "
    "والنتائج تُخزَّن مؤقتاً نصف ساعة.</i>"
)


def extract_username(raw: str) -> Optional[str]:
    text = (raw or "").strip()
    text = re.sub(r"^https?://", "", text, flags=re.I)
    text = re.sub(r"^(www\.)?instagram\.com/", "", text, flags=re.I)
    text = text.split("?")[0].split("/")[0].lstrip("@").strip()
    return text if USERNAME_RE.match(text) else None


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(WELCOME)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(HELP)


async def send_profile(message: Message, username: str, *, force: bool = False) -> None:
    status = await message.answer("🔄 <i>جارٍ الجلب…</i>")

    try:
        profile = await ig.fetch(username, force=force)
    except IGError as exc:
        log.warning("lookup failed @%s → %r", username, exc)
        await status.edit_text(getattr(exc, "user_message", IGError.user_message))
        return

    card = render_card(profile)
    kb = build_keyboard(profile.username)

    avatar = await ig.download_avatar(profile.avatar_url)
    if avatar:
        await status.delete()
        await message.answer_photo(
            BufferedInputFile(avatar, filename=f"{profile.username}.jpg"),
            caption=card,
            reply_markup=kb,
        )
    else:
        await status.edit_text(card, reply_markup=kb, disable_web_page_preview=True)


@router.message(F.text & ~F.text.startswith("/"))
async def on_username(message: Message) -> None:
    ok, wait = throttle.allow(message.from_user.id)
    if not ok:
        await message.answer(f"⏱ تمهّل قليلاً — <b>{wait:.1f}s</b>")
        return

    username = extract_username(message.text)
    if not username:
        await message.answer(
            "❌ اسم مستخدم غير صالح.\n"
            "<i>يُسمح بالأحرف والأرقام و</i> <code>.</code> <i>و</i> <code>_</code> "
            "<i>فقط (حتى 30 حرفاً).</i>"
        )
        return

    await send_profile(message, username)


@router.callback_query(F.data.startswith("rf:"))
async def on_refresh(cq: CallbackQuery) -> None:
    ok, wait = throttle.allow(cq.from_user.id)
    if not ok:
        await cq.answer(f"تمهّل {wait:.1f} ثانية")
        return
    await cq.answer("جارٍ التحديث…")
    await send_profile(cq.message, cq.data.split(":", 1)[1], force=True)


@router.callback_query(F.data == "new")
async def on_new(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.answer("✍️ أرسل اسم المستخدم التالي:")


# ════════════════════════════════════════════════════════════════════
#   الإقلاع
# ════════════════════════════════════════════════════════════════════

async def main() -> None:
    global ig

    if not BOT_TOKEN:
        raise SystemExit("❌ متغيّر البيئة BOT_TOKEN غير مضبوط.")

    ig = InstagramPublicClient()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    me = await bot.get_me()
    log.info("✅ البوت يعمل → @%s  (وضع بدون جلسة)", me.username)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await ig.aclose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("👋 إيقاف.")

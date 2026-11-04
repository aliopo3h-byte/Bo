"""قراءة ملف الإكسل وتصنيف كل صف حسب لونه (أخضر / أحمر / أزرق / أصفر)."""
import colorsys
import io
import os
import re

import openpyxl
from openpyxl.styles.colors import COLOR_INDEX

GREEN, RED, BLUE, YELLOW, NONE = "green", "red", "blue", "yellow", "none"

LABELS = {
    GREEN: "أخضر - تفعيل",
    RED: "أحمر - رفض",
    BLUE: "أزرق - لاحقاً",
    YELLOW: "أصفر - لم يرد",
    NONE: "بدون لون",
}

# ألوان ثيم أوفيس 2013+ الافتراضية (تُستعمل فقط إذا لم نجد ثيم داخل الملف)
DEFAULT_THEME = [
    "FFFFFF", "000000", "E7E6E6", "44546A", "4472C4",
    "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47",
]
_THEME_TAGS = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6"]


class ExcelError(Exception):
    """خطأ مفهوم يُعرض للمستخدم كما هو."""


def parse_theme(theme_xml):
    """يقرأ ألوان الثيم الحقيقية من الملف (ترتيب إكسل: lt1, dk1, lt2, dk2, accent1..6)."""
    if not theme_xml:
        return list(DEFAULT_THEME)
    try:
        text = theme_xml.decode("utf-8", "ignore") if isinstance(theme_xml, bytes) else str(theme_xml)
        out = []
        for tag in _THEME_TAGS:
            m = re.search(r"<a:%s>(.*?)</a:%s>" % (tag, tag), text, re.S)
            col = None
            if m:
                inner = m.group(1)
                mm = re.search(r'srgbClr val="([0-9A-Fa-f]{6})"', inner) or \
                    re.search(r'lastClr="([0-9A-Fa-f]{6})"', inner)
                if mm:
                    col = mm.group(1).upper()
            out.append(col)
        return [c or d for c, d in zip(out, DEFAULT_THEME)]
    except Exception:
        return list(DEFAULT_THEME)


def _apply_tint(rgb, tint):
    if not tint:
        return rgb
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    l = min(1.0, max(0.0, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def color_to_rgb(color, theme=None):
    """يحول لون openpyxl إلى نص RRGGBB أو None."""
    if color is None:
        return None
    theme = theme or DEFAULT_THEME
    try:
        if color.type == "rgb" and isinstance(color.rgb, str):
            return color.rgb[-6:].upper()
        if color.type == "indexed" and isinstance(color.indexed, int):
            if 0 <= color.indexed < len(COLOR_INDEX):
                return COLOR_INDEX[color.indexed][-6:].upper()
            return None
        if color.type == "theme" and isinstance(color.theme, int):
            if 0 <= color.theme < len(theme):
                return _apply_tint(theme[color.theme], color.tint or 0)
    except Exception:
        pass
    return None


def classify_rgb(rgb):
    if not rgb or not re.fullmatch(r"[0-9A-Fa-f]{6}", rgb):
        return NONE
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.07 or v < 0.2:  # أبيض / رمادي / أسود
        return NONE
    h *= 360
    if h < 20 or h >= 330:
        return RED
    if h < 70:
        return YELLOW  # يشمل البرتقالي
    if h < 170:
        return GREEN
    if h < 270:
        return BLUE
    return NONE


def cell_category(cell, theme=None):
    fill = cell.fill
    if fill is not None and fill.fill_type:
        cat = classify_rgb(color_to_rgb(fill.fgColor, theme))
        if cat == NONE and fill.fill_type != "solid":
            cat = classify_rgb(color_to_rgb(fill.bgColor, theme))
        if cat != NONE:
            return cat
    # إذا كان النص نفسه ملوّناً بدل الخلفية
    if cell.font is not None and cell.value not in (None, ""):
        return classify_rgb(color_to_rgb(cell.font.color, theme))
    return NONE


# ----------------------------------------------------------------------
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ة": "ه", "ؤ": "و"})
_AR_STRIP = re.compile("[ً-ٰٟـ]")  # التشكيل والتطويل


def normalize_ar(text):
    """توحيد الحروف العربية للبحث (أ/ا، ى/ي، ة/ه، حذف التشكيل)."""
    text = _AR_STRIP.sub("", str(text or "")).translate(_AR_MAP)
    return " ".join(text.lower().split())


def shorten_name(name, words=0):
    """أول `words` كلمات من الاسم (0 = الاسم كاملاً)."""
    parts = str(name).split()
    return " ".join(parts[:words]) if words and words > 0 else " ".join(parts)


def _norm(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def _find_col(headers, *keys):
    for i, h in enumerate(headers):
        for k in keys:
            if k in h:
                return i
    return None


def load_subscribers(path):
    """يرجع قائمة قواميس: name, sub, phone, notes, color, row, sheet."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        raise ExcelError("الملف بصيغة xls القديمة.\nافتحه في إكسل واحفظه بصيغة xlsx ثم حاول مجدداً.")
    if ext == ".csv":
        raise ExcelError("ملف CSV لا يحمل الألوان.\nاستعمل ملف إكسل xlsx.")
    try:
        with open(path, "rb") as f:  # القراءة من الذاكرة تعمل حتى لو الملف مفتوح في إكسل
            data = f.read()
        wb = openpyxl.load_workbook(io.BytesIO(data))
    except FileNotFoundError:
        raise ExcelError("الملف غير موجود:\n" + path)
    except PermissionError:
        raise ExcelError("لا توجد صلاحية لقراءة الملف:\n" + path)
    except Exception as e:
        raise ExcelError("تعذر فتح الملف، تأكد أنه ملف إكسل xlsx سليم.\n(%s)" % e)

    theme = parse_theme(getattr(wb, "loaded_theme", None))
    result = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows())
        if not rows:
            continue
        header_idx, headers = -1, []
        for idx, row in enumerate(rows[:10]):
            hs = [_norm(c.value) for c in row]
            if any("اسم المشترك" in h for h in hs):
                header_idx, headers = idx, hs
                break
        if headers:
            name_col = _find_col(headers, "اسم المشترك")
            sub_col = _find_col(headers, "اسم الاشتراك")
            phone_col = _find_col(headers, "الهاتف", "رقم")
            notes_col = _find_col(headers, "ملاحظ")
        else:  # بدون عناوين: العمود الأول هو الاسم
            name_col, sub_col, phone_col, notes_col = 0, None, None, None

        def val(row, col):
            if col is None or col >= len(row):
                return ""
            return _norm(row[col].value)

        for row in rows[header_idx + 1:]:
            if name_col >= len(row):
                continue
            name = val(row, name_col)
            if not name:
                continue
            color = cell_category(row[name_col], theme)
            if color == NONE:
                for c in row:
                    color = cell_category(c, theme)
                    if color != NONE:
                        break
            result.append({
                "name": name,
                "sub": val(row, sub_col),
                "phone": val(row, phone_col),
                "notes": val(row, notes_col),
                "color": color,
                "row": row[0].row,
                "sheet": ws.title,
            })
    if not result:
        raise ExcelError("لم أجد أي أسماء في الملف.\nتأكد أن هناك عموداً عنوانه (اسم المشترك).")
    return result

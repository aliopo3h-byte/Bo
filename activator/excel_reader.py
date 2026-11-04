"""قراءة ملف الإكسل وتصنيف كل صف حسب لونه (أخضر / أحمر / أزرق / أصفر)."""
import colorsys

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

# ألوان ثيم أوفيس الافتراضية (تُستخدم عندما يكون اللون من ألوان الثيم)
THEME_COLORS = [
    "FFFFFF", "000000", "E7E6E6", "44546A", "4472C4",
    "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47",
]


def _apply_tint(rgb, tint):
    if not tint:
        return rgb
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def color_to_rgb(color):
    """يحول لون openpyxl إلى نص RRGGBB أو None."""
    if color is None:
        return None
    try:
        if color.type == "rgb" and isinstance(color.rgb, str):
            return color.rgb[-6:]
        if color.type == "indexed" and isinstance(color.indexed, int):
            if 0 <= color.indexed < len(COLOR_INDEX):
                return COLOR_INDEX[color.indexed][-6:]
            return None
        if color.type == "theme" and isinstance(color.theme, int):
            if 0 <= color.theme < len(THEME_COLORS):
                return _apply_tint(THEME_COLORS[color.theme], color.tint or 0)
    except Exception:
        pass
    return None


def classify_rgb(rgb):
    if not rgb:
        return NONE
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.15 or v < 0.2:  # أبيض / رمادي / أسود
        return NONE
    h *= 360
    if h < 20 or h >= 330:
        return RED
    if h < 70:
        return YELLOW
    if h < 170:
        return GREEN
    if h < 270:
        return BLUE
    return NONE


def cell_category(cell):
    fill = cell.fill
    if fill is not None and fill.fill_type:
        cat = classify_rgb(color_to_rgb(fill.fgColor))
        if cat == NONE and fill.fill_type != "solid":
            cat = classify_rgb(color_to_rgb(fill.bgColor))
        if cat != NONE:
            return cat
    # إذا كان النص نفسه ملوّن بدل الخلفية
    if cell.font is not None:
        return classify_rgb(color_to_rgb(cell.font.color))
    return NONE


def _norm(text):
    return " ".join(str(text or "").split())


def _find_col(headers, *keys):
    for i, h in enumerate(headers):
        for k in keys:
            if k in h:
                return i
    return None


def load_subscribers(path):
    """يرجع قائمة قواميس: name, sub, phone, notes, color, row."""
    wb = openpyxl.load_workbook(path)
    result = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows())
        if not rows:
            continue
        # البحث عن صف العناوين ضمن أول 10 صفوف
        header_idx, headers = 0, []
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
        else:
            header_idx = -1
            name_col, sub_col, phone_col, notes_col = 0, None, None, None

        def val(row, col):
            if col is None or col >= len(row):
                return ""
            return _norm(row[col].value)

        for row in rows[header_idx + 1:]:
            name = val(row, name_col)
            if not name:
                continue
            # اللون: من خلية الاسم أولاً، وإلا من أي خلية في الصف
            color = cell_category(row[name_col])
            if color == NONE:
                for c in row:
                    color = cell_category(c)
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
    return result

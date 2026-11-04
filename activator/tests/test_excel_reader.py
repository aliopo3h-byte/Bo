import os
import sys

import openpyxl
import pytest
from openpyxl.styles import Font, PatternFill
from openpyxl.styles.colors import Color

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from excel_reader import (BLUE, GREEN, NONE, RED, YELLOW, ExcelError, classify_rgb,  # noqa: E402
                          load_subscribers, normalize_ar, parse_theme, shorten_name)

HEAD = ["اسم الاشتراك", "اسم المشترك", "الهاتف", "الملاحظات", "تاريخ الانتهاء", "فئة الاشتراك"]


def make(tmp_path, rows, header=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    r = 1
    if header:
        ws.append(HEAD)
        for c in ws[1]:
            c.fill = PatternFill("solid", fgColor="A9A9A9")
        r = 2
    for name, fill, kw in rows:
        ws.append(["kat-1-1-%d" % r, name, 7762211888.0, "ملاحظة", None, "1-Silver"])
        if fill is not None:
            ws.cell(row=r, column=2).fill = fill
        if kw.get("font"):
            ws.cell(row=r, column=2).font = Font(color=kw["font"])
        if kw.get("other_col_fill") is not None:
            ws.cell(row=r, column=3).fill = kw["other_col_fill"]
        r += 1
    p = tmp_path / "t.xlsx"
    wb.save(p)
    return str(p)


def solid(c):
    return PatternFill("solid", fgColor=c)


def test_four_colors_and_variants(tmp_path):
    rows = [
        ("اخضر", solid("92D050"), {}),
        ("احمر", solid("FF0000"), {}),
        ("ازرق", solid("00B0F0"), {}),
        ("اصفر", solid("FFFF00"), {}),
        ("اخضر باهت", solid("C6EFCE"), {}),
        ("احمر باهت", solid("FFC7CE"), {}),
        ("ازرق باهت اكسل", solid("DDEBF7"), {}),
        ("اصفر باهت", solid("FFEB9C"), {}),
        ("برتقالي", solid("FFC000"), {}),
        ("ثيم اخضر (accent3 في ثيم الملف)", solid(Color(theme=6, tint=0.6)), {}),
        ("اندكس احمر", solid(Color(indexed=10)), {}),
        ("خط اخضر", None, {"font": "00B050"}),
        ("لون بخلية اخرى", None, {"other_col_fill": solid("FF0000")}),
        ("بلا لون", None, {}),
        ("ابيض", solid("FFFFFF"), {}),
        ("رمادي", solid("D3D3D3"), {}),
    ]
    got = [x["color"] for x in load_subscribers(make(tmp_path, rows))]
    assert got == [GREEN, RED, BLUE, YELLOW, GREEN, RED, BLUE, YELLOW, YELLOW, GREEN, RED, GREEN, RED, NONE, NONE, NONE]


def test_fields_and_numeric_phone(tmp_path):
    items = load_subscribers(make(tmp_path, [("  احمد   خلف  ", solid("92D050"), {})]))
    it = items[0]
    assert it["name"] == "احمد خلف"
    assert it["phone"] == "7762211888"       # بدون .0
    assert it["sub"].startswith("kat-")
    assert it["row"] == 2


def test_no_header_uses_first_column(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["علي"])
    ws["A1"].fill = solid("92D050")
    ws.append(["حسن"])
    p = tmp_path / "n.xlsx"
    wb.save(p)
    items = load_subscribers(str(p))
    assert [(i["name"], i["color"]) for i in items] == [("علي", GREEN), ("حسن", NONE)]


def test_header_not_in_first_row(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["تقرير"])
    ws.append(HEAD)
    ws.append(["k-1", "كريم", 1, "", None, ""])
    p = tmp_path / "h.xlsx"
    wb.save(p)
    assert [i["name"] for i in load_subscribers(str(p))] == ["كريم"]


def test_file_open_elsewhere_still_readable(tmp_path):
    p = make(tmp_path, [("س", solid("92D050"), {})])
    with open(p, "rb"):  # ملف مفتوح للقراءة
        assert load_subscribers(p)[0]["color"] == GREEN


def test_errors(tmp_path):
    with pytest.raises(ExcelError):
        load_subscribers(str(tmp_path / "missing.xlsx"))
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ExcelError):
        load_subscribers(str(bad))
    with pytest.raises(ExcelError):
        load_subscribers(str(tmp_path / "old.xls"))
    with pytest.raises(ExcelError):
        load_subscribers(make(tmp_path, []))  # لا أسماء


def test_theme_parsing():
    xml = ('<a:clrScheme><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
           '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
           '<a:dk2><a:srgbClr val="1F497D"/></a:dk2><a:lt2><a:srgbClr val="EEECE1"/></a:lt2>'
           '<a:accent1><a:srgbClr val="4F81BD"/></a:accent1><a:accent2><a:srgbClr val="C0504D"/></a:accent2>'
           '<a:accent3><a:srgbClr val="9BBB59"/></a:accent3></a:clrScheme>')
    th = parse_theme(xml.encode())
    assert th[0] == "FFFFFF" and th[1] == "000000" and th[5] == "C0504D"
    assert parse_theme(None)[9] == "70AD47"
    assert parse_theme(b"garbage")[4] == "4472C4"


def test_classify_edges():
    assert classify_rgb(None) == NONE
    assert classify_rgb("zzzzzz") == NONE
    assert classify_rgb("000000") == NONE
    assert classify_rgb("800080") == NONE  # بنفسجي


def test_normalize_and_shorten():
    assert normalize_ar("أَحْمَد  إبراهيم") == normalize_ar("احمد ابراهيم")
    assert normalize_ar("فاطمة") == normalize_ar("فاطمه")
    assert normalize_ar("علي") == normalize_ar("على")
    assert shorten_name("حيدر حاتم محيسن علوان", 2) == "حيدر حاتم"
    assert shorten_name("حيدر حاتم", 5) == "حيدر حاتم"
    assert shorten_name("  حيدر   حاتم ", 0) == "حيدر حاتم"

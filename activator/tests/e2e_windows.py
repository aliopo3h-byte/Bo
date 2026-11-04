"""اختبار شامل على ويندوز: التطبيق الحقيقي + نافذة وهمية لبرنامج الاشتراكات."""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
tmp = tempfile.mkdtemp()
os.environ["APPDATA"] = tmp  # إعدادات معزولة

import openpyxl  # noqa: E402
import tkinter as tk  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402
from tkinter import messagebox  # noqa: E402

import app as appmod  # noqa: E402
import winput  # noqa: E402

msgs = []
for n in ("showinfo", "showwarning", "showerror", "askokcancel"):
    setattr(messagebox, n, lambda *a, _n=n, **k: msgs.append((_n, a)) or True)

NAMES = ["حيدر حاتم محيسن علوان", "سعد ماجد حميد", "عباس كاظم"]
xlsx = os.path.join(tmp, "t.xlsx")
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["اسم الاشتراك", "اسم المشترك", "الهاتف", "الملاحظات", "تاريخ الانتهاء", "فئة الاشتراك"])
for i, (n, c) in enumerate(zip(NAMES, ["92D050", "FF0000", "92D050"]), start=2):
    ws.append(["kat-1-%d" % i, n, 7708753549, "", None, "1-Silver"])
    ws.cell(row=i, column=2).fill = PatternFill("solid", fgColor=c)
wb.save(xlsx)

out = os.path.join(tmp, "fake")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "fake_subscriptions.py"), out])


def wait_for(path, timeout=10):
    t = time.time()
    while time.time() - t < timeout:
        if os.path.exists(path):
            return True
        time.sleep(0.1)
    return False


def result_after(action, timeout=4):
    if os.path.exists(out + ".result"):
        os.remove(out + ".result")
    action()
    if not wait_for(out + ".result", timeout):
        return None
    time.sleep(0.2)
    with open(out + ".result", encoding="utf-8") as f:
        return f.read()


failures = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra if not cond else "")
    if not cond:
        failures.append(name)


try:
    assert wait_for(out + ".ready"), "fake app did not start"
    pos = json.load(open(out + ".ready"))
    root = tk.Tk()
    app = appmod.App(root)
    root.geometry("400x420+620+40")
    root.update()

    # ---- تحميل الملف والفلترة
    check("load file", app.load(xlsx))
    app.filter_var.set("green")
    app.refresh()
    kids = app.tree.get_children()
    check("green list has 2", len(kids) == 2, str(len(kids)))
    app.filter_var.set("red")
    app.refresh()
    check("red list has 1", len(app.tree.get_children()) == 1)
    app.filter_var.set("green")
    app.refresh()
    app.search_var.set("حيدر")
    check("list search", len(app.tree.get_children()) == 1)
    app.search_var.set("")

    # ---- تحديد الحقل
    winput.set_cursor(pos["x"], pos["y"])
    app._capture_target()
    t = app.cfg.get("target")
    check("calibrated on fake window", bool(t) and "TEST" in t["title"], str(t))

    def send_first(words=None, sub=False):
        app.refresh()
        iid = app.tree.get_children()[0]
        it = app.items[int(iid)]
        text = it["sub"] if sub else appmod.shorten_name(it["name"], words or 0)
        return text, result_after(lambda: app.send(it, iid, text))

    # ---- كتابة مباشرة (النص القديم "حيدر" يجب أن يُستبدل)
    app.method_var.set("type")
    text, got = send_first()
    check("type mode full arabic name", got == NAMES[0], repr(got))
    check("marked done", appmod.done_key(app.items[0]) in app.done)

    app.done.clear()
    text, got = send_first(words=2)
    check("type mode first 2 words", got == "حيدر حاتم", repr(got))

    text, got = send_first(sub=True)
    check("type mode subscription name", got == "kat-1-2", repr(got))

    # ---- لصق
    app.method_var.set("paste")
    text, got = send_first()
    check("paste mode", got == NAMES[0], repr(got))
    app.method_var.set("type")

    # ---- تحريك نافذة البرنامج (يجب أن يتتبعها)
    hwnd = winput.find_window(t["title"], t["cls"])
    check("find_window", bool(hwnd))
    mv = winput.user32.MoveWindow
    mv.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    mv(hwnd, 60, 160, 520, 220, True)
    time.sleep(0.5)
    text, got = send_first()
    check("follows moved window", got == NAMES[0], repr(got))

    # ---- تغيير حجم النافذة (نسبة)
    mv(hwnd, 60, 160, 700, 300, True)
    time.sleep(0.5)
    text, got = send_first()
    check("follows resized window", got == NAMES[0], repr(got))
    mv(hwnd, 40, 40, 520, 220, True)
    time.sleep(0.4)

    # ---- نافذة المساعد تغطي الحقل: يجب الرفض وعدم الكتابة
    msgs.clear()
    l, tp, r, b = winput.window_rect(hwnd)
    root.geometry("400x300+%d+%d" % (pos["x"] - 100, pos["y"] - 100))
    root.update()
    time.sleep(0.3)
    iid = app.tree.get_children()[0]
    got = result_after(lambda: app.send(app.items[int(iid)], iid, "XXX"), timeout=2)
    check("refuses when helper covers field", got is None and any(m[0] == "showwarning" for m in msgs), repr(got))

    print("messages:", [m[0] for m in msgs])
except Exception:
    traceback.print_exc()
    failures.append("exception")
finally:
    proc.kill()

print("E2E RESULT:", "FAILED %s" % failures if failures else "ALL OK")
sys.exit(1 if failures else 0)

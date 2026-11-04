"""مساعد التفعيل: يعرض أسماء المشتركين من ملف الإكسل حسب اللون،
وعند الضغط على اسم يكتبه تلقائياً في حقل "بحث عن مشترك" في برنامج الاشتراكات."""
import json
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import winput
from excel_reader import BLUE, GREEN, LABELS, NONE, RED, YELLOW, load_subscribers

APP_TITLE = "مساعد التفعيل"
ROW_BG = {GREEN: "#C6EFCE", RED: "#FFC7CE", BLUE: "#BDD7EE", YELLOW: "#FFEB9C", NONE: "#FFFFFF"}
DONE_BG = "#D9D9D9"


def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "ActivatorHelper")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.items = []
        self.done = set(self.cfg.get("done", []))

        root.title(APP_TITLE)
        root.geometry(self.cfg.get("geometry", "560x650"))
        root.attributes("-topmost", self.cfg.get("topmost", True))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # ---- الشريط العلوي ----
        top = ttk.Frame(root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="📂 فتح ملف إكسل", command=self.open_file).pack(side="right", padx=3)
        ttk.Button(top, text="🎯 تحديد حقل البحث", command=self.calibrate).pack(side="right", padx=3)
        self.pos_label = ttk.Label(top, text="")
        self.pos_label.pack(side="right", padx=6)
        self.update_pos_label()

        # ---- الفلتر حسب اللون ----
        flt = ttk.Frame(root, padding=(6, 0))
        flt.pack(fill="x")
        self.filter_var = tk.StringVar(value=self.cfg.get("filter", GREEN))
        for key in (GREEN, RED, BLUE, YELLOW, NONE, "all"):
            text = "الكل" if key == "all" else LABELS[key].split(" -")[0]
            ttk.Radiobutton(flt, text=text, value=key, variable=self.filter_var,
                            command=self.refresh).pack(side="right", padx=3)

        # ---- بحث داخل القائمة ----
        srch = ttk.Frame(root, padding=6)
        srch.pack(fill="x")
        ttk.Label(srch, text="بحث بالقائمة:").pack(side="right")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(srch, textvariable=self.search_var, justify="right").pack(side="right", fill="x", expand=True, padx=4)

        # ---- الخيارات ----
        opts = ttk.Frame(root, padding=(6, 0))
        opts.pack(fill="x")
        self.send_var = tk.StringVar(value=self.cfg.get("send", "name"))
        ttk.Label(opts, text="يُكتب في البحث:").pack(side="right")
        ttk.Radiobutton(opts, text="اسم المشترك", value="name", variable=self.send_var).pack(side="right", padx=3)
        ttk.Radiobutton(opts, text="اسم الاشتراك", value="sub", variable=self.send_var).pack(side="right", padx=3)
        self.method_var = tk.StringVar(value=self.cfg.get("method", "type"))
        opts2 = ttk.Frame(root, padding=(6, 2))
        opts2.pack(fill="x")
        ttk.Label(opts2, text="طريقة الإدخال:").pack(side="right")
        ttk.Radiobutton(opts2, text="كتابة مباشرة", value="type", variable=self.method_var).pack(side="right", padx=3)
        ttk.Radiobutton(opts2, text="لصق Ctrl+V", value="paste", variable=self.method_var).pack(side="right", padx=3)
        if sys.platform == "win32" and not winput.is_admin():
            ttk.Button(opts2, text="🛡 تشغيل كمسؤول", command=self.run_as_admin).pack(side="left", padx=3)
        self.enter_var = tk.BooleanVar(value=self.cfg.get("enter", True))
        ttk.Checkbutton(opts, text="ضغط Enter", variable=self.enter_var).pack(side="left", padx=3)
        self.top_var = tk.BooleanVar(value=self.cfg.get("topmost", True))
        ttk.Checkbutton(opts, text="فوق كل النوافذ", variable=self.top_var,
                        command=lambda: root.attributes("-topmost", self.top_var.get())).pack(side="left", padx=3)

        # ---- القائمة ----
        body = ttk.Frame(root, padding=6)
        body.pack(fill="both", expand=True)
        cols = ("phone", "sub", "name", "n")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for c, t, w, anchor in (("n", "ت", 40, "center"), ("name", "اسم المشترك", 230, "e"),
                                ("sub", "اسم الاشتراك", 120, "center"), ("phone", "الهاتف", 110, "center")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "name"))
        for key, bg in ROW_BG.items():
            self.tree.tag_configure(key, background=bg)
        self.tree.tag_configure("done", background=DONE_BG, foreground="#777777")
        sb = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<ButtonRelease-1>", self.on_click)
        self.tree.bind("<Return>", self.on_click)
        self.tree.bind("<Button-3>", self.toggle_done)

        # ---- الحالة ----
        bottom = ttk.Frame(root, padding=6)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="مسح علامات (تم)", command=self.clear_done).pack(side="left")
        self.status = ttk.Label(bottom, text="افتح ملف الإكسل للبدء", anchor="e")
        self.status.pack(side="right", fill="x", expand=True)

        last = self.cfg.get("last_file")
        if last and os.path.exists(last):
            self.load(last)

    # ------------------------------------------------------------------
    def update_pos_label(self):
        pos = self.cfg.get("pos")
        self.pos_label.config(text=f"الحقل: {pos[0]},{pos[1]}" if pos else "⚠ لم يتم تحديد حقل البحث",
                              foreground="green" if pos else "red")

    def open_file(self):
        path = filedialog.askopenfilename(title="اختر ملف الإكسل",
                                          filetypes=[("Excel", "*.xlsx *.xlsm"), ("All", "*.*")])
        if path:
            self.load(path)

    def load(self, path):
        try:
            self.items = load_subscribers(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"تعذر قراءة الملف:\n{e}")
            return
        if path != self.cfg.get("last_file"):
            self.done = set()
        self.cfg["last_file"] = path
        self.root.title(f"{APP_TITLE} - {os.path.basename(path)}")
        self.refresh()

    def key(self, it):
        return f"{it['sheet']}:{it['row']}"

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filter_var.get()
        q = self.search_var.get().strip()
        shown = 0
        for it in self.items:
            if f != "all" and it["color"] != f:
                continue
            if q and q not in it["name"] and q not in it["sub"] and q not in it["phone"]:
                continue
            shown += 1
            tag = "done" if self.key(it) in self.done else it["color"]
            name = ("✔ " if tag == "done" else "") + it["name"]
            self.tree.insert("", "end", iid=self.key(it), tags=(tag,),
                             values=(it["phone"], it["sub"], name, shown))
        counts = {c: sum(1 for i in self.items if i["color"] == c) for c in (GREEN, RED, BLUE, YELLOW)}
        done_green = sum(1 for i in self.items if i["color"] == GREEN and self.key(i) in self.done)
        self.status.config(text=f"المعروض: {shown} | أخضر {counts[GREEN]} (تم {done_green}) | "
                                f"أحمر {counts[RED]} | أزرق {counts[BLUE]} | أصفر {counts[YELLOW]}")

    def find_item(self, iid):
        for it in self.items:
            if self.key(it) == iid:
                return it
        return None

    # ------------------------------------------------------------------
    def calibrate(self):
        if not messagebox.askokcancel(
                APP_TITLE,
                "بعد الضغط على موافق: ضع مؤشر الماوس فوق حقل (بحث عن مشترك) في برنامج الاشتراكات "
                "واتركه هناك لمدة 4 ثواني.\n(لا تضغط، فقط ضع المؤشر)"):
            return
        for i in range(4, 0, -1):
            self.pos_label.config(text=f"ضع المؤشر على الحقل... {i}", foreground="blue")
            self.root.update()
            time.sleep(1)
        x, y = winput.get_cursor()
        self.cfg["pos"] = [int(x), int(y)]
        save_config(self.cfg)
        self.update_pos_label()
        msg = f"تم حفظ مكان الحقل: {x}, {y}"
        if not winput.is_admin() and winput.window_is_elevated(x, y):
            msg += ("\n\n⚠ برنامج الاشتراكات يعمل كمسؤول (Administrator)، وويندوز يمنع الكتابة فيه.\n"
                    "اضغط زر (🛡 تشغيل كمسؤول).")
        messagebox.showinfo(APP_TITLE, msg)

    def run_as_admin(self):
        self.on_close(save_only=True)
        if winput.relaunch_as_admin():
            self.root.destroy()

    def on_click(self, event=None):
        if event is not None and getattr(event, "y", None) is not None and event.type == tk.EventType.ButtonRelease:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            iid = self.tree.identify_row(event.y)
        else:
            iid = self.tree.focus()
        it = self.find_item(iid) if iid else None
        if not it:
            return
        text = it["sub"] if self.send_var.get() == "sub" and it["sub"] else it["name"]
        self.root.after(50, lambda: self.send_to_search(text))
        self.done.add(iid)
        self.refresh()
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)

    def send_to_search(self, text):
        if sys.platform != "win32":
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            return
        winput.set_clipboard(text)
        pos = self.cfg.get("pos")
        if not pos:
            messagebox.showwarning(APP_TITLE, "تم نسخ الاسم فقط.\nاضغط (🎯 تحديد حقل البحث) أولاً "
                                              "حتى يكتب البرنامج الاسم تلقائياً.")
            return
        if not winput.is_admin() and winput.window_is_elevated(*pos):
            messagebox.showwarning(APP_TITLE, "برنامج الاشتراكات يعمل كمسؤول، وويندوز يمنع الكتابة فيه.\n"
                                              "اضغط زر (🛡 تشغيل كمسؤول). الاسم منسوخ، الصقه بـ Ctrl+V.")
            return
        try:
            old = winput.get_cursor()
            winput.focus_window_at(*pos)
            time.sleep(0.1)
            ok = winput.click(*pos)
            time.sleep(0.2)
            # مسح الحقل: Ctrl+A ثم End و Shift+Home احتياطاً
            winput.hotkey(winput.VK_CONTROL, winput.VK_A)
            winput.press(winput.VK_DELETE)
            winput.press(winput.VK_END)
            winput.hotkey(winput.VK_SHIFT, winput.VK_HOME)
            winput.press(winput.VK_DELETE)
            time.sleep(0.05)
            if self.method_var.get() == "paste":
                ok &= winput.hotkey(winput.VK_CONTROL, winput.VK_V)
            else:
                ok &= winput.type_unicode(text)
            if self.enter_var.get():
                time.sleep(0.15)
                winput.press(winput.VK_RETURN)
            time.sleep(0.05)
            user32_pos = old
            winput.user32.SetCursorPos(*user32_pos)
            self.status.config(text=("تم إرسال: " if ok else "⚠ ويندوز رفض الإدخال: ") + text)
            if not ok:
                messagebox.showwarning(APP_TITLE, "ويندوز رفض إرسال الكتابة.\nجرّب زر (🛡 تشغيل كمسؤول).")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"تعذر الكتابة في البرنامج (الاسم منسوخ، الصقه بـ Ctrl+V):\n{e}")

    def toggle_done(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.done.symmetric_difference_update({iid})
        self.refresh()

    def clear_done(self):
        self.done.clear()
        self.refresh()

    def on_close(self, save_only=False):
        self.cfg.update(filter=self.filter_var.get(), send=self.send_var.get(), enter=self.enter_var.get(),
                        method=self.method_var.get(),
                        topmost=self.top_var.get(), geometry=self.root.geometry(), done=sorted(self.done))
        save_config(self.cfg)
        if not save_only:
            self.root.destroy()


def main():
    if sys.platform == "win32":
        try:  # دقة صحيحة لإحداثيات الماوس على الشاشات المكبّرة
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

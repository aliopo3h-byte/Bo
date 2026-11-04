"""مساعد التفعيل: يعرض أسماء المشتركين من ملف الإكسل حسب اللون،
وعند الضغط على اسم يكتبه تلقائياً في حقل "بحث عن مشترك" في برنامج الاشتراكات."""
import json
import logging
import logging.handlers
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

import shell_integration
import winput
from excel_reader import (BLUE, GREEN, LABELS, NONE, RED, YELLOW, ExcelError,
                          load_subscribers, normalize_ar, shorten_name)

VERSION = "1.3"
APP_TITLE = "مساعد التفعيل"
ROW_BG = {GREEN: "#C6EFCE", RED: "#FFC7CE", BLUE: "#BDD7EE", YELLOW: "#FFEB9C", NONE: "#FFFFFF"}
DONE_BG = "#D9D9D9"
WORD_CHOICES = {"الاسم كاملاً": 0, "أول كلمة": 1, "أول كلمتين": 2, "أول 3 كلمات": 3}

log = logging.getLogger("activator")


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "ActivatorHelper")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = os.path.expanduser("~")
    return folder


def setup_logging():
    try:
        h = logging.handlers.RotatingFileHandler(os.path.join(data_dir(), "activator.log"),
                                                 maxBytes=300_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    except Exception:
        pass


def config_path():
    return os.path.join(data_dir(), "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def save_config(cfg):
    try:
        tmp = config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, config_path())
    except Exception:
        log.exception("save_config failed")


def request_path():
    return os.path.join(data_dir(), "open_request.txt")


def send_to_running_instance(path):
    tmp = request_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(path)
    os.replace(tmp, request_path())


def done_key(it):
    return "%s|%s" % (it["name"], it["sub"])


class App:
    def __init__(self, root, initial_file=None):
        self.root = root
        self.cfg = load_config()
        self.items = []
        self.done = set(self.cfg.get("done", []))
        self.hwnd = None          # نافذة برنامج الاشتراكات (في الذاكرة فقط)
        self.busy = False
        self.file_mtime = None

        root.title("%s %s" % (APP_TITLE, VERSION))
        try:
            root.geometry(self.cfg.get("geometry", "580x680"))
        except tk.TclError:
            root.geometry("580x680")
        root.minsize(480, 420)
        root.attributes("-topmost", bool(self.cfg.get("topmost", True)))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self.on_tk_error

        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.build_ui()
        if initial_file:
            self.load(initial_file)
        else:
            last = self.cfg.get("last_file")
            if last and os.path.exists(last):
                self.load(last, quiet=True)
        self.root.after(2000, self.watch_file)
        self.root.after(700, self.poll_requests)

    # ------------------------------------------------------------ واجهة
    def build_ui(self):
        root = self.root
        top = ttk.Frame(root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="📂 فتح ملف إكسل", command=self.open_file).pack(side="right", padx=3)
        ttk.Button(top, text="🔄", width=3, command=self.reload).pack(side="right", padx=3)
        ttk.Button(top, text="🎯 تحديد حقل البحث", command=self.calibrate).pack(side="right", padx=3)
        self.pos_label = ttk.Label(top, text="")
        self.pos_label.pack(side="right", padx=6)
        ttk.Button(top, text="📄", width=3, command=self.open_log).pack(side="left", padx=3)
        if winput.IS_WIN:
            ttk.Button(top, text="🔗 فتح باستخدام", command=self.register_shell).pack(side="left", padx=3)
        self.update_pos_label()

        flt = ttk.Frame(root, padding=(6, 0))
        flt.pack(fill="x")
        self.filter_var = tk.StringVar(value=self.cfg.get("filter", GREEN))
        for key in (GREEN, RED, BLUE, YELLOW, NONE, "all"):
            text = "الكل" if key == "all" else LABELS[key].split(" -")[0]
            ttk.Radiobutton(flt, text=text, value=key, variable=self.filter_var,
                            command=self.refresh).pack(side="right", padx=3)

        srch = ttk.Frame(root, padding=6)
        srch.pack(fill="x")
        ttk.Label(srch, text="بحث بالقائمة:").pack(side="right")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(srch, textvariable=self.search_var, justify="right").pack(side="right", fill="x", expand=True, padx=4)

        opts = ttk.Frame(root, padding=(6, 0))
        opts.pack(fill="x")
        self.send_var = tk.StringVar(value=self.cfg.get("send", "name"))
        ttk.Label(opts, text="يُكتب في البحث:").pack(side="right")
        ttk.Radiobutton(opts, text="اسم المشترك", value="name", variable=self.send_var).pack(side="right", padx=3)
        ttk.Radiobutton(opts, text="اسم الاشتراك", value="sub", variable=self.send_var).pack(side="right", padx=3)
        self.words_var = tk.StringVar(value=self.cfg.get("words", "الاسم كاملاً"))
        if self.words_var.get() not in WORD_CHOICES:
            self.words_var.set("الاسم كاملاً")
        ttk.Combobox(opts, textvariable=self.words_var, values=list(WORD_CHOICES), width=12,
                     state="readonly", justify="right").pack(side="right", padx=3)

        opts2 = ttk.Frame(root, padding=(6, 2))
        opts2.pack(fill="x")
        self.method_var = tk.StringVar(value=self.cfg.get("method", "type"))
        ttk.Label(opts2, text="طريقة الإدخال:").pack(side="right")
        ttk.Radiobutton(opts2, text="كتابة مباشرة", value="type", variable=self.method_var).pack(side="right", padx=3)
        ttk.Radiobutton(opts2, text="لصق Ctrl+V", value="paste", variable=self.method_var).pack(side="right", padx=3)
        self.enter_var = tk.BooleanVar(value=bool(self.cfg.get("enter", True)))
        ttk.Checkbutton(opts2, text="ضغط Enter", variable=self.enter_var).pack(side="right", padx=8)
        self.top_var = tk.BooleanVar(value=bool(self.cfg.get("topmost", True)))
        ttk.Checkbutton(opts2, text="فوق كل النوافذ", variable=self.top_var,
                        command=lambda: root.attributes("-topmost", self.top_var.get())).pack(side="left", padx=3)
        if winput.IS_WIN and not winput.is_admin():
            ttk.Button(opts2, text="🛡 تشغيل كمسؤول", command=self.run_as_admin).pack(side="left", padx=3)

        body = ttk.Frame(root, padding=6)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("phone", "sub", "name", "n"), show="headings", selectmode="browse")
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

        bottom = ttk.Frame(root, padding=6)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="مسح علامات (تم)", command=self.clear_done).pack(side="left")
        self.status = ttk.Label(bottom, text="افتح ملف الإكسل للبدء", anchor="e")
        self.status.pack(side="right", fill="x", expand=True)

    def set_status(self, text):
        self.status.config(text=text)

    def update_pos_label(self):
        t = self.cfg.get("target")
        if t:
            self.pos_label.config(text="✔ الحقل محدد: " + (t.get("title") or "")[:22], foreground="green")
        else:
            self.pos_label.config(text="⚠ لم يتم تحديد حقل البحث", foreground="red")

    # ------------------------------------------------------------ الملف
    def open_file(self):
        path = filedialog.askopenfilename(title="اختر ملف الإكسل",
                                          filetypes=[("Excel", "*.xlsx *.xlsm"), ("All", "*.*")])
        if path:
            self.load(path)

    def reload(self):
        p = self.cfg.get("last_file")
        if p:
            self.load(p)
        else:
            self.open_file()

    def load(self, path, quiet=False):
        try:
            items = load_subscribers(path)
            self.file_mtime = os.path.getmtime(path)
        except ExcelError as e:
            if not quiet:
                messagebox.showerror(APP_TITLE, str(e))
            self.set_status("⚠ " + str(e).splitlines()[0])
            return False
        except Exception as e:
            log.exception("load failed")
            if not quiet:
                messagebox.showerror(APP_TITLE, "تعذر قراءة الملف:\n%s" % e)
            return False
        self.items = items
        self.cfg["last_file"] = path
        self.root.title("%s %s - %s" % (APP_TITLE, VERSION, os.path.basename(path)))
        log.info("loaded %s rows=%d", path, len(items))
        self.refresh()
        return True

    def register_shell(self):
        exe = shell_integration.current_exe_path()
        if any(s in exe.lower() for s in ("whatsapp", "\\temp\\", "/temp/")):
            messagebox.showwarning(APP_TITLE, "البرنامج يعمل من مجلد مؤقت:\n%s\n\nانقل المجلد إلى سطح المكتب "
                                              "أو أي مكان ثابت ثم أعد الضغط على الزر." % exe)
            return
        try:
            shell_integration.register_open_with(APP_TITLE, icon=exe)
        except Exception as e:
            log.exception("register failed")
            messagebox.showerror(APP_TITLE, "تعذر الربط:\n%s" % e)
            return
        messagebox.showinfo(APP_TITLE, "تم! الآن:\nزر الماوس الأيمن على أي ملف إكسل ← فتح في %s\n(أو: فتح باستخدام ← %s)\n\n"
                                       "(اختر «دائماً» إذا أردته الافتراضي لكل ملفات إكسل.)\n"
                                       "أو اسحب الملف وأفلته على أيقونة البرنامج.\n\n"
                                       "إذا نقلت البرنامج لمكان آخر أعد الضغط على هذا الزر." % (APP_TITLE, APP_TITLE))

    def poll_requests(self):
        """استلام ملف أُرسل من نسخة ثانية للبرنامج (فتح ملف إكسل بينما البرنامج يعمل)."""
        try:
            p = request_path()
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    path = f.read().strip()
                os.remove(p)
                if path and os.path.isfile(path):
                    self.load(path)
                    self.root.deiconify()
                    self.root.lift()
                    self.set_status("📂 تم فتح: " + os.path.basename(path))
        except Exception:
            log.exception("poll_requests")
        self.root.after(700, self.poll_requests)

    def watch_file(self):
        """إعادة تحميل الملف تلقائياً عند حفظه من إكسل."""
        try:
            p = self.cfg.get("last_file")
            if p and os.path.exists(p) and self.file_mtime and os.path.getmtime(p) != self.file_mtime:
                if self.load(p, quiet=True):
                    self.set_status("🔄 تم تحديث الملف تلقائياً")
                else:
                    self.file_mtime = os.path.getmtime(p)  # لا نكرر المحاولة على ملف تالف
        except Exception:
            log.exception("watch_file")
        self.root.after(2000, self.watch_file)

    def refresh(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        f = self.filter_var.get()
        q = normalize_ar(self.search_var.get())
        shown = 0
        for i, it in enumerate(self.items):
            if f != "all" and it["color"] != f:
                continue
            if q and q not in normalize_ar(it["name"]) and q not in normalize_ar(it["sub"]) and q not in it["phone"]:
                continue
            shown += 1
            is_done = done_key(it) in self.done
            self.tree.insert("", "end", iid=str(i), tags=("done" if is_done else it["color"],),
                             values=(it["phone"], it["sub"], ("✔ " if is_done else "") + it["name"], shown))
        counts = {c: sum(1 for i in self.items if i["color"] == c) for c in (GREEN, RED, BLUE, YELLOW)}
        done_green = sum(1 for i in self.items if i["color"] == GREEN and done_key(i) in self.done)
        self.set_status("المعروض: %d | أخضر %d (تم %d) | أحمر %d | أزرق %d | أصفر %d" % (
            shown, counts[GREEN], done_green, counts[RED], counts[BLUE], counts[YELLOW]))

    # ------------------------------------------------------------ تحديد الحقل
    def calibrate(self):
        if not messagebox.askokcancel(
                APP_TITLE,
                "بعد الضغط على موافق: ضع مؤشر الماوس فوق حقل (بحث عن مشترك) في برنامج الاشتراكات "
                "واتركه هناك لمدة 4 ثواني.\n(لا تضغط، فقط ضع المؤشر)"):
            return
        self._countdown(4)

    def _countdown(self, n):
        if n > 0:
            self.pos_label.config(text="ضع المؤشر على الحقل... %d" % n, foreground="blue")
            self.root.after(1000, lambda: self._countdown(n - 1))
            return
        self._capture_target()

    def _capture_target(self):
        x, y = winput.get_cursor()
        hwnd = winput.root_at(x, y)
        if not hwnd or winput.window_pid(hwnd) == winput.own_pid():
            self.update_pos_label()
            messagebox.showwarning(APP_TITLE, "المؤشر كان فوق نافذة المساعد نفسها.\n"
                                              "ضع المؤشر فوق حقل البحث في برنامج الاشتراكات وأعد المحاولة.")
            return
        l, t, r, b = winput.window_rect(hwnd)
        w, h = max(1, r - l), max(1, b - t)
        self.cfg["target"] = {
            "title": winput.window_title(hwnd), "cls": winput.window_class(hwnd),
            "size": [w, h], "rel": [x - l, y - t], "frac": [(x - l) / w, (y - t) / h],
        }
        self.hwnd = hwnd
        save_config(self.cfg)
        log.info("calibrated %s", self.cfg["target"])
        self.update_pos_label()
        msg = "تم حفظ مكان الحقل في نافذة:\n%s" % (self.cfg["target"]["title"] or self.cfg["target"]["cls"])
        if not winput.is_admin() and winput.hwnd_is_elevated(hwnd):
            msg += ("\n\n⚠ برنامج الاشتراكات يعمل كمسؤول (Administrator)، وويندوز يمنع الكتابة فيه.\n"
                    "اضغط زر (🛡 تشغيل كمسؤول).")
        messagebox.showinfo(APP_TITLE, msg)

    def resolve_target(self):
        """يرجع (hwnd, x, y) لحقل البحث الحالي أو None."""
        t = self.cfg.get("target")
        if not t:
            return None
        hwnd = self.hwnd
        if not (winput.is_window(hwnd) and winput.window_title(hwnd) == t.get("title")):
            hwnd = winput.find_window(t.get("title", ""), t.get("cls", ""))
            self.hwnd = hwnd
        if not hwnd:
            return None
        l, tp, r, b = winput.window_rect(hwnd)
        w, h = max(1, r - l), max(1, b - tp)
        if [w, h] == list(t.get("size", [])):
            x, y = l + t["rel"][0], tp + t["rel"][1]
        else:  # تغيّر حجم النافذة: نستعمل النسبة
            x, y = l + t["frac"][0] * w, tp + t["frac"][1] * h
        return hwnd, int(x), int(y)

    # ------------------------------------------------------------ الإرسال
    def on_click(self, event=None):
        if event is not None and event.type == tk.EventType.ButtonRelease:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            iid = self.tree.identify_row(event.y)
        else:
            iid = self.tree.focus()
        if not iid or self.busy:
            return
        it = self.items[int(iid)]
        text = it["sub"] if self.send_var.get() == "sub" and it["sub"] else \
            shorten_name(it["name"], WORD_CHOICES.get(self.words_var.get(), 0))
        self.tree.selection_set(iid)
        self.root.after(30, lambda: self.send(it, iid, text))

    def send(self, it, iid, text):
        if self.busy:
            return
        self.busy = True
        try:
            if self.deliver(text):
                self.done.add(done_key(it))
                self.set_status("✔ تم إرسال: " + text)
                self.refresh()
                if self.tree.exists(iid):
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
        except Exception as e:
            log.exception("deliver failed")
            messagebox.showerror(APP_TITLE, "تعذر الكتابة في البرنامج:\n%s\n\n(راجع السجل 📄)" % e)
        finally:
            self.busy = False

    def deliver(self, text):
        """يكتب النص في حقل البحث. يرجع True عند النجاح."""
        if not winput.IS_WIN:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status("تم نسخ: " + text)
            return False
        if not self.cfg.get("target"):
            winput.set_clipboard(text)
            messagebox.showwarning(APP_TITLE, "تم نسخ الاسم فقط.\nاضغط (🎯 تحديد حقل البحث) أولاً "
                                              "حتى يكتب البرنامج الاسم تلقائياً.")
            return False
        target = self.resolve_target()
        if not target:
            winput.set_clipboard(text)
            messagebox.showwarning(APP_TITLE, "لم أجد نافذة برنامج الاشتراكات.\n"
                                              "افتح البرنامج ثم حاول مجدداً، أو أعد (🎯 تحديد حقل البحث).\n"
                                              "الاسم منسوخ، الصقه بـ Ctrl+V.")
            return False
        hwnd, x, y = target
        if not winput.is_admin() and winput.hwnd_is_elevated(hwnd):
            winput.set_clipboard(text)
            messagebox.showwarning(APP_TITLE, "برنامج الاشتراكات يعمل كمسؤول، وويندوز يمنع الكتابة فيه.\n"
                                              "اضغط زر (🛡 تشغيل كمسؤول).\nالاسم منسوخ، الصقه بـ Ctrl+V.")
            return False

        old = winput.get_cursor()
        if not winput.force_foreground(hwnd):
            log.warning("could not bring target to foreground (continuing)")
        time.sleep(0.12)
        cover = winput.root_at(x, y)
        if cover and winput.window_pid(cover) == winput.own_pid():
            messagebox.showwarning(APP_TITLE, "نافذة المساعد تغطي حقل البحث!\n"
                                              "حرّكها بعيداً عن الحقل (أو أزل علامة فوق كل النوافذ) وحاول مجدداً.")
            return False

        paste = self.method_var.get() == "paste"
        if paste:
            winput.set_clipboard(text)
        ok = winput.click(x, y)
        time.sleep(0.2)
        winput.hotkey(winput.VK_CONTROL, winput.VK_A)   # مسح أي اسم سابق
        winput.press(winput.VK_DELETE)
        winput.press(winput.VK_END)
        winput.hotkey(winput.VK_SHIFT, winput.VK_HOME)
        winput.press(winput.VK_DELETE)
        time.sleep(0.05)
        ok &= winput.hotkey(winput.VK_CONTROL, winput.VK_V) if paste else winput.type_unicode(text)
        if self.enter_var.get():
            time.sleep(0.15)
            ok &= winput.press(winput.VK_RETURN)
        time.sleep(0.05)
        winput.set_cursor(*old)
        log.info("sent %r method=%s at=(%d,%d) ok=%s", text, "paste" if paste else "type", x, y, ok)
        if not ok:
            messagebox.showwarning(APP_TITLE, "ويندوز رفض إرسال الكتابة.\nجرّب زر (🛡 تشغيل كمسؤول).")
        return bool(ok)

    # ------------------------------------------------------------ متفرقات
    def toggle_done(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        k = done_key(self.items[int(iid)])
        self.done.symmetric_difference_update({k})
        self.refresh()

    def clear_done(self):
        self.done.clear()
        self.refresh()

    def run_as_admin(self):
        self.on_close(save_only=True)
        winput.release_instance()  # حتى تقبل النسخة الجديدة بالتشغيل
        if winput.relaunch_as_admin():
            self.root.destroy()
        else:
            winput.single_instance()
            messagebox.showwarning(APP_TITLE, "لم تتم الموافقة على التشغيل كمسؤول.")

    def open_log(self):
        try:
            os.startfile(os.path.join(data_dir(), "activator.log"))  # noqa
        except Exception:
            messagebox.showinfo(APP_TITLE, "ملف السجل:\n" + os.path.join(data_dir(), "activator.log"))

    def on_tk_error(self, exc, val, tb):
        log.error("tk error\n%s", "".join(traceback.format_exception(exc, val, tb)))
        self.set_status("⚠ خطأ: %s" % val)

    def on_close(self, save_only=False):
        self.cfg.update(filter=self.filter_var.get(), send=self.send_var.get(), enter=self.enter_var.get(),
                        method=self.method_var.get(), words=self.words_var.get(), topmost=self.top_var.get(),
                        geometry=self.root.geometry(), done=sorted(self.done))
        save_config(self.cfg)
        if not save_only:
            self.root.destroy()


def main():
    setup_logging()
    file_arg = shell_integration.find_file_arg(sys.argv[1:])
    if winput.IS_WIN:
        try:  # دقة صحيحة لإحداثيات الماوس على الشاشات المكبّرة
            ctypes_ = __import__("ctypes")
            ctypes_.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        if not winput.single_instance():
            if file_arg:
                send_to_running_instance(file_arg)  # النسخة العاملة ستفتح الملف
            else:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(APP_TITLE, "البرنامج يعمل بالفعل.")
            return
    root = tk.Tk()
    App(root, initial_file=file_arg)
    log.info("started v%s admin=%s", VERSION, winput.is_admin() if winput.IS_WIN else "-")
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        setup_logging()
        log.exception("fatal")
        raise

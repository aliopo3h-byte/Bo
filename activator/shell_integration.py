"""ربط البرنامج بويندوز: فتح ملفات إكسل بواسطته (فتح باستخدام / سحب الملف على الأيقونة)."""
import os
import sys

EXTS = (".xlsx", ".xlsm")
APP_EXE = "ActivatorHelper.exe"
BASE = r"Software\Classes\Applications\%s" % APP_EXE


def find_file_arg(argv):
    """أول وسيط يشير إلى ملف إكسل موجود (يعمل مع المسافات والعربي)."""
    for a in argv:
        a = str(a).strip().strip('"')
        if a.lower().endswith(EXTS) and os.path.isfile(a):
            return os.path.abspath(a)
    return None


def current_command():
    if getattr(sys, "frozen", False):
        return '"%s" "%%1"' % sys.executable
    return '"%s" "%s" "%%1"' % (sys.executable, os.path.abspath(sys.argv[0]))


def current_exe_path():
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])


def _winreg():
    import winreg
    return winreg


def _set(path, name, value):
    w = _winreg()
    with w.CreateKeyEx(w.HKEY_CURRENT_USER, path, 0, w.KEY_SET_VALUE) as k:
        w.SetValueEx(k, name, 0, w.REG_SZ, value)


def _del_tree(path):
    w = _winreg()
    try:
        with w.OpenKey(w.HKEY_CURRENT_USER, path, 0, w.KEY_READ | w.KEY_WRITE) as k:
            while True:
                try:
                    sub = w.EnumKey(k, 0)
                except OSError:
                    break
                _del_tree(path + "\\" + sub)
        w.DeleteKey(w.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


def _notify():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass


def register_open_with(title, command=None, icon=None):
    """يضيف البرنامج إلى قائمة (فتح باستخدام) لملفات xlsx/xlsm للمستخدم الحالي (بدون صلاحيات مسؤول)."""
    command = command or current_command()
    _set(BASE, "FriendlyAppName", title)
    _set(BASE + r"\shell\open\command", "", command)
    if icon:
        _set(BASE + r"\DefaultIcon", "", icon + ",0")
    for ext in EXTS:
        _set(BASE + r"\SupportedTypes", ext, "")
        _set(r"Software\Classes\%s\OpenWithList\%s" % (ext, APP_EXE), "", "")
    _notify()


def unregister_open_with():
    _del_tree(BASE)
    for ext in EXTS:
        _del_tree(r"Software\Classes\%s\OpenWithList\%s" % (ext, APP_EXE))
    _notify()


def registered_command():
    w = _winreg()
    try:
        with w.OpenKey(w.HKEY_CURRENT_USER, BASE + r"\shell\open\command") as k:
            return w.QueryValueEx(k, "")[0]
    except OSError:
        return None

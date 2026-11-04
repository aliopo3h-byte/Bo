"""إدخال الماوس ولوحة المفاتيح وإدارة النوافذ على ويندوز مباشرة عبر Win32 (يدعم العربي)."""
import ctypes
import os
import sys
import time
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYUP, UNICODE = 0x0002, 0x0004
MOUSE_LEFTDOWN, MOUSE_LEFTUP = 0x0002, 0x0004
VK_CONTROL, VK_SHIFT, VK_HOME, VK_END, VK_DELETE, VK_BACK, VK_RETURN = 0x11, 0x10, 0x24, 0x23, 0x2E, 0x08, 0x0D
VK_A, VK_V = 0x41, 0x56
SW_RESTORE = 9

if IS_WIN:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.WindowFromPoint.argtypes = (wintypes.POINT,)
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))


# ---------------------------------------------------------------- إدخال
def _send(inputs):
    arr = (INPUT * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT)) == len(inputs)


def _key(vk=0, scan=0, flags=0):
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return i


def press(vk):
    return _send([_key(vk), _key(vk, flags=KEYUP)])


def hotkey(mod, vk):
    return _send([_key(mod), _key(vk), _key(vk, flags=KEYUP), _key(mod, flags=KEYUP)])


def type_unicode(text):
    """كتابة النص حرفاً حرفاً (لا يعتمد على الحافظة ولا على لغة الكيبورد)."""
    ok = True
    for ch in text:
        units = ch.encode("utf-16-le")
        for k in range(0, len(units), 2):
            code = int.from_bytes(units[k:k + 2], "little")
            ok &= _send([_key(scan=code, flags=UNICODE), _key(scan=code, flags=UNICODE | KEYUP)])
        time.sleep(0.008)
    return ok


def get_cursor():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor(x, y):
    user32.SetCursorPos(int(x), int(y))


def click(x, y):
    set_cursor(x, y)
    time.sleep(0.03)
    down, up = INPUT(type=INPUT_MOUSE), INPUT(type=INPUT_MOUSE)
    down.u.mi = MOUSEINPUT(0, 0, 0, MOUSE_LEFTDOWN, 0, 0)
    up.u.mi = MOUSEINPUT(0, 0, 0, MOUSE_LEFTUP, 0, 0)
    return _send([down, up])


def set_clipboard(text):
    """وضع النص في الحافظة مباشرة (بدون تأخير مثل حافظة Tk)."""
    data = (text + "\0").encode("utf-16-le")
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        return bool(user32.SetClipboardData(13, h))  # CF_UNICODETEXT
    finally:
        user32.CloseClipboard()


# ---------------------------------------------------------------- نوافذ
def root_at(x, y):
    """النافذة الرئيسية (الأم العليا) تحت النقطة."""
    hwnd = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    return (user32.GetAncestor(hwnd, 2) or hwnd) if hwnd else None  # GA_ROOT


def root_of(hwnd):
    return (user32.GetAncestor(hwnd, 2) or hwnd) if hwnd else None


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def own_pid():
    return os.getpid()


def window_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def is_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def find_window(title="", cls=""):
    """يبحث عن نافذة ظاهرة: (عنوان+صنف) ثم العنوان ثم الصنف. يتجاهل نوافذ البرنامج نفسه."""
    found = []
    me = own_pid()

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and window_pid(hwnd) != me:
            found.append((hwnd, window_title(hwnd), window_class(hwnd)))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    for test in (lambda t, c: t == title and c == cls and title,
                 lambda t, c: t == title and title,
                 lambda t, c: c == cls and cls):
        for hwnd, t, c in found:
            if test(t, c):
                return hwnd
    return None


def force_foreground(hwnd):
    """إظهار النافذة في المقدمة (مع استعادتها إن كانت مصغّرة) ويرجع True عند النجاح."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.2)
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    tgt = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(tgt and tgt != cur and user32.AttachThreadInput(cur, tgt, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur, tgt, False)
    for _ in range(10):
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------- صلاحيات
def is_admin():
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def hwnd_is_elevated(hwnd):
    """True إذا كانت النافذة تعمل كمسؤول (أو تعذّر فحصها)."""
    try:
        hproc = kernel32.OpenProcess(0x1000, False, window_pid(hwnd))  # QUERY_LIMITED_INFORMATION
        if not hproc:
            return True
        try:
            tok = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(hproc, 0x0008, ctypes.byref(tok)):
                return True
            try:
                elev, ret = wintypes.DWORD(), wintypes.DWORD()
                advapi32.GetTokenInformation(tok, 20, ctypes.byref(elev), 4, ctypes.byref(ret))
                return bool(elev.value)
            finally:
                kernel32.CloseHandle(tok)
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        return False


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe, params = sys.executable, " ".join('"%s"' % a for a in sys.argv)
    return shell32.ShellExecuteW(None, "runas", exe, params, None, 1) > 32


_mutex = None


def single_instance(name="ActivatorHelper_SingleInstance"):
    """False إذا كان هناك نسخة أخرى تعمل."""
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def release_instance():
    global _mutex
    if _mutex:
        kernel32.CloseHandle(_mutex)
        _mutex = None

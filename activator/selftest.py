"""اختبار على ويندوز: كتابة اسم عربي في حقل نصي حقيقي عبر winput."""
import sys
import time
import tkinter as tk

import winput

NAME = "حيدر حاتم محيسن"
results = {}


def run(mode):
    root = tk.Tk()
    root.geometry("400x100+200+200")
    root.attributes("-topmost", True)
    e = tk.Entry(root, font=("Segoe UI", 14))
    e.pack(fill="x", padx=20, pady=30)
    e.insert(0, "old text")

    def go():
        root.update()
        x = e.winfo_rootx() + 30
        y = e.winfo_rooty() + 10
        winput.set_clipboard(NAME)
        winput.click(x, y)
        time.sleep(0.2)
        winput.hotkey(winput.VK_CONTROL, winput.VK_A)
        winput.press(winput.VK_DELETE)
        winput.press(winput.VK_END)
        winput.hotkey(winput.VK_SHIFT, winput.VK_HOME)
        winput.press(winput.VK_DELETE)
        if mode == "paste":
            winput.hotkey(winput.VK_CONTROL, winput.VK_V)
        else:
            winput.type_unicode(NAME)
        root.after(800, finish)

    def finish():
        results[mode] = e.get()
        root.destroy()

    root.after(800, go)
    root.mainloop()


for m in ("type", "paste"):
    run(m)
print(results)
bad = [m for m, v in results.items() if v != NAME]
sys.exit(1 if bad else 0)

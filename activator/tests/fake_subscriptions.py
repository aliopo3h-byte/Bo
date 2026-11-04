"""نافذة تحاكي برنامج الاشتراكات: حقل بحث فيه نص قديم، ويكتب محتواه في ملف عند Enter."""
import json
import sys
import tkinter as tk

out = sys.argv[1]
root = tk.Tk()
root.title("وحدة المشتركين - TEST")
root.geometry("520x220+40+40")
e = tk.Entry(root, font=("Segoe UI", 16), justify="right")
e.pack(fill="x", padx=20, pady=60)
e.insert(0, "حيدر")
e.focus_set()


def on_return(_):
    with open(out + ".result", "w", encoding="utf-8") as f:
        f.write(e.get())


e.bind("<Return>", on_return)


def ready():
    root.update_idletasks()
    with open(out + ".ready", "w") as f:
        json.dump({"x": e.winfo_rootx() + 40, "y": e.winfo_rooty() + 12}, f)


root.after(700, ready)
root.mainloop()

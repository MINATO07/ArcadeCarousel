"""In-game floating credit timer overlay.

Runs in a dedicated process to ensure Tkinter runs on its own main thread,
preventing tcl86t.dll thread conflicts with Pygame while providing a stable,
click-through, topmost timer above all games (including Tekken 8).
"""

import ctypes
import os
import sys
import time
from pathlib import Path
import tkinter as tk

APP_DIR = Path(__file__).resolve().parent
TIMER_FILE = APP_DIR / "credit_timer.txt"

parent_pid = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

def is_parent_alive():
    if not parent_pid:
        return True
    try:
        # Check if parent process is still alive
        handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, parent_pid)
        if not handle:
            return False
        # If WaitForSingleObject with 0 timeout returns WAIT_OBJECT_0 (0), process has terminated
        ret = kernel32.WaitForSingleObject(handle, 0)
        kernel32.CloseHandle(handle)
        return ret != 0
    except Exception:
        return True

root = tk.Tk()
root.title("ArcadeTimerOverlay")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.configure(bg="#010203")

try:
    root.attributes("-transparentcolor", "#010203")
except Exception:
    pass

label = tk.Label(
    root,
    text="INSERT COIN",
    font=("Segoe UI", 18, "bold"),
    fg="#52d3be",
    bg="#010203",
    padx=18,
    pady=10
)
label.pack()
root.update_idletasks()

screen_w = root.winfo_screenwidth()
overlay_width = max(220, label.winfo_reqwidth())
root.geometry(f"{overlay_width}x52+{screen_w - overlay_width - 24}+24")

user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetAncestor.restype = ctypes.c_void_p
hwnd = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
LWA_COLORKEY = 0x00000001

user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetLayeredWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ubyte, ctypes.c_uint]
user32.SetLayeredWindowAttributes.restype = ctypes.c_bool
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
user32.SetWindowLongW(
    hwnd,
    GWL_EXSTYLE,
    style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
)
# Color key matches #010203 (0x00030201)
user32.SetLayeredWindowAttributes(hwnd, 0x00030201, 0, LWA_COLORKEY)

last_text = ""
check_parent_counter = 0

def refresh():
    global last_text, check_parent_counter
    check_parent_counter += 1
    if check_parent_counter % 10 == 0:
        if not is_parent_alive():
            root.destroy()
            sys.exit(0)

    try:
        if TIMER_FILE.exists():
            text = TIMER_FILE.read_text(encoding="utf-8").strip()
            if text and text != last_text:
                last_text = text
                if text == "HIDE":
                    root.withdraw()
                else:
                    root.deiconify()
                    label.configure(text=text)
    except Exception:
        pass

    # Ensure overlay stays topmost above games without stealing focus
    HWND_TOPMOST = ctypes.c_void_p(-1)
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    root.after(200, refresh)

root.after(200, refresh)
root.mainloop()

"""In-game full-screen 2-minute grace period warning overlay.

Runs in a dedicated process to ensure Tkinter runs on its own main thread,
preventing tcl86t.dll thread conflicts with Pygame while providing a stable,
click-through (WS_EX_TRANSPARENT), non-activating (WS_EX_NOACTIVATE), topmost
overlay above all games (including DirectX/exclusive borderless games).
"""

import ctypes
import os
import sys
import time
from pathlib import Path
import tkinter as tk

APP_DIR = Path(__file__).resolve().parent
WARNING_TIMER_FILE = APP_DIR / "warning_timer.txt"

parent_pid = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
duration = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000


def is_parent_alive():
    if not parent_pid:
        return True
    try:
        handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, parent_pid)
        if not handle:
            return False
        ret = kernel32.WaitForSingleObject(handle, 0)
        kernel32.CloseHandle(handle)
        return ret != 0
    except Exception:
        return True


root = tk.Tk()
root.title("ArcadeGraceWarningOverlay")
root.withdraw()
root.overrideredirect(True)
root.attributes("-topmost", True)
try:
    root.attributes("-alpha", 0.78)
except Exception:
    pass

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
root.geometry(f"{screen_w}x{screen_h}+0+0")
root.configure(bg="#050811")

canvas = tk.Canvas(root, width=screen_w, height=screen_h, bg="#050811", highlightthickness=0)
canvas.pack(fill="both", expand=True)

# Top warning hazard stripe
canvas.create_rectangle(0, 0, screen_w, 46, fill="#1a080c", outline="")
canvas.create_line(0, 46, screen_w, 46, fill="#ff3355", width=2)
canvas.create_text(
    screen_w // 2, 23,
    text="⚠️   TIME EXPIRED  —  2-MINUTE GRACE PERIOD RUNNING   ⚠️",
    font=("Segoe UI", 13, "bold"),
    fill="#ff6677"
)

# Bottom guidance bar
canvas.create_rectangle(0, screen_h - 38, screen_w, screen_h, fill="#080e1a", outline="")
canvas.create_line(0, screen_h - 38, screen_w, screen_h - 38, fill="#1e293b", width=1)
canvas.create_text(
    screen_w // 2, screen_h - 19,
    text="CONTROLS REMAIN FULLY ACTIVE  •  INSERT COIN TO KEEP PLAYING  •  GAME CLOSES AT 00:00",
    font=("Segoe UI", 10, "bold"),
    fill="#7dd3fc"
)

# Central Arcade Warning HUD Box
cx = screen_w // 2
cy = screen_h // 2
card_w = min(760, int(screen_w * 0.62))
card_h = min(460, int(screen_h * 0.58))
x1 = cx - card_w // 2
y1 = cy - card_h // 2
x2 = cx + card_w // 2
y2 = cy + card_h // 2

# Card background & glowing border
canvas.create_rectangle(x1, y1, x2, y2, fill="#0b1220", outline="#ff3355", width=3)
canvas.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, fill="", outline="#1e2c47", width=1)

# Header
canvas.create_text(
    cx, y1 + 46,
    text="⚠️  TIME IS UP! INSERT COIN  ⚠️",
    font=("Segoe UI", 22, "bold"),
    fill="#ff3355"
)
canvas.create_text(
    cx, y1 + 78,
    text="Add a coin to keep playing. Game terminates automatically when timer reaches 00:00.",
    font=("Segoe UI", 11),
    fill="#94a3b8"
)

# Big Digital Countdown Timer
clock_id = canvas.create_text(
    cx, y1 + 162,
    text="02:00",
    font=("Consolas", 64, "bold"),
    fill="#ffffff"
)
closing_hint_id = canvas.create_text(
    cx, y1 + 214,
    text="GAME WILL CLOSE IN [ 02:00 ]",
    font=("Segoe UI", 11, "bold"),
    fill="#cbd5e1"
)

# Progress Bar
bar_w = card_w - 140
bar_h = 16
bx1 = cx - bar_w // 2
by1 = y1 + 242
canvas.create_rectangle(bx1, by1, bx1 + bar_w, by1 + bar_h, fill="#162238", outline="#263554")
progress_bar_id = canvas.create_rectangle(bx1, by1, bx1 + bar_w, by1 + bar_h, fill="#f59e0b", outline="")

# Call to Action Button / Banner
btn_w = card_w - 200
btn_h = 52
btn_y = y1 + 316
btn_rect_id = canvas.create_rectangle(
    cx - btn_w // 2, btn_y - btn_h // 2,
    cx + btn_w // 2, btn_y + btn_h // 2,
    fill="#0f1d33", outline="#52d3be", width=2
)
btn_text_id = canvas.create_text(
    cx, btn_y,
    text="🪙   INSERT COIN TO CONTINUE PLAYING   🪙",
    font=("Segoe UI", 15, "bold"),
    fill="#52d3be"
)

# Bottom note inside card
canvas.create_text(
    cx, y1 + 382,
    text="Your controls are still working! Insert coin to remove this screen.",
    font=("Segoe UI", 11),
    fill="#94a3b8"
)

root.update_idletasks()

# Set up Win32 Click-Through, Non-Activating, Topmost Layered Window
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetAncestor.restype = ctypes.c_void_p
hwnd = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint
]

style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
user32.SetWindowLongW(
    hwnd,
    GWL_EXSTYLE,
    style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
)

# Show without activating, so focus stays 100% on the game
SW_SHOWNOACTIVATE = 4
user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)

start_time = time.monotonic()
end_time = start_time + duration
tick_count = 0


def refresh():
    global tick_count
    tick_count += 1

    # Check parent process liveness every 1.5 seconds
    if tick_count % 15 == 0:
        if not is_parent_alive():
            root.destroy()
            sys.exit(0)

    now = time.monotonic()
    remaining = max(0.0, end_time - now)

    mins, secs = divmod(int(remaining + 0.999), 60)
    time_str = f"{mins:02d}:{secs:02d}"

    if remaining <= 0.0:
        canvas.itemconfigure(clock_id, text="00:00", fill="#ff3355")
        canvas.itemconfigure(closing_hint_id, text="CLOSING GAME AND RETURNING TO ARCADE...", fill="#ff3355")
        canvas.coords(progress_bar_id, bx1, by1, bx1, by1 + bar_h)
        if now - end_time > 4.0:
            root.destroy()
            sys.exit(0)
    else:
        # Dynamic color for clock and progress bar
        color = "#f59e0b" if remaining > 60 else "#ff3355"
        canvas.itemconfigure(clock_id, text=time_str, fill="#ffffff" if remaining > 30 else color)
        canvas.itemconfigure(closing_hint_id, text=f"GAME WILL CLOSE IN [ {time_str} ]", fill="#cbd5e1")

        pct = max(0.0, min(1.0, remaining / max(1.0, duration)))
        bar_fill_w = int(bar_w * pct)
        canvas.coords(progress_bar_id, bx1, by1, bx1 + bar_fill_w, by1 + bar_h)
        canvas.itemconfigure(progress_bar_id, fill=color)

    # Flashing / pulsing arcade button glow every 500ms
    if (tick_count // 5) % 2 == 0:
        canvas.itemconfigure(btn_rect_id, outline="#52d3be")
        canvas.itemconfigure(btn_text_id, fill="#52d3be")
    else:
        canvas.itemconfigure(btn_rect_id, outline="#fbbf24")
        canvas.itemconfigure(btn_text_id, fill="#fbbf24")

    # Maintain topmost position above games without stealing focus
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

    root.after(100, refresh)


root.after(100, refresh)
root.mainloop()

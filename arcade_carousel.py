import os
import sys
import math
import subprocess
import ctypes
import threading
import time
import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
GAMES_DIR = APP_DIR / "Games"
SUPPORTED_ART = (".png", ".jpg", ".jpeg", ".webp")

def _handle_exception(exc_type, exc_value, exc_traceback):
    import traceback
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with (APP_DIR / "arcade_error.log").open("a", encoding="utf-8") as f:
            f.write(f"\n--- Crash at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{msg}\n")
    except Exception:
        pass
    try:
        with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as f:
            f.write(f"Arcade Carousel CRASH: {exc_value}\n")
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(None, f"Arcade Carousel Error:\n\n{msg}", "Arcade Carousel Error", 0x10)
    except Exception:
        pass

sys.excepthook = _handle_exception

try:
    _log_file = (APP_DIR / "arcade_debug.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
except Exception:
    pass

def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_admin():
    """Ensure the process runs with administrator privileges (High Integrity Level).

    Required for arcade cabinets and launchers: Windows UIPI blocks standard-user
    processes from detecting keystrokes (GetAsyncKeyState) while games running as
    Administrator (such as Tekken 8, Horizon Zero Dawn, GTA V) have focus.
    """
    if is_elevated():
        return True
    try:
        shell32 = ctypes.windll.shell32
        shell32.ShellExecuteW.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int
        ]
        shell32.ShellExecuteW.restype = ctypes.c_void_p

        python_exe = sys.executable
        script_path = str(Path(__file__).resolve())
        args = subprocess.list2cmdline(sys.argv[1:])
        cmd_line = f'"{script_path}" {args}'.strip()
        ret = shell32.ShellExecuteW(
            None, "runas", python_exe, cmd_line, str(APP_DIR), 1
        )
        if (ret or 0) > 32:
            sys.exit(0)
    except Exception:
        pass
    return False

ensure_admin()

try:
    with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
        _sf.write(f"Arcade Carousel started at {time.strftime('%Y-%m-%d %H:%M:%S')} (Elevated={is_elevated()})\n")
except OSError:
    pass

# Keep SDL joystick state updating while another app (a game) has focus.
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
# Ensure SDL enables XInput driver on Windows
os.environ["SDL_XINPUT_ENABLED"] = "1"
import pygame
import xinput_helper

xinput_poller = xinput_helper.XInputPoller()

# Enable SDL2 GameController subsystem if available in Pygame
try:
    from pygame._sdl2 import controller as sdl2_controller
    sdl2_controller.init()
    has_sdl2_controller = True
except Exception:
    has_sdl2_controller = False

BG = (12, 15, 25)
PANEL = (24, 29, 44)
TEXT = (245, 247, 252)
MUTED = (150, 160, 180)
ACCENT = (82, 211, 190)
ACCENT2 = (123, 109, 255)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.c_void_p
user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
user32.SetActiveWindow.argtypes = [ctypes.c_void_p]
user32.SetFocus.argtypes = [ctypes.c_void_p]
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.IsWindow.argtypes = [ctypes.c_void_p]
user32.IsWindow.restype = ctypes.c_bool
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

# Single-instance check BEFORE creating any window: prevent duplicate processes from fighting for DirectX
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
kernel32.CreateMutexW.restype = ctypes.c_void_p
_single_instance_mutex = kernel32.CreateMutexW(None, True, "SikkaAndSmashArcade_SingleInstanceMutex")
if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    existing_hwnd = user32.FindWindowW(None, "Sikka and Smash Arcade")
    if existing_hwnd:
        user32.ShowWindow(existing_hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(existing_hwnd)
        user32.SetForegroundWindow(existing_hwnd)
    sys.exit(0)

pygame.init()
pygame.joystick.init()
if has_sdl2_controller:
    try:
        sdl2_controller.init()
    except Exception:
        pass
pygame.display.set_caption("Sikka and Smash Arcade")
display_info = pygame.display.Info()
screen_w = display_info.current_w
screen_h = display_info.current_h
is_fullscreen = True
screen = pygame.display.set_mode((screen_w, screen_h), pygame.NOFRAME)
W, H = screen.get_size()
clock = pygame.time.Clock()

wm_info = pygame.display.get_wm_info()
launcher_hwnd = wm_info.get("window") or user32.FindWindowW(None, "Sikka and Smash Arcade")

if launcher_hwnd:
    user32.ShowWindow(launcher_hwnd, 5)  # SW_SHOW
    user32.BringWindowToTop(launcher_hwnd)
    user32.SetForegroundWindow(launcher_hwnd)

startup_focus_until = time.monotonic() + 2.0
next_focus_attempt = 0.0
startup_focus_acquired = False
game_launched = False
game_seen_running = False
game_consecutive_missing = 0
game_launch_time = 0.0
active_game_title = ""
next_game_check_time = 0.0

class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260)]

active_game_pids = set()
active_game_shortcut_path = None

def _compact_name(value):
    return "".join(character.casefold() for character in value
                   if character.isalnum())

def get_game_process_aliases(title, shortcut_path=None):
    """Return a set of compact names for process matching."""
    wanted = _compact_name(title)
    matching = {wanted}
    if "tekken" in wanted:
        matching.update(["tekken", "tekken7", "tekkengame", "tekkengamewin64shipping",
                         "tekken8", "polaris", "polariswin64shipping"])
    elif "gta" in wanted:
        matching.update(["gtav", "gta5", "playgtav", "gtavlauncher"])
    elif "horizon" in wanted:
        matching.update(["horizon", "horizonzerodawn"])
    elif "speed" in wanted or "payback" in wanted or "nfs" in wanted:
        matching.update(["needforspeed", "payback", "nfs", "nfs18", "fitgirllauncher"])
    elif "notepad" in wanted:
        matching.update(["notepad"])

    if shortcut_path:
        try:
            with open(shortcut_path, "rb") as f:
                data = f.read()
            for part in data.split(b"\x00"):
                if b".exe" in part.lower():
                    try:
                        s = part.decode("utf-8", errors="ignore")
                        stem = Path(s).stem
                        if stem:
                            matching.add(_compact_name(stem))
                    except Exception:
                        pass
        except Exception:
            pass
    return matching

def get_game_exe_names(title, shortcut_path=None):
    """Return a set of expected executable image names for taskkill."""
    wanted = _compact_name(title)
    exes = set()
    if "tekken" in wanted:
        exes.update(["Tekken8.exe", "Polaris-Win64-Shipping.exe", "Polaris.exe",
                     "Tekken7.exe", "TekkenGame-Win64-Shipping.exe"])
    elif "gta" in wanted:
        exes.update(["GTA5.exe", "GTAV.exe", "PlayGTAV.exe", "GTAVLauncher.exe"])
    elif "horizon" in wanted:
        exes.update(["HorizonZeroDawn.exe", "Horizon.exe"])
    elif "speed" in wanted or "payback" in wanted or "nfs" in wanted:
        exes.update(["FitGirl-Launcher.exe", "NeedForSpeedPayback.exe", "NFS18.exe"])
    elif "notepad" in wanted:
        exes.update(["notepad.exe"])

    if shortcut_path:
        try:
            with open(shortcut_path, "rb") as f:
                data = f.read()
            for part in data.split(b"\x00"):
                if b".exe" in part.lower():
                    try:
                        s = part.decode("utf-8", errors="ignore")
                        name = Path(s).name
                        if name.lower().endswith(".exe"):
                            exes.add(name)
                    except Exception:
                        pass
        except Exception:
            pass
    return exes

def is_game_running(title, extra_names=None):
    """Check if any process belonging to the launched game is currently running."""
    global active_game_pids, active_game_shortcut_path
    matching = get_game_process_aliases(title, active_game_shortcut_path)
    if extra_names:
        for n in extra_names:
            matching.add(_compact_name(n))

    kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = ctypes.c_bool
    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return False

    found = False
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                pname = _compact_name(Path(entry.szExeFile).stem)
                matched = False
                for m in matching:
                    if m and (m in pname or pname in m):
                        matched = True
                        break
                if matched or (entry.th32ParentProcessID in active_game_pids and entry.th32ParentProcessID != 0):
                    found = True
                    active_game_pids.add(entry.th32ProcessID)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return found

def kill_game(title):
    """Forcefully terminate all processes belonging to the active game and its tree."""
    global active_game_pids, active_game_shortcut_path
    aliases = get_game_process_aliases(title, active_game_shortcut_path)
    exe_names = get_game_exe_names(title, active_game_shortcut_path)

    snapshot_pids = set()
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot and snapshot != ctypes.c_void_p(-1).value:
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                while True:
                    pname = _compact_name(Path(entry.szExeFile).stem)
                    matched = False
                    for a in aliases:
                        if a and (a in pname or pname in a):
                            matched = True
                            break
                    if matched or (entry.th32ParentProcessID in active_game_pids and entry.th32ParentProcessID != 0):
                        snapshot_pids.add(entry.th32ProcessID)
                    if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                        break
        finally:
            kernel32.CloseHandle(snapshot)

    all_pids = active_game_pids.union(snapshot_pids)

    # 1. Terminate all identified PIDs and child trees forcefully
    for pid in all_pids:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=3)
        except Exception:
            pass

    # 2. Terminate by image names
    for exe in exe_names:
        try:
            subprocess.run(["taskkill", "/F", "/IM", exe, "/T"],
                           capture_output=True, timeout=3)
        except Exception:
            pass

    # 3. Direct Win32 TerminateProcess fallback for any stubborn PIDs
    PROCESS_TERMINATE = 0x0001
    for pid in all_pids:
        try:
            h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if h:
                kernel32.TerminateProcess(h, 1)
                kernel32.CloseHandle(h)
        except Exception:
            pass

    try:
        with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
            _sf.write(f"kill_game: terminated '{title}' (PIDs: {all_pids}, Exes: {exe_names}) at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except OSError:
        pass

    active_game_pids.clear()
    active_game_shortcut_path = None

def restore_carousel_window():
    """Bring the arcade carousel launcher back to fullscreen foreground."""
    global launcher_hwnd
    hwnd = launcher_hwnd or user32.FindWindowW(None, "Sikka and Smash Arcade")
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        launcher_hwnd = hwnd

# Credits are process-local. The Coin Mapper configures the input and time amount.
COIN_CONFIG_PATH = APP_DIR / "coin_mapper_config.json"
DEFAULT_COIN_CONFIG = {
    "add_minutes": 10,
    "input": {
        "type": "joy_button", "index": 3, "guid": "", "device_name": "",
        "label": "Triangle / Y",
    },
}

def load_coin_config():
    try:
        with COIN_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
        merged = dict(DEFAULT_COIN_CONFIG)
        merged.update(saved)
        merged["add_minutes"] = max(1, min(1440, int(merged.get("add_minutes", 10))))
        if not isinstance(merged.get("input"), dict):
            merged["input"] = dict(DEFAULT_COIN_CONFIG["input"])
        return merged
    except (OSError, ValueError, TypeError):
        return {**DEFAULT_COIN_CONFIG, "input": dict(DEFAULT_COIN_CONFIG["input"])}

coin_config = load_coin_config()
coin_config_mtime = COIN_CONFIG_PATH.stat().st_mtime if COIN_CONFIG_PATH.exists() else None
credit_until = 0.0
coin_label = "INSERT COIN"
message = ""
message_until = 0
coin_input_down = {}
coin_input_release_since = {}
# -- Subprocess-based coin keyboard hook -----------------------------------
# The keyboard hook now runs in a dedicated subprocess (coin_hook_worker.py)
# to avoid WH_KEYBOARD_LL timeout caused by GIL contention with Pygame.
COIN_SIGNAL_PATH = APP_DIR / "coin_signal.txt"
_coin_hook_process = None
_last_coin_signal = ""
_last_credit_time = 0.0

CREDIT_TIMER_PATH = APP_DIR / "credit_timer.txt"
_credit_overlay_process = None
_last_rendered_coin_label = ""

_warning_overlay_process = None
_warning_active = False
_warning_started_at = 0.0
_warning_duration = 120.0  # 2 minutes grace overlay period

def start_warning_overlay():
    """Launch the 2-minute full-screen click-through warning overlay."""
    global _warning_overlay_process, _warning_active, _warning_started_at
    if _warning_active and _warning_overlay_process and _warning_overlay_process.poll() is None:
        return
    overlay_script = APP_DIR / "warning_overlay.py"
    if not overlay_script.exists():
        return
    _warning_active = True
    _warning_started_at = time.monotonic()
    try:
        # Hide the small credit pill so only the full-screen warning HUD is shown
        try:
            CREDIT_TIMER_PATH.write_text("HIDE", encoding="utf-8")
        except OSError:
            pass
        _warning_overlay_process = subprocess.Popen(
            [sys.executable, str(overlay_script), str(os.getpid()), str(int(_warning_duration))],
            cwd=str(APP_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass

def stop_warning_overlay():
    """Terminate the full-screen warning overlay and restore the credit label."""
    global _warning_overlay_process, _warning_active
    _warning_active = False
    if _warning_overlay_process is not None:
        try:
            _warning_overlay_process.terminate()
            _warning_overlay_process.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                _warning_overlay_process.kill()
            except OSError:
                pass
        _warning_overlay_process = None
    update_credit_timer_file()

def update_credit_timer_file():
    try:
        CREDIT_TIMER_PATH.write_text(coin_label, encoding="utf-8")
    except OSError:
        pass

def start_credit_overlay():
    """Launch the click-through in-game timer overlay in its own process.

    Running as a dedicated process ensures Tkinter executes on its own main thread,
    preventing tcl86t.dll thread crashes with Pygame while keeping the click-through
    timer reliably floating above all games and applications.
    """
    global _credit_overlay_process
    overlay_script = APP_DIR / "credit_overlay.py"
    if not overlay_script.exists():
        return
    update_credit_timer_file()
    try:
        _credit_overlay_process = subprocess.Popen(
            [sys.executable, str(overlay_script), str(os.getpid())],
            cwd=str(APP_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass

def add_credit(source="mapped input"):
    global credit_until, coin_label, message, message_until, _last_credit_time
    # Debounce: both the subprocess and inline GetAsyncKeyState can detect
    # the same key press.  Ignore credits that arrive within 0.3 s of each other.
    now = time.monotonic()
    if now - _last_credit_time < 0.3:
        return
    _last_credit_time = now
    minutes = coin_config["add_minutes"]
    credit_until = max(time.monotonic(), credit_until) + minutes * 60
    if _warning_active:
        stop_warning_overlay()
    remaining = max(0, int(credit_until - time.monotonic() + 0.999))
    credit_minutes, credit_seconds = divmod(remaining, 60)
    coin_label = f"CREDIT  {credit_minutes:02d}:{credit_seconds:02d}"
    update_credit_timer_file()
    message = f"{minutes} minutes added"
    message_until = pygame.time.get_ticks() + 2000
    try:
        foreground = user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(260)
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(ctypes.c_wchar), ctypes.c_int]
        user32.GetWindowTextW(foreground, title, len(title))
        with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as status_file:
            status_file.write(
                f"Credit added at {time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"via {source} ({coin_config.get('input', {}).get('label', 'mapped input')}); "
                f"foreground={title.value!r}\n")
    except Exception:
        pass

def start_coin_hook_worker():
    """Launch the coin key listener in a separate process.

    The standalone process polls GetAsyncKeyState — which reads the
    physical key state directly from the keyboard driver — at ~200 Hz.
    This works unconditionally with all games, including those with
    anti-cheat or running as Administrator (like Tekken 8).  A subprocess keeps
    the polling reliable even when the main Pygame process is busy.
    """
    global _coin_hook_process
    worker_script = APP_DIR / "coin_hook_worker.py"
    if not worker_script.exists():
        try:
            with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as f:
                f.write("coin_hook_worker.py not found; keyboard coin input disabled\n")
        except OSError:
            pass
        return
    try:
        COIN_SIGNAL_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        _coin_hook_process = subprocess.Popen(
            [sys.executable, str(worker_script)],
            cwd=str(APP_DIR),
            # Hide the console window on Windows.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        try:
            with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as f:
                f.write(f"Failed to start coin_hook_worker: {exc}\n")
        except OSError:
            pass


def poll_coin_signal():
    """Check whether the hook worker signalled a new coin key press."""
    global _last_coin_signal
    try:
        content = COIN_SIGNAL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if content and content != _last_coin_signal:
        _last_coin_signal = content
        add_credit("keyboard hook (subprocess)")


# --- Inline GetAsyncKeyState fallback (runs in the main loop) -------------
# Belt-and-suspenders: even if the subprocess has issues, this catches the
# coin key directly from the main process.  GetAsyncKeyState is a single
# fast API call per frame — no hooks, no message pumps.
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
_inline_coin_key_down = False


def poll_coin_key_inline():
    """Detect the mapped coin key via GetAsyncKeyState (main-process fallback)."""
    global _inline_coin_key_down
    mapped = coin_config.get("input", {})
    if mapped.get("type") != "key":
        return
    vk = int(mapped.get("virtual_key", 0) or 0)
    if not vk:
        return
    state = user32.GetAsyncKeyState(vk)
    is_pressed = bool((state & 0x8000) or (state & 0x0001))
    if is_pressed and not _inline_coin_key_down:
        _inline_coin_key_down = True
        add_credit("GetAsyncKeyState (inline)")
    elif not is_pressed:
        _inline_coin_key_down = False


start_coin_hook_worker()

def credit_text():
    remaining = max(0, int(credit_until - time.monotonic() + 0.999))
    if remaining == 0:
        return "INSERT COIN"
    minutes, seconds = divmod(remaining, 60)
    return f"CREDIT  {minutes:02d}:{seconds:02d}"

_font_cache = {}

def font(size, bold=False):
    size = int(size)
    key = (size, bool(bold))
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("segoeui", size, bold=bold)
    return _font_cache[key]

def scan_games():
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    games = []
    # Each Windows shortcut in Games is a launchable game.
    for shortcut in GAMES_DIR.iterdir():
        if shortcut.is_file() and shortcut.suffix.lower() == ".lnk":
            art = None
            for ext in SUPPORTED_ART:
                candidate = shortcut.with_suffix(ext)
                if candidate.exists():
                    art = candidate
                    break
            title = shortcut.stem.replace("_", " ").replace("-", " ")
            games.append({"title": title, "path": shortcut, "art": art})
    return sorted(games, key=lambda x: x["title"].casefold())

def load_art(path, size):
    if not path:
        return None
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        iw, ih = image.get_size()
        scale = min(size[0] / max(iw, 1), size[1] / max(ih, 1))
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        image = pygame.transform.smoothscale(image, (nw, nh))
        canvas = pygame.Surface(size, pygame.SRCALPHA)
        canvas.blit(image, ((size[0]-nw)//2, (size[1]-nh)//2))
        return canvas
    except Exception:
        return None

def gradient_background():
    # Subtle dark blue vertical gradient.
    surf = pygame.Surface((W, H))
    for y in range(H):
        t = y / max(H, 1)
        col = (int(10 + 9*t), int(13 + 8*t), int(25 + 13*t))
        pygame.draw.line(surf, col, (0, y), (W, y))
    return surf

background = gradient_background()

def rounded_rect(surface, color, rect, radius=20, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, border, border_radius=radius)

def draw_text(surface, text, fnt, color, pos, anchor="topleft"):
    img = fnt.render(text, True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)
    return rect

def gamepad_hint(surface, label, x, y):
    pygame.draw.circle(surface, (55, 65, 88), (x, y), 15)
    draw_text(surface, label, font(15, True), TEXT, (x, y), "center")

games = scan_games()
selected = 0
last_scan = pygame.time.get_ticks()
last_coin_config_scan = 0
art_cache = {}
running = True
exit_reason = "none"
message = "Add .lnk shortcuts to the Games folder"
message_until = pygame.time.get_ticks() + 5000
joysticks = {}
sdl2_controllers = {}

def open_joystick(device_index):
    """Initialize and retain a joystick and game controller so Pygame delivers its input events."""
    try:
        joystick = pygame.joystick.Joystick(device_index)
        joystick.init()
        joysticks[joystick.get_instance_id()] = joystick

        if has_sdl2_controller and sdl2_controller.is_controller(device_index):
            try:
                gc = sdl2_controller.Controller(device_index)
                gc.init()
                sdl2_controllers[gc.id] = gc
            except Exception:
                pass
        return joystick
    except pygame.error:
        return None

# Devices connected before the launcher starts do not produce JOYDEVICEADDED.
for device_index in range(pygame.joystick.get_count()):
    open_joystick(device_index)

def nav_prev():
    global selected
    if games:
        selected = (selected - 1) % len(games)

def nav_next():
    global selected
    if games:
        selected = (selected + 1) % len(games)

def nav_jump_prev(step=5):
    global selected
    if games:
        selected = (selected - step) % len(games)

def nav_jump_next(step=5):
    global selected
    if games:
        selected = (selected + step) % len(games)

def reload_coin_config_if_changed():
    global coin_config, coin_config_mtime
    try:
        mtime = COIN_CONFIG_PATH.stat().st_mtime
    except OSError:
        mtime = None
    if mtime != coin_config_mtime:
        coin_config = load_coin_config()
        coin_config_mtime = mtime
        coin_input_down.clear()
        coin_input_release_since.clear()

def joystick_matches_coin_input(joystick):
    config_input = coin_config["input"]
    guid = config_input.get("guid", "")
    name = config_input.get("device_name", "")
    try:
        if guid and joystick.get_guid().casefold() != guid.casefold():
            return False
        if not guid and name and joystick.get_name() != name:
            return False
        return True
    except pygame.error:
        return False

def joystick_coin_input_down(joystick, was_down=False):
    config_input = coin_config["input"]
    input_type = config_input.get("type")
    try:
        if input_type == "joy_button":
            index = int(config_input["index"])
            return index < joystick.get_numbuttons() and bool(joystick.get_button(index))
        if input_type == "joy_axis":
            index = int(config_input["index"])
            if index >= joystick.get_numaxes():
                return False
            value = joystick.get_axis(index)
            direction = int(config_input.get("direction", 1))
            threshold = 0.45 if was_down else 0.65
            return value >= threshold if direction > 0 else value <= -threshold
        if input_type == "joy_hat":
            index = int(config_input["index"])
            value = tuple(config_input.get("value", (0, 0)))
            return index < joystick.get_numhats() and tuple(joystick.get_hat(index)) == value
    except (KeyError, ValueError, IndexError, pygame.error):
        return False
    return False

def poll_coin_input():
    """Poll mapped controller input, including while the game has focus."""
    config_input = coin_config["input"]
    active_sources = set()
    input_type = config_input.get("type")

    # 1. Native XInput check (works in background even during games like Tekken 8):
    if input_type == "xinput_button":
        u_idx = int(config_input.get("user_index", 0))
        bit = int(config_input.get("button_mask", 0))
        if xinput_helper.is_button_down(u_idx, bit):
            active_sources.add(f"xinput:{u_idx}:{bit}")
    elif input_type == "xinput_trigger":
        u_idx = int(config_input.get("user_index", 0))
        trig = str(config_input.get("trigger", "lt"))
        if xinput_helper.is_trigger_down(u_idx, trig):
            active_sources.add(f"xinput_trig:{u_idx}:{trig}")
    elif input_type not in ("key",):
        # 2. DirectInput, HID, and standard SDL joysticks
        for instance_id, joystick in list(joysticks.items()):
            source = f"joystick:{instance_id}"
            if (joystick_matches_coin_input(joystick)
                    and joystick_coin_input_down(joystick, coin_input_down.get(source, False))):
                active_sources.add(source)

    now = time.monotonic()
    for source in active_sources:
        coin_input_release_since.pop(source, None)
        if not coin_input_down.get(source, False):
            add_credit("controller (" + config_input.get("label", "mapped input") + ")")
            coin_input_down[source] = True
    # Require a short, continuous release before rearming. SDL can report
    # transient up/down edges while a controller button or stick is held.
    for source, is_down in tuple(coin_input_down.items()):
        if is_down and source not in active_sources:
            released_at = coin_input_release_since.setdefault(source, now)
            if now - released_at >= 0.15:
                coin_input_down[source] = False
                coin_input_release_since.pop(source, None)

def key_event_matches_coin_input(event):
    config_input = coin_config["input"]
    if config_input.get("type") != "key":
        return False
    expected = str(config_input.get("key_name", "")).casefold()
    actual = pygame.key.name(event.key).casefold()
    return bool(expected and actual == expected)

def joystick_event_matches_coin_input(event):
    config_input = coin_config["input"]
    input_type = config_input.get("type")
    if input_type not in ("joy_button", "joy_axis", "joy_hat"):
        return False
    joystick = joysticks.get(getattr(event, "instance_id", None))
    if joystick is None or not joystick_matches_coin_input(joystick):
        return False
    try:
        if input_type == "joy_button":
            return event.type == pygame.JOYBUTTONDOWN and event.button == int(config_input["index"])
        if input_type == "joy_axis":
            return (event.type == pygame.JOYAXISMOTION
                    and event.axis == int(config_input["index"])
                    and ((int(config_input.get("direction", 1)) > 0 and event.value >= 0.65)
                         or (int(config_input.get("direction", 1)) < 0 and event.value <= -0.65)))
        return (event.type == pygame.JOYHATMOTION
                and event.hat == int(config_input["index"])
                and tuple(event.value) == tuple(config_input.get("value", (0, 0))))
    except (KeyError, ValueError, AttributeError):
        return False

def launch_game(game):
    global message, message_until, game_launched, game_launch_time
    global active_game_title, next_game_check_time, game_seen_running, game_consecutive_missing
    global active_game_shortcut_path, active_game_pids
    if game_launched:
        return
    if credit_until <= time.monotonic():
        message = "INSERT COIN TO PLAY"
        message_until = pygame.time.get_ticks() + 3000
        return
    stop_warning_overlay()
    game_launched = True
    game_seen_running = False
    game_consecutive_missing = 0
    game_launch_time = time.monotonic()
    active_game_title = game["title"]
    active_game_shortcut_path = game.get("path")
    active_game_pids.clear()
    next_game_check_time = game_launch_time + 1.0
    try:
        os.startfile(str(game["path"]))
        message = "Launching " + game["title"]
        try:
            with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
                _sf.write(f"Game launched: {active_game_title} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except OSError:
            pass
        # Minimize the carousel window so the game gets full screen & DirectX GPU access!
        if launcher_hwnd:
            user32.ShowWindow(launcher_hwnd, 6)  # SW_MINIMIZE
    except Exception as exc:
        game_launched = False
        message = "Could not launch: " + str(exc)
        restore_carousel_window()
    message_until = pygame.time.get_ticks() + 3000

def refresh():
    global games, selected, art_cache
    old = games[selected]["path"].name if games and selected < len(games) else None
    games = scan_games()
    selected = next((i for i, g in enumerate(games) if g["path"].name == old), 0)
    art_cache = {}

def controller_event(event):
    global selected, message, message_until, running, exit_reason
    if game_launched or not games:
        return

    # 1. Operator Exit buttons:
    # Standard joystick Button 1 (B / Circle)
    if event.type == pygame.JOYBUTTONDOWN and event.button in (1,):
        exit_reason = "controller button B"
        running = False
        return

    # SDL2 GameController B button
    if has_sdl2_controller and event.type == getattr(pygame, "CONTROLLERBUTTONDOWN", -1):
        if event.button == getattr(pygame, "CONTROLLER_BUTTON_B", 1):
            exit_reason = "GameController button B"
            running = False
            return

    # UI controls are active ONLY while credit remains!
    if credit_until <= time.monotonic():
        return

    # 2. SDL2 GameController Events (Standardized layout across XInput/Xbox/PS4/PS5/Switch)
    if has_sdl2_controller:
        if event.type == getattr(pygame, "CONTROLLERBUTTONDOWN", -1):
            btn = event.button
            # A (0) or Start (6) -> Launch game!
            if btn in (getattr(pygame, "CONTROLLER_BUTTON_A", 0), getattr(pygame, "CONTROLLER_BUTTON_START", 6)):
                launch_game(games[selected])
                return
            # D-Pad Left (13) or D-Pad Up (11) -> Previous
            elif btn in (getattr(pygame, "CONTROLLER_BUTTON_DPAD_LEFT", 13), getattr(pygame, "CONTROLLER_BUTTON_DPAD_UP", 11)):
                nav_prev()
                return
            # D-Pad Right (14) or D-Pad Down (12) -> Next
            elif btn in (getattr(pygame, "CONTROLLER_BUTTON_DPAD_RIGHT", 14), getattr(pygame, "CONTROLLER_BUTTON_DPAD_DOWN", 12)):
                nav_next()
                return
            # Left Bumper (9) -> Quick jump 5 backward
            elif btn == getattr(pygame, "CONTROLLER_BUTTON_LEFTSHOULDER", 9):
                nav_jump_prev(5)
                return
            # Right Bumper (10) -> Quick jump 5 forward
            elif btn == getattr(pygame, "CONTROLLER_BUTTON_RIGHTSHOULDER", 10):
                nav_jump_next(5)
                return
            # Back (4) -> Refresh
            elif btn == getattr(pygame, "CONTROLLER_BUTTON_BACK", 4):
                refresh()
                return

        elif event.type == getattr(pygame, "CONTROLLERAXISMOTION", -1):
            now = pygame.time.get_ticks()
            if not hasattr(controller_event, "axis_time") or now - controller_event.axis_time > 200:
                val = event.value
                axis = event.axis
                leftx = getattr(pygame, "CONTROLLER_AXIS_LEFTX", 0)
                rightx = getattr(pygame, "CONTROLLER_AXIS_RIGHTX", 2)
                lefty = getattr(pygame, "CONTROLLER_AXIS_LEFTY", 1)
                righty = getattr(pygame, "CONTROLLER_AXIS_RIGHTY", 3)

                # Horizontal sticks
                if axis in (leftx, rightx):
                    if val > 16000:
                        nav_next()
                        controller_event.axis_time = now
                    elif val < -16000:
                        nav_prev()
                        controller_event.axis_time = now
                # Vertical sticks (Up = prev, Down = next)
                elif axis in (lefty, righty):
                    if val > 16000:
                        nav_next()
                        controller_event.axis_time = now
                    elif val < -16000:
                        nav_prev()
                        controller_event.axis_time = now
            return

    # 3. DirectInput, HID, and Standard Joystick Events
    if event.type == pygame.JOYHATMOTION:
        x, y = event.value
        if x < 0 or y > 0:
            nav_prev()
        elif x > 0 or y < 0:
            nav_next()

    elif event.type == pygame.JOYBUTTONDOWN:
        # Button 0 (A / Cross), Button 7 (Start on XInput), Button 9 (1P Start on Arcade encoder)
        if event.button in (0, 7, 9):
            launch_game(games[selected])
        elif event.button in (4,):  # Left Bumper (LB)
            nav_jump_prev(5)
        elif event.button in (5,):  # Right Bumper (RB)
            nav_jump_next(5)
        elif event.button in (6, 8):  # Back / Select
            refresh()
        elif event.button in (11, 13):  # D-pad Left / Up on some arcade encoders
            nav_prev()
        elif event.button in (12, 14):  # D-pad Right / Down on some arcade encoders
            nav_next()

    elif event.type == pygame.JOYAXISMOTION and abs(event.value) >= 0.65:
        now = pygame.time.get_ticks()
        if not hasattr(controller_event, "axis_time") or now - controller_event.axis_time > 200:
            joystick = joysticks.get(getattr(event, "instance_id", None))
            numaxes = joystick.get_numaxes() if joystick else 4
            # On 6-axis controllers (like XInput), axes 2 & 5 are analog triggers (LT / RT), NOT sticks!
            if numaxes >= 6:
                if event.axis in (0, 3):  # Left Stick X or Right Stick X
                    if event.value > 0: nav_next()
                    else: nav_prev()
                    controller_event.axis_time = now
                elif event.axis in (1, 4):  # Left Stick Y or Right Stick Y
                    if event.value > 0: nav_next()
                    else: nav_prev()
                    controller_event.axis_time = now
            else:
                # DirectInput 2-axis or 4-axis gamepads
                if event.axis in (0, 2):
                    if event.value > 0: nav_next()
                    else: nav_prev()
                    controller_event.axis_time = now
                elif event.axis in (1,):
                    if event.value > 0: nav_next()
                    else: nav_prev()
                    controller_event.axis_time = now

def poll_xinput_hardware():
    """Poll direct Windows XInput hardware for Xbox 360, Xbox One, Xbox Series, and compatible controllers."""
    global selected, running, exit_reason
    if not xinput_helper.is_available():
        return

    for event_name, user_index, data in xinput_poller.poll():
        # 1. Coin check for XInput (works both in carousel and while game is running)
        config_input = coin_config.get("input", {})
        if config_input.get("type") == "xinput_button":
            target_slot = int(config_input.get("user_index", 0))
            target_mask = int(config_input.get("button_mask", 0))
            if event_name == "button_down" and user_index == target_slot and data == target_mask:
                add_credit(f"XInput #{user_index + 1} {config_input.get('label', 'button')}")
                continue
        elif config_input.get("type") == "xinput_trigger":
            target_slot = int(config_input.get("user_index", 0))
            target_trig = str(config_input.get("trigger", "lt"))
            if event_name == "trigger_down" and user_index == target_slot and data == target_trig:
                add_credit(f"XInput #{user_index + 1} Trigger ({target_trig.upper()})")
                continue

        # 2. Carousel UI navigation (only active when game is not launched and credit remains)
        if game_launched or not games:
            continue
        if credit_until <= time.monotonic():
            continue

        if event_name == "button_down":
            if data in (xinput_helper.XINPUT_GAMEPAD_A, xinput_helper.XINPUT_GAMEPAD_START):
                launch_game(games[selected])
            elif data == xinput_helper.XINPUT_GAMEPAD_B:
                exit_reason = "XInput B button"
                running = False
            elif data == xinput_helper.XINPUT_GAMEPAD_LEFT_SHOULDER:
                nav_jump_prev(5)
            elif data == xinput_helper.XINPUT_GAMEPAD_RIGHT_SHOULDER:
                nav_jump_next(5)
            elif data == xinput_helper.XINPUT_GAMEPAD_BACK:
                refresh()
        elif event_name in ("nav_left", "nav_up"):
            nav_prev()
        elif event_name in ("nav_right", "nav_down"):
            nav_next()

start_credit_overlay()

while running:
    now = pygame.time.get_ticks()
    monotonic_now = time.monotonic()
    if now - last_coin_config_scan > 500:
        reload_coin_config_if_changed()
        last_coin_config_scan = now
    coin_label = credit_text()
    if coin_label != _last_rendered_coin_label:
        _last_rendered_coin_label = coin_label
        update_credit_timer_file()

    if game_launched:
        # A game is actively running!
        # Coin inputs are continuously detected everywhere (including inside Tekken 8):
        poll_xinput_hardware()
        poll_coin_input()
        poll_coin_signal()
        poll_coin_key_inline()

        # Discard carousel input events while game is running
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit_reason = "pygame.QUIT"
                running = False

        # --- TIMER EXPIRATION & 2-MINUTE GRACE OVERLAY LOGIC ---
        if monotonic_now >= credit_until:
            # Credit timer has ended while game is running!
            if not _warning_active:
                # Trigger full-screen 2-minute overlay without stopping player input!
                start_warning_overlay()
            else:
                # Warning overlay is already active; check if the 2 minutes have expired
                if monotonic_now - _warning_started_at >= _warning_duration:
                    try:
                        with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
                            _sf.write(f"Grace timer (2 mins) expired without coin. Killing game '{active_game_title}' at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    except OSError:
                        pass
                    stop_warning_overlay()
                    kill_game(active_game_title)
                    game_launched = False
                    active_game_title = ""
                    game_seen_running = False
                    game_consecutive_missing = 0
                    message = "TIME EXPIRED — GAME CLOSED"
                    message_until = pygame.time.get_ticks() + 4000
                    restore_carousel_window()
                    continue
        else:
            # Credit is active / coin was inserted
            if _warning_active:
                stop_warning_overlay()

        # Periodically check if the game is still alive:
        if monotonic_now >= next_game_check_time:
            next_game_check_time = monotonic_now + 1.0
            is_running = is_game_running(active_game_title)
            if is_running:
                game_seen_running = True
                game_consecutive_missing = 0
            else:
                if game_seen_running:
                    game_consecutive_missing += 1
                    # Require 3 consecutive checks (~3 seconds) where process is absent before concluding game exited
                    if game_consecutive_missing >= 3:
                        game_launched = False
                        stop_warning_overlay()
                        try:
                            with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
                                _sf.write(f"Game exited: {active_game_title} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        except OSError:
                            pass
                        restore_carousel_window()
                else:
                    # Allow up to 45s grace period after launch for heavy games (Tekken 8, GTA V) to load
                    if monotonic_now - game_launch_time > 45.0:
                        game_launched = False
                        stop_warning_overlay()
                        message = f"{active_game_title} closed or failed to start"
                        message_until = pygame.time.get_ticks() + 4000
                        restore_carousel_window()

        clock.tick(20)
        continue

    # Normal carousel browsing mode (game is NOT running)
    if not startup_focus_acquired and monotonic_now < startup_focus_until:
        if launcher_hwnd:
            if user32.GetForegroundWindow() == launcher_hwnd:
                startup_focus_acquired = True
            elif monotonic_now >= next_focus_attempt:
                user32.ShowWindow(launcher_hwnd, 5)
                user32.BringWindowToTop(launcher_hwnd)
                user32.SetForegroundWindow(launcher_hwnd)
                next_focus_attempt = monotonic_now + 0.5

    events = pygame.event.get()
    poll_xinput_hardware()
    poll_coin_input()
    poll_coin_signal()
    poll_coin_key_inline()
    for event in events:
        if event.type == pygame.QUIT:
            exit_reason = "pygame.QUIT"
            running = False
        elif event.type == pygame.KEYDOWN:
            if key_event_matches_coin_input(event):
                continue
            if event.key in (pygame.K_ESCAPE,):
                exit_reason = f"key {event.key}"
                running = False
                continue
            elif event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    screen = pygame.display.set_mode((screen_w, screen_h), pygame.NOFRAME)
                else:
                    win_w = min(1280, int(screen_w * 0.8))
                    win_h = min(720, int(screen_h * 0.8))
                    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                W, H = screen.get_size()
                background = gradient_background()
                art_cache.clear()
                continue

            # UI controls are active ONLY while credit remains!
            if credit_until <= monotonic_now:
                continue

            if event.key in (pygame.K_RIGHT, pygame.K_d):
                if games: selected = (selected + 1) % len(games)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if games: selected = (selected - 1) % len(games)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if games: launch_game(games[selected])
            elif event.key == pygame.K_F5:
                refresh()
        elif event.type in (
            pygame.JOYHATMOTION, pygame.JOYBUTTONDOWN, pygame.JOYAXISMOTION,
            getattr(pygame, "CONTROLLERBUTTONDOWN", -999),
            getattr(pygame, "CONTROLLERAXISMOTION", -998),
        ):
            if joystick_event_matches_coin_input(event):
                source = f"joystick:{getattr(event, 'instance_id', 0)}"
                if not coin_input_down.get(source, False):
                    add_credit()
                coin_input_down[source] = True
                coin_input_release_since.pop(source, None)
                continue
            controller_event(event)
        elif event.type in (pygame.JOYDEVICEADDED, getattr(pygame, "CONTROLLERDEVICEADDED", -997)):
            open_joystick(getattr(event, "device_index", 0))
        elif event.type in (pygame.JOYDEVICEREMOVED, getattr(pygame, "CONTROLLERDEVICEREMOVED", -996)):
            inst_id = getattr(event, "instance_id", None)
            if inst_id is not None:
                joysticks.pop(inst_id, None)
                sdl2_controllers.pop(inst_id, None)
                coin_input_down.pop(f"joystick:{inst_id}", None)
                coin_input_release_since.pop(f"joystick:{inst_id}", None)
    if now - last_scan > 2500:
        refresh()
        last_scan = now

    screen.blit(background, (0, 0))
    # Header
    brand_font = font(max(22, H//32), True)
    brand_x, brand_y = int(W*.065), int(H*.055)
    brand_name = "SIKKA AND SMASH"
    draw_text(screen, brand_name, brand_font, ACCENT, (brand_x, brand_y))
    draw_text(screen, "ARCADE", brand_font, TEXT,
              (brand_x + brand_font.size(brand_name + " ")[0], brand_y))
    draw_text(screen, "YOUR LIBRARY", font(max(13, H//75), True), MUTED, (int(W*.067), int(H*.115)))
    pygame.draw.line(screen, (43, 50, 70), (int(W*.065), int(H*.16)), (int(W*.935), int(H*.16)), 2)

    center_y = int(H * .49)
    card_w = int(min(W*.28, H*.43))
    card_h = int(H*.49)
    gap = int(card_w*.12)
    center_x = W//2

    if not games:
        rounded_rect(screen, PANEL, (int(W*.25), int(H*.29), int(W*.5), int(H*.38)), 26, 1, (48, 57, 80))
        draw_text(screen, "YOUR NEXT GAME STARTS HERE", font(max(20,H//36), True), TEXT, (center_x, int(H*.39)), "center")
        draw_text(screen, "Drop Windows .lnk shortcuts into the Games folder.", font(max(15,H//58)), MUTED, (center_x, int(H*.47)), "center")
        draw_text(screen, "Optional artwork: same filename + .png / .jpg / .jpeg", font(max(13,H//68)), MUTED, (center_x, int(H*.52)), "center")
        draw_text(screen, "The library refreshes automatically.", font(max(13,H//68)), ACCENT, (center_x, int(H*.57)), "center")
    else:
        # Render the selected card and its neighbors as a horizontal carousel.
        for offset in (-2, -1, 0, 1, 2):
            idx = (selected + offset) % len(games)
            game = games[idx]
            x = center_x + offset*(card_w+gap) - card_w//2
            y = center_y - card_h//2 + (18 if offset else 0)
            w = card_w if offset == 0 else int(card_w*.83)
            h = card_h if offset == 0 else int(card_h*.83)
            x = center_x + offset*(card_w+gap) - w//2
            y = center_y - h//2 + (18 if offset else 0)
            if x + w < 0 or x > W: continue
            rect = pygame.Rect(x, y, w, h)
            selected_card = offset == 0
            shade = (29, 36, 55) if selected_card else (20, 25, 39)
            rounded_rect(screen, shade, rect, 24, 3 if selected_card else 1,
                         ACCENT if selected_card else (45, 52, 73))
            inner = rect.inflate(-14, -14)
            rounded_rect(screen, (15, 19, 30), inner, 18)
            art = game["art"]
            cache_key = str(art) if art else ""
            if cache_key not in art_cache:
                art_cache[cache_key] = load_art(art, (inner.width-10, int(inner.height*.76))) if art else None
            art_img = art_cache.get(cache_key)
            if art_img:
                art_rect = art_img.get_rect(center=(inner.centerx, inner.y + int(inner.height*.40)))
                screen.blit(art_img, art_rect)
            else:
                # Stylish placeholder tile.
                cx, cy = inner.centerx, inner.y + int(inner.height*.37)
                pygame.draw.circle(screen, (38, 48, 77), (cx, cy), int(min(w,h)*.19))
                pygame.draw.circle(screen, ACCENT2, (cx, cy), int(min(w,h)*.13), 3)
                pygame.draw.polygon(screen, ACCENT, [(cx-10,cy-18),(cx-10,cy+18),(cx+18,cy)], 0)
            title = game["title"]
            title_font = font(max(15, int(H*.027)), True) if selected_card else font(max(13, int(H*.022)), True)
            max_title_w = inner.width - 24
            while title_font.size(title)[0] > max_title_w and title_font.get_height() > 12:
                title_font = font(title_font.get_height()-1, True)
            draw_text(screen, title, title_font, TEXT if selected_card else MUTED,
                      (inner.centerx, inner.bottom-int(inner.height*.14)), "center")
            if selected_card:
                rounded_rect(screen, ACCENT, (inner.centerx-48, inner.bottom-15, 96, 4), 2)

        draw_text(screen, f"{selected+1:02d}  /  {len(games):02d}", font(max(15,H//60), True), MUTED,
                  (center_x, int(H*.80)), "center")

    # Footer controls
    footer_y = int(H*.90)
    pygame.draw.line(screen, (43, 50, 70), (int(W*.065), footer_y-25), (int(W*.935), footer_y-25), 1)
    gamepad_hint(screen, "◀", int(W*.075), footer_y+3)
    draw_text(screen, "PREVIOUS", font(max(12,H//75), True), MUTED, (int(W*.095), footer_y+3), "midleft")
    gamepad_hint(screen, "▶", int(W*.205), footer_y+3)
    draw_text(screen, "NEXT", font(max(12,H//75), True), MUTED, (int(W*.225), footer_y+3), "midleft")
    rounded_rect(screen, (37, 47, 66), (int(W*.37), footer_y-18, int(W*.26), 38), 18, 1, (70, 84, 110))
    draw_text(screen, "A / START   PLAY GAME", font(max(13,H//68), True), ACCENT, (center_x, footer_y+1), "center")
    draw_text(screen, "B  BACK / EXIT", font(max(12,H//75), True), MUTED, (int(W*.935), footer_y+3), "midright")
    if now < message_until and message:
        draw_text(screen, message, font(max(12,H//75)), ACCENT, (center_x, int(H*.845)), "center")
    draw_text(screen, coin_label, font(max(14, H//65), True), ACCENT,
              (int(W*.935), int(H*.055)), "topright")

    pygame.display.flip()
    clock.tick(60)

try:
    with (APP_DIR / "coin_input_status.txt").open("a", encoding="utf-8") as _sf:
        _sf.write(f"Arcade Carousel exited main loop! running={running}, exit_reason={exit_reason}\n")
except Exception:
    pass

# Terminate the coin hook worker before exiting.
if _coin_hook_process is not None:
    try:
        _coin_hook_process.terminate()
        _coin_hook_process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            _coin_hook_process.kill()
        except OSError:
            pass

# Terminate the floating credit overlay before exiting.
if _credit_overlay_process is not None:
    try:
        _credit_overlay_process.terminate()
        _credit_overlay_process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        try:
            _credit_overlay_process.kill()
        except OSError:
            pass

# Terminate the full-screen warning overlay before exiting.
if _warning_overlay_process is not None:
    try:
        _warning_overlay_process.terminate()
        _warning_overlay_process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        try:
            _warning_overlay_process.kill()
        except OSError:
            pass

try:
    CREDIT_TIMER_PATH.unlink(missing_ok=True)
except OSError:
    pass

# Clean up the signal file so stale data does not trigger credits next launch.
try:
    COIN_SIGNAL_PATH.unlink(missing_ok=True)
except OSError:
    pass
if _single_instance_mutex:
    try:
        kernel32.CloseHandle(_single_instance_mutex)
    except Exception:
        pass
pygame.quit()
sys.exit(0)

"""Standalone coin-key listener that runs in its own process.

Uses GetAsyncKeyState polling. Runs with administrator privileges (High Integrity)
so that it can read key state across all windows on the system, including games
that run as Administrator (such as Tekken 8, Horizon Zero Dawn, GTA V) which
Windows UIPI blocks non-admin processes from inspecting.
"""

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "coin_mapper_config.json"
SIGNAL_PATH = APP_DIR / "coin_signal.txt"
STATUS_PATH = APP_DIR / "coin_input_status.txt"

user32 = ctypes.windll.user32
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin():
    """Relaunch as administrator if not already elevated."""
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


def load_config():
    """Return the virtual-key code of the mapped coin key, or 0."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        inp = cfg.get("input", {})
        if inp.get("type") == "key":
            return int(inp.get("virtual_key", 0) or 0)
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return 0


def _log(text):
    try:
        with STATUS_PATH.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def main():
    try:
        ensure_admin()
        expected_vk = load_config()
        elevated_str = "Elevated=True" if is_elevated() else "Elevated=False"
        if not expected_vk:
            _log(f"[coin_hook_worker] No keyboard coin key configured; exiting ({elevated_str})")
            sys.exit(0)

        config_mtime = None
        try:
            config_mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            pass

        key_is_down = False
        _log(f"[coin_hook_worker] Polling GetAsyncKeyState for VK 0x{expected_vk:02X} ({elevated_str})")

        while True:
            # Reload config if the file changed.
            try:
                mt = CONFIG_PATH.stat().st_mtime
            except OSError:
                mt = None
            if mt != config_mtime:
                config_mtime = mt
                expected_vk = load_config()
                key_is_down = False
                if not expected_vk:
                    _log("[coin_hook_worker] Coin key cleared; sleeping")
                    time.sleep(2)
                    continue

            # GetAsyncKeyState returns a SHORT.
            # Bit 15 (0x8000) is set if the key is currently down.
            # Bit 0 (0x0001) is set if the key was pressed since previous call.
            state = user32.GetAsyncKeyState(expected_vk)
            is_pressed = bool((state & 0x8000) or (state & 0x0001))

            if is_pressed and not key_is_down:
                key_is_down = True
                try:
                    SIGNAL_PATH.write_text(str(time.monotonic()), encoding="utf-8")
                except OSError:
                    pass
            elif not is_pressed:
                key_is_down = False

            time.sleep(0.005)
    except Exception as exc:
        import traceback
        _log(f"[coin_hook_worker] Crash: {exc}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()

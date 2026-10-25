"""Configure the insert-coin input and the number of minutes it adds."""

import json
import os
import sys
import ctypes
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import xinput_helper

APP_DIR = Path(__file__).resolve().parent

def is_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_admin():
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

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
import pygame

CONFIG_PATH = APP_DIR / "coin_mapper_config.json"
DEFAULT_CONFIG = {
    "add_minutes": 10,
    "input": {
        "type": "joy_button", "index": 3, "guid": "", "device_name": "",
        "label": "Triangle / Y",
    },
}


def read_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        result = dict(DEFAULT_CONFIG)
        result.update(saved)
        if not isinstance(result.get("input"), dict):
            result["input"] = dict(DEFAULT_CONFIG["input"])
        result["add_minutes"] = max(1, min(1440, int(result.get("add_minutes", 10))))
        return result
    except (OSError, ValueError, TypeError):
        return {**DEFAULT_CONFIG, "input": dict(DEFAULT_CONFIG["input"])}


def write_config(config):
    temporary = CONFIG_PATH.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)
    temporary.replace(CONFIG_PATH)


class CoinMapper:
    def __init__(self, root):
        self.root = root
        self.settings = read_config()
        self.mapping = dict(self.settings["input"])
        self.minutes = tk.StringVar(value=str(self.settings["add_minutes"]))
        self.mapping_text = tk.StringVar(value=self.mapping.get("label", "Not mapped"))
        self.status = tk.StringVar(value="Settings apply to the launcher automatically.")
        self.capturing = False
        self.previous_controls = {}
        self.joysticks = {}
        self.device_indices = {}

        root.title("Sikka and Smash — Coin Mapper")
        root.resizable(False, False)
        root.configure(bg="#101522")
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#101522")
        style.configure("TLabel", background="#101522", foreground="#eef2fa",
                        font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"), foreground="#52d3be")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("TEntry", padding=6)

        frame = ttk.Frame(root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="COIN INPUT", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        ttk.Label(frame, text="Choose the input that adds time to the arcade.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 18)
        )
        ttk.Label(frame, text="Time added per press (minutes)").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.minutes_box = ttk.Spinbox(frame, from_=1, to=1440, width=8,
                                       textvariable=self.minutes)
        self.minutes_box.grid(row=2, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=5)

        ttk.Label(frame, text="Insert coin input").grid(row=3, column=0, sticky="w", pady=5)
        self.mapping_box = ttk.Entry(frame, textvariable=self.mapping_text, state="readonly", width=28)
        self.mapping_box.grid(row=3, column=1, sticky="ew", padx=(12, 8), pady=5)
        self.mapping_box.bind("<Button-1>", self.start_capture)
        self.capture_button = ttk.Button(frame, text="Map input…", command=self.start_capture)
        self.capture_button.grid(row=3, column=2, sticky="ew", pady=5)

        ttk.Label(frame, textvariable=self.status, wraplength=410).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(12, 16)
        )
        ttk.Label(frame, text="Click Map input, then press a keyboard key, controller button,\n"
                             "D-pad direction, or move a stick/trigger.").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 18)
        )
        ttk.Button(frame, text="Save time", command=self.save_minutes).grid(
            row=6, column=1, sticky="e", padx=(0, 8)
        )
        ttk.Button(frame, text="Close", command=self.close).grid(row=6, column=2, sticky="e")
        frame.columnconfigure(1, weight=1)

        pygame.init()
        pygame.joystick.init()
        try:
            pygame.display.set_mode((1, 1), pygame.HIDDEN)
        except pygame.error:
            pass
        self.refresh_joysticks()

    def refresh_joysticks(self):
        for device_index in range(pygame.joystick.get_count()):
            if (device_index in self.device_indices
                    and self.device_indices[device_index] in self.joysticks):
                continue
            try:
                joystick = pygame.joystick.Joystick(device_index)
                joystick.init()
                instance_id = joystick.get_instance_id()
                self.joysticks[instance_id] = joystick
                self.device_indices[device_index] = instance_id
            except pygame.error:
                continue

    def start_capture(self, event=None):
        self.capturing = True
        self.status.set("Waiting for input… press a key or controller control.")
        self.capture_button.configure(state="disabled")
        self.root.bind_all("<KeyPress>", self.capture_key, add="+")
        self.root.focus_force()
        self.root.after(50, self.begin_controller_capture)

    def begin_controller_capture(self):
        if not self.capturing:
            return
        self.refresh_joysticks()
        pygame.event.pump()
        self.previous_controls = self.active_controller_controls()
        self.root.after(15, self.poll_controller_capture)

    def capture_key(self, event):
        if not self.capturing:
            return
        key_name = event.keysym.casefold()
        aliases = {
            "shift_l": "left shift", "shift_r": "right shift",
            "control_l": "left ctrl", "control_r": "right ctrl",
            "alt_l": "left alt", "alt_r": "right alt",
            "meta_l": "left meta", "meta_r": "right meta",
        }
        pygame_name = aliases.get(key_name, key_name)
        try:
            pygame_name = pygame.key.name(pygame.key.key_code(pygame_name)).casefold()
        except (TypeError, ValueError, pygame.error):
            pass
        self.finish_capture({
            "type": "key", "key_name": pygame_name,
            "virtual_key": int(getattr(event, "keycode", 0) or 0),
            "label": event.keysym,
        })
        return "break"

    def active_controller_controls(self):
        controls = {}
        # 1. Native XInput gamepad polling (Xbox 360, Xbox One, Xbox Series, 8BitDo, etc.)
        if xinput_helper.is_available():
            for user_index in range(4):
                state = xinput_helper.get_state(user_index)
                if state:
                    slot_name = f"Xbox / XInput #{user_index + 1}"
                    for bit, btn_name in xinput_helper.BUTTON_NAMES.items():
                        if state.Gamepad.wButtons & bit:
                            token = ("xinput_button", user_index, bit)
                            controls[token] = {
                                "type": "xinput_button",
                                "user_index": user_index,
                                "button_mask": bit,
                                "button_name": btn_name,
                                "label": f"{slot_name} — {btn_name}",
                            }
                    if state.Gamepad.bLeftTrigger >= xinput_helper.XINPUT_TRIGGER_THRESHOLD:
                        token = ("xinput_trigger", user_index, "lt")
                        controls[token] = {
                            "type": "xinput_trigger",
                            "user_index": user_index,
                            "trigger": "lt",
                            "label": f"{slot_name} — Left Trigger (LT)",
                        }
                    if state.Gamepad.bRightTrigger >= xinput_helper.XINPUT_TRIGGER_THRESHOLD:
                        token = ("xinput_trigger", user_index, "rt")
                        controls[token] = {
                            "type": "xinput_trigger",
                            "user_index": user_index,
                            "trigger": "rt",
                            "label": f"{slot_name} — Right Trigger (RT)",
                        }

        # 2. DirectInput, HID, and Pygame/SDL joysticks (Generic USB, arcade fight sticks, PS4/PS5, etc.)
        XBOX_BUTTON_NAMES = {
            0: "A (Cross)", 1: "B (Circle)", 2: "X (Square)", 3: "Y (Triangle)",
            4: "LB (Left Bumper)", 5: "RB (Right Bumper)", 6: "Back / View",
            7: "Start / Menu", 8: "L3 (Left Stick)", 9: "R3 (Right Stick)", 10: "Guide / Home"
        }

        for instance_id, joystick in list(self.joysticks.items()):
            try:
                guid = joystick.get_guid()
                name = joystick.get_name()
                is_xbox = any(k in name.lower() for k in ("xbox", "xinput", "360", "one", "series"))
                for index in range(joystick.get_numbuttons()):
                    if joystick.get_button(index):
                        token = ("button", instance_id, index)
                        if is_xbox and index in XBOX_BUTTON_NAMES:
                            btn_text = f"{XBOX_BUTTON_NAMES[index]} (Btn {index + 1})"
                        else:
                            btn_text = f"Button {index + 1}"
                        controls[token] = {
                            "type": "joy_button", "index": index, "guid": guid,
                            "device_name": name, "label": f"{name} — {btn_text}",
                        }
                for index in range(joystick.get_numaxes()):
                    value = joystick.get_axis(index)
                    if value >= 0.65:
                        direction = 1
                    elif value <= -0.65:
                        direction = -1
                    else:
                        continue
                    token = ("axis", instance_id, index, direction)
                    sign = "+" if direction > 0 else "−"
                    controls[token] = {
                        "type": "joy_axis", "index": index, "direction": direction,
                        "guid": guid, "device_name": name,
                        "label": f"{name} — Axis {index + 1} {sign}",
                    }
                for index in range(joystick.get_numhats()):
                    value = tuple(joystick.get_hat(index))
                    if value == (0, 0):
                        continue
                    token = ("hat", instance_id, index, value)
                    direction = self.hat_label(value)
                    controls[token] = {
                        "type": "joy_hat", "index": index, "value": list(value),
                        "guid": guid, "device_name": name,
                        "label": f"{name} — D-pad {direction}",
                    }
            except pygame.error:
                self.joysticks.pop(instance_id, None)
        return controls

    @staticmethod
    def hat_label(value):
        x, y = value
        vertical = "up" if y > 0 else "down" if y < 0 else ""
        horizontal = "right" if x > 0 else "left" if x < 0 else ""
        return " + ".join(part for part in (vertical, horizontal) if part)

    def poll_controller_capture(self):
        if not self.capturing:
            return
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEADDED:
                try:
                    joystick = pygame.joystick.Joystick(event.device_index)
                    joystick.init()
                    instance_id = joystick.get_instance_id()
                    self.joysticks[instance_id] = joystick
                    self.device_indices[event.device_index] = instance_id
                except pygame.error:
                    pass
            elif event.type == pygame.JOYDEVICEREMOVED:
                self.joysticks.pop(event.instance_id, None)
                self.device_indices = {
                    index: instance for index, instance in self.device_indices.items()
                    if instance != event.instance_id
                }
        controls = self.active_controller_controls()
        new_controls = [token for token in controls if token not in self.previous_controls]
        if new_controls:
            self.finish_capture(controls[new_controls[0]])
            return
        self.previous_controls = controls
        self.root.after(15, self.poll_controller_capture)

    def finish_capture(self, mapping):
        self.capturing = False
        self.root.unbind_all("<KeyPress>")
        self.capture_button.configure(state="normal")
        self.mapping = mapping
        self.mapping_text.set(mapping["label"])
        self.settings["input"] = mapping
        self.persist()
        self.status.set(f"Mapped to {mapping['label']}. This setting is saved.")

    def save_minutes(self):
        try:
            minutes = int(self.minutes.get())
            if not 1 <= minutes <= 1440:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid time", "Enter a whole number from 1 to 1440 minutes.",
                                 parent=self.root)
            return
        self.settings["add_minutes"] = minutes
        self.settings["input"] = self.mapping
        self.persist()
        self.status.set(f"Saved: each insert-coin input adds {minutes} minutes.")

    def persist(self):
        try:
            write_config(self.settings)
        except OSError as error:
            messagebox.showerror("Could not save settings", str(error), parent=self.root)

    def close(self):
        self.capturing = False
        pygame.quit()
        self.root.destroy()


if __name__ == "__main__":
    ensure_admin()
    window = tk.Tk()
    CoinMapper(window)
    window.mainloop()

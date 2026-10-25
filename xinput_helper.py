"""Direct XInput 1.4 / 1.3 ctypes polling module for Windows.

Provides native hardware polling for all Xbox 360, Xbox One, Xbox Series X/S,
and XInput-compatible gamepads (8BitDo, Logitech F310/F710, PowerA, etc.).

Works globally across the entire system, whether foreground or background,
allowing instant detection of controller navigation and insert-coin actions
even while full-screen exclusive games (such as Tekken 8) have focus.
"""

import ctypes
import time

# --- XInput Constants & Button Bitmasks ---
XINPUT_GAMEPAD_DPAD_UP = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT = 0x0008
XINPUT_GAMEPAD_START = 0x0010
XINPUT_GAMEPAD_BACK = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A = 0x1000
XINPUT_GAMEPAD_B = 0x2000
XINPUT_GAMEPAD_X = 0x4000
XINPUT_GAMEPAD_Y = 0x8000

# Analog thresholds
XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE = 16000
XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE = 16000
XINPUT_TRIGGER_THRESHOLD = 30

BUTTON_NAMES = {
    XINPUT_GAMEPAD_A: "A (Cross)",
    XINPUT_GAMEPAD_B: "B (Circle)",
    XINPUT_GAMEPAD_X: "X (Square)",
    XINPUT_GAMEPAD_Y: "Y (Triangle)",
    XINPUT_GAMEPAD_START: "Start / Menu",
    XINPUT_GAMEPAD_BACK: "Back / View",
    XINPUT_GAMEPAD_LEFT_SHOULDER: "LB (Left Bumper)",
    XINPUT_GAMEPAD_RIGHT_SHOULDER: "RB (Right Bumper)",
    XINPUT_GAMEPAD_LEFT_THUMB: "Left Stick Click (L3)",
    XINPUT_GAMEPAD_RIGHT_THUMB: "Right Stick Click (R3)",
    XINPUT_GAMEPAD_DPAD_UP: "D-pad Up",
    XINPUT_GAMEPAD_DPAD_DOWN: "D-pad Down",
    XINPUT_GAMEPAD_DPAD_LEFT: "D-pad Left",
    XINPUT_GAMEPAD_DPAD_RIGHT: "D-pad Right",
}


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]


# Attempt to load XInput DLL (Windows 11/10 xinput1_4.dll -> xinput1_3.dll -> xinput9_1_0.dll)
_xinput_dll = None
for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
    try:
        _xinput_dll = ctypes.windll.LoadLibrary(dll_name)
        break
    except Exception:
        pass


def is_available():
    """Return True if Windows XInput subsystem is loaded and accessible."""
    return _xinput_dll is not None


def get_state(user_index):
    """Query state of XInput controller slot (0..3). Returns XINPUT_STATE or None."""
    if not _xinput_dll:
        return None
    state = XINPUT_STATE()
    try:
        ret = _xinput_dll.XInputGetState(int(user_index), ctypes.byref(state))
        if ret == 0:  # ERROR_SUCCESS
            return state
    except Exception:
        pass
    return None


def get_connected_controllers():
    """Return a list of integer user indices (0..3) for connected XInput gamepads."""
    connected = []
    if not _xinput_dll:
        return connected
    state = XINPUT_STATE()
    for i in range(4):
        try:
            if _xinput_dll.XInputGetState(i, ctypes.byref(state)) == 0:
                connected.append(i)
        except Exception:
            pass
    return connected


def is_button_down(user_index, button_mask):
    """Check if a specific button mask is held on the given XInput slot."""
    state = get_state(user_index)
    if state:
        return bool(state.Gamepad.wButtons & button_mask)
    return False


def is_trigger_down(user_index, trigger="lt"):
    """Check if Left Trigger ('lt') or Right Trigger ('rt') is pulled past threshold."""
    state = get_state(user_index)
    if state:
        if trigger.lower() in ("lt", "left"):
            return state.Gamepad.bLeftTrigger >= XINPUT_TRIGGER_THRESHOLD
        if trigger.lower() in ("rt", "right"):
            return state.Gamepad.bRightTrigger >= XINPUT_TRIGGER_THRESHOLD
    return False


class XInputPoller:
    """Tracks state changes across all 4 XInput controller slots for clean edge detection."""

    def __init__(self):
        self.prev_buttons = [0, 0, 0, 0]
        self.prev_lt = [False, 0, 0, 0]
        self.prev_rt = [False, 0, 0, 0]
        self.last_axis_time = [0.0, 0.0, 0.0, 0.0]

    def poll(self):
        """Yield events: (event_name, user_index, extra_data).

        Events:
        - ('button_down', user_index, button_bit)
        - ('button_up', user_index, button_bit)
        - ('nav_left', user_index, source)
        - ('nav_right', user_index, source)
        - ('nav_up', user_index, source)
        - ('nav_down', user_index, source)
        - ('trigger_down', user_index, 'lt'|'rt')
        """
        if not _xinput_dll:
            return

        now = time.monotonic()
        state = XINPUT_STATE()

        for user_index in range(4):
            try:
                ret = _xinput_dll.XInputGetState(user_index, ctypes.byref(state))
            except Exception:
                continue

            if ret != 0:
                self.prev_buttons[user_index] = 0
                self.prev_lt[user_index] = False
                self.prev_rt[user_index] = False
                continue

            buttons = state.Gamepad.wButtons
            prev_btn = self.prev_buttons[user_index]

            # Button edge detection
            pressed = buttons & ~prev_btn
            released = prev_btn & ~buttons

            if pressed:
                for bit, name in BUTTON_NAMES.items():
                    if pressed & bit:
                        yield ("button_down", user_index, bit)
                        # Map D-pad buttons to navigation
                        if bit == XINPUT_GAMEPAD_DPAD_LEFT:
                            yield ("nav_left", user_index, "dpad")
                        elif bit == XINPUT_GAMEPAD_DPAD_RIGHT:
                            yield ("nav_right", user_index, "dpad")
                        elif bit == XINPUT_GAMEPAD_DPAD_UP:
                            yield ("nav_up", user_index, "dpad")
                        elif bit == XINPUT_GAMEPAD_DPAD_DOWN:
                            yield ("nav_down", user_index, "dpad")

            if released:
                for bit in BUTTON_NAMES:
                    if released & bit:
                        yield ("button_up", user_index, bit)

            self.prev_buttons[user_index] = buttons

            # Trigger edge detection
            lt = state.Gamepad.bLeftTrigger >= XINPUT_TRIGGER_THRESHOLD
            rt = state.Gamepad.bRightTrigger >= XINPUT_TRIGGER_THRESHOLD
            if lt and not self.prev_lt[user_index]:
                yield ("trigger_down", user_index, "lt")
            if rt and not self.prev_rt[user_index]:
                yield ("trigger_down", user_index, "rt")
            self.prev_lt[user_index] = lt
            self.prev_rt[user_index] = rt

            # Analog Thumbsticks Navigation (Left Stick & Right Stick) with 200ms debounce
            if now - self.last_axis_time[user_index] > 0.20:
                lx = state.Gamepad.sThumbLX
                ly = state.Gamepad.sThumbLY
                rx = state.Gamepad.sThumbRX
                ry = state.Gamepad.sThumbRY

                # Horizontal navigation (Left / Right)
                if lx < -XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE or rx < -XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
                    self.last_axis_time[user_index] = now
                    yield ("nav_left", user_index, "stick")
                elif lx > XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE or rx > XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
                    self.last_axis_time[user_index] = now
                    yield ("nav_right", user_index, "stick")
                # Vertical navigation (Up / Down)
                elif ly > XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE or ry > XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
                    self.last_axis_time[user_index] = now
                    yield ("nav_up", user_index, "stick")
                elif ly < -XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE or ry < -XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
                    self.last_axis_time[user_index] = now
                    yield ("nav_down", user_index, "stick")

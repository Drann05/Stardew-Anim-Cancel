import time
import subprocess
import threading
from pynput import keyboard, mouse
import os
import math

# --- CONFIGURATION ---
ACTIVATION_BUTTON = "button9" # Mouse button
SCREEN_WIDTH = 2560
SCREEN_HEIGHT = 1440
CURSOR_DIRECTION_MIN_THRESHOLD = 15  # pixel screen, calibra se necessario
CURSOR_DIRECTION_MAX_THRESHOLD= 100

# Use keyboard.Key.space for Spacebar, or a string like 'f' for letters
ACTIVATION_KEY = keyboard.Key.space
WATERING_CAN_SLOT = 4

# EXIT_SHORTCUT uses pynput syntax: <ctrl>, <alt>, <shift>, etc.
EXIT_SHORTCUT = "<ctrl>+q"

# Detect session type (Wayland or X11)
session_type = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
socket_path = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")

# approximate user position (screen center by default)
char_x = SCREEN_WIDTH // 2
char_y = SCREEN_HEIGHT // 2

cursor_x = SCREEN_WIDTH // 2
cursor_y = SCREEN_HEIGHT // 2


_DIR_PRIORITY = ['down', 'up', 'right', 'left']

# wait_frames per direction (without watering can)
FRAMES_BY_DIR = {
    'up':    4,
    'down':  7.40,
    'left':  4,
    'right': 4,
}

# wait_frames per direzione con annaffiatoio (slot 4)
FRAMES_BY_DIR_WATERING = {
    'up':    7.40,
    'down':  7.40,
    'left':  7.40,
    'right': 7.40,
}

# Currently pressed direction keys
pressed_dirs = set()
last_wasd_dir = 'down'  # fallback when no key is pressed


wait_frames = 5
is_active = threading.Event()
state_lock = threading.Lock()
current_slot = 1

# Pre-calculated env for ydotool to avoid overhead in subprocess calls
_env = os.environ.copy()
_env["YDOTOOL_SOCKET"] = socket_path

def send_cmd(cmd):
    """Sends commands to the appropriate backend (ydotool for Wayland, xdotool for X11)."""
    if session_type == "wayland":
        # Wayland backend (ydotool)
        subprocess.Popen(["ydotool"] + cmd.split(), env=_env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # X11 backend (xdotool)
        # Mapping key codes for xdotool (Note: xdotool uses names like 'r', 'Delete', 'Shift_R')
        if "key" in cmd:
            parts = cmd.split()
            # Basic mapping for the specific cancel sequence
            # key 272 is mouse left click in ydotool, xdotool uses 'click 1'
            if "272" in cmd:
                action = "mousedown 1" if ":1" in cmd else "mouseup 1"
                subprocess.Popen(["xdotool", action], stdout=subprocess.DEVNULL)
            else:
                # Handle the R + Del + Shift sequence
                # ydotool: "key 19:1 111:1 54:1" -> xdotool: "keydown r keydown Delete keydown Shift_R"
                actions = []
                for p in parts[1:]:
                    code, state = p.split(':')
                    verb = "keydown" if state == "1" else "keyup"
                    key_map = {"19": "r", "111": "Delete", "54": "Shift_R"}
                    actions.append(verb)
                    actions.append(key_map.get(code, "space"))
                subprocess.Popen(["xdotool"] + actions, stdout=subprocess.DEVNULL)

def cancel_anim():
    """Executes the Animation Cancel sequence based on current frame timing."""
    frames = get_wait_frames()
    direction = get_direction_from_cursor()
    dx = cursor_x - char_x
    dy = cursor_y - char_y
    dist = math.sqrt(dx * dx + dy * dy)
    print(f"[DEBUG] dir={direction} frames={frames} cursor=({cursor_x},{cursor_y}) char=({char_x},{char_y}) dist={dist:.0f}")

    # Left Click (Tool action)
    send_cmd("key 272:1")
    time.sleep(0.05)
    send_cmd("key 272:0")
    

    # Small safety gap to ensure the game registers the swing direction
    time.sleep(0.02)

    # Dynamic wait
    time.sleep(frames * 0.014)

    # Animation Cancel: R (19) + Del (111) + RShift (54)
    send_cmd("key 19:1 111:1 54:1")
    time.sleep(0.06)
    send_cmd("key 19:0 111:0 54:0")

    time.sleep(0.04)

def macro_loop():
    while True:
        if is_active.wait(timeout=0.05):
            cancel_anim()
            time.sleep(0.01)

t = threading.Thread(target=macro_loop, daemon=True)
t.start()


# --- INPUT MANAGEMENT ---

def on_move(x, y):
    """Updates current cursor position"""
    global cursor_x, cursor_y
    cursor_x = x
    cursor_y = y


def on_press(key):
    global current_slot
    if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
        is_active.set()
    try:
        char = key.char.lower()
        if char in '1234567890':
            with state_lock:
                current_slot = int(char) if char != '0' else 10
        # Updates last_wasd_dir
        dir_map = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}
        if char in dir_map:
            with state_lock:
                pressed_dirs.add(dir_map[char])
    except AttributeError:
        pass

def on_release(key):
    global last_wasd_dir
    if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
        is_active.clear()
    try:
        char = key.char.lower()
        dir_map = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}
        if char in dir_map:
            with state_lock:
                pressed_dirs.discard(dir_map[char])
                last_wasd_dir = dir_map[char]
    except AttributeError:
        pass

def get_wasd_dir() -> str:
    with state_lock:
        active = set(pressed_dirs)
        fallback = last_wasd_dir
    if not active:
        return fallback  # fallback neutro
    for d in _DIR_PRIORITY:
        if d in active:
            return d

def on_click(x, y, button, pressed):
    if ACTIVATION_BUTTON in str(button):
        if pressed:
            is_active.set()
        else:
            is_active.clear()

def on_scroll(x, y, dx, dy):
    global current_slot
    with state_lock:
        if dy > 0:
            current_slot -= 1
        elif dy < 0:
            current_slot += 1
        if current_slot > 10: current_slot = 1
        elif current_slot < 1: current_slot = 10

def get_direction_from_cursor() -> str:
    """
    Calcualte the direction based on the position of the cursor from the character.
    If the cursor is near the character, the direction will be the same as the
    cursor; otherwise the last direction key will be used (wasd)
    """
    dx = cursor_x - char_x
    dy = cursor_y - char_y
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < CURSOR_DIRECTION_MIN_THRESHOLD or dist > CURSOR_DIRECTION_MAX_THRESHOLD:
        return get_wasd_dir()

    angle = math.degrees(math.atan2(dy, dx))

    if 42 <= angle <= 119:
        return 'down'
    elif -131 <= angle <= -31:
        return 'up'
    elif -31 < angle < 42:
        return 'right'
    else:
        return 'left'

def get_wait_frames() -> float:
    """Returns the correct wait_frames value based on direction and active slot"""
    direction = get_direction_from_cursor()
    with state_lock:
        slot = current_slot
    if slot == WATERING_CAN_SLOT:
        return FRAMES_BY_DIR_WATERING[direction]
    return FRAMES_BY_DIR[direction]


# --- START ---
print(f"--- STARDEW ANIMATION CANCEL ({session_type.upper()}) ---")
if session_type == "wayland":
    print(f"Backend: ydotool | Socket: {socket_path}")
else:
    print(f"Backend: xdotool")

print(f"Activation: Mouse {ACTIVATION_BUTTON} / Keyboard {ACTIVATION_KEY}")
print("Press CTRL+C to stop.")

key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
key_listener.start()

with mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move) as mouse_listener:
    mouse_listener.join()

import time
import subprocess
import threading
from pynput import keyboard, mouse
import os

# --- CONFIGURATION ---
ACTIVATION_BUTTON = "button9" # Mouse button

# Use keyboard.Key.space for Spacebar, or a string like 'f' for letters
ACTIVATION_KEY = keyboard.Key.space
WATERING_CAN_SLOT = 4

# Detect session type (Wayland or X11)
session_type = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
socket_path = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")

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
    with state_lock:
        frames = wait_frames

    # 1. Left Click (Tool action)
    send_cmd("key 272:1")
    time.sleep(0.03)
    send_cmd("key 272:0")

    # 2. Dynamic wait
    time.sleep(frames * 0.014)

    # 3. Animation Cancel: R (19) + Del (111) + RShift (54)
    send_cmd("key 19:1 111:1 54:1")
    time.sleep(0.04)
    send_cmd("key 19:0 111:0 54:0")

    time.sleep(0.02)

def macro_loop():
    while True:
        if is_active.wait(timeout=0.05):
            cancel_anim()
            time.sleep(0.01)

t = threading.Thread(target=macro_loop, daemon=True)
t.start()

# --- INPUT MANAGEMENT ---

def on_press(key):
    global wait_frames, current_slot
    if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
        is_active.set()
    try:
        char = key.char.lower()
        if char in '1234567890':
            with state_lock:
                current_slot = int(char) if char != '0' else 10
        with state_lock:
            if char == 'w':
                wait_frames = 10 if current_slot == WATERING_CAN_SLOT else 6
            elif char == 's':
                wait_frames = 10
            elif char in ('a', 'd'):
                wait_frames = 11 if current_slot == WATERING_CAN_SLOT else 5
    except AttributeError:
        pass

def on_release(key):
    if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
        is_active.clear()

def on_click(x, y, button, pressed):
    if ACTIVATION_BUTTON in str(button):
        if pressed:
            is_active.set()
        else:
            is_active.clear()

def on_scroll(x, y, dx, dy):
    global current_slot, wait_frames
    with state_lock:
        if dy > 0:
            current_slot -= 1
        elif dy < 0:
            current_slot += 1
        if current_slot > 10: current_slot = 1
        elif current_slot < 1: current_slot = 10
        if current_slot == WATERING_CAN_SLOT and wait_frames < 10:
            wait_frames = 10

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

with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as mouse_listener:
    mouse_listener.join()

import time
import subprocess
import threading
from pynput import keyboard, mouse
import os

# --- CONFIGURATION ---

ACTIVATION_BUTTON = "button9"
WATERING_CAN_SLOT = 4

socket_path = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")
wait_frames = 5
is_active = threading.Event()      # Thread-safe: replaces the bool is_active
state_lock = threading.Lock()      # Protects wait_frames and current_slot
current_slot = 1

# Pre-calculated env only once instead of copying it at every send_ydo
_env = os.environ.copy()
_env["YDOTOOL_SOCKET"] = socket_path

def send_ydo(cmd):
    """Sends commands to ydotool without blocking (fire-and-forget)."""
    subprocess.Popen(["ydotool"] + cmd.split(), env=_env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cancel_anim():
    """Executes the Animation Cancel sequence based on current frames."""
    with state_lock:
        frames = wait_frames   # Local atomic read

    # 1. Left Click (Tool action)
    send_ydo("key 272:1")
    time.sleep(0.03)           # ← unchanged
    send_ydo("key 272:0")

    # 2. Dynamic wait
    time.sleep(frames * 0.014) # ← unchanged

    # 3. Animation Cancel: R (19) + Del (111) + RShift (54)
    send_ydo("key 19:1 111:1 54:1")
    time.sleep(0.04)           # ← unchanged
    send_ydo("key 19:0 111:0 54:0")

    # Minimum pause to avoid clogging the ydotool daemon
    time.sleep(0.02)           # ← unchanged

def macro_loop():
    """Main macro loop in a separate thread."""
    while True:
        if is_active.wait(timeout=0.05):   # Blocks efficiently when inactive
            cancel_anim()
            time.sleep(0.01)               # ← unchanged

# Thread start
t = threading.Thread(target=macro_loop, daemon=True)
t.start()

# --- INPUT MANAGEMENT (Keyboard and Mouse) ---
def on_press(key):
    global wait_frames, current_slot
    try:
        char = key.char.lower()

        # Slot Detection (Keyboard)
        if char in '1234567890':
            with state_lock:
                current_slot = int(char) if char != '0' else 10

        # Timing Update based on Direction
        with state_lock:
            if char == 'w':
                wait_frames = 10 if current_slot == WATERING_CAN_SLOT else 6
            elif char == 's':
                wait_frames = 10
            elif char in ('a', 'd'):
                wait_frames = 11 if current_slot == WATERING_CAN_SLOT else 5

    except AttributeError:
        pass   # Special keys (Shift, Ctrl, etc.) — intentionally ignored

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

        # Range 1–10 cyclic
        if current_slot > 10:
            current_slot = 1
        elif current_slot < 1:
            current_slot = 10

        # Slot 4 (watering can) requires more frames
        if current_slot == WATERING_CAN_SLOT and wait_frames < 10:
            wait_frames = 10

# --- LISTENER START ---
print("--- STARDEW ANIMATION CANCEL (ARCH/HYPRLAND) ---")
print(f"Socket: {socket_path}")
print("Instructions: Hold the SIDE BUTTON to activate.")
print("The scroll wheel and numbers update the slot correctly.")
print("Press CTRL+C to terminate the script.")

key_listener = keyboard.Listener(on_press=on_press)
key_listener.start()

with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as mouse_listener:
    mouse_listener.join()

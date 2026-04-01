import time
import subprocess
import threading
from pynput import keyboard, mouse
import os

# --- CONFIGURATION ---
ACTIVATION_BUTTON = "button9"      # Mouse button
# Use keyboard.Key.space for Spacebar, or a string like 'f' for letters
ACTIVATION_KEY = keyboard.Key.space               
WATERING_CAN_SLOT = 4

socket_path = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")
wait_frames = 5
is_active = threading.Event()      # Thread-safe: replaces the bool is_active
state_lock = threading.Lock()      # Protects wait_frames and current_slot
current_slot = 1

# Pre-calculated env once to avoid overhead in subprocess calls
_env = os.environ.copy()
_env["YDOTOOL_SOCKET"] = socket_path

def send_ydo(cmd):
    """Sends commands to ydotool without blocking (fire-and-forget)."""
    subprocess.Popen(["ydotool"] + cmd.split(), env=_env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cancel_anim():
    """Executes the Animation Cancel sequence based on current frame timing."""
    with state_lock:
        frames = wait_frames   # Atomic local read

    # 1. Left Click (Tool action)
    send_ydo("key 272:1")
    time.sleep(0.03)
    send_ydo("key 272:0")

    # 2. Dynamic wait based on active tool/direction
    time.sleep(frames * 0.014)

    # 3. Animation Cancel: R (19) + Del (111) + RShift (54)
    send_ydo("key 19:1 111:1 54:1")
    time.sleep(0.04)
    send_ydo("key 19:0 111:0 54:0")

    # Minimum pause to prevent ydotool daemon congestion
    time.sleep(0.02)

def macro_loop():
    """Main macro loop running in a separate thread."""
    while True:
        if is_active.wait(timeout=0.05):   # Blocks efficiently when inactive
            cancel_anim()
            time.sleep(0.01)

# Start background thread
t = threading.Thread(target=macro_loop, daemon=True)
t.start()

# --- INPUT MANAGEMENT ---

def on_press(key):
    global wait_frames, current_slot

    # Check for Macro Activation (Special keys or Char keys)
    if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
        is_active.set()

    try:
        # Slot Detection and Timing (Only for keys with characters)
        char = key.char.lower()
        if char in '1234567890':
            with state_lock:
                current_slot = int(char) if char != '0' else 10

        # Timing Update based on Movement Direction
        with state_lock:
            if char == 'w':
                wait_frames = 11 if current_slot == WATERING_CAN_SLOT else 6
            elif char == 's':
                wait_frames = 11
            elif char in ('a', 'd'):
                wait_frames = 11 if current_slot == WATERING_CAN_SLOT else 5

    except AttributeError:
        pass

def on_release(key):
    """Stops the macro when the activation key is released."""
    try:
        if key == ACTIVATION_KEY or (hasattr(key, 'char') and key.char == ACTIVATION_KEY):
            is_active.clear()
    except AttributeError:
        pass

def on_click(x, y, button, pressed):
    """Activates the macro when the specified mouse button is held."""
    if ACTIVATION_BUTTON in str(button):
        if pressed:
            is_active.set()
        else:
            is_active.clear()

def on_scroll(x, y, dx, dy):
    """Updates current slot and adjusts frames on mouse wheel scroll."""
    global current_slot, wait_frames
    with state_lock:
        if dy > 0:
            current_slot -= 1
        elif dy < 0:
            current_slot += 1

        if current_slot > 10:
            current_slot = 1
        elif current_slot < 1:
            current_slot = 10

        if current_slot == WATERING_CAN_SLOT and wait_frames < 10:
            wait_frames = 10

# --- START LISTENERS ---
print("--- STARDEW ANIMATION CANCEL (ARCH/HYPRLAND) ---")
print(f"Socket: {socket_path}")
print(f"Mouse Activation: {ACTIVATION_BUTTON}")
print(f"Keyboard Activation: '{ACTIVATION_KEY}'")
print(f"Watering can slot: {WATERING_CAN_SLOT}")
print("Instructions: Hold either activation key to start.")
print("Press CTRL+C to stop the script.")

# Start keyboard listener with release detection
key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
key_listener.start()

with mouse.Listener(on_click=on_click, on_scroll=on_scroll) as mouse_listener:
    mouse_listener.join()

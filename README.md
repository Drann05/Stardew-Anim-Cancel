# stardew-anim-cancel

A Python script I made for myself to automate **Animation Cancel** in Stardew Valley on Linux. Sharing it in case someone else finds it useful.

Works on both **Wayland** (via `ydotool`) and **X11** (via `xdotool`) — the backend is detected automatically.

---

## What is Animation Cancel?

Every tool use in Stardew Valley locks the player in an animation for a fraction of a second. Pressing **R + Delete + Right Shift** at the right moment cancels it early, allowing much faster farming and watering.

This script holds the side mouse button to repeatedly perform the sequence at the correct timing, adjusted for the active tool slot and movement direction.

> Single-player game, no ToS violations.

---

## Requirements

**Wayland:** `ydotool` (daemon must be running) + `pynput`
```bash
sudo pacman -S ydotool python-pynput
sudo systemctl enable --now ydotoold
```

**X11:** `xdotool` + `pynput`
```bash
sudo pacman -S xdotool python-pynput  # Arch
sudo apt install xdotool python3-pynput  # Debian/Ubuntu
```

---

## Usage

```bash
git clone https://github.com/Drann05/stardew-anim-cancel.git
cd Stardew-Anim-Cancel
python anim_cancel.py
```

Hold the **macro button** to activate. Number keys and scroll wheel update the active slot.

WARNING: By default, the script identifies the Watering Can in Slot 4, applying a specific delay for it.

## Configuration
You can change the activation key by modifying the ACTIVATION_BUTTON constant on line 9 of anim_cancel.py
You can change the watering can slot by modifying the WATERING_CAN_SLOT constant on line 10 of anim_cancel.py

---

## License

[MIT](LICENSE) — © 2025 Drann05

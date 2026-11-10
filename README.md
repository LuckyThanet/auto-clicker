# Python Auto Clicker 🚀

A high-performance, precision auto-clicker for Windows built with Python.

---

## 📦 Files Included

1. **[autoclicker.py](autoclicker.py)**: Full-featured Graphical User Interface (GUI).
2. **[simple_autoclicker.py](simple_autoclicker.py)**: Lightweight console/terminal-based auto-clicker.
3. **[roblox_mover.py](roblox_mover.py)**: Roblox auto mover (holds movement keys in a repeating pattern).
4. **[requirements.txt](requirements.txt)**: Python package requirements (`keyboard`).

---

## ✨ Features (GUI Application)

- **Intuitive GUI**: Built with modern dark styling using Tkinter and TTK.
- **Ultra-Fast & Precision Timing**: Uses native Windows API (`ctypes.windll.user32.mouse_event`) and multimedia 1ms timer (`winmm.timeBeginPeriod`).
- **Global Hotkey**: Press **`F6`** (customizable to F7–F12) to Start and Stop clicking at any time, even while playing games or using other apps.
- **Custom Click Interval**: Specify Hours, Minutes, Seconds, and Milliseconds.
- **Mouse Options**: Choose Left, Right, or Middle mouse button; Single or Double click.
- **Key Auto-Press**: Set **Action** to **Key Press** to repeatedly press a keyboard key instead of clicking (Space, Enter, arrows, A–Z, 0–9, F1–F12, etc., or type any single character). It presses into whichever window is focused, at the same interval, repeat count, and Single/Double setting.
- **Click Repeat**: Repeat indefinitely until stopped, or stop after a fixed number of clicks.
- **Cursor Position**: Click wherever your cursor is, or set fixed X/Y coordinates using the interactive **"Pick Location"** screen picker.
- **Always on Top**: Keeps the window visible over other programs.

---

## 🚀 How to Run

### Option 1: Full GUI Auto Clicker (Recommended)
Open a terminal in this folder and run:
```powershell
python autoclicker.py
```
- Set your desired interval (e.g., `100` milliseconds).
- Press **F6** to start clicking, and **F6** again to stop.

### Option 3: Roblox Auto Mover
Double-click **run_roblox_mover.bat**, or run:
```powershell
python roblox_mover.py
```
Walks your Roblox character by **holding** movement keys in a repeating pattern.
- **Movement Pattern**: a list of steps, each holding keys for a number of seconds. Combine keys with `+` (e.g. `W+D` to walk diagonally, `W+Space` to walk while jumping), or use `Idle` to stand still. Load a preset (Square, Back and forth, Circle, Anti-AFK, ...) or build your own with Add / Update / Move / Remove.
- **Timing**: pause between steps, total run time in minutes (`0` = until stopped), and a start delay so you can click into Roblox.
- **Start / Stop**: press **F6** (changeable to F7–F12) or use the buttons.
- **Safety**: by default keys are only pressed while the Roblox window is active; switching away pauses the pattern and releases all keys, and it resumes where it left off. Held keys are always released when it stops.
- Uses hardware scan codes, so it works in Roblox and with any keyboard language (e.g. Thai) active.

### Option 2: Lightweight Terminal Auto Clicker
```powershell
python simple_autoclicker.py
```
- Press **F6** to toggle Start/Pause.
- Press **F7** to Exit.

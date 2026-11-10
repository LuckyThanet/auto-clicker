"""
Simple CLI Auto Clicker
=======================
A lightweight terminal-based auto clicker in Python.
- Press F6 to Start / Pause clicking
- Press F7 to Exit the program
- Configure CPS (clicks per second) or interval directly below
"""

import time
import ctypes
import threading

# Windows mouse constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010

# Try enabling 1ms multimedia timer resolution
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

try:
    import keyboard
except ImportError:
    print("Error: 'keyboard' module is required. Install it using: pip install keyboard")
    exit(1)

# ================= Configuration =================
CLICKS_PER_SECOND = 10      # Number of clicks per second
MOUSE_BUTTON = "left"       # "left" or "right"
TOGGLE_HOTKEY = "f6"        # Hotkey to toggle start/pause
EXIT_HOTKEY = "f7"          # Hotkey to exit program
# =================================================

interval = 1.0 / CLICKS_PER_SECOND
running = False
exit_flag = False
click_counter = 0


def perform_click():
    if MOUSE_BUTTON.lower() == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)


def toggle_clicking():
    global running
    running = not running
    status = "RUNNING" if running else "PAUSED"
    print(f"\n[Status]: {status} (Total clicks: {click_counter})")


def exit_program():
    global exit_flag, running
    running = False
    exit_flag = True
    print("\n[Exiting] Auto Clicker stopped. Goodbye!")


def clicker_loop():
    global click_counter
    while not exit_flag:
        if running:
            start_time = time.perf_counter()
            perform_click()
            click_counter += 1

            # High precision timing
            elapsed = time.perf_counter() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        else:
            time.sleep(0.05)


def main():
    print("=" * 45)
    print("         Python CLI Auto Clicker")
    print("=" * 45)
    print(f" Toggle Hotkey : [{TOGGLE_HOTKEY.upper()}] to Start/Pause")
    print(f" Exit Hotkey   : [{EXIT_HOTKEY.upper()}] to Exit")
    print(f" Speed         : {CLICKS_PER_SECOND} CPS (Interval: {interval:.3f}s)")
    print(f" Mouse Button  : {MOUSE_BUTTON.title()} Click")
    print("=" * 45)
    print("\nPress", TOGGLE_HOTKEY.upper(), "to start clicking...")

    keyboard.add_hotkey(TOGGLE_HOTKEY, toggle_clicking)
    keyboard.add_hotkey(EXIT_HOTKEY, exit_program)

    worker = threading.Thread(target=clicker_loop, daemon=True)
    worker.start()

    try:
        while not exit_flag:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nTerminated by user.")
    finally:
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass


if __name__ == "__main__":
    main()

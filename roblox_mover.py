"""
Roblox Auto Mover
=================
Moves a Roblox character automatically by holding movement keys (W, A, S, D, ...)
in a repeating pattern of steps.
- Hardware scan codes via SendInput, which Roblox accepts (plain virtual-key events are often ignored)
- Pattern editor: each step holds one or more keys (e.g. "W+D") for a set number of seconds
- Pause between steps, total run time limit, start delay to switch to the game
- Global Start/Stop hotkey (Default: F6)
- Safety: only sends keys while the Roblox window is active, and always releases held keys on stop
"""

import time
import ctypes
import threading
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk, messagebox

# Optional keyboard library for global hotkeys
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# ---------------------------------------------------------------------------
# Native keyboard input (SendInput with hardware scan codes)
# ---------------------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD        = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_SCANCODE    = 0x0008

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    # Only present so the INPUT union has the size Windows expects
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)

# Key name -> (scan code, is_extended). Scan codes are physical key positions,
# so they work the same whatever keyboard language is active.
KEYS = {
    "W": (0x11, False),
    "A": (0x1E, False),
    "S": (0x1F, False),
    "D": (0x20, False),
    "Space": (0x39, False),
    "Shift": (0x2A, False),
    "Q": (0x10, False),
    "E": (0x12, False),
    "Up": (0x48, True),
    "Down": (0x50, True),
    "Left": (0x4B, True),
    "Right": (0x4D, True),
}

KEY_CHOICES = [
    "W", "A", "S", "D", "W+A", "W+D", "S+A", "S+D",
    "Space", "W+Space", "W+Shift", "Q", "E", "Idle",
]

PRESETS = {
    "Square": [("W", 2.0), ("D", 2.0), ("S", 2.0), ("A", 2.0)],
    "Back and forth": [("W", 3.0), ("S", 3.0)],
    "Side to side": [("A", 2.0), ("D", 2.0)],
    "Circle (diagonals)": [
        ("W", 0.8), ("W+D", 0.8), ("D", 0.8), ("S+D", 0.8),
        ("S", 0.8), ("S+A", 0.8), ("A", 0.8), ("W+A", 0.8),
    ],
    "Walk and jump": [("W+Space", 3.0), ("S+Space", 3.0)],
    "Anti-AFK (small steps)": [("W", 0.3), ("Idle", 60.0), ("S", 0.3), ("Idle", 60.0)],
}


def send_key(scan_code, extended=False, key_up=False):
    """Press or release one key by hardware scan code."""
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if key_up:
        flags |= KEYEVENTF_KEYUP
    inp = INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan_code, flags, 0, 0)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def parse_keys(text: str):
    """Turn "W+D" into ["W", "D"]; "Idle" into []. Raises ValueError for unknown keys."""
    text = text.strip()
    if not text or text.lower() == "idle":
        return []
    names = []
    for part in text.split("+"):
        part = part.strip()
        match = next((k for k in KEYS if k.lower() == part.lower()), None)
        if match is None:
            raise ValueError(f"Unknown key '{part}'. Use: {', '.join(KEYS)} or Idle.")
        if match not in names:
            names.append(match)
    return names


def roblox_is_active() -> bool:
    """True when the foreground window is the Roblox game client."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip().lower() == "roblox"


def format_step(keys, hold):
    label = "+".join(keys) if keys else "Idle"
    return f"{label:<12}{hold:g} s"


class RobloxMoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Roblox Auto Mover")
        self.root.geometry("500x720")
        self.root.resizable(False, False)

        # State variables
        self.steps = [(parse_keys(k), h) for k, h in PRESETS["Square"]]
        self.is_running = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.current_hotkey_hook = None
        self.current_hotkey = "F6"
        self.status_msg = "Ready / Stopped"
        self.loops_done = 0
        self.started_at = None
        self.finish_reason = None

        # Theme Colors (Modern Dark Slate, matching autoclicker.py)
        self.bg_color = "#181825"
        self.panel_bg = "#1e1e2e"
        self.field_bg = "#313244"
        self.accent_color = "#89b4fa"
        self.text_color = "#cdd6f4"
        self.subtext_color = "#a6adc8"
        self.start_btn_color = "#a6e3a1"
        self.stop_btn_color = "#f38ba8"
        self.btn_text_color = "#11111b"

        self.root.configure(bg=self.bg_color)

        self._setup_styles()
        self._build_ui()
        self._refresh_step_list()
        self._register_hotkey(self.current_hotkey)
        self._poll_status()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------ UI
    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Card.TFrame", background=self.panel_bg, relief="solid", borderwidth=1)
        self.style.configure("TLabel", background=self.panel_bg, foreground=self.text_color, font=("Segoe UI", 9))
        self.style.configure("Hint.TLabel", background=self.panel_bg, foreground=self.subtext_color, font=("Segoe UI", 8))
        self.style.configure(
            "CardTitle.TLabel", background=self.panel_bg, foreground=self.accent_color, font=("Segoe UI", 10, "bold")
        )
        self.style.configure("Header.TLabel", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 14, "bold"))
        for name, bg in (("TCheckbutton", self.bg_color), ("Card.TCheckbutton", self.panel_bg)):
            self.style.configure(name, background=bg, foreground=self.text_color, font=("Segoe UI", 9))
            self.style.map(name, background=[("active", bg)], foreground=[("active", "#ffffff")])

    def _entry(self, parent, var, width=6):
        return tk.Entry(
            parent,
            textvariable=var,
            width=width,
            justify=tk.CENTER,
            bg=self.field_bg,
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )

    def _small_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#45475a",
            fg="#ffffff",
            activebackground="#585b70",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 8),
            padx=8,
            pady=2,
            cursor="hand2",
        )

    def _build_ui(self):
        main = tk.Frame(self.root, bg=self.bg_color, padx=14, pady=12)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Header ---
        header = tk.Frame(main, bg=self.bg_color)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="Roblox Auto Mover", style="Header.TLabel").pack(side=tk.LEFT)
        self.always_on_top_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            header,
            text="Always on Top",
            variable=self.always_on_top_var,
            command=lambda: self.root.attributes("-topmost", self.always_on_top_var.get()),
        ).pack(side=tk.RIGHT)

        # --- Section 1: Movement Pattern ---
        pattern = ttk.Frame(main, style="Card.TFrame", padding=(10, 8))
        pattern.pack(fill=tk.X, pady=4)
        pattern.columnconfigure(0, weight=1)

        title_row = tk.Frame(pattern, bg=self.panel_bg)
        title_row.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))
        ttk.Label(title_row, text="Movement Pattern", style="CardTitle.TLabel").pack(side=tk.LEFT)
        self._small_button(title_row, "Load", self._load_preset).pack(side=tk.RIGHT)
        self.preset_var = tk.StringVar(value="Square")
        ttk.Combobox(
            title_row, textvariable=self.preset_var, values=list(PRESETS), state="readonly", width=20
        ).pack(side=tk.RIGHT, padx=6)

        self.step_list = tk.Listbox(
            pattern,
            height=8,
            bg=self.field_bg,
            fg="#ffffff",
            selectbackground=self.accent_color,
            selectforeground=self.btn_text_color,
            relief="flat",
            highlightthickness=0,
            font=("Consolas", 10),
            activestyle="none",
        )
        self.step_list.grid(row=1, column=0, sticky=tk.NSEW)
        self.step_list.bind("<<ListboxSelect>>", self._on_step_selected)

        side_btns = tk.Frame(pattern, bg=self.panel_bg)
        side_btns.grid(row=1, column=1, sticky=tk.N, padx=(8, 0))
        for text, cmd in (("Move Up", lambda: self._move_step(-1)), ("Move Down", lambda: self._move_step(1)),
                          ("Remove", self._remove_step), ("Clear", self._clear_steps)):
            self._small_button(side_btns, text, cmd).pack(fill=tk.X, pady=2)

        editor = tk.Frame(pattern, bg=self.panel_bg)
        editor.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
        ttk.Label(editor, text="Keys:").pack(side=tk.LEFT)
        self.step_keys_var = tk.StringVar(value="W")
        ttk.Combobox(editor, textvariable=self.step_keys_var, values=KEY_CHOICES, width=10).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Label(editor, text="Hold (s):").pack(side=tk.LEFT)
        self.step_hold_var = tk.StringVar(value="2")
        self._entry(editor, self.step_hold_var).pack(side=tk.LEFT, padx=(4, 10), ipady=2)
        self._small_button(editor, "Add", self._add_step).pack(side=tk.LEFT, padx=2)
        self._small_button(editor, "Update", self._update_step).pack(side=tk.LEFT, padx=2)

        ttk.Label(
            pattern,
            text="Combine keys with + (e.g. W+D). Keys: W A S D Space Shift Q E Up Down Left Right, or Idle.",
            style="Hint.TLabel",
            wraplength=440,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))

        # --- Section 2: Timing ---
        timing = ttk.Frame(main, style="Card.TFrame", padding=(10, 8))
        timing.pack(fill=tk.X, pady=4)
        ttk.Label(timing, text="Timing", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 6))

        self.pause_var = tk.StringVar(value="0.2")
        self.run_minutes_var = tk.StringVar(value="0")
        self.start_delay_var = tk.StringVar(value="3")
        rows = (
            ("Pause between steps:", self.pause_var, "seconds"),
            ("Run for:", self.run_minutes_var, "minutes (0 = until stopped)"),
            ("Start delay:", self.start_delay_var, "seconds (time to click into Roblox)"),
        )
        for i, (label, var, unit) in enumerate(rows, start=1):
            ttk.Label(timing, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            self._entry(timing, var).grid(row=i, column=1, padx=8, pady=2, ipady=2)
            ttk.Label(timing, text=unit, style="Hint.TLabel").grid(row=i, column=2, sticky=tk.W)

        self.repeat_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            timing, text="Repeat the pattern (off = run it once)", variable=self.repeat_var, style="Card.TCheckbutton"
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))

        # --- Section 3: Safety ---
        safety = ttk.Frame(main, style="Card.TFrame", padding=(10, 8))
        safety.pack(fill=tk.X, pady=4)
        ttk.Label(safety, text="Safety", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 6))
        self.require_focus_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            safety,
            text="Only press keys while the Roblox window is active (pauses otherwise)",
            variable=self.require_focus_var,
            style="Card.TCheckbutton",
        ).pack(anchor=tk.W)

        # --- Hotkey & Control Buttons ---
        controls = tk.Frame(main, bg=self.bg_color)
        controls.pack(fill=tk.X, pady=(10, 4))

        hotkey_bar = tk.Frame(controls, bg=self.bg_color)
        hotkey_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hotkey_bar, text="Hotkey to Start / Stop:", background=self.bg_color).pack(side=tk.LEFT)
        self.hotkey_var = tk.StringVar(value="F6")
        hotkey_combo = ttk.Combobox(
            hotkey_bar,
            textvariable=self.hotkey_var,
            values=["F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            state="readonly",
            width=6,
        )
        hotkey_combo.pack(side=tk.LEFT, padx=8)
        hotkey_combo.bind("<<ComboboxSelected>>", lambda e: self._register_hotkey(self.hotkey_var.get()))
        if not KEYBOARD_AVAILABLE:
            tk.Label(
                hotkey_bar,
                text="(Global hotkey disabled: pip install keyboard)",
                bg=self.bg_color,
                fg=self.stop_btn_color,
                font=("Segoe UI", 8),
            ).pack(side=tk.LEFT)

        btns = tk.Frame(controls, bg=self.bg_color)
        btns.pack(fill=tk.X, pady=4)
        self.start_btn = tk.Button(
            btns,
            command=self.start,
            bg=self.start_btn_color,
            fg=self.btn_text_color,
            activebackground="#94e2d5",
            activeforeground=self.btn_text_color,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            pady=8,
            cursor="hand2",
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.stop_btn = tk.Button(
            btns,
            command=self.stop,
            bg=self.stop_btn_color,
            fg=self.btn_text_color,
            activebackground="#eba0ac",
            activeforeground=self.btn_text_color,
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            pady=8,
            state=tk.DISABLED,
            cursor="hand2",
        )
        self.stop_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))
        self._update_button_labels()

        # --- Bottom Status Bar ---
        status = tk.Frame(main, bg="#11111b", padx=10, pady=6)
        status.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        self.status_dot = tk.Canvas(status, width=12, height=12, bg="#11111b", highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_circle = self.status_dot.create_oval(2, 2, 10, 10, fill="#6c7086", outline="")
        self.status_label = tk.Label(status, text="Status: Ready / Stopped", bg="#11111b", fg=self.text_color, font=("Segoe UI", 9))
        self.status_label.pack(side=tk.LEFT)
        self.elapsed_label = tk.Label(status, text="", bg="#11111b", fg=self.accent_color, font=("Segoe UI", 9, "bold"))
        self.elapsed_label.pack(side=tk.RIGHT)

    # ------------------------------------------------------- Pattern editor
    def _refresh_step_list(self, select=None):
        self.step_list.delete(0, tk.END)
        for i, (keys, hold) in enumerate(self.steps, start=1):
            self.step_list.insert(tk.END, f" {i:>2}.  {format_step(keys, hold)}")
        if select is not None and 0 <= select < len(self.steps):
            self.step_list.selection_set(select)
            self.step_list.see(select)

    def _selected_index(self):
        sel = self.step_list.curselection()
        return sel[0] if sel else None

    def _read_editor(self):
        try:
            keys = parse_keys(self.step_keys_var.get())
        except ValueError as err:
            messagebox.showerror("Invalid Keys", str(err))
            return None
        try:
            hold = float(self.step_hold_var.get())
            if hold <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Hold Time", "Hold time must be a number greater than 0.")
            return None
        return keys, hold

    def _on_step_selected(self, event=None):
        idx = self._selected_index()
        if idx is None:
            return
        keys, hold = self.steps[idx]
        self.step_keys_var.set("+".join(keys) if keys else "Idle")
        self.step_hold_var.set(f"{hold:g}")

    def _add_step(self):
        step = self._read_editor()
        if step is None or self._block_while_running():
            return
        idx = self._selected_index()
        insert_at = len(self.steps) if idx is None else idx + 1
        self.steps.insert(insert_at, step)
        self._refresh_step_list(select=insert_at)

    def _update_step(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("No Step Selected", "Select a step in the list to update it.")
            return
        step = self._read_editor()
        if step is None or self._block_while_running():
            return
        self.steps[idx] = step
        self._refresh_step_list(select=idx)

    def _remove_step(self):
        idx = self._selected_index()
        if idx is None or self._block_while_running():
            return
        del self.steps[idx]
        self._refresh_step_list(select=min(idx, len(self.steps) - 1))

    def _move_step(self, offset):
        idx = self._selected_index()
        if idx is None or self._block_while_running():
            return
        new_idx = idx + offset
        if 0 <= new_idx < len(self.steps):
            self.steps[idx], self.steps[new_idx] = self.steps[new_idx], self.steps[idx]
            self._refresh_step_list(select=new_idx)

    def _clear_steps(self):
        if self._block_while_running():
            return
        self.steps = []
        self._refresh_step_list()

    def _load_preset(self):
        if self._block_while_running():
            return
        self.steps = [(parse_keys(k), h) for k, h in PRESETS[self.preset_var.get()]]
        self._refresh_step_list()

    def _block_while_running(self):
        if self.is_running:
            messagebox.showinfo("Running", "Stop the automation before editing the pattern.")
            return True
        return False

    # ------------------------------------------------------------- Hotkey
    def _register_hotkey(self, key: str):
        self.current_hotkey = key
        self._update_button_labels()
        if not KEYBOARD_AVAILABLE:
            return
        try:
            if self.current_hotkey_hook is not None:
                keyboard.remove_hotkey(self.current_hotkey_hook)
        except Exception:
            pass
        try:
            # Schedule execution on the Tkinter main thread
            self.current_hotkey_hook = keyboard.add_hotkey(key.lower(), lambda: self.root.after(0, self.toggle))
        except Exception as err:
            print(f"Warning: Failed to bind hotkey {key}: {err}")

    def _update_button_labels(self):
        self.start_btn.config(text=f"START ({self.current_hotkey})")
        self.stop_btn.config(text=f"STOP ({self.current_hotkey})")

    # ------------------------------------------------------- Start / Stop
    def toggle(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def _read_number(self, var, name):
        try:
            value = float(var.get() or 0)
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            messagebox.showerror("Invalid Value", f"{name} must be a number of 0 or more.")
            return None

    def start(self):
        if self.is_running:
            return
        if not self.steps:
            messagebox.showerror("No Steps", "Add at least one step to the movement pattern.")
            return

        pause = self._read_number(self.pause_var, "Pause between steps")
        run_minutes = self._read_number(self.run_minutes_var, "Run for")
        start_delay = self._read_number(self.start_delay_var, "Start delay")
        if None in (pause, run_minutes, start_delay):
            return

        self.is_running = True
        self.stop_event.clear()
        self.loops_done = 0
        self.started_at = None
        self.finish_reason = None

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_dot.itemconfig(self.dot_circle, fill=self.start_btn_color)

        self.worker_thread = threading.Thread(
            target=self._worker,
            args=(
                list(self.steps),
                pause,
                run_minutes * 60,
                start_delay,
                self.require_focus_var.get(),
                self.repeat_var.get(),
            ),
            daemon=True,
        )
        self.worker_thread.start()

    def stop(self, reason="Stopped"):
        if not self.is_running:
            return
        self.stop_event.set()
        self.is_running = False
        self.status_msg = reason

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_dot.itemconfig(self.dot_circle, fill="#6c7086")
        self.status_label.config(text=f"Status: {reason}", fg=self.text_color)

    # -------------------------------------------------------------- Worker
    def _worker(self, steps, pause, run_seconds, start_delay, require_focus, repeat):
        """Background thread: hold each step's keys for its duration, in order."""
        held = []
        deadline = None

        def press(keys):
            for name in keys:
                scan, ext = KEYS[name]
                send_key(scan, ext)
                held.append(name)

        def release_all():
            while held:
                scan, ext = KEYS[held.pop()]
                send_key(scan, ext, key_up=True)

        def wait(seconds, keys=(), label=""):
            """Spend `seconds` of active time holding `keys`. Returns False if stopped or out of time.

            Time spent waiting for the Roblox window to become active does not count
            toward the step, so a step resumes where it left off.
            """
            remaining = seconds
            last = time.perf_counter()
            while remaining > 0:
                now = time.perf_counter()
                if self.stop_event.is_set():
                    return False
                if deadline is not None and now >= deadline:
                    self.finish_reason = "Finished (time limit reached)"
                    return False
                if require_focus and not roblox_is_active():
                    release_all()
                    self.status_msg = "Paused: waiting for the Roblox window"
                    time.sleep(0.1)
                    last = time.perf_counter()
                    continue
                if keys and not held:
                    press(keys)
                self.status_msg = label
                remaining -= now - last
                last = now
                time.sleep(min(0.01, max(remaining, 0)))
            return True

        try:
            # Countdown so the user can click into Roblox
            end = time.perf_counter() + start_delay
            while time.perf_counter() < end:
                if self.stop_event.is_set():
                    return
                self.status_msg = f"Starting in {end - time.perf_counter():.0f}s... click into Roblox"
                time.sleep(0.05)

            self.started_at = time.perf_counter()
            if run_seconds > 0:
                deadline = self.started_at + run_seconds

            while True:
                for i, (keys, hold) in enumerate(steps, start=1):
                    label = f"Step {i}/{len(steps)}: {'+'.join(keys) if keys else 'Idle'} ({hold:g}s)"
                    if not wait(hold, keys, label):
                        return
                    release_all()
                    if pause > 0 and not wait(pause, label=f"Pause after step {i}"):
                        return
                self.loops_done += 1
                if not repeat:
                    self.finish_reason = "Finished (pattern complete)"
                    return
        except Exception as err:
            print(f"Error in mover worker: {err}")
            self.finish_reason = f"Error: {err}"
        finally:
            release_all()
            self.root.after(0, self._on_worker_finished)

    def _on_worker_finished(self):
        if self.is_running:
            self.stop(self.finish_reason or "Stopped")

    def _poll_status(self):
        """Update status text and elapsed time on the GUI."""
        if self.is_running:
            self.status_label.config(text=f"Status: {self.status_msg}", fg=self.start_btn_color)
            if self.started_at is not None:
                elapsed = int(time.perf_counter() - self.started_at)
                self.elapsed_label.config(text=f"{elapsed // 60:02d}:{elapsed % 60:02d} · Loops: {self.loops_done}")
        self.root.after(100, self._poll_status)

    def on_close(self):
        """Stop the worker (which releases held keys) and clean up hooks."""
        self.stop()
        if self.worker_thread is not None:
            self.worker_thread.join(timeout=1.0)
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    RobloxMoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

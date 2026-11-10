"""
Python Auto Clicker
===================
A high-performance auto-clicker for Windows featuring:
- Responsive Tkinter GUI with modern styling
- Native Windows API clicking via ctypes (SendInput / mouse_event) for ultra-fast, accurate clicks
- High-resolution 1ms multimedia timer (winmm.timeBeginPeriod)
- Global hotkey support (Default: F6, customizable)
- Configurable interval (Hours, Minutes, Seconds, Milliseconds)
- Click types: Single / Double click; Left / Right / Middle button
- Repeat indefinitely or for a fixed number of clicks
- Dynamic cursor position or fixed coordinates with screen coordinate picker
- Thread-safe background worker
"""

import sys
import time
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# Optional keyboard library for global hotkeys
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Windows mouse event constants
MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_ABSOLUTE   = 0x8000

# High-resolution multimedia timer setup for sub-10ms precision
try:
    winmm = ctypes.windll.winmm
    winmm.timeBeginPeriod(1)
except Exception:
    winmm = None


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_current_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def click_mouse(button="Left", click_type="Single", x=None, y=None):
    """Trigger a mouse click via native Windows API."""
    if x is not None and y is not None:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    if button == "Left":
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    elif button == "Right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif button == "Middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    repeats = 2 if click_type == "Double" else 1
    for i in range(repeats):
        ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
        if repeats > 1 and i < repeats - 1:
            time.sleep(0.015)


# Windows keyboard event constants
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002

# Named keys -> (virtual-key code, is_extended)
NAMED_KEYS = {
    "Space": (0x20, False),
    "Enter": (0x0D, False),
    "Tab": (0x09, False),
    "Esc": (0x1B, False),
    "Backspace": (0x08, False),
    "Up": (0x26, True),
    "Down": (0x28, True),
    "Left": (0x25, True),
    "Right": (0x27, True),
    "Insert": (0x2D, True),
    "Delete": (0x2E, True),
    "Home": (0x24, True),
    "End": (0x23, True),
    "Page Up": (0x21, True),
    "Page Down": (0x22, True),
    "Shift": (0x10, False),
    "Ctrl": (0x11, False),
    "Alt": (0x12, False),
}
NAMED_KEYS.update({f"F{n}": (0x6F + n, False) for n in range(1, 13)})
NAMED_KEYS.update({chr(c): (c, False) for c in range(ord("A"), ord("Z") + 1)})
NAMED_KEYS.update({str(d): (0x30 + d, False) for d in range(10)})

KEY_CHOICES = (
    ["Space", "Enter", "Tab", "Esc", "Backspace", "Up", "Down", "Left", "Right"]
    + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [str(d) for d in range(10)]
    + [f"F{n}" for n in range(1, 13)]
    + ["Insert", "Delete", "Home", "End", "Page Up", "Page Down", "Shift", "Ctrl", "Alt"]
)


def resolve_key(name: str):
    """Return (vk_code, is_extended) for a key name or single typed character."""
    name = name.strip()
    for key_name, value in NAMED_KEYS.items():
        if key_name.lower() == name.lower():
            return value
    if len(name) == 1:
        # Any other single character (e.g. "-", "/") via the current keyboard layout
        vk = ctypes.windll.user32.VkKeyScanW(ord(name)) & 0xFF
        if vk != 0xFF:
            return vk, False
    raise ValueError(f"Unknown key: '{name}'")


def press_key(vk_code, extended=False, press_type="Single"):
    """Trigger a keyboard key press via native Windows API."""
    flags = KEYEVENTF_EXTENDEDKEY if extended else 0
    repeats = 2 if press_type == "Double" else 1
    for i in range(repeats):
        ctypes.windll.user32.keybd_event(vk_code, 0, flags, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, flags | KEYEVENTF_KEYUP, 0)
        if repeats > 1 and i < repeats - 1:
            time.sleep(0.015)


class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Python Auto Clicker")
        self.root.geometry("490x620")
        self.root.resizable(False, False)

        # State variables
        self.is_running = False
        self.click_thread = None
        self.stop_event = threading.Event()
        self.click_count = 0
        self.current_hotkey_hook = None
        self.current_hotkey = "F6"

        # Theme Colors (Modern Dark Slate)
        self.bg_color = "#181825"
        self.panel_bg = "#1e1e2e"
        self.accent_color = "#89b4fa"
        self.text_color = "#cdd6f4"
        self.subtext_color = "#a6adc8"
        self.border_color = "#313244"
        self.start_btn_color = "#a6e3a1"
        self.stop_btn_color = "#f38ba8"
        self.btn_text_color = "#11111b"

        self.root.configure(bg=self.bg_color)

        self._setup_styles()
        self._build_ui()
        self._register_hotkey(self.current_hotkey)

        # Periodic UI update for click counter and state
        self._poll_status()

        # Handle window close cleanup
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Configure generic frame styles
        self.style.configure(
            "Card.TFrame",
            background=self.panel_bg,
            relief="solid",
            borderwidth=1,
        )
        self.style.configure(
            "TLabel",
            background=self.panel_bg,
            foreground=self.text_color,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "CardTitle.TLabel",
            background=self.panel_bg,
            foreground=self.accent_color,
            font=("Segoe UI", 10, "bold"),
        )
        self.style.configure(
            "Header.TLabel",
            background=self.bg_color,
            foreground="#cdd6f4",
            font=("Segoe UI", 14, "bold"),
        )
        self.style.configure(
            "SubHeader.TLabel",
            background=self.bg_color,
            foreground=self.subtext_color,
            font=("Segoe UI", 8),
        )
        self.style.configure(
            "TRadiobutton",
            background=self.panel_bg,
            foreground=self.text_color,
            font=("Segoe UI", 9),
        )
        self.style.map(
            "TRadiobutton",
            background=[("active", self.panel_bg)],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure(
            "TCheckbutton",
            background=self.bg_color,
            foreground=self.text_color,
            font=("Segoe UI", 9),
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", self.bg_color)],
            foreground=[("active", "#ffffff")],
        )

    def _build_ui(self):
        main_container = tk.Frame(self.root, bg=self.bg_color, padx=14, pady=12)
        main_container.pack(fill=tk.BOTH, expand=True)

        # --- Top Header ---
        header_frame = tk.Frame(main_container, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_lbl = ttk.Label(header_frame, text="Python Auto Clicker", style="Header.TLabel")
        title_lbl.pack(side=tk.LEFT)

        self.always_on_top_var = tk.BooleanVar(value=False)
        always_on_top_cb = ttk.Checkbutton(
            header_frame,
            text="Always on Top",
            variable=self.always_on_top_var,
            command=self._toggle_always_on_top,
        )
        always_on_top_cb.pack(side=tk.RIGHT)

        # --- Section 1: Click Interval ---
        interval_frame = ttk.Frame(main_container, style="Card.TFrame", padding=(10, 8))
        interval_frame.pack(fill=tk.X, pady=4)

        ttk.Label(interval_frame, text="Click Interval", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=8, sticky=tk.W, pady=(0, 6)
        )

        self.hours_var = tk.StringVar(value="0")
        self.mins_var = tk.StringVar(value="0")
        self.secs_var = tk.StringVar(value="0")
        self.millis_var = tk.StringVar(value="100")

        # Helper for entry layout
        entries = [
            ("Hours", self.hours_var, 0),
            ("Mins", self.mins_var, 2),
            ("Secs", self.secs_var, 4),
            ("Millis", self.millis_var, 6),
        ]

        for label_text, var, col in entries:
            entry = tk.Entry(
                interval_frame,
                textvariable=var,
                width=5,
                justify=tk.CENTER,
                bg="#313244",
                fg="#ffffff",
                insertbackground="#ffffff",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
            )
            entry.grid(row=1, column=col, padx=(0, 4), ipady=3)
            ttk.Label(interval_frame, text=label_text).grid(
                row=1, column=col + 1, padx=(0, 8), sticky=tk.W
            )

        # --- Section 2: Click Options ---
        options_frame = ttk.Frame(main_container, style="Card.TFrame", padding=(10, 8))
        options_frame.pack(fill=tk.X, pady=4)

        ttk.Label(options_frame, text="Click Options", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 6)
        )

        ttk.Label(options_frame, text="Action:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.action_var = tk.StringVar(value="Mouse Click")
        action_combo = ttk.Combobox(
            options_frame,
            textvariable=self.action_var,
            values=["Mouse Click", "Key Press"],
            state="readonly",
            width=10,
        )
        action_combo.grid(row=1, column=1, sticky=tk.W, padx=8, pady=2)
        action_combo.bind("<<ComboboxSelected>>", self._on_action_changed)

        ttk.Label(options_frame, text="Key:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.key_var = tk.StringVar(value="Space")
        # Editable so any single character can also be typed in
        self.key_combo = ttk.Combobox(
            options_frame,
            textvariable=self.key_var,
            values=KEY_CHOICES,
            width=10,
        )
        self.key_combo.grid(row=1, column=3, sticky=tk.W, padx=8, pady=2)

        ttk.Label(options_frame, text="Mouse Button:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.mouse_button_var = tk.StringVar(value="Left")
        self.button_combo = ttk.Combobox(
            options_frame,
            textvariable=self.mouse_button_var,
            values=["Left", "Right", "Middle"],
            state="readonly",
            width=10,
        )
        self.button_combo.grid(row=2, column=1, sticky=tk.W, padx=8, pady=2)

        ttk.Label(options_frame, text="Click Type:").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.click_type_var = tk.StringVar(value="Single")
        type_combo = ttk.Combobox(
            options_frame,
            textvariable=self.click_type_var,
            values=["Single", "Double"],
            state="readonly",
            width=10,
        )
        type_combo.grid(row=2, column=3, sticky=tk.W, padx=8, pady=2)

        # --- Section 3: Click Repeat ---
        repeat_frame = ttk.Frame(main_container, style="Card.TFrame", padding=(10, 8))
        repeat_frame.pack(fill=tk.X, pady=4)

        ttk.Label(repeat_frame, text="Click Repeat", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 6)
        )

        self.repeat_mode_var = tk.StringVar(value="infinite")
        self.repeat_count_var = tk.StringVar(value="100")

        rb_infinite = ttk.Radiobutton(
            repeat_frame,
            text="Repeat until stopped",
            variable=self.repeat_mode_var,
            value="infinite",
        )
        rb_infinite.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=2)

        rb_repeat_count = ttk.Radiobutton(
            repeat_frame,
            text="Repeat",
            variable=self.repeat_mode_var,
            value="fixed",
        )
        rb_repeat_count.grid(row=2, column=0, sticky=tk.W, pady=2)

        count_entry = tk.Entry(
            repeat_frame,
            textvariable=self.repeat_count_var,
            width=8,
            justify=tk.CENTER,
            bg="#313244",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9),
        )
        count_entry.grid(row=2, column=1, sticky=tk.W, padx=6, ipady=2)
        ttk.Label(repeat_frame, text="times").grid(row=2, column=2, sticky=tk.W)

        # --- Section 4: Cursor Position ---
        pos_frame = ttk.Frame(main_container, style="Card.TFrame", padding=(10, 8))
        pos_frame.pack(fill=tk.X, pady=4)

        ttk.Label(pos_frame, text="Cursor Position", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=5, sticky=tk.W, pady=(0, 6)
        )

        self.pos_mode_var = tk.StringVar(value="current")
        self.x_coord_var = tk.StringVar(value="0")
        self.y_coord_var = tk.StringVar(value="0")

        rb_cur_pos = ttk.Radiobutton(
            pos_frame,
            text="Current mouse location",
            variable=self.pos_mode_var,
            value="current",
        )
        rb_cur_pos.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=2)

        rb_fixed_pos = ttk.Radiobutton(
            pos_frame,
            text="Fixed location",
            variable=self.pos_mode_var,
            value="fixed",
        )
        rb_fixed_pos.grid(row=2, column=0, sticky=tk.W, pady=2)

        ttk.Label(pos_frame, text="X:").grid(row=2, column=1, sticky=tk.E, padx=(6, 2))
        x_entry = tk.Entry(
            pos_frame,
            textvariable=self.x_coord_var,
            width=5,
            justify=tk.CENTER,
            bg="#313244",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
        )
        x_entry.grid(row=2, column=2, padx=(0, 6), ipady=2)

        ttk.Label(pos_frame, text="Y:").grid(row=2, column=3, sticky=tk.E, padx=(2, 2))
        y_entry = tk.Entry(
            pos_frame,
            textvariable=self.y_coord_var,
            width=5,
            justify=tk.CENTER,
            bg="#313244",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
        )
        y_entry.grid(row=2, column=4, padx=(0, 8), ipady=2)

        pick_btn = tk.Button(
            pos_frame,
            text="Pick Location",
            command=self._pick_location,
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
        pick_btn.grid(row=2, column=5, padx=(6, 0))

        # Widgets that only apply to mouse clicks (disabled in Key Press mode)
        self.mouse_only_widgets = [rb_cur_pos, rb_fixed_pos, x_entry, y_entry, pick_btn]

        # --- Section 5: Hotkey & Control Buttons ---
        controls_frame = tk.Frame(main_container, bg=self.bg_color)
        controls_frame.pack(fill=tk.X, pady=(10, 4))

        hotkey_bar = tk.Frame(controls_frame, bg=self.bg_color)
        hotkey_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            hotkey_bar,
            text="Hotkey to Start / Stop:",
            style="TLabel",
            background=self.bg_color,
        ).pack(side=tk.LEFT)

        self.hotkey_var = tk.StringVar(value="F6")
        hotkey_combo = ttk.Combobox(
            hotkey_bar,
            textvariable=self.hotkey_var,
            values=["F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            state="readonly",
            width=6,
        )
        hotkey_combo.pack(side=tk.LEFT, padx=8)
        hotkey_combo.bind("<<ComboboxSelected>>", self._on_hotkey_changed)

        if not KEYBOARD_AVAILABLE:
            no_kb_lbl = tk.Label(
                hotkey_bar,
                text="(Global hotkey disabled: pip install keyboard)",
                bg=self.bg_color,
                fg="#f38ba8",
                font=("Segoe UI", 8),
            )
            no_kb_lbl.pack(side=tk.LEFT)

        # Start and Stop Buttons
        btns_bar = tk.Frame(controls_frame, bg=self.bg_color)
        btns_bar.pack(fill=tk.X, pady=4)

        self.start_btn = tk.Button(
            btns_bar,
            text=f"START ({self.current_hotkey})",
            command=self.start_clicking,
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
            btns_bar,
            text=f"STOP ({self.current_hotkey})",
            command=self.stop_clicking,
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

        # --- Bottom Status Bar ---
        status_frame = tk.Frame(main_container, bg="#11111b", padx=10, pady=6)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))

        self.status_dot = tk.Canvas(status_frame, width=12, height=12, bg="#11111b", highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_circle = self.status_dot.create_oval(2, 2, 10, 10, fill="#6c7086", outline="")

        self.status_label = tk.Label(
            status_frame,
            text="Status: Ready / Stopped",
            bg="#11111b",
            fg="#cdd6f4",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side=tk.LEFT)

        self.clicks_counter_label = tk.Label(
            status_frame,
            text="Clicks: 0",
            bg="#11111b",
            fg=self.accent_color,
            font=("Segoe UI", 9, "bold"),
        )
        self.clicks_counter_label.pack(side=tk.RIGHT)

        self._on_action_changed()

    def _on_action_changed(self, event=None):
        is_key_mode = self.action_var.get() == "Key Press"
        self.key_combo.config(state=tk.NORMAL if is_key_mode else tk.DISABLED)
        self.button_combo.config(state=tk.DISABLED if is_key_mode else "readonly")
        for widget in self.mouse_only_widgets:
            if isinstance(widget, ttk.Widget):
                widget.state(["disabled"] if is_key_mode else ["!disabled"])
            else:
                widget.config(state=tk.DISABLED if is_key_mode else tk.NORMAL)

    def _toggle_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def _register_hotkey(self, key: str):
        if not KEYBOARD_AVAILABLE:
            return

        try:
            if self.current_hotkey_hook is not None:
                keyboard.remove_hotkey(self.current_hotkey_hook)
        except Exception:
            pass

        try:
            self.current_hotkey = key
            # Schedule execution on the Tkinter main thread
            self.current_hotkey_hook = keyboard.add_hotkey(
                key.lower(), lambda: self.root.after(0, self.toggle_clicking)
            )
            self._update_button_labels()
        except Exception as err:
            print(f"Warning: Failed to bind hotkey {key}: {err}")

    def _on_hotkey_changed(self, event=None):
        new_key = self.hotkey_var.get()
        self._register_hotkey(new_key)

    def _update_button_labels(self):
        self.start_btn.config(text=f"START ({self.current_hotkey})")
        self.stop_btn.config(text=f"STOP ({self.current_hotkey})")

    def _get_interval_seconds(self) -> float:
        try:
            hours = float(self.hours_var.get() or 0)
            mins = float(self.mins_var.get() or 0)
            secs = float(self.secs_var.get() or 0)
            millis = float(self.millis_var.get() or 0)
        except ValueError:
            raise ValueError("All interval fields must be valid numbers.")

        total_secs = (hours * 3600) + (mins * 60) + secs + (millis / 1000.0)
        if total_secs <= 0:
            raise ValueError("Click interval must be greater than 0.")
        return total_secs

    def _pick_location(self):
        """Open a semi-transparent screen overlay to capture target coordinates."""
        overlay = tk.Toplevel(self.root)
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="#89b4fa", cursor="crosshair")

        info_lbl = tk.Label(
            overlay,
            text="Click anywhere to capture coordinates (or press ESC to cancel)",
            font=("Segoe UI", 16, "bold"),
            bg="#181825",
            fg="#cdd6f4",
            padx=20,
            pady=10,
        )
        info_lbl.pack(pady=40)

        def on_screen_clicked(event):
            x, y = event.x_root, event.y_root
            self.x_coord_var.set(str(x))
            self.y_coord_var.set(str(y))
            self.pos_mode_var.set("fixed")
            overlay.destroy()

        def on_cancel(event):
            overlay.destroy()

        overlay.bind("<Button-1>", on_screen_clicked)
        overlay.bind("<Escape>", on_cancel)

    def toggle_clicking(self):
        if self.is_running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        if self.is_running:
            return

        try:
            interval = self._get_interval_seconds()
        except ValueError as err:
            messagebox.showerror("Invalid Interval", str(err))
            return

        # Validate repeat count if fixed
        repeat_mode = self.repeat_mode_var.get()
        max_clicks = None
        if repeat_mode == "fixed":
            try:
                max_clicks = int(self.repeat_count_var.get())
                if max_clicks <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Count", "Repeat count must be a positive integer.")
                return

        # Validate the key if pressing keys instead of clicking
        action = self.action_var.get()
        key = None
        if action == "Key Press":
            if self.key_var.get().strip().upper() == self.current_hotkey:
                messagebox.showerror(
                    "Invalid Key",
                    f"{self.current_hotkey} is the Start/Stop hotkey. Choose another key or hotkey.",
                )
                return
            try:
                key = resolve_key(self.key_var.get())
            except ValueError as err:
                messagebox.showerror("Invalid Key", str(err))
                return

        # Validate coordinates if fixed
        pos_mode = self.pos_mode_var.get()
        fixed_coords = None
        if pos_mode == "fixed" and key is None:
            try:
                fx = int(self.x_coord_var.get())
                fy = int(self.y_coord_var.get())
                fixed_coords = (fx, fy)
            except ValueError:
                messagebox.showerror("Invalid Coordinates", "Fixed coordinates X and Y must be integers.")
                return

        mouse_btn = self.mouse_button_var.get()
        click_type = self.click_type_var.get()

        self.is_running = True
        self.stop_event.clear()
        self.click_count = 0

        # UI state
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_dot.itemconfig(self.dot_circle, fill="#a6e3a1")
        status_text = "Status: Pressing keys..." if key else "Status: Clicking..."
        self.status_label.config(text=status_text, fg="#a6e3a1")

        # Launch background worker
        self.click_thread = threading.Thread(
            target=self._clicking_worker,
            args=(interval, mouse_btn, click_type, max_clicks, fixed_coords, key),
            daemon=True,
        )
        self.click_thread.start()

    def stop_clicking(self):
        if not self.is_running:
            return

        self.stop_event.set()
        self.is_running = False

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_dot.itemconfig(self.dot_circle, fill="#6c7086")
        self.status_label.config(text="Status: Stopped", fg="#cdd6f4")

    def _clicking_worker(self, interval, button, click_type, max_clicks, fixed_coords, key=None):
        """Background thread executing the clicks (or key presses) with precision timing."""
        clicks = 0
        try:
            while not self.stop_event.is_set():
                start_time = time.perf_counter()

                # Perform the click or key press
                if key is not None:
                    press_key(key[0], extended=key[1], press_type=click_type)
                else:
                    click_mouse(button=button, click_type=click_type, x=fixed_coords[0] if fixed_coords else None, y=fixed_coords[1] if fixed_coords else None)
                clicks += 1
                self.click_count = clicks

                if max_clicks is not None and clicks >= max_clicks:
                    break

                # High-precision sleep accounting for execution time
                elapsed = time.perf_counter() - start_time
                remaining = interval - elapsed

                if remaining > 0:
                    # Sleep in small slices so stopping is immediate
                    slice_step = 0.01
                    while remaining > 0 and not self.stop_event.is_set():
                        sleep_for = min(remaining, slice_step)
                        time.sleep(sleep_for)
                        remaining -= sleep_for

        except Exception as err:
            print(f"Error in click worker: {err}")
        finally:
            self.root.after(0, self._on_worker_finished)

    def _on_worker_finished(self):
        if self.is_running:
            self.stop_clicking()

    def _poll_status(self):
        """Update live click counter on the GUI."""
        if self.is_running:
            self.clicks_counter_label.config(text=f"Clicks: {self.click_count}")
        self.root.after(100, self._poll_status)

    def on_close(self):
        """Clean up threads and timers on exit."""
        self.stop_clicking()
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        if winmm:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

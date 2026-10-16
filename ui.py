"""CustomTkinter Floating Palette for LightMem Autofill.

Adheres to Apple HIG / Modern Minimalist Dark Design:
- Frameless, rounded floating search palette
- Push-to-talk STT voice button (Cactus Needle Whistle)
- Sub-50ms non-blocking thread-safe event queue
- Direct keyboard shortcuts (Enter to autofill, Esc to cancel)
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

import customtkinter as ctk

logger = logging.getLogger("lightmem_autofill.ui")

# Design tokens
COLOR_CANVAS = "#1C1C1E"
COLOR_CARD = "#2C2C2E"
COLOR_INSET = "#3A3A3C"
COLOR_ACCENT = "#0A84FF"
COLOR_MIC_ACTIVE = "#FF453A"
COLOR_SUCCESS = "#30D158"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#98989D"


class FloatingAutofillPalette(ctk.CTkToplevel):
    def __init__(
        self,
        on_query: Callable[[str], None],
        on_stt_toggle: Callable[[bool], None],
        on_confirm_autofill: Callable[[str], None],
        on_dismiss: Callable[[], None],
    ):
        super().__init__()

        self.on_query = on_query
        self.on_stt_toggle = on_stt_toggle
        self.on_confirm_autofill = on_confirm_autofill
        self.on_dismiss = on_dismiss

        self.event_queue: queue.Queue = queue.Queue()
        self.current_value: str = ""
        self._is_recording = False
        self._search_debounce_job = None

        self._init_window()
        self._build_ui()
        self._bind_keys()

        # Start non-blocking UI event pump
        self.after(40, self._drain_events)

    def _init_window(self):
        self.overrideredirect(True)  # Frameless
        self.attributes("-topmost", True)
        self.configure(fg_color=COLOR_CANVAS)

        # Center on screen (640x210)
        width, height = 640, 210
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = int(screen_h * 0.28)  # Centered in upper third for natural eye level
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        # Outer Card Container
        self.card = ctk.CTkFrame(
            self,
            fg_color=COLOR_CARD,
            corner_radius=14,
            border_width=1,
            border_color="#38383A",
        )
        self.card.pack(fill="both", expand=True, padx=4, pady=4)

        # Top Bar: Search Input + Mic Button
        top_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(16, 8))

        # Search Entry
        self.search_entry = ctk.CTkEntry(
            top_frame,
            placeholder_text="Search LightMem or speak...",
            placeholder_text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(family="SF Pro Text", size=15),
            fg_color=COLOR_INSET,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=0,
            corner_radius=10,
            height=44,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self._on_key_release)

        # Mic Toggle Button (Whistle STT)
        self.mic_btn = ctk.CTkButton(
            top_frame,
            text="🎙️ Mic",
            font=ctk.CTkFont(family="SF Pro Text", size=13, weight="bold"),
            fg_color=COLOR_INSET,
            hover_color="#48484A",
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=10,
            width=76,
            height=44,
            command=self._toggle_mic,
        )
        self.mic_btn.pack(side="right")

        # Result Display Box (Read-only / Selected Text)
        self.result_frame = ctk.CTkFrame(
            self.card,
            fg_color=COLOR_INSET,
            corner_radius=10,
            height=64,
        )
        self.result_frame.pack(fill="x", padx=16, pady=6)
        self.result_frame.pack_propagate(False)

        self.result_label = ctk.CTkLabel(
            self.result_frame,
            text="Type a query or press Mic to retrieve facts...",
            font=ctk.CTkFont(family="SF Pro Text", size=14),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=580,
            justify="left",
        )
        self.result_label.pack(side="left", fill="both", expand=True, padx=14, pady=8)

        # Bottom Status & Shortcuts Bar
        bottom_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=16, pady=(4, 12))

        self.status_pill = ctk.CTkLabel(
            bottom_frame,
            text="Ready",
            font=ctk.CTkFont(family="SF Pro Text", size=11, weight="bold"),
            text_color=COLOR_ACCENT,
            anchor="w",
        )
        self.status_pill.pack(side="left")

        hints_label = ctk.CTkLabel(
            bottom_frame,
            text="[Enter] Autofill  •  [Esc] Dismiss",
            font=ctk.CTkFont(family="SF Pro Text", size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="e",
        )
        hints_label.pack(side="right")

    def _bind_keys(self):
        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.hide_palette())

    def _on_key_release(self, event):
        if event.keysym in ("Return", "Escape", "Up", "Down"):
            return
        # Debounce text search
        if self._search_debounce_job:
            self.after_cancel(self._search_debounce_job)
        self._search_debounce_job = self.after(180, self._trigger_query)

    def _trigger_query(self):
        query = self.search_entry.get().strip()
        if query:
            self.set_status("Searching LightMem...", COLOR_ACCENT)
            self.on_query(query)

    def _toggle_mic(self):
        self._is_recording = not self._is_recording
        if self._is_recording:
            self.mic_btn.configure(fg_color=COLOR_MIC_ACTIVE, text="🔴 Rec")
            self.set_status("Listening (Whistle STT)...", COLOR_MIC_ACTIVE)
            self.on_stt_toggle(True)
        else:
            self.mic_btn.configure(fg_color=COLOR_INSET, text="🎙️ Mic")
            self.set_status("Transcribing...", COLOR_ACCENT)
            self.on_stt_toggle(False)

    def _confirm(self):
        if self.current_value:
            val = self.current_value
            self.hide_palette()
            self.on_confirm_autofill(val)

    def show_palette(self):
        self.search_entry.delete(0, "end")
        self.result_label.configure(
            text="Type a query or press Mic to retrieve facts...",
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.current_value = ""
        self.set_status("Ready", COLOR_ACCENT)
        self.deiconify()
        self.lift()
        self.search_entry.focus_force()

    def hide_palette(self):
        if self._is_recording:
            self._toggle_mic()
        self.withdraw()
        self.on_dismiss()

    def set_status(self, text: str, color: str = COLOR_ACCENT):
        self.status_pill.configure(text=text, text_color=color)

    def display_result(self, value: str, mode: str = "answer"):
        self.current_value = value
        if value:
            self.result_label.configure(
                text=value,
                text_color=COLOR_TEXT_PRIMARY,
            )
            self.set_status(f"Found via {mode} • Press Enter to paste", COLOR_SUCCESS)
        else:
            self.result_label.configure(
                text="No matching memory found.",
                text_color=COLOR_TEXT_SECONDARY,
            )
            self.set_status("Not found", COLOR_TEXT_SECONDARY)

    def set_transcribed_query(self, query: str):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)
        self.set_status("Transcribed • Searching...", COLOR_ACCENT)
        self.on_query(query)

    def _drain_events(self):
        """Process thread-safe events posted from background tasks."""
        try:
            while not self.event_queue.empty():
                evt, data = self.event_queue.get_nowait()
                if evt == "result":
                    self.display_result(data.get("value", ""), data.get("mode", "recall"))
                elif evt == "transcription":
                    self.set_transcribed_query(data)
                elif evt == "status":
                    self.set_status(data.get("text", ""), data.get("color", COLOR_ACCENT))
        finally:
            self.after(40, self._drain_events)

"""LightMem Windows Voice Autofill Application.

Main entry point that registers the global `Ctrl + Shift + Space` hotkey,
manages the floating CustomTkinter palette, and orchestrates:
- Target window capture & focus restoration (win32gui)
- On-device Speech-to-Text transcription (Cactus Needle / Whistle)
- Hybrid memory answering & recall (LightMem CLI)
"""

from __future__ import annotations

import logging
import sys
import threading
import time

import customtkinter as ctk

from injector import WindowsInjector
from lmem_bridge import LightMemBridge
from stt_engine import SpeechToTextEngine
from ui import FloatingAutofillPalette

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lightmem_autofill.main")


class AutofillApplication:
    def __init__(self):
        # Configure appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Hidden root window
        self.root = ctk.CTk()
        self.root.withdraw()

        # Components
        self.injector = WindowsInjector()
        self.bridge = LightMemBridge()
        self.stt = SpeechToTextEngine()

        # UI Palette
        self.palette = FloatingAutofillPalette(
            on_query=self.handle_query,
            on_stt_toggle=self.handle_stt_toggle,
            on_confirm_autofill=self.handle_autofill,
            on_dismiss=self.handle_dismiss,
        )

        self.target_hwnd = None
        self._setup_hotkey()

    def _setup_hotkey(self):
        """Register the global Ctrl+Shift+Space hotkey."""
        try:
            import keyboard

            hotkey = "ctrl+shift+space"
            keyboard.add_hotkey(hotkey, self._on_hotkey_triggered)
            logger.info(f"Global hotkey registered: '{hotkey.upper()}'.")
        except Exception as e:
            logger.warning(
                f"Global hotkey registration warning: {e}. "
                "(If running on Windows, make sure terminal has standard permissions)."
            )

    def _on_hotkey_triggered(self):
        """Called asynchronously when user presses Ctrl+Shift+Space."""
        logger.info("Hotkey detected. Capturing active window...")
        self.target_hwnd = self.injector.capture_target_window()

        # Schedule show on UI main thread
        self.root.after(0, self.palette.show_palette)

    def handle_query(self, query: str):
        """Query LightMem in a background daemon thread."""
        def worker():
            res = self.bridge.query(query)
            self.palette.event_queue.put(("result", res))

        threading.Thread(target=worker, daemon=True).start()

    def handle_stt_toggle(self, is_starting: bool):
        """Start or stop the audio recording and transcription worker."""
        if is_starting:
            started = self.stt.start_recording()
            if not started:
                self.palette.event_queue.put((
                    "status",
                    {"text": "Mic error or dependencies missing", "color": "#FF453A"}
                ))
        else:
            def transcribe_worker():
                transcription = self.stt.stop_and_transcribe()
                if transcription:
                    self.palette.event_queue.put(("transcription", transcription))
                else:
                    self.palette.event_queue.put((
                        "status",
                        {"text": "No speech detected", "color": "#98989D"}
                    ))

            threading.Thread(target=transcribe_worker, daemon=True).start()

    def handle_autofill(self, text: str):
        """Inject the selected text into the previously active window."""
        def inject_worker():
            # Brief delay to allow palette window to completely release focus
            time.sleep(0.05)
            self.injector.inject_text(text, self.target_hwnd)

        threading.Thread(target=inject_worker, daemon=True).start()

    def handle_dismiss(self):
        logger.debug("Palette dismissed.")

    def run(self):
        """Start the application loop."""
        logger.info("LightMem Voice Autofill active. Press Ctrl+Shift+Space to open.")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Shutting down...")


if __name__ == "__main__":
    app = AutofillApplication()
    app.run()

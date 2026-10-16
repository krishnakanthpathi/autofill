"""Target Window Focus & Keystroke Injection Module.

Handles tracking the user's previously focused window (HWND) and safely
restoring focus to simulate `Ctrl + V` clipboard paste on Windows.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

import pyperclip

logger = logging.getLogger("lightmem_autofill.injector")

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32con
    import win32gui
    import win32process
    import keyboard
else:
    win32gui = None
    win32con = None
    keyboard = None


class WindowsInjector:
    def __init__(self):
        self.last_target_hwnd: Optional[int] = None

    def capture_target_window(self) -> Optional[int]:
        """Capture the currently focused window handle before displaying the palette."""
        if not IS_WINDOWS or not win32gui:
            return None

        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                self.last_target_hwnd = hwnd
                title = win32gui.GetWindowText(hwnd)
                logger.debug(f"Captured target window: HWND={hwnd}, Title='{title}'")
                return hwnd
        except Exception as e:
            logger.error(f"Error capturing foreground window: {e}")
        return None

    def inject_text(self, text: str, target_hwnd: Optional[int] = None) -> bool:
        """Restore target window focus, write text to clipboard, and send Ctrl+V."""
        if not text:
            return False

        target = target_hwnd or self.last_target_hwnd

        # 1. Place text onto system clipboard
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
            return False

        if not IS_WINDOWS:
            logger.info(f"[Non-Windows Simulation] Copied text to clipboard: '{text}'")
            return True

        # 2. Switch focus back to the recorded target window
        if target and win32gui:
            try:
                # Force window to foreground
                win32gui.ShowWindow(target, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target)
            except Exception as e:
                logger.debug(f"SetForegroundWindow notice: {e}")

        # 3. Allow target window message loop to activate focus
        time.sleep(0.08)

        # 4. Simulate Ctrl+V paste
        try:
            if keyboard:
                keyboard.send("ctrl+v")
                logger.info(f"Pasted text into HWND={target}")
                return True
        except Exception as e:
            logger.error(f"Failed to send Ctrl+V keystroke: {e}")

        return False

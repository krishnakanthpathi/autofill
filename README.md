# LightMem Windows Voice Autofill 🎙️⚡

A minimalist, floating Windows desktop autofill palette powered by **LightMem** and **Cactus Needle** (Whistle on-device Speech-to-Text).

No browser extensions required. Works across any Windows application (Chrome, Edge, Slack, Terminal, Notepad, VS Code).

---

## Architecture & How It Works

1. **Global Hotkey (`Ctrl + Shift + Space`)**:
   - Captures the handle (`HWND`) of your active window.
   - Pops up a floating, frameless dark-mode palette at natural eye level.

2. **Push-to-Talk Speech-to-Text (Cactus Needle)**:
   - Click **🎙️ Mic** or toggle recording.
   - Whistle model runs locally on your CPU (~17MB) with zero cloud latency.
   - Transcribed query fills the search bar automatically.

3. **LightMem Hybrid Retrieval**:
   - Queries `lmem answer "<query>"` for exact span extraction.
   - Falls back to `lmem recall "<query>"` if no high-confidence single answer exists.

4. **Window Focus Restoration & Keystroke Injection**:
   - Press `Enter`: The palette hides, restores focus to your original window, and simulates `Ctrl + V` clipboard paste.

---

## Installation (Windows)

1. **Clone or copy the directory**:
   ```cmd
   cd lightmem-autofill
   ```

2. **Install dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
   *(Ensure `cactus-needle[mic]` and `pywin32` install cleanly)*

3. **Verify LightMem CLI**:
   Ensure `lmem` is available in your PATH:
   ```cmd
   lmem --version
   ```

---

## Running the Application

```cmd
python main.py
```

### Controls:
- **`Ctrl + Shift + Space`**: Toggle floating autofill palette from anywhere in Windows.
- **`🎙️ Mic` Button**: Start/stop on-device voice recording.
- **`Enter`**: Autofill the found memory directly into your active input field.
- **`Esc`**: Dismiss the palette without pasting.

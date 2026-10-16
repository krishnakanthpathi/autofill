"""Speech-to-Text Engine for LightMem Autofill.

Uses `cactus-needle` (Whistle on-device STT model) + `sounddevice` for
push-to-talk microphone audio recording and instant local transcription.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import wave
from typing import Callable, Optional

logger = logging.getLogger("lightmem_autofill.stt")

# Check needle availability
try:
    import needle
    NEEDLE_AVAILABLE = True
except ImportError:
    NEEDLE_AVAILABLE = False
    logger.warning("Cactus Needle not found. Run `pip install cactus-needle[mic]`.")

# Check sounddevice & numpy
try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("sounddevice or numpy missing. Run `pip install sounddevice numpy`.")


class SpeechToTextEngine:
    SAMPLE_RATE = 16000  # 16 kHz required by Whistle / Whisper models
    CHANNELS = 1         # Mono

    def __init__(self):
        self._is_recording = False
        self._audio_chunks: list[np.ndarray] = []
        self._record_thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.InputStream] = None

    @property
    def is_available(self) -> bool:
        return NEEDLE_AVAILABLE and AUDIO_AVAILABLE

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self) -> bool:
        """Start capturing audio from the default microphone."""
        if not self.is_available:
            logger.error("STT engine dependencies not met.")
            return False

        if self._is_recording:
            return True

        self._audio_chunks = []
        self._is_recording = True

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio status: {status}")
            if self._is_recording:
                self._audio_chunks.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="float32",
                callback=audio_callback,
            )
            self._stream.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self._is_recording = False
            return False

    def stop_and_transcribe(self, timeout_sec: float = 15.0) -> str:
        """Stop audio recording, save temporary WAV, and run Whistle transcription."""
        if not self._is_recording:
            return ""

        self._is_recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug(f"Error stopping stream: {e}")
            self._stream = None

        if not self._audio_chunks:
            return ""

        # Concatenate audio frames
        try:
            audio_data = np.concatenate(self._audio_chunks, axis=0)
        except Exception as e:
            logger.error(f"Error concatenating audio: {e}")
            return ""

        # Ignore tiny clicks (< 0.25 seconds)
        if len(audio_data) < int(self.SAMPLE_RATE * 0.25):
            return ""

        # Save to temporary 16-bit PCM WAV
        temp_wav = os.path.join(tempfile.gettempdir(), f"stt_{int(time.time()*1000)}.wav")
        try:
            int16_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(temp_wav, "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(2)  # 2 bytes = 16-bit
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(int16_data.tobytes())

            # Run needle transcription
            logger.info("Transcribing audio via Cactus Needle...")
            result = needle.transcribe(temp_wav)
            if isinstance(result, dict):
                text = result.get("text", "").strip()
            elif isinstance(result, str):
                text = result.strip()
            else:
                text = str(result).strip()

            return text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

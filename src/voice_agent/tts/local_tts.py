"""Local macOS native Text-to-Speech using 'say' command with barge-in stop support."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "Samantha"  # High-quality macOS built-in voice


class LocalAudioPlayback:
    """
    Plays speech aloud using macOS native speech synthesis.
    Supports instant barge-in cancellation by terminating the active speech process.
    """

    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        self.voice = voice
        self._current_proc: asyncio.subprocess.Process | None = None
        self._is_playing = False
        self._stop_event = asyncio.Event()
        self._last_played_time = 0.0

    @property
    def last_played_time(self) -> float:
        return self._last_played_time

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def stop(self) -> None:
        """Immediately interrupt/stop playback."""
        self._stop_event.set()
        if self._current_proc and self._current_proc.returncode is None:
            try:
                self._current_proc.terminate()
            except ProcessLookupError:
                pass
        self._is_playing = False
        logger.debug("LocalTTS: stopped")

    async def speak(self, text: str, cancel_event: asyncio.Event | None = None) -> None:
        """Speak a sentence aloud, respecting cancellation events."""
        clean_text = text.strip()
        if not clean_text:
            return

        if cancel_event and cancel_event.is_set():
            return

        self._stop_event.clear()
        self._is_playing = True

        cmd = ["say", "-v", self.voice, clean_text]
        try:
            self._current_proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Wait for speech to complete or cancellation
            while self._current_proc.returncode is None:
                if (cancel_event and cancel_event.is_set()) or self._stop_event.is_set():
                    self.stop()
                    break
                await asyncio.sleep(0.04)

        except asyncio.CancelledError:
            self.stop()
        finally:
            self._is_playing = False
            self._current_proc = None
            self._last_played_time = time.monotonic()

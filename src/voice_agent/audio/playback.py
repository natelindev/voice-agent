"""Streaming PCM audio playback via sounddevice with immediate barge-in stop."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import AsyncGenerator

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000   # matches OpenAI TTS PCM output
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 2048      # samples per callback (≈85ms at 24kHz)


class AudioPlayback:
    """Plays streaming int16 PCM audio to the speaker with immediate stop support."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        blocksize: int = BLOCKSIZE,
        device: int | str | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._blocksize = blocksize
        self._device = device

        # Thread-safe buffer queue shared between async producer and SD callback
        self._pcm_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=50)
        self._stream: sd.OutputStream | None = None
        self._playing = False
        self._stop_event = threading.Event()
        self._leftover: np.ndarray = np.array([], dtype=np.int16)

    def _callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("sounddevice playback status: %s", status)

        if self._stop_event.is_set():
            outdata[:] = 0
            return

        needed = frames
        out_buf = np.zeros(frames, dtype=np.int16)
        offset = 0

        # Drain leftover from previous callback first
        if len(self._leftover) > 0:
            take = min(needed, len(self._leftover))
            out_buf[offset : offset + take] = self._leftover[:take]
            self._leftover = self._leftover[take:]
            offset += take
            needed -= take

        while needed > 0:
            try:
                chunk = self._pcm_queue.get_nowait()
            except queue.Empty:
                break  # underrun — output silence for remaining frames

            if chunk is None:
                # Sentinel: stream finished
                self._stop_event.set()
                break

            take = min(needed, len(chunk))
            out_buf[offset : offset + take] = chunk[:take]
            if len(chunk) > take:
                self._leftover = chunk[take:]
            offset += take
            needed -= take

        outdata[:, 0] = out_buf

    async def play_stream(
        self,
        pcm_stream: AsyncGenerator[bytes, None],
    ) -> None:
        """
        Consume an async generator of raw int16 PCM bytes and play them.
        Returns when the stream is exhausted or stop() is called.
        """
        self._stop_event.clear()
        self._playing = True
        self._leftover = np.array([], dtype=np.int16)

        # Drain any stale data
        while not self._pcm_queue.empty():
            try:
                self._pcm_queue.get_nowait()
            except queue.Empty:
                break

        self._stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=self._blocksize,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()

        try:
            async for chunk_bytes in pcm_stream:
                if self._stop_event.is_set():
                    break
                samples = np.frombuffer(chunk_bytes, dtype=np.int16)
                # Block with a small timeout so stop() is responsive
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda s=samples: self._pcm_queue.put(s, timeout=1.0),
                )

            # Send sentinel to signal end-of-stream to callback
            if not self._stop_event.is_set():
                self._pcm_queue.put(None)
                # Wait until the callback processes the sentinel
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._wait_until_done)
        finally:
            self._playing = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    def _wait_until_done(self) -> None:
        """Block until the sentinel is consumed (playback finishes)."""
        self._stop_event.wait(timeout=30)

    def stop(self) -> None:
        """Immediately stop playback (barge-in or cancel)."""
        self._stop_event.set()
        # Drain queue so callback and producer unblock quickly
        while not self._pcm_queue.empty():
            try:
                self._pcm_queue.get_nowait()
            except queue.Empty:
                break
        logger.debug("Playback: stopped")

    @property
    def is_playing(self) -> bool:
        return self._playing

"""Microphone audio capture using sounddevice."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512  # 32ms at 16kHz


class AudioCapture:
    """Captures microphone input and exposes an async stream of numpy chunks."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_samples: int = CHUNK_SAMPLES,
        device: int | str | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_samples = chunk_samples
        self._device = device
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        self._stream: sd.InputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("sounddevice status: %s", status)
        # indata shape: (frames, channels) — take channel 0, copy to own memory
        chunk = indata[:, 0].copy()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, chunk)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self._chunk_samples,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()
        logger.info(
            "Audio capture started (device=%s, %dHz, %d samples/chunk)",
            self._device or "default",
            self._sample_rate,
            self._chunk_samples,
        )

    async def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Audio capture stopped")

    def __aiter__(self) -> AsyncIterator[np.ndarray]:
        return self._chunk_generator()

    async def _chunk_generator(self) -> AsyncIterator[np.ndarray]:
        while True:
            chunk = await self._queue.get()
            yield chunk

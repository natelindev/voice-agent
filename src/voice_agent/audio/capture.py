"""Microphone audio capture using sounddevice."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

import numpy as np
import sounddevice as sd

if TYPE_CHECKING:
    from voice_agent.events.hub import EventHub

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
        event_hub: EventHub | None = None,
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_samples = chunk_samples
        self._device = device
        self._event_hub = event_hub
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        self._stream: sd.InputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self._mock_task: asyncio.Task | None = None
        self._downsample_step: int = 1

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("sounddevice status: %s", status)
        flat = indata if indata.ndim == 1 else indata[:, 0]
        if self._downsample_step > 1:
            chunk = flat[::self._downsample_step].copy()
        else:
            chunk = flat.copy()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, chunk)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            # 1. Try direct 16kHz stream
            self._downsample_step = 1
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
            return
        except Exception as e1:
            logger.debug("Direct 16kHz capture failed: %s; trying device native rate", e1)

        try:
            # 2. Try native device sample rate (e.g. 48kHz on Mac)
            dev_info = sd.query_devices(self._device or sd.default.device[0])
            native_rate = int(dev_info.get("default_samplerate", 48000))
            if native_rate >= 32000:
                self._downsample_step = native_rate // self._sample_rate
                blocksize = self._chunk_samples * self._downsample_step
                self._stream = sd.InputStream(
                    samplerate=native_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=blocksize,
                    device=self._device,
                    callback=self._callback,
                )
                self._stream.start()
                logger.info(
                    "Audio capture started at native %dHz (downsampling %dx to 16kHz)",
                    native_rate,
                    self._downsample_step,
                )
                return
        except Exception as e2:
            logger.warning("Native capture failed (%s). Falling back to mock audio generator.", e2)

        # 3. Graceful fallback if mic permission is blocked or unavailable
        self._stream = None
        self._mock_task = asyncio.create_task(self._mock_stream_loop())

    async def _mock_stream_loop(self) -> None:
        """Fallback silence/ambient stream when physical mic is inaccessible."""
        try:
            while True:
                chunk = np.zeros(self._chunk_samples, dtype=np.float32)
                await self._queue.put(chunk)
                await asyncio.sleep(self._chunk_samples / self._sample_rate)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self._mock_task is not None:
            self._mock_task.cancel()
            self._mock_task = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Audio capture stopped")

    def __aiter__(self) -> AsyncIterator[np.ndarray]:
        return self._chunk_generator()

    async def _chunk_generator(self) -> AsyncIterator[np.ndarray]:
        import time
        last_emit = 0.0
        while True:
            chunk = await self._queue.get()
            if self._event_hub is not None and self._event_hub.is_muted:
                chunk = np.zeros_like(chunk)
            elif self._event_hub is not None:
                now = time.monotonic()
                if now - last_emit >= 0.03:  # ~33 fps
                    last_emit = now
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    peak = float(np.max(np.abs(chunk)))
                    level = min(1.0, rms * 5.0)
                    self._event_hub.emit_audio_level(level=level, peak=peak)
            yield chunk

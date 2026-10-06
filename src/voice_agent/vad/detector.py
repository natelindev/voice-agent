"""Silero VAD wrapper for real-time speech start/end detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore
    HAS_TORCH = False

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512  # must be 512 for Silero VAD at 16kHz


class VADEventType(Enum):
    SPEECH_START = auto()
    SPEECH_END = auto()


@dataclass
class VADEvent:
    type: VADEventType
    # Populated only for SPEECH_END: accumulated int16 PCM bytes
    audio_buffer: bytes = field(default=b"")


class VADDetector:
    """Wraps Silero VAD (or adaptive energy VAD fallback) for streaming speech detection."""

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_ms: int = 600,
        min_speech_ms: int = 100,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self._threshold = threshold
        self._min_silence_ms = min_silence_ms
        self._min_speech_ms = min_speech_ms
        self._sample_rate = sample_rate

        self._in_speech: bool = False
        self._speech_chunks: list[np.ndarray] = []
        self._silence_chunks_count: int = 0
        self._speech_chunks_count: int = 0
        self._energy_threshold: float = 0.015

        if HAS_TORCH:
            try:
                logger.info("Loading Silero VAD model...")
                self._model, self._utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    trust_repo=True,
                    verbose=False,
                )
                self._model.eval()
                _, _, _, VADIterator, _ = self._utils
                self._VADIterator = VADIterator
                self._iterator: object = self._make_iterator()
                logger.info("Silero VAD model loaded")
                return
            except Exception as e:
                logger.warning("Could not load torch silero-vad: %s; using adaptive energy VAD", e)

        self._iterator = None
        logger.info("Using native adaptive energy VAD detector")

    def _make_iterator(self) -> object:
        if not HAS_TORCH or not hasattr(self, "_VADIterator"):
            return None
        return self._VADIterator(
            self._model,
            threshold=self._threshold,
            sampling_rate=self._sample_rate,
            min_silence_duration_ms=self._min_silence_ms,
            speech_pad_ms=30,
        )

    def process_chunk(self, chunk: np.ndarray) -> VADEvent | None:
        """Process one audio chunk (float32, 512 samples). Returns a VADEvent or None."""
        if self._iterator is not None and HAS_TORCH:
            return self._process_silero(chunk)
        return self._process_energy(chunk)

    def _process_silero(self, chunk: np.ndarray) -> VADEvent | None:
        tensor = torch.from_numpy(chunk)
        try:
            result = self._iterator(tensor, return_seconds=False)
        except Exception:
            self.reset()
            return None

        if result is None:
            if self._in_speech:
                self._speech_chunks.append(chunk)
            return None

        if "start" in result and not self._in_speech:
            self._in_speech = True
            self._speech_chunks = [chunk]
            logger.debug("VAD: speech start")
            return VADEvent(type=VADEventType.SPEECH_START)

        if "end" in result and self._in_speech:
            self._in_speech = False
            audio_buffer = self._flush_buffer()
            logger.debug("VAD: speech end (%d bytes)", len(audio_buffer))
            self._speech_chunks = []
            return VADEvent(type=VADEventType.SPEECH_END, audio_buffer=audio_buffer)

        if self._in_speech:
            self._speech_chunks.append(chunk)

        return None

    def _process_energy(self, chunk: np.ndarray) -> VADEvent | None:
        """Adaptive energy VAD fallback with zero PyTorch dependency."""
        rms = float(np.sqrt(np.mean(chunk**2)))
        chunk_ms = (len(chunk) / self._sample_rate) * 1000  # 32ms

        is_voice = rms > self._energy_threshold

        if is_voice:
            self._silence_chunks_count = 0
            self._speech_chunks_count += 1
            self._speech_chunks.append(chunk)

            if not self._in_speech and (self._speech_chunks_count * chunk_ms >= self._min_speech_ms):
                self._in_speech = True
                logger.debug("Energy VAD: speech start (rms=%.4f)", rms)
                return VADEvent(type=VADEventType.SPEECH_START)

        else:
            if self._in_speech:
                self._speech_chunks.append(chunk)
                self._silence_chunks_count += 1
                if self._silence_chunks_count * chunk_ms >= self._min_silence_ms:
                    self._in_speech = False
                    self._speech_chunks_count = 0
                    self._silence_chunks_count = 0
                    audio_buffer = self._flush_buffer()
                    logger.debug("Energy VAD: speech end (%d bytes)", len(audio_buffer))
                    self._speech_chunks = []
                    return VADEvent(type=VADEventType.SPEECH_END, audio_buffer=audio_buffer)
            else:
                self._speech_chunks_count = 0

        return None

    def _flush_buffer(self) -> bytes:
        """Convert accumulated float32 chunks to int16 PCM bytes."""
        if not self._speech_chunks:
            return b""
        combined = np.concatenate(self._speech_chunks)
        # Clamp and convert float32 [-1, 1] → int16
        int16 = (np.clip(combined, -1.0, 1.0) * 32767).astype(np.int16)
        return int16.tobytes()

    def reset(self) -> None:
        """Reset VAD state (call after barge-in or session restart)."""
        self._iterator = self._make_iterator()
        self._in_speech = False
        self._speech_chunks = []
        logger.debug("VAD: reset")

    @property
    def in_speech(self) -> bool:
        return self._in_speech

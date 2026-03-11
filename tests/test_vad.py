"""Tests for the VAD detector."""

from __future__ import annotations

import numpy as np
import pytest

from voice_agent.vad.detector import VADDetector, VADEventType


@pytest.fixture(scope="module")
def vad() -> VADDetector:
    return VADDetector(threshold=0.5, min_silence_ms=300)


def _silence_chunk() -> np.ndarray:
    return np.zeros(512, dtype=np.float32)


def _speech_chunk(amplitude: float = 0.5) -> np.ndarray:
    t = np.linspace(0, 0.032, 512, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.float32)


def test_silence_produces_no_event(vad: VADDetector) -> None:
    vad.reset()
    for _ in range(10):
        event = vad.process_chunk(_silence_chunk())
        assert event is None or event.type == VADEventType.SPEECH_END


def test_vad_resets_cleanly(vad: VADDetector) -> None:
    vad.reset()
    assert not vad.in_speech


def test_speech_buffer_flushed_as_bytes(vad: VADDetector) -> None:
    """Verify that flush returns bytes on speech end."""
    vad.reset()
    # Simulate internal accumulation then flush
    vad._in_speech = True
    chunk = _speech_chunk()
    vad._speech_chunks = [chunk, chunk]
    buf = vad._flush_buffer()
    assert isinstance(buf, bytes)
    # 2 chunks × 512 samples × 2 bytes/sample (int16)
    assert len(buf) == 2 * 512 * 2

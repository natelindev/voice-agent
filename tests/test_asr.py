"""Tests for the ASR transcriber helper functions."""

from __future__ import annotations

import io
import wave

import pytest

from voice_agent.asr.transcriber import _pcm_to_wav


def test_pcm_to_wav_produces_valid_wav() -> None:
    """Verify that _pcm_to_wav wraps PCM bytes in a valid WAV container."""
    # 0.5s of silence: 16000 samples × 2 bytes
    pcm = bytes(16000 * 2)
    wav_bytes = _pcm_to_wav(pcm, sample_rate=16000, channels=1)

    buf = io.BytesIO(wav_bytes)
    with wave.open(buf) as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


def test_pcm_to_wav_empty() -> None:
    """Empty PCM produces a valid zero-frame WAV."""
    wav_bytes = _pcm_to_wav(b"", sample_rate=16000, channels=1)
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf) as wf:
        assert wf.getnframes() == 0

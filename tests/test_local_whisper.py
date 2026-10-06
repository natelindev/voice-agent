"""Tests for local Apple Silicon Whisper ASR."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from voice_agent.asr.local_whisper import LocalWhisperTranscriber, _pcm_to_wav


def test_pcm_to_wav_header() -> None:
    pcm_data = b"\x00\x00" * 800  # 800 samples of 16-bit silence
    wav_bytes = _pcm_to_wav(pcm_data, sample_rate=16000, channels=1)
    assert len(wav_bytes) == len(pcm_data) + 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_transcribe_short_buffer_returns_empty() -> None:
    transcriber = LocalWhisperTranscriber()
    # Less than 3200 bytes (0.1s at 16kHz 16-bit)
    result = await transcriber.transcribe(b"\x00" * 100)
    assert result == ""


@pytest.mark.asyncio
async def test_transcribe_http_success() -> None:
    transcriber = LocalWhisperTranscriber()
    fake_pcm = b"\x01\x00" * 2000

    with patch.object(transcriber, "_http_transcribe", return_value="hello voice assistant") as mock_http:
        result = await transcriber.transcribe(fake_pcm)
        assert result == "hello voice assistant"
        mock_http.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_http_fallback_to_cli() -> None:
    transcriber = LocalWhisperTranscriber()
    fake_pcm = b"\x01\x00" * 2000

    with patch.object(transcriber, "_http_transcribe", side_effect=Exception("Server down")), \
         patch.object(transcriber, "_cli_transcribe", new_callable=AsyncMock, return_value="cli fallback text") as mock_cli:
        result = await transcriber.transcribe(fake_pcm)
        assert result == "cli fallback text"
        mock_cli.assert_awaited_once()

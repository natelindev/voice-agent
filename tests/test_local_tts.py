"""Tests for local macOS native TTS playback and barge-in."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from voice_agent.tts.local_tts import LocalAudioPlayback


@pytest.mark.asyncio
async def test_speak_empty_text_does_nothing() -> None:
    tts = LocalAudioPlayback()
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        await tts.speak("   ")
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_speak_cancelled_before_start() -> None:
    tts = LocalAudioPlayback()
    cancel_event = asyncio.Event()
    cancel_event.set()
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        await tts.speak("Hello there", cancel_event=cancel_event)
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_stop_terminates_subprocess() -> None:
    from unittest.mock import MagicMock
    tts = LocalAudioPlayback()
    proc = AsyncMock()
    proc.terminate = MagicMock()
    proc.returncode = None
    tts._current_proc = proc
    tts._is_playing = True

    tts.stop()

    assert not tts.is_playing
    proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_speak_records_completion_time() -> None:
    tts = LocalAudioPlayback()
    proc = AsyncMock()
    proc.returncode = 0
    with patch("asyncio.create_subprocess_exec", return_value=proc), patch(
        "voice_agent.tts.local_tts.time.monotonic", return_value=123.0
    ):
        await tts.speak("Example response")
    assert not tts.is_playing
    assert tts.last_played_time == 123.0

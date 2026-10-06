"""Tests for TUIDashboard rendering and event handling."""

import asyncio
from unittest.mock import patch
import pytest

from voice_agent.events.hub import (
    AudioLevelEvent,
    EventHub,
    PipelineState,
    StateChangeEvent,
    TokenDeltaEvent,
    TranscriptEvent,
    TurnMetricsEvent,
)
from voice_agent.tui.dashboard import TUIDashboard


def test_status_pill_formatting() -> None:
    hub = EventHub()
    tui = TUIDashboard(hub)

    tui._current_state = "listening"
    assert "LISTENING" in tui._get_status_pill()

    tui._current_state = "thinking"
    assert "THINKING" in tui._get_status_pill()

    tui._current_state = "speaking"
    assert "SPEAKING" in tui._get_status_pill()

    tui._current_state = "interrupted"
    assert "INTERRUPTED" in tui._get_status_pill()


def test_vu_meter_rendering() -> None:
    hub = EventHub()
    tui = TUIDashboard(hub)

    tui._audio_level = 0.0
    meter_silent = tui._render_vu_meter(width=10)
    assert len(meter_silent) > 0

    tui._audio_level = 0.8
    meter_loud = tui._render_vu_meter(width=10)
    assert len(meter_loud) > 0


@pytest.mark.asyncio
async def test_tui_event_consumer() -> None:
    hub = EventHub()
    tui = TUIDashboard(hub)
    tui._is_running = True

    consumer_task = asyncio.create_task(tui._event_consumer())
    await asyncio.sleep(0.02)  # Allow consumer to subscribe to hub

    hub.emit_state(PipelineState.TRANSCRIBING, "Transcribing...")
    hub.emit_audio_level(0.42, 0.75)
    hub.emit_transcript("user", "Hello there", is_final=True)
    hub.emit_token_delta("Hi! ")
    hub.emit_token_delta("How are you?")
    hub.emit_transcript("assistant", "Hi! How are you?", is_final=True)
    hub.emit_turn_metrics("turn-1", asr_seconds=0.15, ttft_seconds=0.20, tts_first_chunk_seconds=0.08, total_seconds=0.85)

    await asyncio.sleep(0.05)

    assert tui._current_state == "transcribing"
    assert len(tui._history) == 2
    assert tui._history[0].role == "user"
    assert tui._history[0].text == "Hello there"
    assert tui._history[1].role == "assistant"
    assert tui._history[1].text == "Hi! How are you?"
    assert "ASR: 150ms" in tui._history[1].metrics

    tui._is_running = False
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

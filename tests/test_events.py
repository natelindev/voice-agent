"""Tests for EventHub pub-sub and telemetry events."""

from __future__ import annotations

import asyncio
try:
    import pytest
except ImportError:
    class DummyMark:
        def __getattr__(self, name: str):
            return lambda fn: fn

    class DummyPytest:
        mark = DummyMark()

    pytest = DummyPytest()  # type: ignore

from voice_agent.events.hub import (
    AudioLevelEvent,
    ControlCommandEvent,
    EventHub,
    PipelineState,
    StateChangeEvent,
    TranscriptEvent,
    TurnMetricsEvent,
)


@pytest.mark.asyncio
async def test_event_hub_publish_and_subscribe() -> None:
    hub = EventHub()
    hub.set_loop(asyncio.get_running_loop())
    q = hub.subscribe()

    # Emit state
    hub.emit_state(PipelineState.LISTENING, "Listening test")
    event = await q.get()
    assert isinstance(event, StateChangeEvent)
    assert event.state == PipelineState.LISTENING
    assert event.message == "Listening test"
    assert hub.current_state == PipelineState.LISTENING

    # Emit transcript
    hub.emit_transcript("user", "Hello assistant", is_final=True)
    event2 = await q.get()
    assert isinstance(event2, TranscriptEvent)
    assert event2.role == "user"
    assert event2.text == "Hello assistant"

    # Emit turn metrics
    hub.emit_turn_metrics("turn-1", asr_seconds=0.3, ttft_seconds=0.2, tts_first_chunk_seconds=0.1, total_seconds=1.1)
    event3 = await q.get()
    assert isinstance(event3, TurnMetricsEvent)
    assert event3.turn_id == "turn-1"
    assert event3.total_seconds == 1.1

    hub.unsubscribe(q)


@pytest.mark.asyncio
async def test_control_commands() -> None:
    hub = EventHub()
    received_commands = []

    def handler(cmd: ControlCommandEvent) -> None:
        received_commands.append(cmd.action)

    hub.add_control_handler(handler)

    # Dispatch mute
    hub.dispatch_control(ControlCommandEvent(action="mute"))
    assert hub.is_muted is True
    assert "mute" in received_commands

    # Dispatch unmute
    hub.dispatch_control(ControlCommandEvent(action="unmute"))
    assert hub.is_muted is False
    assert "unmute" in received_commands

"""Central event and telemetry hub for Voice Agent."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from enum import Enum
import logging
import time
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger(__name__)


class PipelineState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SPEECH_DETECTED = "speech_detected"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class BaseEvent:
    event_type: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Ensure enums serialize to their value
        for k, v in list(data.items()):
            if isinstance(v, Enum):
                data[k] = v.value
        return data


@dataclass
class AudioLevelEvent(BaseEvent):
    event_type: str = "audio_level"
    level: float = 0.0  # RMS normalized [0.0, 1.0]
    peak: float = 0.0
    is_speech: bool = False


@dataclass
class StateChangeEvent(BaseEvent):
    event_type: str = "state_change"
    state: PipelineState = PipelineState.IDLE
    message: str = ""


@dataclass
class TranscriptEvent(BaseEvent):
    event_type: str = "transcript"
    role: str = "user"  # "user" or "assistant"
    text: str = ""
    is_final: bool = True


@dataclass
class TokenDeltaEvent(BaseEvent):
    event_type: str = "token_delta"
    delta: str = ""


@dataclass
class TurnMetricsEvent(BaseEvent):
    event_type: str = "turn_metrics"
    turn_id: str = ""
    asr_seconds: float = 0.0
    ttft_seconds: float = 0.0
    tts_first_chunk_seconds: float = 0.0
    total_seconds: float = 0.0


@dataclass
class ControlCommandEvent(BaseEvent):
    event_type: str = "control_command"
    action: str = ""  # "interrupt", "mute", "unmute", "clear_history"
    payload: dict[str, Any] = field(default_factory=dict)


class EventHub:
    """
    Central non-blocking event dispatcher for the voice pipeline.
    Broadcasters (AudioCapture, PipelineOrchestrator) publish events here.
    Subscribers (Rich TUI, WebSockets) receive events through async queues.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[BaseEvent]] = set()
        self._control_handlers: list[Callable[[ControlCommandEvent], None]] = []
        self._current_state: PipelineState = PipelineState.IDLE
        self._state_message: str = "Initializing"
        self._is_muted: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def current_state(self) -> PipelineState:
        return self._current_state

    @property
    def state_message(self) -> str:
        return self._state_message

    @property
    def is_muted(self) -> bool:
        return self._is_muted

    def add_control_handler(self, handler: Callable[[ControlCommandEvent], None]) -> None:
        self._control_handlers.append(handler)

    def remove_control_handler(self, handler: Callable[[ControlCommandEvent], None]) -> None:
        if handler in self._control_handlers:
            self._control_handlers.remove(handler)

    def dispatch_control(self, event: ControlCommandEvent) -> None:
        """Process an inbound command from TUI or Web UI."""
        logger.info("Control command received: %s", event.action)
        if event.action == "mute":
            self._is_muted = True
        elif event.action == "unmute":
            self._is_muted = False

        # Notify registered command handlers
        for handler in list(self._control_handlers):
            try:
                handler(event)
            except Exception:
                logger.exception("Error executing control handler for %s", event.action)

        # Broadcast the control event to all subscribers (so UI stays in sync)
        self.publish(event)

    def subscribe(self, maxsize: int = 256) -> asyncio.Queue[BaseEvent]:
        """Subscribe to the event stream. Returns an asyncio.Queue."""
        q: asyncio.Queue[BaseEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[BaseEvent]) -> None:
        """Unsubscribe a queue from the event stream."""
        self._subscribers.discard(q)

    def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all subscribers.
        Thread-safe: can be called from audio threads or async coroutines.
        """
        if isinstance(event, StateChangeEvent):
            self._current_state = event.state
            self._state_message = event.message

        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        for q in list(self._subscribers):
            # For high-frequency audio level events, drop if full to avoid latency lag
            if isinstance(event, AudioLevelEvent):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass
            else:
                # Essential events: try put_nowait, or schedule thread-safe
                if self._loop and self._loop.is_running():
                    try:
                        self._loop.call_soon_threadsafe(self._safe_put, q, event)
                    except RuntimeError:
                        pass
                else:
                    self._safe_put(q, event)

    @staticmethod
    def _safe_put(q: asyncio.Queue[BaseEvent], event: BaseEvent) -> None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Drain oldest non-critical item to make space
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    # Convenience publisher helpers
    def emit_state(self, state: PipelineState, message: str = "") -> None:
        self.publish(StateChangeEvent(state=state, message=message))

    def emit_audio_level(self, level: float, peak: float = 0.0, is_speech: bool = False) -> None:
        self.publish(AudioLevelEvent(level=level, peak=peak, is_speech=is_speech))

    def emit_transcript(self, role: str, text: str, is_final: bool = True) -> None:
        self.publish(TranscriptEvent(role=role, text=text, is_final=is_final))

    def emit_token_delta(self, delta: str) -> None:
        self.publish(TokenDeltaEvent(delta=delta))

    def emit_turn_metrics(
        self,
        turn_id: str,
        asr_seconds: float,
        ttft_seconds: float,
        tts_first_chunk_seconds: float,
        total_seconds: float,
    ) -> None:
        self.publish(
            TurnMetricsEvent(
                turn_id=turn_id,
                asr_seconds=asr_seconds,
                ttft_seconds=ttft_seconds,
                tts_first_chunk_seconds=tts_first_chunk_seconds,
                total_seconds=total_seconds,
            )
        )

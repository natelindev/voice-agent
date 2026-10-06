"""Modern, high-polish Terminal User Interface for Voice Agent."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import os
import shutil
import sys
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voice_agent.events.hub import (
        AudioLevelEvent,
        BaseEvent,
        EventHub,
        StateChangeEvent,
        TokenDeltaEvent,
        TranscriptEvent,
        TurnMetricsEvent,
    )
    from voice_agent.events.hub import PipelineState


# Try importing rich for enhanced rendering if available
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


@dataclass
class ChatTurn:
    role: str
    text: str
    timestamp: str
    metrics: str = ""


class TUIDashboard:
    """
    Renders a live, responsive terminal dashboard for Voice Agent.
    Subscribes to EventHub and updates the UI at 20-30 FPS.
    """

    # ANSI Colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[38;5;51m"
    BLUE = "\033[38;5;75m"
    GREEN = "\033[38;5;84m"
    YELLOW = "\033[38;5;220m"
    PURPLE = "\033[38;5;141m"
    ORANGE = "\033[38;5;208m"
    GRAY = "\033[38;5;242m"
    WHITE = "\033[38;5;255m"
    BG_DARK = "\033[48;5;234m"

    VU_BARS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def __init__(self, event_hub: EventHub, model_name: str = "gpt-4o-mini", voice_name: str = "coral") -> None:
        self._hub = event_hub
        self._model_name = model_name
        self._voice_name = voice_name

        self._current_state: str = "listening"
        self._state_message: str = "Ready. Speak into microphone."
        self._audio_level: float = 0.0
        self._audio_peak: float = 0.0
        self._history: list[ChatTurn] = []
        self._active_assistant_text: str = ""
        self._last_metrics: str = ""
        self._is_running: bool = False
        self._sub_task: asyncio.Task | None = None
        self._render_task: asyncio.Task | None = None
        self._start_time = time.time()

    async def start(self) -> None:
        """Start the TUI event listener and render loop."""
        self._is_running = True
        # Hide cursor and clear screen
        sys.stdout.write("\033[?25l\033[2J\033[H")
        sys.stdout.flush()

        self._sub_task = asyncio.create_task(self._event_consumer(), name="tui_consumer")
        self._render_task = asyncio.create_task(self._render_loop(), name="tui_renderer")

    async def stop(self) -> None:
        """Stop dashboard and restore terminal state."""
        self._is_running = False
        if self._sub_task:
            self._sub_task.cancel()
        if self._render_task:
            self._render_task.cancel()

        # Show cursor and restore normal style
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()

    async def _event_consumer(self) -> None:
        from voice_agent.events.hub import (
            AudioLevelEvent,
            StateChangeEvent,
            TokenDeltaEvent,
            TranscriptEvent,
            TurnMetricsEvent,
        )

        q = self._hub.subscribe(maxsize=128)
        try:
            while self._is_running:
                event = await q.get()
                if isinstance(event, AudioLevelEvent):
                    # Smooth audio level transition
                    self._audio_level = self._audio_level * 0.4 + event.level * 0.6
                    self._audio_peak = max(self._audio_peak * 0.95, event.peak)

                elif isinstance(event, StateChangeEvent):
                    self._current_state = event.state.value if hasattr(event.state, "value") else str(event.state)
                    self._state_message = event.message or self._default_state_msg(self._current_state)

                elif isinstance(event, TranscriptEvent):
                    ts = datetime.now().strftime("%H:%M:%S")
                    if event.role == "user":
                        self._history.append(ChatTurn(role="user", text=event.text, timestamp=ts))
                        self._active_assistant_text = ""
                    elif event.role == "assistant":
                        if self._active_assistant_text:
                            # Update existing turn
                            if self._history and self._history[-1].role == "assistant":
                                self._history[-1].text = event.text
                            else:
                                self._history.append(ChatTurn(role="assistant", text=event.text, timestamp=ts))
                        else:
                            self._history.append(ChatTurn(role="assistant", text=event.text, timestamp=ts))
                        self._active_assistant_text = ""

                elif isinstance(event, TokenDeltaEvent):
                    self._active_assistant_text += event.delta
                    ts = datetime.now().strftime("%H:%M:%S")
                    if not self._history or self._history[-1].role != "assistant":
                        self._history.append(ChatTurn(role="assistant", text=self._active_assistant_text, timestamp=ts))
                    else:
                        self._history[-1].text = self._active_assistant_text

                elif isinstance(event, TurnMetricsEvent):
                    metrics_str = (
                        f"ASR: {int(event.asr_seconds*1000)}ms · "
                        f"TTFT: {int(event.ttft_seconds*1000)}ms · "
                        f"TTS: {int(event.tts_first_chunk_seconds*1000)}ms · "
                        f"Total: {event.total_seconds:.2f}s"
                    )
                    self._last_metrics = metrics_str
                    if self._history and self._history[-1].role == "assistant":
                        self._history[-1].metrics = metrics_str

        except asyncio.CancelledError:
            pass
        finally:
            self._hub.unsubscribe(q)

    def _default_state_msg(self, state: str) -> str:
        msgs = {
            "listening": "Listening... (speak naturally)",
            "speech_detected": "Speech detected...",
            "transcribing": "Transcribing audio with Whisper...",
            "thinking": "Generating response with GPT-4o-mini...",
            "speaking": "Streaming voice playback via TTS...",
            "interrupted": "Barge-in detected! Interrupted playback.",
            "idle": "Idle",
        }
        return msgs.get(state, state)

    async def _render_loop(self) -> None:
        """Render loop running at ~25 FPS."""
        try:
            while self._is_running:
                self._draw()
                await asyncio.sleep(0.04)
        except asyncio.CancelledError:
            pass

    def _get_status_pill(self) -> str:
        s = self._current_state
        if s == "listening":
            return f"{self.BOLD}{self.GREEN}● LISTENING{self.RESET}"
        elif s == "speech_detected":
            return f"{self.BOLD}{self.YELLOW}◉ SPEECH DETECTED{self.RESET}"
        elif s == "transcribing":
            return f"{self.BOLD}{self.YELLOW}◐ TRANSCRIBING{self.RESET}"
        elif s == "thinking":
            return f"{self.BOLD}{self.PURPLE}✦ THINKING{self.RESET}"
        elif s == "speaking":
            return f"{self.BOLD}{self.CYAN}🔊 SPEAKING{self.RESET}"
        elif s == "interrupted":
            return f"{self.BOLD}{self.ORANGE}⚡ INTERRUPTED{self.RESET}"
        return f"{self.GRAY}○ IDLE{self.RESET}"

    def _render_vu_meter(self, width: int = 24) -> str:
        """Render a smooth Unicode VU meter."""
        level = min(1.0, max(0.0, self._audio_level))
        filled = int(level * width)
        bar = ""
        for i in range(width):
            if i < filled:
                if i < width * 0.6:
                    bar += f"{self.GREEN}█{self.RESET}"
                elif i < width * 0.85:
                    bar += f"{self.YELLOW}█{self.RESET}"
                else:
                    bar += f"{self.ORANGE}█{self.RESET}"
            else:
                bar += f"{self.GRAY}░{self.RESET}"
        pct = int(level * 100)
        return f"[{bar}] {self.WHITE}{pct:2d}%{self.RESET}"

    def _draw(self) -> None:
        """Draw full terminal frame."""
        cols, rows = shutil.get_terminal_size(fallback=(80, 24))
        content_width = max(40, min(cols - 2, 90))

        elapsed_sec = int(time.time() - self._start_time)
        m, s = divmod(elapsed_sec, 60)
        uptime = f"{m:02d}:{s:02d}"

        lines: list[str] = []
        sep = "─" * (content_width - 2)

        # Header
        lines.append(f"{self.CYAN}╭{sep}╮{self.RESET}")
        header_title = f"{self.BOLD}{self.WHITE}🎙️  VOICE AGENT{self.RESET} {self.GRAY}v0.1.0{self.RESET}"
        status_pill = self._get_status_pill()
        uptime_str = f"{self.GRAY}Session: {uptime}{self.RESET}"
        lines.append(f"│  {header_title}   {status_pill}   {uptime_str}".ljust(content_width + 12) + "│")

        config_info = (
            f"│  {self.DIM}Model: {self.WHITE}{self._model_name}{self.RESET}{self.DIM} · "
            f"Voice: {self.WHITE}{self._voice_name}{self.RESET}{self.DIM} · "
            f"VAD: {self.WHITE}Silero (16kHz){self.RESET}"
        )
        lines.append(config_info.ljust(content_width + 16) + "│")
        lines.append(f"{self.CYAN}├{sep}┤{self.RESET}")

        # Live State & Audio Meter
        vu = self._render_vu_meter(width=max(12, min(24, content_width - 40)))
        state_line = f"│  {self.BOLD}State:{self.RESET} {self._state_message}"
        lines.append(state_line.ljust(content_width + 8) + "│")
        meter_line = f"│  {self.BOLD}Input:{self.RESET} {vu}"
        if self._last_metrics:
            meter_line += f"  {self.GRAY}[{self._last_metrics}]{self.RESET}"
        lines.append(meter_line.ljust(content_width + 18) + "│")

        lines.append(f"{self.CYAN}├{sep}┤{self.RESET}")
        lines.append(f"│  {self.BOLD}{self.WHITE}CONVERSATION HISTORY{self.RESET}".ljust(content_width + 10) + "│")

        # Chat History Area
        max_chat_lines = max(5, rows - 14)
        chat_turns = self._history[-6:]  # show recent turns

        if not chat_turns:
            lines.append(f"│  {self.GRAY}(No turns yet. Speak into your microphone to start...){self.RESET}".ljust(content_width + 10) + "│")
            for _ in range(max_chat_lines - 1):
                lines.append(f"│{' ' * (content_width - 2)}│")
        else:
            rendered_chat_count = 0
            for turn in chat_turns:
                role_label = (
                    f"{self.BOLD}{self.GREEN}You{self.RESET} {self.GRAY}({turn.timestamp}){self.RESET}: "
                    if turn.role == "user"
                    else f"{self.BOLD}{self.PURPLE}Agent{self.RESET} {self.GRAY}({turn.timestamp}){self.RESET}: "
                )
                text_preview = turn.text
                if len(text_preview) > content_width - 22:
                    text_preview = text_preview[: content_width - 25] + "..."
                lines.append(f"│  {role_label}{text_preview}".ljust(content_width + 16) + "│")
                rendered_chat_count += 1
                if turn.metrics:
                    lines.append(f"│     {self.GRAY}↳ [{turn.metrics}]{self.RESET}".ljust(content_width + 12) + "│")
                    rendered_chat_count += 1

            # Pad empty rows
            for _ in range(max(0, max_chat_lines - rendered_chat_count)):
                lines.append(f"│{' ' * (content_width - 2)}│")

        # Footer
        lines.append(f"{self.CYAN}├{sep}┤{self.RESET}")
        footer_keys = (
            f"│  {self.DIM}[Ctrl+C] Quit  ·  "
            f"[Barge-in] Speak anytime to interrupt  ·  "
            f"[Web] --web for visual companion{self.RESET}"
        )
        lines.append(footer_keys.ljust(content_width + 12) + "│")
        lines.append(f"{self.CYAN}╰{sep}╯{self.RESET}")

        # Render buffer to terminal home
        buffer = "\033[H" + "\n".join(lines)
        sys.stdout.write(buffer)
        sys.stdout.flush()

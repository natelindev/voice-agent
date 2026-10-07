"""Interactive Demo and Preview Orchestrator for Voice Agent UI.

Used when OPENAI_API_KEY is not configured or when testing the Web UI & TUI.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import TYPE_CHECKING

from voice_agent.events.hub import PipelineState

if TYPE_CHECKING:
    from voice_agent.events.hub import ControlCommandEvent, EventHub

logger = logging.getLogger(__name__)


class DemoOrchestrator:
    """
    Simulates a live pipeline with interactive responsiveness.
    Drives the Web UI and TUI so users can inspect visual feedback,
    test controls (mute, barge-in, clear), and view latency stats.
    """

    DEMO_TURNS = [
        (
            "How does the barge-in feature work?",
            "Barge-in allows you to interrupt me naturally at any moment. "
            "As soon as you begin speaking, the audio playback cancels immediately "
            "and the pipeline begins capturing your new query.",
            0.32, 0.18, 0.11, 1.15
        ),
        (
            "What can I see in this preview?",
            "You can explore the terminal dashboard and web companion, follow a simulated conversation, "
            "and try the mute and interrupt controls. The timing values in this preview are sample data.",
            0.29, 0.16, 0.09, 1.08
        ),
        (
            "Can you tell me about the architecture?",
            "The architecture uses an asynchronous event bus to connect audio capture, speech detection, "
            "transcription, response generation, and playback with the terminal and web interfaces.",
            0.34, 0.19, 0.12, 1.22
        ),
    ]

    def __init__(self, event_hub: EventHub) -> None:
        self._hub = event_hub
        self._is_running = False
        self._interrupted = False
        self._turn_index = 0

        self._hub.add_control_handler(self._handle_control)

    def _handle_control(self, cmd: ControlCommandEvent) -> None:
        if cmd.action == "interrupt":
            self._interrupted = True
            self._hub.emit_state(PipelineState.INTERRUPTED, "Barge-in triggered via control dock!")
            logger.info("Demo: Barge-in triggered")

    async def run(self) -> None:
        """Run interactive demo simulation loop."""
        self._is_running = True
        self._hub.emit_state(PipelineState.LISTENING, "Listening... (Preview Mode)")

        audio_task = asyncio.create_task(self._ambient_audio_loop())

        try:
            while self._is_running:
                # 1. Listening stage
                self._hub.emit_state(PipelineState.LISTENING, "Listening... (Preview Mode)")
                await asyncio.sleep(4.0)
                if not self._is_running:
                    break

                # 2. Pick next demo utterance
                user_text, assistant_text, asr_s, ttft_s, tts_s, total_s = self.DEMO_TURNS[
                    self._turn_index % len(self.DEMO_TURNS)
                ]
                self._turn_index += 1
                self._interrupted = False

                # 3. Speech detected
                self._hub.emit_state(PipelineState.SPEECH_DETECTED, "Speech detected from microphone...")
                await asyncio.sleep(1.2)
                if self._interrupted:
                    continue

                # 4. Transcribing
                self._hub.emit_state(PipelineState.TRANSCRIBING, "Transcribing speech via Whisper...")
                await asyncio.sleep(asr_s)
                self._hub.emit_transcript("user", user_text, is_final=True)
                if self._interrupted:
                    continue

                # 5. Thinking
                self._hub.emit_state(PipelineState.THINKING, "Generating response with GPT-4o-mini...")
                await asyncio.sleep(ttft_s)
                if self._interrupted:
                    continue

                # 6. Speaking & streaming tokens
                self._hub.emit_state(PipelineState.SPEAKING, "Speaking voice response via TTS...")
                words = assistant_text.split(" ")
                for i, word in enumerate(words):
                    if self._interrupted:
                        break
                    self._hub.emit_token_delta(word + " ")
                    await asyncio.sleep(0.08)

                if not self._interrupted:
                    self._hub.emit_transcript("assistant", assistant_text, is_final=True)
                    self._hub.emit_turn_metrics(
                        turn_id=f"demo-{self._turn_index}",
                        asr_seconds=asr_s,
                        ttft_seconds=ttft_s,
                        tts_first_chunk_seconds=tts_s,
                        total_seconds=total_s,
                    )
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        finally:
            self._is_running = False
            audio_task.cancel()
            self._hub.remove_control_handler(self._handle_control)

    async def _ambient_audio_loop(self) -> None:
        """Simulate organic audio level fluctuations for the orb and waveform."""
        t = 0.0
        try:
            while self._is_running:
                t += 0.05
                if self._hub.is_muted:
                    self._hub.emit_audio_level(0.0, 0.0)
                elif self._hub.current_state == PipelineState.SPEAKING:
                    # High energetic ripple when assistant speaks
                    level = 0.35 + 0.3 * abs(math.sin(t * 3.5)) + 0.15 * math.sin(t * 8.0)
                    self._hub.emit_audio_level(max(0.0, min(1.0, level)), level * 1.1)
                elif self._hub.current_state == PipelineState.SPEECH_DETECTED:
                    # User speaking
                    level = 0.45 + 0.25 * math.sin(t * 4.0)
                    self._hub.emit_audio_level(max(0.0, min(1.0, level)), level * 1.1)
                else:
                    # Subtle ambient breath
                    level = 0.03 + 0.02 * math.sin(t * 1.5)
                    self._hub.emit_audio_level(level, level)
                await asyncio.sleep(0.033)  # ~30 FPS
        except asyncio.CancelledError:
            pass

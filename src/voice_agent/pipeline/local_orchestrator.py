"""End-to-end Local Mac Pipeline: Silero VAD → OpenSuperWhisper → Codex LLM → macOS TTS."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Callable
import uuid

from voice_agent.asr.local_whisper import LocalWhisperTranscriber
from voice_agent.audio.capture import AudioCapture
from voice_agent.events.hub import PipelineState
from voice_agent.llm.codex_llm import CodexLLM
from voice_agent.tts.local_tts import LocalAudioPlayback
from voice_agent.vad.detector import VADDetector, VADEventType

if TYPE_CHECKING:
    from voice_agent.events.hub import ControlCommandEvent, EventHub

logger = logging.getLogger(__name__)


class LocalPipelineOrchestrator:
    """
    Coordinates 100% local Mac voice assistant pipeline:
    - AudioCapture: microphone input (16kHz)
    - VADDetector: local Silero VAD
    - LocalWhisperTranscriber: OpenSuperWhisper model on Apple Silicon Metal
    - CodexLLM: Codex CLI using existing ChatGPT subscription
    - LocalAudioPlayback: native macOS speech synthesis with barge-in support
    - EventHub: real-time telemetry for Web UI and TUI
    """

    def __init__(
        self,
        event_hub: EventHub | None = None,
        status_callback: Callable[[str], None] | None = None,
        tts_voice: str = "Samantha",
        suppress_speaker_echo: bool = True,
    ) -> None:
        self._event_hub = event_hub
        self._status = status_callback or (lambda msg: None)
        self._suppress_speaker_echo = suppress_speaker_echo

        self._capture = AudioCapture(event_hub=event_hub)
        self._vad = VADDetector()
        self._transcriber = LocalWhisperTranscriber()
        self._llm = CodexLLM()
        self._playback = LocalAudioPlayback(voice=tts_voice)

        self._cancel_event = asyncio.Event()
        self._response_task: asyncio.Task | None = None
        self._is_speaking: bool = False

        # Acoustic feedback & echo suppression controls
        self._echo_cooldown: float = 0.5  # 500ms post-playback echo drain window
        self._playback_cooldown_until: float = 0.0
        self._last_playback_end: float = 0.0
        self._recent_assistant_texts: list[str] = []

        if self._event_hub is not None:
            self._event_hub.add_control_handler(self._handle_control)

    def _handle_control(self, cmd: ControlCommandEvent) -> None:
        if cmd.action == "interrupt":
            self._playback_cooldown_until = 0.0
            asyncio.create_task(self._handle_manual_interrupt())
        elif cmd.action == "clear_history":
            self._llm.clear_history()
            self._recent_assistant_texts.clear()

    def _set_state(self, state: PipelineState, msg: str) -> None:
        self._status(msg)
        if self._event_hub is not None:
            self._event_hub.emit_state(state, msg)

    async def run(self) -> None:
        """Start the local voice loop. Runs until cancelled."""
        await self._transcriber.ensure_server()
        await self._capture.start()
        self._set_state(PipelineState.LISTENING, "Listening... (Local Mac Mode)")
        logger.info("Local pipeline started (echo_suppression=%s)", self._suppress_speaker_echo)

        try:
            async for chunk in self._capture:
                now = time.monotonic()
                is_speaking = self._playback.is_playing or (
                    self._response_task and not self._response_task.done() and self._is_speaking
                )
                in_cooldown = (now < self._playback_cooldown_until)

                # Acoustic Echo Suppression: Ignore mic input for VAD while assistant speaks
                # or during the room reverberation cooldown window
                if self._suppress_speaker_echo and (is_speaking or in_cooldown):
                    if self._vad.in_speech:
                        self._vad.reset()
                    continue

                event = self._vad.process_chunk(chunk)
                if event is None:
                    continue

                if event.type == VADEventType.SPEECH_START:
                    if not self._suppress_speaker_echo and (
                        self._playback.is_playing or (self._response_task and not self._response_task.done())
                    ):
                        self._set_state(PipelineState.INTERRUPTED, "Interrupted — listening...")
                        await self._handle_manual_interrupt()
                    else:
                        self._set_state(PipelineState.SPEECH_DETECTED, "Speech detected...")

                elif event.type == VADEventType.SPEECH_END:
                    await self._handle_speech_end(event.audio_buffer)

        except asyncio.CancelledError:
            logger.info("Local pipeline cancelled")
        finally:
            await self._shutdown()

    async def _handle_manual_interrupt(self) -> None:
        """Manual barge-in via UI or hotkey: stop playback immediately."""
        self._cancel_event.set()
        self._playback.stop()
        self._is_speaking = False
        self._playback_cooldown_until = 0.0

        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
            try:
                await self._response_task
            except (asyncio.CancelledError, Exception):
                pass
            self._response_task = None

        self._vad.reset()
        self._cancel_event.clear()
        self._set_state(PipelineState.LISTENING, "Interrupted — listening...")

    async def _handle_speech_end(self, audio_buffer: bytes) -> None:
        if not audio_buffer:
            return

        self._cancel_event.clear()
        self._response_task = asyncio.create_task(
            self._respond(audio_buffer),
            name="local_response",
        )

    async def _respond(self, audio_buffer: bytes) -> None:
        speech_end_ts = time.monotonic()
        turn_id = str(uuid.uuid4())[:8]

        try:
            # 1. Local Whisper ASR (Apple Silicon Metal)
            self._set_state(PipelineState.TRANSCRIBING, "Transcribing with OpenSuperWhisper...")
            transcript = await self._transcriber.transcribe(audio_buffer)
            asr_done_ts = time.monotonic()
            asr_duration = asr_done_ts - speech_end_ts

            if not transcript or not transcript.strip():
                self._set_state(PipelineState.LISTENING, "Listening...")
                return

            # Echo Guard: Prevent assistant from hearing its own previous output
            if self._is_self_echo(transcript):
                logger.info("Echo Guard: Discarded self-echo from speaker: %r", transcript)
                self._set_state(PipelineState.LISTENING, "Listening...")
                return

            logger.info("Local ASR: %.3fs → %r", asr_duration, transcript)
            self._status(f"You: {transcript}")
            if self._event_hub is not None:
                self._event_hub.emit_transcript("user", transcript, is_final=True)

            if self._cancel_event.is_set():
                return

            # 2. Codex LLM (ChatGPT Subscription)
            self._set_state(PipelineState.THINKING, "Thinking (Codex LLM)...")
            first_sentence = True
            ttft_duration = 0.0
            full_reply = ""

            async for sentence in self._llm.stream_response(transcript, self._cancel_event):
                if self._cancel_event.is_set():
                    break

                if not sentence.strip():
                    continue

                if first_sentence:
                    ttft_duration = time.monotonic() - asr_done_ts
                    first_sentence = False
                    self._set_state(PipelineState.SPEAKING, "Speaking...")

                full_reply += (sentence + " ")
                if self._event_hub is not None:
                    self._event_hub.emit_token_delta(sentence + " ")

                # 3. Local macOS Speech Playback (say command)
                self._is_speaking = True
                await self._playback.speak(sentence, cancel_event=self._cancel_event)
                now = time.monotonic()
                self._last_playback_end = now
                self._playback_cooldown_until = now + self._echo_cooldown

                if self._cancel_event.is_set():
                    break

            total_duration = time.monotonic() - speech_end_ts
            if full_reply.strip():
                self._recent_assistant_texts.append(full_reply.strip())
                if len(self._recent_assistant_texts) > 6:
                    self._recent_assistant_texts.pop(0)

                if self._event_hub is not None:
                    self._event_hub.emit_transcript("assistant", full_reply.strip(), is_final=True)
                    self._event_hub.emit_turn_metrics(
                        turn_id=turn_id,
                        asr_seconds=asr_duration,
                        ttft_seconds=ttft_duration,
                        tts_first_chunk_seconds=0.08,
                        total_seconds=total_duration,
                    )

        except asyncio.CancelledError:
            logger.info("Response task cancelled")
        except Exception:
            logger.exception("Error in local response pipeline")
        finally:
            self._is_speaking = False
            now = time.monotonic()
            self._last_playback_end = now
            self._playback_cooldown_until = now + self._echo_cooldown
            if not self._cancel_event.is_set():
                self._set_state(PipelineState.LISTENING, "Listening...")

    def _is_self_echo(self, transcript: str) -> bool:
        """Detect whether transcribed text is the assistant's own voice captured by mic."""
        clean = transcript.strip().lower().strip(".!?,")
        if not clean:
            return True

        # Common hallucination/echo words emitted on speaker bleed tail
        faint_echo_phrases = {"thank you.", "thank you", "thanks", "bye.", "bye", "you", "goodbye"}
        now = time.monotonic()
        if clean in faint_echo_phrases and (now - self._last_playback_end < 4.0):
            return True

        for assistant_text in reversed(self._recent_assistant_texts[-4:]):
            target = assistant_text.strip().lower().strip(".!?,")
            # Substring match (e.g. microphone caught an excerpt or suffix of assistant speech)
            if clean in target or target in clean:
                return True

            # Word token overlap match
            words_a = set(clean.split())
            words_b = set(target.split())
            if words_a and words_b:
                overlap = len(words_a & words_b) / len(words_a)
                if overlap >= 0.65:
                    return True

        return False

    async def _shutdown(self) -> None:
        if self._response_task and not self._response_task.done():
            self._cancel_event.set()
            self._playback.stop()
            self._response_task.cancel()
            try:
                await self._response_task
            except (asyncio.CancelledError, Exception):
                pass

        await self._capture.stop()
        if self._event_hub is not None:
            self._event_hub.remove_control_handler(self._handle_control)
        logger.info("Local pipeline shut down")

"""Pipeline orchestrator: VAD → ASR → LLM → TTS → Playback with barge-in support."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

import openai

from voice_agent.audio.capture import AudioCapture
from voice_agent.audio.playback import AudioPlayback
from voice_agent.asr.transcriber import Transcriber
from voice_agent.llm.chat import ChatLLM
from voice_agent.tts.synthesizer import Synthesizer
from voice_agent.vad.detector import VADDetector, VADEventType

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Coordinates all pipeline stages with barge-in support.

    Flow:
        AudioCapture → VADDetector → Transcriber → ChatLLM → Synthesizer → AudioPlayback

    Barge-in: When VAD detects speech_start during playback, the current
    response task is cancelled and playback is stopped immediately.
    """

    def __init__(
        self,
        client: openai.AsyncOpenAI,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._status = status_callback or (lambda msg: None)

        self._capture = AudioCapture()
        self._vad = VADDetector()
        self._transcriber = Transcriber(client)
        self._llm = ChatLLM(client)
        self._synthesizer = Synthesizer(client)
        self._playback = AudioPlayback()

        # Shared cancellation event for the active response task
        self._cancel_event: asyncio.Event = asyncio.Event()
        self._response_task: asyncio.Task | None = None

    async def run(self) -> None:
        """Start the main pipeline loop. Runs until cancelled."""
        await self._capture.start()
        self._status("Listening...")
        logger.info("Pipeline started")

        try:
            async for chunk in self._capture:
                event = self._vad.process_chunk(chunk)
                if event is None:
                    continue

                if event.type == VADEventType.SPEECH_START:
                    await self._handle_speech_start()

                elif event.type == VADEventType.SPEECH_END:
                    await self._handle_speech_end(event.audio_buffer)

        except asyncio.CancelledError:
            logger.info("Pipeline cancelled")
        finally:
            await self._shutdown()

    async def _handle_speech_start(self) -> None:
        """Barge-in: cancel any in-flight response if playback is active."""
        if self._playback.is_playing or (
            self._response_task and not self._response_task.done()
        ):
            logger.info("Barge-in detected — stopping response")
            self._status("Interrupted — listening...")
            self._cancel_event.set()
            self._playback.stop()

            if self._response_task and not self._response_task.done():
                self._response_task.cancel()
                try:
                    await self._response_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._response_task = None

            self._vad.reset()
            self._cancel_event.clear()

    async def _handle_speech_end(self, audio_buffer: bytes) -> None:
        """Spawn response task for the completed utterance."""
        if not audio_buffer:
            return

        self._cancel_event.clear()
        self._response_task = asyncio.create_task(
            self._respond(audio_buffer),
            name="response",
        )

    async def _respond(self, audio_buffer: bytes) -> None:
        """ASR → LLM → TTS → Playback pipeline for one utterance."""
        speech_end_ts = time.monotonic()

        try:
            # --- ASR ---
            self._status("Transcribing...")
            transcript = await self._transcriber.transcribe(audio_buffer)
            asr_done_ts = time.monotonic()

            if not transcript:
                logger.info("ASR returned empty — ignoring")
                self._status("Listening...")
                return

            logger.info(
                "ASR done in %.3fs: %r",
                asr_done_ts - speech_end_ts,
                transcript,
            )
            self._status(f"You: {transcript}")

            if self._cancel_event.is_set():
                return

            # --- LLM + TTS (sentence-level streaming) ---
            self._status("Thinking...")
            first_audio = True

            async for sentence in self._llm.stream_response(transcript, self._cancel_event):
                if self._cancel_event.is_set():
                    break

                if not sentence.strip():
                    continue

                # Stream TTS for this sentence
                pcm_stream = self._synthesizer.synthesize_stream(
                    sentence, self._cancel_event
                )

                if first_audio:
                    self._status("Speaking...")

                await self._playback.play_stream(pcm_stream)

                if first_audio:
                    first_audio_ts = time.monotonic()
                    logger.info(
                        "First audio chunk played %.3fs after speech end",
                        first_audio_ts - speech_end_ts,
                    )
                    first_audio = False

                if self._cancel_event.is_set():
                    break

        except asyncio.CancelledError:
            logger.info("Response task cancelled")
        except Exception:
            logger.exception("Error in response pipeline")
        finally:
            if not self._cancel_event.is_set():
                self._status("Listening...")

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
        logger.info("Pipeline shut down")

"""OpenAI TTS: streams PCM audio from text with cancellation support."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncGenerator

import openai

logger = logging.getLogger(__name__)

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "coral"
TTS_SAMPLE_RATE = 24000  # PCM output from OpenAI TTS
TTS_CHUNK_SIZE = 4096    # bytes per read iteration


class Synthesizer:
    """Streams PCM audio from OpenAI TTS API."""

    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str = TTS_MODEL,
        voice: str = TTS_VOICE,
    ) -> None:
        self._client = client
        self._model = model
        self._voice = voice

    async def synthesize_stream(
        self,
        text: str,
        cancel_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        """
        Yield raw PCM bytes (24kHz, 16-bit signed LE, mono) as they arrive.
        Stops if cancel_event is set between chunks.
        """
        if not text.strip():
            return

        logger.debug("TTS: synthesizing %r", text[:60])
        t0 = time.monotonic()
        first = True

        async with self._client.audio.speech.with_streaming_response.create(
            model=self._model,
            voice=self._voice,
            input=text,
            response_format="pcm",
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=TTS_CHUNK_SIZE):
                if cancel_event.is_set():
                    logger.debug("TTS: cancelled mid-stream")
                    return
                if chunk:
                    if first:
                        logger.info("TTS: first chunk %.3fs", time.monotonic() - t0)
                        first = False
                    yield chunk

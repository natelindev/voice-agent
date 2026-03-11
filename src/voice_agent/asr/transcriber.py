"""OpenAI Whisper ASR: converts raw PCM audio buffer to text."""

from __future__ import annotations

import io
import logging
import struct
import wave

import openai

logger = logging.getLogger(__name__)

ASR_MODEL = "whisper-1"


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw int16 PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class Transcriber:
    """Transcribes audio buffers using OpenAI Whisper API."""

    def __init__(self, client: openai.AsyncOpenAI, model: str = ASR_MODEL) -> None:
        self._client = client
        self._model = model

    async def transcribe(self, audio_buffer: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe int16 PCM audio bytes to text.

        Returns empty string if the buffer is too short or transcription is empty.
        """
        if len(audio_buffer) < 3200:  # < 0.1s of audio, skip
            logger.debug("ASR: audio buffer too short (%d bytes), skipping", len(audio_buffer))
            return ""

        wav_bytes = _pcm_to_wav(audio_buffer, sample_rate=sample_rate)
        wav_file = io.BytesIO(wav_bytes)
        wav_file.name = "audio.wav"

        import time
        logger.debug("ASR: sending %d bytes to Whisper", len(wav_bytes))
        t0 = time.monotonic()
        response = await self._client.audio.transcriptions.create(
            model=self._model,
            file=wav_file,
            response_format="text",
        )
        elapsed = time.monotonic() - t0

        # response is a string when response_format="text"
        text = response.strip() if isinstance(response, str) else response.text.strip()
        logger.info("ASR: %.3fs → %r", elapsed, text)
        return text

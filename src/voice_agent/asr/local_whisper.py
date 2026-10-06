"""Local Apple Silicon Whisper ASR using OpenSuperWhisper model."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from pathlib import Path
import time
import urllib.request
import wave

logger = logging.getLogger(__name__)

OPENSUPERWHISPER_MODEL = (
    Path.home()
    / "Library/Application Support/ru.starmel.OpenSuperWhisper/whisper-models/ggml-large-v3-turbo.bin"
)
LOCAL_SERVER_URL = "http://127.0.0.1:8178/inference"


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw int16 PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class LocalWhisperTranscriber:
    """
    Transcribes audio using local whisper.cpp with the OpenSuperWhisper model on Apple Silicon.
    Connects to whisper-server or invokes whisper-cli directly.
    """

    def __init__(self, model_path: Path | str = OPENSUPERWHISPER_MODEL) -> None:
        self.model_path = Path(model_path)
        self._server_process: asyncio.subprocess.Process | None = None

    async def ensure_server(self) -> bool:
        """Verify whisper-server is active on port 8178 or spawn it."""
        try:
            req = urllib.request.Request("http://127.0.0.1:8178", method="HEAD")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=1))
            return True
        except Exception:
            pass

        # Try to launch whisper-server
        if self.model_path.exists():
            cmd = ["whisper-server", "-m", str(self.model_path), "--port", "8178"]
            try:
                self._server_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.sleep(1.5)
                return True
            except Exception as e:
                logger.warning("Could not spawn whisper-server: %s", e)
        return False

    async def transcribe(self, audio_buffer: bytes, sample_rate: int = 16000) -> str:
        """Transcribe int16 PCM bytes locally."""
        if len(audio_buffer) < 3200:
            return ""

        wav_bytes = _pcm_to_wav(audio_buffer, sample_rate=sample_rate)
        t0 = time.monotonic()

        # Try HTTP inference on local whisper-server first
        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, self._http_transcribe, wav_bytes)
            if text:
                logger.info("Local Whisper (server): %.3fs → %r", time.monotonic() - t0, text)
                return text
        except Exception as e:
            logger.debug("Local whisper-server request failed: %s; falling back to whisper-cli", e)

        # Fallback to direct whisper-cli process
        return await self._cli_transcribe(wav_bytes)

    def _http_transcribe(self, wav_bytes: bytes) -> str:
        boundary = "----VoiceAgentBoundary7MA4YW"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            f"Content-Type: audio/wav\r\n\r\n"
        ).encode("utf-8") + wav_bytes + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="temperature"\r\n\r\n0.0\r\n'
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            LOCAL_SERVER_URL,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("text", "").strip()

    async def _cli_transcribe(self, wav_bytes: bytes) -> str:
        import tempfile
        t0 = time.monotonic()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            cmd = [
                "whisper-cli",
                "-m", str(self.model_path),
                "-f", tmp_path,
                "--no-prints",
                "--no-timestamps",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            text = stdout.decode("utf-8", errors="replace").strip()
            logger.info("Local Whisper (cli): %.3fs → %r", time.monotonic() - t0, text)
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

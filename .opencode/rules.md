# Voice Agent — OpenCode Rules

## Project

Python 3.12 real-time voice assistant CLI. Pipeline: mic → Silero VAD → Whisper → GPT-4o-mini → GPT-4o-mini-tts → speaker. Barge-in support, < 1.5s latency target.

Package manager: `uv`. Never use `pip`. Run via `uv run voice-agent`.

## Must-Follow Rules

### Package Management
- `uv add <pkg>` to add dependencies
- `uv run pytest tests/` to run tests
- Never commit `.env` — it contains `OPENAI_API_KEY`

### Code Style
- `from __future__ import annotations` at top of every module
- `logger = logging.getLogger(__name__)` at module level
- Type hints everywhere; `X | Y` union syntax
- Dataclasses for value objects

### Async/Threading
- All I/O is `asyncio`; the only threading is the `sounddevice` callback bridge
- Capture bridge: `loop.call_soon_threadsafe(queue.put_nowait, chunk)`
- Playback bridge: `queue.Queue` + `run_in_executor`
- Cancellation: cooperative via `asyncio.Event`; always `await` after `Task.cancel()`

### Audio Format Constants (never change without full audit)
- Capture/VAD: float32, 16kHz, **512 samples/chunk** (hard Silero requirement)
- ASR input: int16 PCM bytes @ 16kHz wrapped in WAV
- TTS/Playback: int16 PCM @ 24kHz

### Barge-in Sequence (orchestrator.py)
Must follow this exact order:
1. `_cancel_event.set()`
2. `playback.stop()`
3. `response_task.cancel()` + `await response_task`
4. `vad.reset()`
5. `_cancel_event.clear()`

## Key Files

- `src/voice_agent/pipeline/orchestrator.py` — main coordination + barge-in logic
- `src/voice_agent/llm/chat.py` — streaming LLM + sentence splitting
- `src/voice_agent/vad/detector.py` — Silero VAD wrapper
- `src/voice_agent/audio/playback.py` — thread-safe PCM playback
- `src/voice_agent/audio/capture.py` — async mic capture

## Testing

- `pytest` + `pytest-asyncio`; async tests use `@pytest.mark.asyncio`
- Mock OpenAI with `unittest.mock.AsyncMock`
- No tests that require hardware (mic/speaker) or live API calls

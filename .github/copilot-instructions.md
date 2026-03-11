# Voice Agent — GitHub Copilot Instructions

## Project

Python 3.12 real-time voice assistant CLI. Pipeline: microphone → Silero VAD → OpenAI Whisper ASR → GPT-4o-mini LLM → GPT-4o-mini-tts → speaker output. Supports barge-in interruption. Target latency: < 1.5s speech-end to first audio.

## Package Manager

Always use `uv`, never `pip`:
- `uv add <package>` — add dependency
- `uv run voice-agent` — run the CLI
- `uv run pytest tests/` — run tests

## Code Conventions

- `from __future__ import annotations` at top of every file
- `logger = logging.getLogger(__name__)` at module level in every file
- Type hints everywhere; use `X | Y` syntax (not `Union[X, Y]` or `Optional[X]`)
- Dataclasses for simple value types
- All async I/O via `asyncio`; the only `threading` is the `sounddevice` audio callback bridge

## Audio Format Rules

| Stage | dtype | Sample Rate | Notes |
|---|---|---|---|
| Microphone capture | float32 | 16kHz | 512 samples/chunk — do not change |
| VAD output / ASR input | int16 bytes | 16kHz | |
| TTS output / Playback | int16 bytes | 24kHz | |

Never change `CHUNK_SAMPLES = 512` — Silero VAD requires this exactly.

## Cancellation Pattern

Cancellation uses two events:
- `asyncio.Event` (`_cancel_event`) — for async generators (LLM, TTS)
- `threading.Event` (`_stop_event`) — for the sounddevice playback callback

Always check `cancel_event.is_set()` between async chunks. Always `await` a task after calling `.cancel()`.

## Key Files

- `src/voice_agent/pipeline/orchestrator.py` — main pipeline wiring and barge-in logic
- `src/voice_agent/audio/capture.py` — async mic capture
- `src/voice_agent/audio/playback.py` — streaming PCM playback with stop
- `src/voice_agent/vad/detector.py` — Silero VAD wrapper
- `src/voice_agent/asr/transcriber.py` — Whisper API wrapper
- `src/voice_agent/llm/chat.py` — GPT-4o-mini streaming with sentence splitting
- `src/voice_agent/tts/synthesizer.py` — gpt-4o-mini-tts streaming PCM

## Testing

- Framework: `pytest` + `pytest-asyncio`
- Async tests: `@pytest.mark.asyncio`
- Mock `openai.AsyncOpenAI` with `unittest.mock.AsyncMock`
- No real hardware (mic/speaker) or live API calls in tests

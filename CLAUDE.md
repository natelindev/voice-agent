# Voice Agent — Claude Context

## Project Overview

Real-time voice assistant CLI built in Python. Listens via microphone, uses Silero VAD for speech detection, transcribes with OpenAI Whisper, generates responses with GPT-4o-mini, and speaks back with GPT-4o-mini TTS. Supports barge-in interruption and targets < 1.5s end-to-end latency.

## Tech Stack

- **Language**: Python 3.12 (minimum 3.11)
- **Package manager**: `uv` (Astral) — use `uv run` for all commands, never `pip`
- **Build backend**: Hatchling
- **Key dependencies**: `openai>=1.70.0`, `sounddevice`, `numpy`, `torch`, `torchaudio`, `python-dotenv`
- **Test framework**: pytest + pytest-asyncio

## Repository Layout

```
src/voice_agent/          # Main package (installed as `voice-agent` CLI)
  main.py                 # Entry point: loads .env, creates AsyncOpenAI, runs PipelineOrchestrator
  audio/
    capture.py            # AudioCapture: mic → asyncio.Queue of float32 numpy chunks (16kHz/512 samples)
    playback.py           # AudioPlayback: int16 PCM → sounddevice.OutputStream (24kHz), barge-in stop
  vad/
    detector.py           # VADDetector: Silero VAD, emits VADEvent(SPEECH_START|SPEECH_END)
  asr/
    transcriber.py        # Transcriber: int16 PCM bytes → WAV → whisper-1 → text
    local_whisper.py      # LocalWhisperTranscriber: OpenSuperWhisper model via Apple Silicon Metal
  llm/
    chat.py               # ChatLLM: multi-turn GPT-4o-mini streaming, yields complete sentences
    codex_llm.py          # CodexLLM: calls local Codex CLI with ChatGPT subscription
  tts/
    synthesizer.py        # Synthesizer: text → gpt-4o-mini-tts PCM stream (24kHz int16 mono)
    local_tts.py          # LocalAudioPlayback: native macOS speech (say -v Samantha) with barge-in stop
  pipeline/
    orchestrator.py       # PipelineOrchestrator: wires all stages, manages barge-in cancellation
    local_orchestrator.py # LocalPipelineOrchestrator: 100% local Mac pipeline
    demo.py               # DemoOrchestrator: interactive UI preview simulation
  events/
    hub.py                # EventHub: non-blocking pub-sub for audio RMS, state, and telemetry
  tui/
    dashboard.py          # TUIDashboard: live terminal UI with ASCII VU meter & chat cards
  web/
    server.py             # WebCompanionServer: async HTTP static server + WebSocket gateway
    static/               # Frontend assets: index.html, styles.css, orb.js, waveform.js, app.js
tests/
  test_asr.py             # WAV container wrapping
  test_vad.py             # VAD reset and buffer flush
  test_pipeline.py        # _split_sentences utility
  test_events.py          # EventHub pub-sub and control dispatch
  test_web_server.py      # WebCompanionServer static files & WebSocket
```

## Architecture: Pipeline Data Flow

```
Mic (float32 chunks) → VADDetector → SPEECH_START → barge-in cancel if playing
                                   → SPEECH_END (int16 PCM bytes)
                                       → Transcriber (whisper-1) → str
                                           → ChatLLM (gpt-4o-mini stream) → sentence str
                                               → Synthesizer (gpt-4o-mini-tts) → PCM bytes
                                                   → AudioPlayback (sounddevice)
```

## Key Design Decisions

### Thread/Async Boundary
`sounddevice` callbacks run on a C-level audio thread. They bridge into asyncio using:
- **Capture**: `loop.call_soon_threadsafe(queue.put_nowait, chunk)`
- **Playback**: `threading.Event` for stop signal; `asyncio.Queue` is replaced by `queue.Queue` (thread-safe) with `run_in_executor` on the producer side

### Barge-in Cancellation
Two-level cancellation:
1. `asyncio.Event` (`_cancel_event`) — checked by LLM/TTS async generators between chunks
2. `threading.Event` (`_stop_event` in `AudioPlayback`) — checked inside the sounddevice callback

On `SPEECH_START` during active playback:
1. Set `_cancel_event`
2. Call `playback.stop()` (sets `_stop_event`, drains queue)
3. `cancel()` the response `asyncio.Task`
4. `await` it to completion
5. Call `vad.reset()` to reinitialize the Silero VADIterator
6. Clear `_cancel_event`

### Sentence-Level TTS Streaming
`ChatLLM.stream_response` buffers GPT tokens and yields on sentence boundaries (`[.!?]` + whitespace). Each sentence is independently synthesized and played. This minimizes time-to-first-audio while keeping speech natural.

### Audio Formats
- **Capture**: float32, mono, 16kHz, 512 samples/chunk (32ms) — required by Silero VAD
- **VAD output**: int16 PCM bytes (float32 clamped × 32767)
- **ASR input**: WAV container wrapping int16 PCM (built in-memory with `wave` module)
- **TTS output**: raw PCM, 24kHz, int16 signed LE, mono — streamed in 4096-byte chunks
- **Playback**: int16, mono, 24kHz, 2048-sample blocks (~85ms)

## Constants and Model IDs

| Constant | Value | Location |
|---|---|---|
| `SAMPLE_RATE` (capture/VAD) | 16000 | `audio/capture.py`, `vad/detector.py` |
| `CHUNK_SAMPLES` | 512 | `audio/capture.py`, `vad/detector.py` |
| `TTS_SAMPLE_RATE` | 24000 | `tts/synthesizer.py`, `audio/playback.py` |
| `CHAT_MODEL` | `gpt-4o-mini` | `llm/chat.py` |
| `TTS_MODEL` | `gpt-4o-mini-tts` | `tts/synthesizer.py` |
| `TTS_VOICE` | `coral` | `tts/synthesizer.py` |
| `ASR_MODEL` | `whisper-1` | `asr/transcriber.py` |
| VAD threshold | 0.5 | `vad/detector.py` |
| VAD min silence | 600ms | `vad/detector.py` |

## Development Commands

```bash
# Run with Modern TUI Dashboard (default)
uv run voice-agent

# Run with Modern Web UI Companion (opens http://127.0.0.1:8000)
uv run voice-agent --web

# Run headless (no TUI)
uv run voice-agent --headless

# Verbose logging
uv run voice-agent --verbose

# Run all tests
uv run pytest tests/

# Run a specific test file
uv run pytest tests/test_pipeline.py -v

# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>
```

## Environment Setup

```bash
cp .env.example .env
# Set OPENAI_API_KEY=sk-...
brew install portaudio   # macOS — required by sounddevice
```

## Code Conventions

- All async code uses `asyncio`; no threading except for the sounddevice bridge
- `from __future__ import annotations` at the top of every module
- Module-level `logger = logging.getLogger(__name__)` in every module
- Dataclasses for simple value types (`VADEvent`)
- Type hints throughout; use `X | Y` union syntax (Python 3.10+)
- Cancellation is always cooperative: check `cancel_event.is_set()` between chunks, never force-kill tasks except via `Task.cancel()` + await
- Never import `time` at module level inside async functions — use `import time` at top of file

## Testing Patterns

Tests are in `tests/` and use `pytest-asyncio`. Async tests use `@pytest.mark.asyncio`.

- Mock `openai.AsyncOpenAI` with `unittest.mock.AsyncMock`
- Use `numpy` arrays directly for audio test data
- The `_split_sentences` function in `llm/chat.py` is tested independently
- VAD tests reset state between runs via `detector.reset()`

## What to Watch Out For

1. **Silero VAD chunk size**: Must be exactly 512 samples at 16kHz. Do not change `CHUNK_SAMPLES`.
2. **PCM format mismatch**: Capture is float32; VAD output and ASR input are int16; TTS output is int16 at 24kHz (not 16kHz).
3. **Queue maxsize**: `AudioCapture._queue` has `maxsize=100`; if the pipeline stalls, chunks are dropped silently via `put_nowait`.
4. **History management in ChatLLM**: If a response is cancelled mid-stream with no content, the user message is popped to avoid a dangling turn.
5. **VADIterator exceptions**: The Silero VADIterator can raise on edge cases; `VADDetector.process_chunk` catches and resets on any exception.

# Voice Agent

A low-latency, real-time voice assistant for the terminal.

It captures microphone audio, performs local VAD with Silero, transcribes with OpenAI Whisper, generates responses with GPT-4o-mini, and streams speech back with GPT-4o-mini-tts. It supports barge-in, so users can interrupt playback naturally.

## Why this project

- Real-time, full-duplex interaction loop designed for responsiveness
- Practical async architecture with careful thread/async boundaries around `sounddevice`
- Production-minded cancellation design for smooth barge-in behavior
- Good reference implementation for voice pipeline orchestration in Python

## Features

- Local microphone capture and speaker playback
- Silero VAD speech start/end detection (16 kHz, 512-sample chunks)
- Whisper transcription (`whisper-1`)
- Streaming chat completions (`gpt-4o-mini`)
- Sentence-level streaming TTS (`gpt-4o-mini-tts`)
- Cooperative cancellation and immediate playback stop on interruption
- Multi-turn memory in the chat layer
- CLI-first workflow with minimal setup

## Architecture

```text
Mic (float32 chunks) -> VADDetector -> SPEECH_START -> barge-in cancel if playing
                               -> SPEECH_END (int16 PCM bytes)
                                   -> Transcriber (whisper-1) -> text
                                       -> ChatLLM (gpt-4o-mini stream) -> sentence text
                                           -> Synthesizer (gpt-4o-mini-tts) -> PCM stream
                                               -> AudioPlayback (sounddevice)
```

Latency target: speech end to first playback chunk under 1.5 seconds.

## Quick start

### 1) Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- OpenAI API key with access to `whisper-1`, `gpt-4o-mini`, and `gpt-4o-mini-tts`
- PortAudio (`sounddevice` backend)

macOS:

```bash
brew install portaudio
```

### 2) Configure environment

```bash
cp .env.example .env
```

Set your key in `.env`:

```bash
OPENAI_API_KEY=sk-...
```

### 3) Run

```bash
uv run voice-agent
```

Verbose mode:

```bash
uv run voice-agent --verbose
```

## Development

Run tests:

```bash
uv run pytest tests/
```

Project layout:

```text
src/voice_agent/
  main.py                 # CLI entry point
  audio/capture.py        # microphone capture
  audio/playback.py       # PCM playback and stop signaling
  vad/detector.py         # Silero VAD integration
  asr/transcriber.py      # Whisper API wrapper
  llm/chat.py             # streaming GPT chat + sentence splitting
  tts/synthesizer.py      # streaming TTS PCM generator
  pipeline/orchestrator.py# end-to-end pipeline + barge-in control
tests/
  test_asr.py
  test_vad.py
  test_pipeline.py
```

## Roadmap

- Add packaging metadata for PyPI publishing
- Add benchmark script for latency profiling
- Add optional local/offline ASR and TTS backends
- Add configurable wake-word mode

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` before opening a PR.

## Security

Please report vulnerabilities privately as described in `SECURITY.md`.

## License

This project is licensed under the MIT License. See `LICENSE`.

# Voice Agent

A real-time voice assistant that runs in the local terminal. It listens via microphone, detects speech with Silero VAD, transcribes with OpenAI Whisper, generates responses with GPT-4o-mini, and speaks back with GPT-4o-mini TTS — all with barge-in support and sub-1.5s end-to-end latency.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key with access to `whisper-1`, `gpt-4o-mini`, `gpt-4o-mini-tts`
- Working microphone and speakers
- PortAudio (required by sounddevice): `brew install portaudio`

## Setup

```bash
# Install PortAudio (macOS)
brew install portaudio

# Copy and fill in your API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# Install dependencies and run
uv run voice-agent
```

## How It Works

1. **Microphone** captures audio in 32ms chunks (512 samples @ 16kHz)
2. **Silero VAD** (local model) detects speech start/end in real time
3. On speech end, the audio buffer is sent to **OpenAI Whisper** for transcription
4. The transcript is streamed to **GPT-4o-mini**, which responds sentence by sentence
5. Each sentence is synthesized by **GPT-4o-mini-tts** (streaming PCM) and played immediately
6. If the user speaks during playback (**barge-in**), playback stops instantly and the new utterance is processed

## Latency Target

Speech end → first audio chunk playing: **< 1.5 seconds**

## Project Structure

```
src/voice_agent/
├── main.py              # Entry point
├── audio/
│   ├── capture.py       # Mic input (sounddevice)
│   └── playback.py      # Speaker output, streaming + barge-in stop
├── vad/
│   └── detector.py      # Silero VAD wrapper
├── asr/
│   └── transcriber.py   # OpenAI Whisper API
├── llm/
│   └── chat.py          # GPT-4o-mini streaming chat
├── tts/
│   └── synthesizer.py   # GPT-4o-mini-tts streaming PCM
└── pipeline/
    └── orchestrator.py  # Main pipeline with barge-in logic
```

## Running Tests

```bash
uv run pytest tests/
```

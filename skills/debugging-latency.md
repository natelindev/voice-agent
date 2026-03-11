# Skill: Debugging Latency Issues

Use this skill when diagnosing or optimizing the speech-end → first-audio latency (target: < 1.5s).

## Latency Budget Breakdown

```
Speech end
    ├── ASR (Whisper API)          ~300–700ms  ← biggest variable
    ├── LLM first token            ~200–400ms
    ├── Sentence buffer fill       ~50–200ms   (depends on sentence length)
    ├── TTS first chunk            ~100–300ms
    └── Audio playback start       ~85ms       (one BLOCKSIZE=2048 buffer)
```

Total logged in `orchestrator.py`:
```
"First audio chunk played %.3fs after speech end"
```

## Enable Verbose Logging

```bash
uv run voice-agent --verbose
```

This sets `logging.DEBUG` and shows per-stage timing:
- `ASR: <elapsed>s → <transcript>`
- `TTS: first chunk <elapsed>s`
- `First audio chunk played <elapsed>s after speech end`

## Common Causes of High Latency

### 1. ASR taking > 700ms
- Audio buffer is too large (user spoke too long)
- Silero VAD `min_silence_ms=600` means 600ms of silence before speech_end — this is intentional
- Consider reducing `min_silence_ms` in `VADDetector.__init__` (tradeoff: more false cuts)

### 2. LLM first token slow
- GPT-4o-mini is streaming; first token usually < 400ms
- Check `ChatLLM._history` length — long context increases TTFT
- Call `llm.clear_history()` to reset if needed

### 3. TTS first chunk slow
- `gpt-4o-mini-tts` streams PCM; logged as `TTS: first chunk <elapsed>s`
- If consistently > 500ms, check network or OpenAI API status

### 4. Sentence buffer filling slowly
- `_split_sentences` waits for `[.!?]` + whitespace
- Very long first sentences delay first audio
- The system prompt already requests concise responses

## Key Files for Latency Work

| File | What to look at |
|---|---|
| `pipeline/orchestrator.py:107` | `_respond()` — overall timing, `speech_end_ts` |
| `vad/detector.py:37` | `min_silence_ms=600` — tune for faster cut |
| `llm/chat.py:23` | `_SENTENCE_BOUNDARY` regex — tune sentence chunking |
| `tts/synthesizer.py:17` | `TTS_CHUNK_SIZE=4096` — smaller = lower first-chunk latency |
| `audio/playback.py:19` | `BLOCKSIZE=2048` — smaller = lower playback start latency |

## Tuning Knobs

```python
# vad/detector.py — reduce for faster speech_end detection
min_silence_ms: int = 400   # was 600; tradeoff: more false cuts

# tts/synthesizer.py — smaller chunks = lower first-chunk latency
TTS_CHUNK_SIZE = 2048        # was 4096

# audio/playback.py — smaller blocks = lower playback start latency
BLOCKSIZE = 1024             # was 2048; tradeoff: more callback overhead
```

## Profiling a Full Turn

Add temporary timing around each stage in `_respond()`:
```python
t0 = time.monotonic()
transcript = await self._transcriber.transcribe(audio_buffer)
logger.info("ASR: %.3f", time.monotonic() - t0)

t1 = time.monotonic()
async for sentence in self._llm.stream_response(transcript, self._cancel_event):
    logger.info("LLM sentence latency: %.3f", time.monotonic() - t1)
    t1 = time.monotonic()
    # ...
```

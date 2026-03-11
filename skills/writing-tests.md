# Skill: Writing Tests for Voice Agent

Use this skill when adding or fixing tests in the `tests/` directory.

## Test Setup

```python
# tests/test_<module>.py
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Import the class under test
from voice_agent.<domain>.<module> import MyClass
```

## Async Test Pattern

```python
@pytest.mark.asyncio
async def test_something() -> None:
    mock_client = AsyncMock()
    # configure mock...
    obj = MyClass(mock_client)
    result = await obj.some_method(...)
    assert result == expected
```

## Mocking OpenAI Streaming

```python
# For chat completions streaming
mock_chunk = MagicMock()
mock_chunk.choices = [MagicMock()]
mock_chunk.choices[0].delta.content = "Hello"

async def mock_stream():
    yield mock_chunk

mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
```

## Mocking TTS Streaming

```python
async def mock_tts_stream():
    yield b"\x00\x01" * 2048  # fake int16 PCM bytes

mock_response = AsyncMock()
mock_response.iter_bytes = MagicMock(return_value=mock_tts_stream())
mock_client.audio.speech.with_streaming_response.create = AsyncMock(
    return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
)
```

## Audio Test Data

```python
import numpy as np

# float32 audio chunk (capture/VAD format)
chunk = np.zeros(512, dtype=np.float32)
chunk_with_speech = np.random.uniform(-0.5, 0.5, 512).astype(np.float32)

# int16 PCM bytes (VAD output / ASR input)
pcm_bytes = (np.zeros(512, dtype=np.int16)).tobytes()
```

## Cancel Event Pattern

```python
cancel_event = asyncio.Event()

# Test normal (uncancelled) path
result = await obj.stream_response("hello", cancel_event)

# Test cancellation
cancel_event.set()
result = await obj.stream_response("hello", cancel_event)
```

## VAD Testing

```python
from voice_agent.vad.detector import VADDetector

def test_vad_reset() -> None:
    detector = VADDetector()
    detector.reset()
    assert not detector.in_speech
```

## Running Tests

```bash
uv run pytest tests/                    # all tests
uv run pytest tests/test_pipeline.py -v  # specific file, verbose
uv run pytest -k "test_split" -v         # filter by name
```

## What NOT to Test

- Do not test with a real microphone or speakers
- Do not make real OpenAI API calls in tests
- Do not test the `sounddevice` callbacks directly (they run on C audio thread)

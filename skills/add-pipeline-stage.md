# Skill: Adding a New Pipeline Stage

Use this skill when adding a new processing stage (e.g., emotion detection, language translation, noise filtering) to the voice pipeline.

## Pattern

Every stage follows the same structure:

```python
# src/voice_agent/<domain>/<module>.py
from __future__ import annotations

import asyncio
import logging

import openai

logger = logging.getLogger(__name__)

MODEL = "..."          # model constant at module level
SOME_CONSTANT = ...    # other constants at module level


class MyStage:
    """One-line description of this stage's role in the pipeline."""

    def __init__(self, client: openai.AsyncOpenAI) -> None:
        self._client = client

    async def process(
        self,
        input_data: ...,
        cancel_event: asyncio.Event,
    ) -> ...:
        """Process input and return output. Respect cancel_event."""
        if cancel_event.is_set():
            return ...
        # ... implementation
```

## Checklist

1. Create `src/voice_agent/<domain>/__init__.py` (empty)
2. Create `src/voice_agent/<domain>/<module>.py` following the pattern above
3. Add module-level constants (model name, thresholds, etc.) — not inside `__init__`
4. Accept `cancel_event: asyncio.Event` if the stage does async I/O
5. Check `cancel_event.is_set()` between every async chunk/step
6. Add the stage to `PipelineOrchestrator.__init__` in `pipeline/orchestrator.py`
7. Wire it into `_respond()` or the appropriate handler
8. Write tests in `tests/test_<domain>.py` using `AsyncMock` for the OpenAI client

## Wiring into the Orchestrator

In `orchestrator.py`:

```python
# In __init__:
self._my_stage = MyStage(client)

# In _respond():
result = await self._my_stage.process(input_data, self._cancel_event)
if self._cancel_event.is_set():
    return
```

## Audio Format Reminder

If the stage handles audio, respect these formats:
- Input from VAD: **int16 PCM bytes @ 16kHz**
- Output to TTS/Playback: **int16 PCM bytes @ 24kHz**
- Do not mix sample rates without explicit resampling

"""GPT-4o-mini streaming chat with multi-turn history and sentence-level chunking."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncGenerator

import openai

logger = logging.getLogger(__name__)

CHAT_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "Keep your responses concise and conversational since they will be spoken aloud. "
    "Avoid using markdown, bullet points, or lists — speak in plain sentences."
)

# Sentence boundary: period/exclamation/question followed by space or end-of-string
# Also split on newlines to handle model-generated line breaks
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=\n)")


def _split_sentences(text: str) -> tuple[list[str], str]:
    """
    Split text into complete sentences plus a leftover fragment.
    Returns (sentences, remainder).
    """
    parts = _SENTENCE_BOUNDARY.split(text)
    if len(parts) <= 1:
        return [], text
    return parts[:-1], parts[-1]


class ChatLLM:
    """Streams GPT-4o-mini responses sentence by sentence with cancellation support."""

    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str = CHAT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._client = client
        self._model = model
        self._history: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

    async def stream_response(
        self,
        user_text: str,
        cancel_event: asyncio.Event,
    ) -> AsyncGenerator[str, None]:
        """
        Yield complete sentences as the LLM streams its response.
        Stops yielding if cancel_event is set.
        Appends the full assistant reply to history when done.
        """
        self._history.append({"role": "user", "content": user_text})
        logger.info("LLM: user=%r", user_text)

        buffer = ""
        full_reply = ""

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=self._history,
                stream=True,
            )

            async for chunk in stream:
                if cancel_event.is_set():
                    logger.info("LLM: cancelled")
                    break

                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta is None:
                    continue

                buffer += delta
                sentences, buffer = _split_sentences(buffer)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        full_reply += sentence + " "
                        logger.debug("LLM sentence: %r", sentence)
                        yield sentence

            # Yield any remaining text in buffer as a final fragment
            if buffer.strip() and not cancel_event.is_set():
                full_reply += buffer.strip()
                yield buffer.strip()

        finally:
            # Only record history if we got a meaningful reply
            if full_reply.strip():
                self._history.append(
                    {"role": "assistant", "content": full_reply.strip()}
                )
            else:
                # Remove the user message we just added if we got nothing back
                self._history.pop()

    def clear_history(self) -> None:
        """Reset conversation to just the system prompt."""
        self._history = [self._history[0]]
        logger.info("LLM: history cleared")

    @property
    def history_length(self) -> int:
        return len(self._history) - 1  # exclude system prompt

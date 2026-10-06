"""Codex CLI integration for LLM responses using user's ChatGPT subscription."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re
import shutil
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

CODEX_BIN = Path.home() / ".local/bin/codex"
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=\n)")


def _clean_for_speech(text: str) -> str:
    """Strip markdown links, raw URLs, and decorative characters for spoken output."""
    # Replace markdown links [anchor text](url) with just the anchor text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip standalone URLs
    text = re.sub(r"https?://\S+", "", text)
    # Strip markdown formatting (*, _, `, #, ~)
    text = re.sub(r"[*_`#~]", "", text)
    # Remove leading bullet points or dashes
    text = re.sub(r"^[-*•]\s+", "", text, flags=re.MULTILINE)
    # Collapse excess whitespace
    return re.sub(r"\s+", " ", text).strip()


def _parse_codex_output(output: str) -> str:
    """
    Extract the assistant response from Codex CLI output.
    Codex may output tool calls (e.g. web search) with multiple 'codex' sections.
    We collect all sections and prefer the final synthesis.
    """
    sections: list[list[str]] = []
    current_section: list[str] | None = None

    for line in output.splitlines():
        stripped = line.strip()
        if stripped == "codex":
            if current_section is not None:
                sections.append(current_section)
            current_section = []
            continue
        if current_section is not None:
            if (
                stripped.startswith("hook:")
                or stripped.startswith("tokens used")
                or stripped.startswith("web search:")
                or stripped.startswith("user")
            ):
                sections.append(current_section)
                current_section = None
            else:
                current_section.append(line)

    if current_section is not None:
        sections.append(current_section)

    valid_texts = []
    for sec in sections:
        text = "\n".join(sec).strip()
        if text:
            valid_texts.append(text)

    if valid_texts:
        # Use the final section which holds the synthesized answer after tool executions
        chosen = valid_texts[-1]
    else:
        chosen = output.strip()

    return _clean_for_speech(chosen)


class CodexLLM:
    """
    Invokes Codex CLI (`codex exec`) using the user's existing ChatGPT subscription.
    Yields conversational sentences suitable for speech with full multi-turn context.
    """

    def __init__(self, codex_path: Path | str = CODEX_BIN) -> None:
        self.codex_path = str(codex_path) if Path(codex_path).exists() else shutil.which("codex") or "codex"
        self._history: list[dict[str, str]] = []

    def _build_prompt(self, user_text: str) -> str:
        """Construct prompt with multi-turn conversation history."""
        history_items = []
        for msg in self._history[:-1][-8:]:  # Include up to last 8 turns of context
            role = "User" if msg["role"] == "user" else "Assistant"
            history_items.append(f"{role}: {msg['content']}")

        if history_items:
            history_block = "Previous conversation history:\n" + "\n".join(history_items) + "\n\n"
        else:
            history_block = ""

        return (
            f"You are a helpful, intelligent voice assistant in voice conversation mode. "
            f"{history_block}"
            f"The user said: '{user_text}'. "
            f"Respond conversationally and directly to the user in 1 to 2 short plain sentences suitable to be spoken aloud. "
            f"Maintain full context from the previous conversation. "
            f"Do not use markdown, links, bullet points, asterisks, or code."
        )

    async def stream_response(
        self,
        user_text: str,
        cancel_event: asyncio.Event,
    ) -> AsyncGenerator[str, None]:
        """Generate response via Codex CLI non-interactively with full context."""
        self._history.append({"role": "user", "content": user_text})
        logger.info("CodexLLM turn %d: %r", len(self._history), user_text)

        prompt = self._build_prompt(user_text)
        cmd = [self.codex_path, "exec", prompt]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Wait for execution while checking cancel_event
            while proc.returncode is None:
                if cancel_event.is_set():
                    proc.terminate()
                    logger.info("CodexLLM cancelled")
                    return
                try:
                    await asyncio.wait_for(proc.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass

            stdout_bytes = await proc.stdout.read() if proc.stdout else b""
            output = stdout_bytes.decode("utf-8", errors="replace")

            full_reply = _parse_codex_output(output)
            logger.info("CodexLLM reply: %r", full_reply)

            # Split into sentences and yield
            parts = _SENTENCE_BOUNDARY.split(full_reply)
            for part in parts:
                clean = part.strip()
                if clean and not cancel_event.is_set():
                    yield clean

            if full_reply:
                self._history.append({"role": "assistant", "content": full_reply})

        except Exception as e:
            logger.exception("CodexLLM execution error: %s", e)
            fallback = "I had trouble generating a response, please try again."
            yield fallback

    def clear_history(self) -> None:
        self._history.clear()

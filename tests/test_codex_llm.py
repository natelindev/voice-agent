"""Tests for CodexLLM integration."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from voice_agent.llm.codex_llm import CodexLLM, _clean_for_speech, _parse_codex_output


def test_clean_for_speech_removes_markdown_and_urls() -> None:
    raw = "Here is the [forecast](https://weather.com/shanghai) for **today**! Visit https://example.com for more."
    cleaned = _clean_for_speech(raw)
    assert cleaned == "Here is the forecast for today! Visit for more."
    assert "http" not in cleaned
    assert "**" not in cleaned


def test_parse_codex_output_handles_tool_steps() -> None:
    output = """
OpenAI Codex v0.160.1
user
Prompt here
codex
I will search for the weather.
web search: query
hook: PostToolUse Completed
codex
Shanghai is currently sunny and 22 degrees.
hook: Stop
tokens used
1200
"""
    parsed = _parse_codex_output(output)
    assert parsed == "Shanghai is currently sunny and 22 degrees."


def test_build_prompt_includes_multi_turn_history() -> None:
    llm = CodexLLM()
    llm._history = [
        {"role": "user", "content": "I want to check the weather."},
        {"role": "assistant", "content": "Sure, which city?"},
        {"role": "user", "content": "Shanghai"},
        {"role": "assistant", "content": "What would you like to know about Shanghai?"},
        {"role": "user", "content": "What is the weather like?"},
    ]

    prompt = llm._build_prompt("What is the weather like?")
    assert "User: I want to check the weather." in prompt
    assert "Assistant: Sure, which city?" in prompt
    assert "User: Shanghai" in prompt
    assert "The user said: 'What is the weather like?'" in prompt


@pytest.mark.asyncio
async def test_codex_llm_streams_sentences() -> None:
    llm = CodexLLM()
    cancel_event = asyncio.Event()

    simulated_stdout = b"codex\nHello there! How can I help today?\nhook: finished\n"

    proc_mock = AsyncMock()
    proc_mock.returncode = 0
    proc_mock.wait = AsyncMock(return_value=0)
    proc_mock.stdout.read = AsyncMock(return_value=simulated_stdout)

    with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
        sentences = []
        async for s in llm.stream_response("hi", cancel_event):
            sentences.append(s)

        assert len(sentences) == 2
        assert sentences[0] == "Hello there!"
        assert sentences[1] == "How can I help today?"


@pytest.mark.asyncio
async def test_codex_llm_cancellation() -> None:
    from unittest.mock import MagicMock
    llm = CodexLLM()
    cancel_event = asyncio.Event()
    cancel_event.set()

    proc_mock = AsyncMock()
    proc_mock.returncode = None
    proc_mock.terminate = MagicMock()
    proc_mock.wait = AsyncMock(return_value=0)
    proc_mock.stdout.read = AsyncMock(return_value=b"")

    with patch("asyncio.create_subprocess_exec", return_value=proc_mock):
        sentences = []
        async for s in llm.stream_response("test", cancel_event):
            sentences.append(s)

        assert sentences == []

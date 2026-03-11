"""Tests for pipeline utility functions."""

from __future__ import annotations

import pytest

from voice_agent.llm.chat import _split_sentences


@pytest.mark.parametrize(
    "text, expected_sentences, expected_remainder",
    [
        ("Hello world", [], "Hello world"),
        ("Hello. World", ["Hello."], "World"),
        ("Hello! How are you? I am fine.", ["Hello!", "How are you?"], "I am fine."),
        ("One sentence. ", ["One sentence."], ""),
        ("", [], ""),
        ("No boundary here", [], "No boundary here"),
    ],
)
def test_split_sentences(
    text: str,
    expected_sentences: list[str],
    expected_remainder: str,
) -> None:
    sentences, remainder = _split_sentences(text)
    assert sentences == expected_sentences
    assert remainder == expected_remainder

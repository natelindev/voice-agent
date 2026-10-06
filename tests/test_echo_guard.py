"""Tests for Echo Guard (acoustic echo prevention & self-hearing filtering)."""

import time
import pytest

from voice_agent.pipeline.local_orchestrator import LocalPipelineOrchestrator


def test_echo_guard_filters_identical_assistant_text() -> None:
    orchestrator = LocalPipelineOrchestrator()
    orchestrator._recent_assistant_texts = ["Hello there! How can I help you today?"]
    orchestrator._last_playback_end = time.monotonic()

    # Identical or substring text captured by microphone
    assert orchestrator._is_self_echo("Hello there! How can I help you today?")
    assert orchestrator._is_self_echo("How can I help you today?")
    assert orchestrator._is_self_echo("How can I help you")


def test_echo_guard_filters_hallucinated_tail_artifacts() -> None:
    orchestrator = LocalPipelineOrchestrator()
    orchestrator._recent_assistant_texts = ["Have a good day!"]
    orchestrator._last_playback_end = time.monotonic()

    assert orchestrator._is_self_echo("Bye.")
    assert orchestrator._is_self_echo("Thank you.")
    assert orchestrator._is_self_echo("goodbye")


def test_echo_guard_allows_distinct_user_speech() -> None:
    orchestrator = LocalPipelineOrchestrator()
    orchestrator._recent_assistant_texts = ["The weather in San Francisco is sunny today."]
    orchestrator._last_playback_end = time.monotonic()

    assert not orchestrator._is_self_echo("What time is my next meeting?")
    assert not orchestrator._is_self_echo("Open the project settings")

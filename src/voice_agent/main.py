"""Entry point for the voice agent."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
import openai

from voice_agent.pipeline.orchestrator import PipelineOrchestrator


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers unless verbose
    if not verbose:
        for name in ("httpx", "httpcore", "openai", "urllib3"):
            logging.getLogger(name).setLevel(logging.WARNING)


def _status_print(msg: str) -> None:
    """Print status to terminal, overwriting the current line."""
    sys.stdout.write(f"\r\033[K{msg}")
    sys.stdout.flush()


async def _run(verbose: bool = False) -> None:
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    client = openai.AsyncOpenAI(api_key=api_key)

    print("Voice Agent starting up...")
    print("  - Loading Silero VAD model (first run may take a moment)...")

    orchestrator = PipelineOrchestrator(client=client, status_callback=_status_print)

    print("  - Ready! Speak into your microphone. Press Ctrl+C to quit.\n")

    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Real-time voice assistant")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    _configure_logging(verbose=args.verbose)

    try:
        asyncio.run(_run(verbose=args.verbose))
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()

"""Entry point for the voice agent with dual TUI and Web UI companion support."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import webbrowser

from dotenv import load_dotenv

from voice_agent.events.hub import EventHub
from voice_agent.tui.dashboard import TUIDashboard
from voice_agent.web.server import WebCompanionServer

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool = False, is_tui: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    # If TUI is active and not verbose, avoid stdout logging collisions
    if is_tui and not verbose:
        logging.basicConfig(level=logging.ERROR)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        for name in ("httpx", "httpcore", "openai", "urllib3"):
            logging.getLogger(name).setLevel(logging.WARNING)


def _status_print(msg: str) -> None:
    """Print status to terminal, overwriting the current line."""
    sys.stdout.write(f"\r\033[K{msg}")
    sys.stdout.flush()


async def _run(
    verbose: bool = False,
    web: bool = False,
    port: int = 8000,
    no_open: bool = False,
    tui: bool = True,
    demo: bool = False,
    local: bool = False,
    headphones: bool = False,
) -> None:
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY")
    use_local = local or (not api_key and not demo)
    use_demo = demo and not local
    suppress_speaker_echo = not headphones

    event_hub = EventHub()
    event_hub.set_loop(asyncio.get_running_loop())

    web_server: WebCompanionServer | None = None
    tui_dashboard: TUIDashboard | None = None

    model_display = "gpt-4o-mini"
    voice_display = "coral"
    if use_local:
        model_display = "Codex (ChatGPT)"
        voice_display = "Samantha (Mac)"
        if not tui:
            print("\n[✓] Running in 100% Local Mac Mode:")
            print("    - ASR: OpenSuperWhisper (Apple Silicon Metal)")
            print("    - LLM: OpenAI Codex CLI (using your ChatGPT subscription)")
            print("    - TTS: macOS Native Speech (Samantha)")
            if suppress_speaker_echo:
                print("    - Echo Protection: Active (Speaker ducking & self-echo filtering)\n")
            else:
                print("    - Headphone Mode: Voice barge-in enabled\n")
    elif use_demo and not tui:
        print("\n[!] OPENAI_API_KEY not configured. Running in Preview / Demo Mode.\n")

    # Start Web UI companion if requested
    if web:
        web_server = WebCompanionServer(event_hub=event_hub, host="127.0.0.1", port=port)
        await web_server.start()
        url = f"http://127.0.0.1:{port}"
        if not tui:
            print(f"  - Web UI Companion active at {url}")
        if not no_open:
            webbrowser.open(url)

    # Initialize pipeline orchestrator
    if use_local:
        from voice_agent.pipeline.local_orchestrator import LocalPipelineOrchestrator
        orchestrator = LocalPipelineOrchestrator(
            event_hub=event_hub,
            status_callback=_status_print if not tui else None,
            suppress_speaker_echo=suppress_speaker_echo,
        )
    elif use_demo:
        from voice_agent.pipeline.demo import DemoOrchestrator
        orchestrator = DemoOrchestrator(event_hub=event_hub)
    else:
        import openai
        from voice_agent.pipeline.orchestrator import PipelineOrchestrator
        client = openai.AsyncOpenAI(api_key=api_key)
        orchestrator = PipelineOrchestrator(
            client=client,
            status_callback=_status_print if not tui else None,
            event_hub=event_hub,
            suppress_speaker_echo=suppress_speaker_echo,
        )

    # Start TUI dashboard if enabled
    if tui:
        tui_dashboard = TUIDashboard(
            event_hub=event_hub,
            model_name=model_display,
            voice_name=voice_display,
        )
        await tui_dashboard.start()
    else:
        print("  - Ready! Speak into your microphone. Press Ctrl+C to quit.\n")

    try:
        await orchestrator.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        if tui_dashboard:
            await tui_dashboard.stop()
        if web_server:
            await web_server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time voice assistant with Modern TUI & Web UI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--web", "-w", action="store_true", help="Launch modern Web UI companion")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Web companion port (default: 8000)")
    parser.add_argument("--no-open", action="store_true", help="Do not automatically open browser on --web")
    parser.add_argument("--headless", "--no-tui", dest="no_tui", action="store_true", help="Disable TUI dashboard")
    parser.add_argument("--local", "-l", action="store_true", help="Force 100%% Local Mac mode (OpenSuperWhisper + Codex + Mac TTS)")
    parser.add_argument("--demo", action="store_true", help="Run interactive demo simulation mode")
    parser.add_argument(
        "--headphones",
        action="store_true",
        help="Enable mic-based voice barge-in while speaking (recommended only when using headphones)",
    )
    args = parser.parse_args()

    # Enable TUI by default if stdout is a TTY and not explicitly disabled
    use_tui = not args.no_tui and sys.stdout.isatty()

    _configure_logging(verbose=args.verbose, is_tui=use_tui)

    try:
        asyncio.run(
            _run(
                verbose=args.verbose,
                web=args.web,
                port=args.port,
                no_open=args.no_open,
                tui=use_tui,
                demo=args.demo,
                local=args.local,
                headphones=args.headphones,
            )
        )
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()

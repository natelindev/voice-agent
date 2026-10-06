"""Tests for WebCompanionServer HTTP static serving and WebSocket handshake."""

from __future__ import annotations

import asyncio
import urllib.request
try:
    import pytest
except ImportError:
    class DummyMark:
        def __getattr__(self, name: str):
            return lambda fn: fn

    class DummyPytest:
        mark = DummyMark()

    pytest = DummyPytest()  # type: ignore

from voice_agent.events.hub import EventHub
from voice_agent.web.server import WebCompanionServer


@pytest.mark.asyncio
async def test_web_server_serves_static_assets() -> None:
    hub = EventHub()
    # Use ephemeral port 0 or higher free port
    server = WebCompanionServer(event_hub=hub, host="127.0.0.1", port=8910)
    await server.start()

    try:
        # Request /
        def fetch(path: str) -> tuple[int, bytes]:
            url = f"http://127.0.0.1:8910{path}"
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                return resp.status, resp.read()

        loop = asyncio.get_running_loop()

        # Fetch index.html
        status, content = await loop.run_in_executor(None, fetch, "/")
        assert status == 200
        assert b"Voice Agent" in content

        # Fetch styles.css
        status, css_content = await loop.run_in_executor(None, fetch, "/styles.css")
        assert status == 200
        assert b"--bg-primary" in css_content

        # Fetch orb.js
        status, js_content = await loop.run_in_executor(None, fetch, "/orb.js")
        assert status == 200
        assert b"VoiceOrb" in js_content

    finally:
        await server.stop()

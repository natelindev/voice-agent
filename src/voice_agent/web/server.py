"""Lightweight, zero-dependency async HTTP and WebSocket server for Web UI Companion."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
from pathlib import Path
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voice_agent.events.hub import BaseEvent, EventHub

logger = logging.getLogger(__name__)

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
STATIC_DIR = Path(__file__).parent / "static"


class WebSocketConnection:
    """Manages a single RFC 6455 WebSocket client connection."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        self.is_open = True

    async def send_text(self, text: str) -> None:
        """Send a UTF-8 text frame (unmasked from server)."""
        if not self.is_open or self.writer.is_closing():
            return
        payload = text.encode("utf-8")
        length = len(payload)

        # Fin=1, Opcode=1 (Text)
        header = bytearray([0x81])
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))

        try:
            self.writer.write(header + payload)
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            self.is_open = False

    async def read_frame(self) -> str | None:
        """Read and decode an inbound masked WebSocket frame."""
        try:
            head = await self.reader.readexactly(2)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            self.is_open = False
            return None

        byte1, byte2 = head[0], head[1]
        opcode = byte1 & 0x0F
        masked = (byte2 & 0x80) != 0
        payload_len = byte2 & 0x7F

        if opcode == 0x08:  # Close frame
            self.is_open = False
            return None
        elif opcode == 0x09:  # Ping frame -> reply with Pong
            pong = bytearray([0x8A, 0x00])
            self.writer.write(pong)
            await self.writer.drain()
            return None

        if payload_len == 126:
            ext_len = await self.reader.readexactly(2)
            payload_len = struct.unpack("!H", ext_len)[0]
        elif payload_len == 127:
            ext_len = await self.reader.readexactly(8)
            payload_len = struct.unpack("!Q", ext_len)[0]

        mask = b""
        if masked:
            mask = await self.reader.readexactly(4)

        data = await self.reader.readexactly(payload_len)
        if masked:
            unmasked = bytearray(payload_len)
            for i in range(payload_len):
                unmasked[i] = data[i] ^ mask[i % 4]
            data = bytes(unmasked)

        return data.decode("utf-8", errors="replace")


class WebCompanionServer:
    """
    Serves the modern Web UI companion via HTTP and WebSockets.
    Connects with EventHub to broadcast live audio meters, state, and transcripts.
    """

    def __init__(self, event_hub: EventHub, host: str = "127.0.0.1", port: int = 8000) -> None:
        self._hub = event_hub
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None
        self._clients: set[WebSocketConnection] = set()
        self._broadcast_task: asyncio.Task | None = None
        self._is_running = False

    async def start(self) -> None:
        """Start the HTTP & WebSocket server and telemetry broadcaster."""
        self._is_running = True
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self._broadcast_task = asyncio.create_task(self._hub_broadcast_loop(), name="web_broadcast")
        logger.info("Web Companion Server running on http://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop server and disconnect clients."""
        self._is_running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
        for client in list(self._clients):
            try:
                client.writer.close()
                await client.writer.wait_closed()
            except Exception:
                pass
        self._clients.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("Web Companion Server stopped")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming HTTP request or WebSocket upgrade."""
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                return

            req_line = line.decode("utf-8", errors="replace").strip()
            parts = req_line.split()
            if len(parts) < 2:
                writer.close()
                return

            method, path = parts[0], parts[1]
            headers: dict[str, str] = {}
            while True:
                h_line = await reader.readline()
                if not h_line or h_line == b"\r\n" or h_line == b"\n":
                    break
                decoded = h_line.decode("utf-8", errors="replace").strip()
                if ":" in decoded:
                    k, v = decoded.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # Check if WebSocket upgrade
            if headers.get("upgrade", "").lower() == "websocket":
                await self._handle_ws_upgrade(path, headers, reader, writer)
                return

            # Serve static HTTP assets
            await self._serve_static(path, writer)

        except Exception as e:
            logger.debug("Client handler error: %s", e)
            try:
                writer.close()
            except Exception:
                pass

    async def _handle_ws_upgrade(
        self,
        path: str,
        headers: dict[str, str],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        sec_key = headers.get("sec-websocket-key", "")
        if not sec_key:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Compute Sec-WebSocket-Accept
        accept_raw = sec_key + WS_GUID
        accept_sha = hashlib.sha1(accept_raw.encode("utf-8")).digest()
        accept_b64 = base64.b64encode(accept_sha).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_b64}\r\n\r\n"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()

        ws = WebSocketConnection(reader, writer)
        self._clients.add(ws)
        logger.info("WebSocket client connected (%d active)", len(self._clients))

        # Send initial handshake state
        initial_event = {
            "event_type": "state_change",
            "state": self._hub.current_state.value if hasattr(self._hub.current_state, "value") else str(self._hub.current_state),
            "message": self._hub.state_message,
            "is_muted": self._hub.is_muted,
        }
        await ws.send_text(json.dumps(initial_event))

        # Read inbound client messages (commands)
        try:
            while self._is_running and ws.is_open:
                msg = await ws.read_frame()
                if msg is None:
                    break
                await self._handle_inbound_ws_message(msg)
        finally:
            self._clients.discard(ws)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("WebSocket client disconnected (%d remaining)", len(self._clients))

    async def _handle_inbound_ws_message(self, message_str: str) -> None:
        from voice_agent.events.hub import ControlCommandEvent

        try:
            data = json.loads(message_str)
            action = data.get("action")
            if action:
                cmd = ControlCommandEvent(action=action, payload=data.get("payload", {}))
                self._hub.dispatch_control(cmd)
        except Exception:
            logger.warning("Failed to parse inbound WebSocket message: %s", message_str)

    async def _serve_static(self, path: str, writer: asyncio.StreamWriter) -> None:
        clean_path = path.split("?")[0].lstrip("/")
        if clean_path in ("", "index", "index.html"):
            file_path = STATIC_DIR / "index.html"
        else:
            file_path = (STATIC_DIR / clean_path).resolve()

        # Prevent directory traversal
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.is_file():
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\n\r\nNot Found")
            await writer.drain()
            writer.close()
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"
        if file_path.suffix == ".css":
            mime_type = "text/css"
        elif file_path.suffix == ".js":
            mime_type = "application/javascript"

        content = file_path.read_bytes()
        headers = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {mime_type}; charset=utf-8\r\n"
            f"Content-Length: {len(content)}\r\n"
            f"Cache-Control: no-cache\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(headers.encode("utf-8") + content)
        await writer.drain()
        writer.close()

    async def _hub_broadcast_loop(self) -> None:
        """Subscribe to EventHub and broadcast JSON events to all WebSocket clients."""
        q = self._hub.subscribe(maxsize=128)
        try:
            while self._is_running:
                event = await q.get()
                if not self._clients:
                    continue

                event_dict = event.to_dict()
                payload = json.dumps(event_dict)

                # Broadcast concurrently to all connected clients
                for client in list(self._clients):
                    if client.is_open:
                        asyncio.create_task(client.send_text(payload))
        except asyncio.CancelledError:
            pass
        finally:
            self._hub.unsubscribe(q)

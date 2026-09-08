"""Async TCP client for HLK-DIO16.

Home Assistant and smoke tests only need:

  await client.connect()
  await client.read_inputs()
  await client.read_outputs()
  await client.set_output(channel, state)
  await client.disconnect()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .const import Command, DEFAULT_PORT
from .exceptions import (
    HlkDio16ConnectionError,
    HlkDio16ProtocolError,
    HlkDio16TimeoutError,
)
from .protocol import (
    decode_channel_bits,
    encode_output_control,
    encode_read,
    extract_frame,
)

_LOGGER = logging.getLogger(__name__)


class HlkDio16Client:
    """Persistent TCP client with a single-flight transaction queue."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._buffer = bytearray()

    @property
    def connected(self) -> bool:
        """Return True when the socket is open."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open the TCP connection."""
        if self.connected:
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
        except (OSError, asyncio.TimeoutError) as err:
            self._reader = None
            self._writer = None
            raise HlkDio16ConnectionError(
                f"cannot connect to {self.host}:{self.port}: {err}"
            ) from err
        self._buffer.clear()
        _LOGGER.info("Connected to HLK-DIO16 at %s:%s", self.host, self.port)

    async def disconnect(self) -> None:
        """Close the TCP connection."""
        writer = self._writer
        self._reader = None
        self._writer = None
        self._buffer.clear()
        if writer is None:
            return
        try:
            writer.close()
            await writer.wait_closed()
        except OSError:
            pass
        _LOGGER.info("Disconnected from HLK-DIO16 at %s:%s", self.host, self.port)

    async def read_inputs(self) -> dict[int, bool]:
        """Return digital input states keyed by channel 1–16."""
        payload = await self._transact(encode_read(Command.INPUT_STATE))
        return self._parse_state_payload(payload, Command.INPUT_STATE)

    async def read_outputs(self) -> dict[int, bool]:
        """Return digital output states keyed by channel 1–16."""
        payload = await self._transact(encode_read(Command.OUTPUT_STATE))
        return self._parse_state_payload(payload, Command.OUTPUT_STATE)

    async def set_output(self, channel: int, state: bool) -> dict[int, bool]:
        """Set one output channel and return refreshed output states."""
        await self._transact(encode_output_control(channel, state), expect_control_ack=True)
        return await self.read_outputs()

    async def health_check(self) -> dict[int, bool]:
        """Cheap connectivity check: read outputs."""
        return await self.read_outputs()

    async def _ensure_connected(self) -> None:
        if not self.connected:
            await self.connect()

    async def _transact(
        self,
        packet: bytes,
        *,
        expect_control_ack: bool = False,
    ) -> bytes:
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None
            try:
                self._writer.write(packet)
                await self._writer.drain()
                return await asyncio.wait_for(
                    self._read_one_frame(expect_control_ack=expect_control_ack),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError as err:
                await self.disconnect()
                raise HlkDio16TimeoutError("timed out waiting for HLK-DIO16 response") from err
            except (OSError, HlkDio16ProtocolError) as err:
                await self.disconnect()
                if isinstance(err, HlkDio16ProtocolError):
                    raise
                raise HlkDio16ConnectionError(str(err)) from err

    async def _read_one_frame(self, *, expect_control_ack: bool) -> bytes:
        assert self._reader is not None
        while True:
            frame = extract_frame(self._buffer)
            if frame is not None:
                if expect_control_ack:
                    self._validate_control_ack(frame)
                return frame
            chunk = await self._reader.read(256)
            if not chunk:
                raise HlkDio16ConnectionError("connection closed by HLK-DIO16")
            self._buffer.extend(chunk)

    @staticmethod
    def _validate_control_ack(frame: bytes) -> None:
        if not frame or frame[0] != int(Command.TYPE_RESPONSE):
            raise HlkDio16ProtocolError(
                f"expected control response 0xFF, got {frame[:1]!r}"
            )
        if len(frame) < 4 or frame[1] != int(Command.OUTPUT_CTR):
            raise HlkDio16ProtocolError(f"unexpected control ack payload: {frame!r}")

    @staticmethod
    def _parse_state_payload(frame: bytes, expected: Command) -> dict[int, bool]:
        if not frame or frame[0] != int(expected):
            raise HlkDio16ProtocolError(
                f"expected command 0x{int(expected):02x}, got {frame[:1]!r}"
            )
        try:
            return decode_channel_bits(frame[1:])
        except ValueError as err:
            raise HlkDio16ProtocolError(str(err)) from err


async def probe_device(host: str, port: int = DEFAULT_PORT, timeout: float = 5.0) -> dict[str, Any]:
    """Connect, read DI/DO once, disconnect — used by config flow and smoke tests."""
    client = HlkDio16Client(host, port, timeout=timeout)
    try:
        await client.connect()
        outputs = await client.read_outputs()
        inputs = await client.read_inputs()
        return {"inputs": inputs, "outputs": outputs}
    finally:
        await client.disconnect()

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
        return await self._read_states(Command.INPUT_STATE)

    async def read_outputs(self) -> dict[int, bool]:
        """Return digital output states keyed by channel 1–16."""
        return await self._read_states(Command.OUTPUT_STATE)

    async def set_output(self, channel: int, state: bool) -> dict[int, bool]:
        """Set one output channel and return refreshed output states."""
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None
            try:
                self._writer.write(encode_output_control(channel, state))
                await self._writer.drain()

                # Firmware may reply with 0xFF ack, OUTPUT_STATE, or both.
                deadline = asyncio.get_running_loop().time() + self.timeout
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    frame = await asyncio.wait_for(
                        self._read_one_frame(), timeout=remaining
                    )
                    if frame[0] == int(Command.OUTPUT_STATE):
                        return decode_channel_bits(frame[1:])
                    if frame[0] == int(Command.TYPE_RESPONSE):
                        self._validate_control_ack(frame)
                        # Often a state frame follows immediately in the same burst.
                        try:
                            follow = await asyncio.wait_for(
                                self._read_one_frame(), timeout=0.4
                            )
                        except asyncio.TimeoutError:
                            break
                        if follow[0] == int(Command.OUTPUT_STATE):
                            return decode_channel_bits(follow[1:])
                        # Unexpected follow-up; keep waiting until deadline.
                        continue
                    _LOGGER.debug(
                        "Skipping unexpected frame after output control: %r", frame[:1]
                    )

                self._writer.write(encode_read(Command.OUTPUT_STATE))
                await self._writer.drain()
                frame = await asyncio.wait_for(
                    self._read_frame_matching({Command.OUTPUT_STATE}),
                    timeout=self.timeout,
                )
                return decode_channel_bits(frame[1:])
            except asyncio.TimeoutError as err:
                await self.disconnect()
                raise HlkDio16TimeoutError(
                    "timed out waiting for HLK-DIO16 response"
                ) from err
            except (OSError, HlkDio16ProtocolError, ValueError) as err:
                await self.disconnect()
                if isinstance(err, (HlkDio16ProtocolError, ValueError)):
                    raise HlkDio16ProtocolError(str(err)) from err
                raise HlkDio16ConnectionError(str(err)) from err

    async def health_check(self) -> dict[int, bool]:
        """Cheap connectivity check: read outputs."""
        return await self.read_outputs()

    async def _read_states(self, command: Command) -> dict[int, bool]:
        async with self._lock:
            await self._ensure_connected()
            assert self._writer is not None
            try:
                self._writer.write(encode_read(command))
                await self._writer.drain()
                frame = await asyncio.wait_for(
                    self._read_frame_matching({command}),
                    timeout=self.timeout,
                )
                return decode_channel_bits(frame[1:])
            except asyncio.TimeoutError as err:
                await self.disconnect()
                raise HlkDio16TimeoutError(
                    "timed out waiting for HLK-DIO16 response"
                ) from err
            except (OSError, HlkDio16ProtocolError, ValueError) as err:
                await self.disconnect()
                if isinstance(err, (HlkDio16ProtocolError, ValueError)):
                    raise HlkDio16ProtocolError(str(err)) from err
                raise HlkDio16ConnectionError(str(err)) from err

    async def _ensure_connected(self) -> None:
        if not self.connected:
            await self.connect()

    async def _read_frame_matching(self, accepted: set[Command]) -> bytes:
        """Read frames until one matches an accepted command (skip stale leftovers)."""
        accepted_ids = {int(cmd) for cmd in accepted}
        skips = 0
        while True:
            frame = await self._read_one_frame()
            if frame and frame[0] in accepted_ids:
                return frame
            skips += 1
            _LOGGER.debug("Skipping unexpected HLK frame while waiting: %r", frame[:1])
            if skips > 8:
                raise HlkDio16ProtocolError(
                    f"too many unexpected frames; wanted {[hex(i) for i in accepted_ids]}"
                )

    async def _read_one_frame(self) -> bytes:
        assert self._reader is not None
        while True:
            try:
                frame = extract_frame(self._buffer)
            except ValueError as err:
                raise HlkDio16ProtocolError(str(err)) from err
            if frame is not None:
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


async def probe_device(
    host: str, port: int = DEFAULT_PORT, timeout: float = 5.0
) -> dict[str, Any]:
    """Connect, read DI/DO once, disconnect — used by config flow and smoke tests."""
    client = HlkDio16Client(host, port, timeout=timeout)
    try:
        await client.connect()
        outputs = await client.read_outputs()
        inputs = await client.read_inputs()
        return {"inputs": inputs, "outputs": outputs}
    finally:
        await client.disconnect()

"""HLK-DIO16 frame encode/decode.

Protocol layout (confirmed by upstream MIT hlk-dio16):

  ┌─────────┬────────┬───────────┬──────────┐
  │ 6A A6   │ Length │ Data      │ Checksum │
  └─────────┴────────┴───────────┴──────────┘

Checksum: (sum(bytes before checksum) - 16) % 256

Logic adapted from https://github.com/jameshilliard/hlk-dio16 (MIT).
"""

from __future__ import annotations

from functools import reduce
from struct import pack

from .const import COMMAND_HEAD, COMMAND_TYPE_READ, Command


def checksum(data: bytes) -> int:
    """Return protocol checksum for the given prefix bytes."""
    return (reduce(lambda x, y: x + y, data) - 16) % 256


def decode_channel_bits(data: bytes) -> dict[int, bool]:
    """Decode two state bytes into channels 1–16."""
    if len(data) != 2:
        raise ValueError(f"expected 2 state bytes, got {len(data)}")
    states: dict[int, bool] = {}
    for bit in range(8):
        states[bit + 1] = bool(data[0] >> bit & 1)
        states[bit + 9] = bool(data[1] >> bit & 1)
    return states


def encode_read(cmd: Command) -> bytes:
    """Build a read request frame for the given command."""
    payload = pack("B", int(cmd))
    frame = COMMAND_HEAD + pack("B", len(payload) + 2) + pack("B", COMMAND_TYPE_READ) + payload
    return frame + pack("B", checksum(frame))


def encode_output_control(channel: int, state: bool) -> bytes:
    """Build an output-control frame for a single channel (1–16)."""
    if channel < 1 or channel > 16:
        raise ValueError(f"channel must be 1–16, got {channel}")
    state_byte = 0x01 if state else 0x00
    mask = bytearray(2)
    if channel <= 8:
        mask[0] |= 1 << (channel - 1)
    else:
        mask[1] |= 1 << (channel - 9)
    payload = pack("B", state_byte) + bytes(mask)
    frame = COMMAND_HEAD + pack("B", len(payload) + 2) + pack("B", int(Command.OUTPUT_CTR)) + payload
    return frame + pack("B", checksum(frame))


def extract_frame(buffer: bytearray) -> bytes | None:
    """If buffer holds a complete valid frame, return payload (cmd+data) and consume it.

    Returns None when more bytes are needed. Raises ValueError on bad checksum.
    """
    if len(buffer) < 3:
        return None
    if buffer[0:2] != COMMAND_HEAD:
        # Resync: drop until next possible header start.
        idx = buffer.find(COMMAND_HEAD, 1)
        if idx == -1:
            buffer.clear()
            return None
        del buffer[:idx]
        if len(buffer) < 3:
            return None

    length = buffer[2]
    total = 3 + length
    if len(buffer) < total:
        return None

    packet = bytes(buffer[:total])
    del buffer[:total]
    computed = checksum(packet[:-1])
    if computed != packet[-1]:
        raise ValueError(
            f"checksum mismatch: got 0x{packet[-1]:02x}, expected 0x{computed:02x}"
        )
    # Payload is between length byte and checksum: packet[3:-1]
    return packet[3:-1]

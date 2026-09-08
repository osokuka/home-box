"""Protocol unit checks for HLK-DIO16 (no hardware required)."""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve component path when run from repo or container.
ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "image" / "custom_components" / "hlk_dio16"
if not COMPONENT.is_dir():
    COMPONENT = Path("/config/custom_components/hlk_dio16")
sys.path.insert(0, str(COMPONENT))

from const import COMMAND_HEAD, Command  # noqa: E402
from protocol import (  # noqa: E402
    checksum,
    decode_channel_bits,
    encode_output_control,
    encode_read,
    extract_frame,
)


def test_checksum_and_read_frame() -> None:
    frame = encode_read(Command.OUTPUT_STATE)
    assert frame.startswith(COMMAND_HEAD)
    assert frame[-1] == checksum(frame[:-1])
    buf = bytearray(frame)
    payload = extract_frame(buf)
    assert payload is not None
    assert len(buf) == 0


def test_decode_channel_bits() -> None:
    states = decode_channel_bits(bytes([0b00010001, 0b00000101]))
    assert states[1] is True
    assert states[5] is True
    assert states[9] is True
    assert states[11] is True
    assert states[2] is False


def test_output_control_mask() -> None:
    frame = encode_output_control(4, True)
    assert frame.startswith(COMMAND_HEAD)
    assert frame[-1] == checksum(frame[:-1])
    payload = frame[3:-1]
    assert payload[0] == int(Command.OUTPUT_CTR)
    assert payload[1] == 0x01
    assert payload[2] == 0b00001000
    assert payload[3] == 0x00


def test_extract_resync() -> None:
    good = encode_read(Command.INPUT_STATE)
    buf = bytearray(b"\x00\xff" + good)
    payload = extract_frame(buf)
    assert payload is not None
    assert len(buf) == 0


def main() -> None:
    test_checksum_and_read_frame()
    test_decode_channel_bits()
    test_output_control_mask()
    test_extract_resync()
    print("hlk_dio16 protocol checks: OK")


if __name__ == "__main__":
    main()

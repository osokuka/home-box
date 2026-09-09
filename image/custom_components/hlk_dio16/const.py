"""Constants for the HLK-DIO16 integration."""

from enum import IntEnum

DOMAIN = "hlk_dio16"

DEFAULT_PORT = 8080
DEFAULT_NAME = "HLK-DIO16"

# Polling — inputs need to feel responsive when healthy.
SCAN_INTERVAL_SECONDS = 0.5
# After a failed poll, back off so we do not hammer a dead path / single TCP slot.
RECONNECT_BACKOFF_START_SECONDS = 1.0
# Keep retries snappy so brief SOCKS/LAN idle drops do not look "lost".
RECONNECT_BACKOFF_MAX_SECONDS = 5.0
# Force a full socket reset after this many consecutive failures.
FORCE_RESET_AFTER_FAILURES = 3
# Serve last-known DI/DO during short outages before entities go unavailable.
AVAILABILITY_GRACE_SECONDS = 20.0
# TCP keepalive (seconds) — detect half-open sessions after idle NAT/SOCKS drops.
TCP_KEEPIDLE_SECONDS = 30
TCP_KEEPINTVL_SECONDS = 10
TCP_KEEPCNT = 3

CHANNEL_COUNT = 16

COMMAND_HEAD = b"\x6a\xa6"
COMMAND_TYPE_READ = 0xFE


class Command(IntEnum):
    """HLK-DIO16 command IDs (binary TCP protocol)."""

    OUTPUT_CTR = 0x01
    DEVICE_TIME = 0x02
    TAP_TIME = 0x03
    DELAY_TIME = 0x04
    MODBUS_ADDRESS = 0x05
    OUTPUT_STATE = 0x06
    INPUT_STATE = 0x07
    CYCLE_TIME = 0x08
    AUTO_ENABLE = 0x0F
    TYPE_RESPONSE = 0xFF


CONF_HOST = "host"
CONF_PORT = "port"

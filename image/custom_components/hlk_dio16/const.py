"""Constants for the HLK-DIO16 integration."""

from enum import IntEnum

DOMAIN = "hlk_dio16"

DEFAULT_PORT = 8080
DEFAULT_NAME = "HLK-DIO16"

# Polling — inputs need to feel responsive; outputs change less often.
SCAN_INTERVAL_SECONDS = 0.5

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

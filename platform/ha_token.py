"""Resolve the shared Home Box long-lived access token (GET-scoped).

Same source as MCP / tuya-import / sensory-feed:
  1) env BMS_HA_TOKEN
  2) config/secrets.yaml key bms_ha_token
"""

from __future__ import annotations

import os
import re
from pathlib import Path

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
SECRETS = Path(os.environ.get("BMS_HA_SECRETS", str(CONFIG / "secrets.yaml")))


def _from_secrets(path: Path = SECRETS) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    # Minimal YAML key read — avoids requiring PyYAML in the enroll image.
    match = re.search(
        r"(?m)^\s*bms_ha_token\s*:\s*[\"']?([^\"'\n#]+?)[\"']?\s*(?:#.*)?$",
        text,
    )
    if not match:
        return ""
    return match.group(1).strip()


def resolve_ha_token() -> str:
    """Return the long-lived HA token used for read-only client services."""
    env = os.environ.get("BMS_HA_TOKEN", "").strip()
    if env:
        return env
    return _from_secrets()

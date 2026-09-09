"""Local HA storage helpers for sensory-feed (no API token)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
sys.path.insert(0, str(PLATFORM))

from ha_local import (  # noqa: E402
    entity_display_names,
    load_local_states,
    merge_ha_states,
)


def test_registry_names_and_merge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp)
        storage = cfg / ".storage"
        storage.mkdir()
        (storage / "core.entity_registry").write_text(
            json.dumps(
                {
                    "data": {
                        "entities": [
                            {
                                "entity_id": "binary_sensor.hlk_di01",
                                "name": "Senzori Dritares",
                                "original_name": "DI01",
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        (storage / "core.restore_state").write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "state": {
                                "entity_id": "binary_sensor.hlk_di01",
                                "state": "off",
                                "attributes": {"friendly_name": "old"},
                            }
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        names = entity_display_names(cfg)
        assert names["binary_sensor.hlk_di01"] == "Senzori Dritares"
        local = load_local_states(cfg)
        assert local[0]["attributes"]["friendly_name"] == "Senzori Dritares"
        assert local[0]["state"] == "off"
        merged = merge_ha_states(
            local,
            [
                {
                    "entity_id": "binary_sensor.hlk_di01",
                    "state": "on",
                    "attributes": {},
                }
            ],
        )
        assert merged[0]["state"] == "on"
        assert merged[0]["attributes"]["friendly_name"] == "Senzori Dritares"


def main() -> None:
    test_registry_names_and_merge()
    print("ha_local checks: OK")


if __name__ == "__main__":
    main()

"""Read Home Assistant names/states from shared /config storage.

Sensory-feed does not need BMS_HA_TOKEN: enroll token is for BMS only.
Friendly names come from core.entity_registry; last-known states from
core.restore_state when present. Optional HA API token still enriches live
states when configured for other services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def entity_display_names(config: Path) -> dict[str, str]:
    """entity_id -> preferred display name from the entity registry."""
    blob = _read_json(config / ".storage" / "core.entity_registry")
    if not isinstance(blob, dict):
        return {}
    data = blob.get("data") if isinstance(blob.get("data"), dict) else {}
    entities = data.get("entities") if isinstance(data.get("entities"), list) else []
    out: dict[str, str] = {}
    for row in entities:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("entity_id") or "").strip().lower()
        if not eid:
            continue
        name = str(row.get("name") or "").strip() or str(row.get("original_name") or "").strip()
        if name:
            out[eid] = name
    return out


def restore_states(config: Path) -> dict[str, dict[str, Any]]:
    """entity_id -> last restored state object."""
    blob = _read_json(config / ".storage" / "core.restore_state")
    if not isinstance(blob, dict):
        return {}
    rows = blob.get("data") if isinstance(blob.get("data"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        if not isinstance(state, dict):
            continue
        eid = str(state.get("entity_id") or "").strip().lower()
        if eid:
            out[eid] = state
    return out


def load_local_states(config: Path) -> list[dict[str, Any]]:
    """Build a state-like list from on-disk HA storage (no API token)."""
    names = entity_display_names(config)
    restored = restore_states(config)
    by_id: dict[str, dict[str, Any]] = {}

    for eid, state in restored.items():
        attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
        attrs = dict(attrs)
        if eid in names:
            attrs["friendly_name"] = names[eid]
        elif not attrs.get("friendly_name"):
            attrs["friendly_name"] = eid
        row = dict(state)
        row["entity_id"] = eid
        row["attributes"] = attrs
        by_id[eid] = row

    for eid, name in names.items():
        if eid in by_id:
            continue
        by_id[eid] = {
            "entity_id": eid,
            "state": "unknown",
            "attributes": {"friendly_name": name},
        }

    return list(by_id.values())


def merge_ha_states(
    local: list[dict[str, Any]] | None,
    live: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Prefer live API states; keep registry friendly names when live omits them."""
    names: dict[str, str] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for st in local or []:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "").strip().lower()
        if not eid:
            continue
        by_id[eid] = st
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        fn = str(attrs.get("friendly_name") or "").strip()
        if fn:
            names[eid] = fn
    for st in live or []:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "").strip().lower()
        if not eid:
            continue
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        attrs = dict(attrs)
        if not attrs.get("friendly_name") and eid in names:
            attrs["friendly_name"] = names[eid]
        row = dict(st)
        row["entity_id"] = eid
        row["attributes"] = attrs
        by_id[eid] = row
    return list(by_id.values())

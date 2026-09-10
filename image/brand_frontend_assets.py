#!/usr/bin/env python3
"""Brand Home Box into frontend + Assist strings (no Core fork).

Patches:
  - hass_frontend HTML/JS product chrome
  - hass_frontend logbook translation strings
  - Core homeassistant logbook + start/stop trigger descriptions
  - home_assistant_intents greetings (Hello from Home Box.)
  - conversation DefaultAgent display name when present on disk
  - /config assist pipeline display name (if storage exists)

Safe replacements restore Home Assistant Cloud/Core/Cast/etc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BRAND = "Home Box"

FRONTEND_ROOTS = list(Path("/usr/local/lib").glob("python*/site-packages/hass_frontend"))
INTENTS_ROOTS = list(Path("/usr/local/lib").glob("python*/site-packages/home_assistant_intents"))
CORE_ROOTS = [
    Path("/usr/src/homeassistant/homeassistant"),
    *Path("/usr/local/lib").glob("python*/site-packages/homeassistant"),
]

REPLACEMENTS: list[tuple[str, str]] = [
    (">Home Assistant</title>", f">{BRAND}</title>"),
    ('content="Home Assistant"', f'content="{BRAND}"'),
    ('alt="Home Assistant"', f'alt="{BRAND}"'),
    ("alt='Home Assistant'", f"alt='{BRAND}'"),
    (" – Home Assistant", f" – {BRAND}"),
    (" –Home Assistant", f" –{BRAND}"),
    (" - Home Assistant", f" - {BRAND}"),
    ('"Home Assistant"', f'"{BRAND}"'),
    ("'Home Assistant'", f"'{BRAND}'"),
    ("`Home Assistant`", f"`{BRAND}`"),
    ("Hello from Home Assistant.", f"Hello from {BRAND}."),
    ("Hello from Home Assistant", f"Hello from {BRAND}"),
    ("triggered by Home Assistant starting", f"triggered by {BRAND} starting"),
    ("triggered by Home Assistant stopping", f"triggered by {BRAND} stopping"),
    ("Home Assistant starting", f"{BRAND} starting"),
    ("Home Assistant stopping", f"{BRAND} stopping"),
    ("Home Assistant started", f"{BRAND} started"),
    ("Home Assistant stopped", f"{BRAND} stopped"),
    (
        "Apps require the Home Assistant Operating System",
        f"Apps are not part of {BRAND}",
    ),
    (
        "Why you see this page instead of an app store",
        f"Home Box does not include an app store",
    ),
    (
        "What is an app?",
        "What are extras on Home Box?",
    ),
]

RESTORE: list[tuple[str, str]] = [
    (f"{BRAND} Cloud", "Home Assistant Cloud"),
    (f"{BRAND} Core", "Home Assistant Core"),
    (f"{BRAND} Cast", "Home Assistant Cast"),
    (f"{BRAND} Supervisor", "Home Assistant Supervisor"),
    (f"{BRAND} Operating System", "Home Assistant Operating System"),
    (f"{BRAND} Yellow", "Home Assistant Yellow"),
    (f"{BRAND} Green", "Home Assistant Green"),
    (f"{BRAND} Blue", "Home Assistant Blue"),
    (f"{BRAND} SkyConnect", "Home Assistant SkyConnect"),
    (f"{BRAND} Connect", "Home Assistant Connect"),
    (f"{BRAND} Analytics", "Home Assistant Analytics"),
    (f"{BRAND} Community", "Home Assistant Community"),
    (f"my.{BRAND}", "my.home-assistant"),
]


def patch_text(text: str) -> str:
    out = text
    for old, new in REPLACEMENTS:
        out = out.replace(old, new)
    for old, new in RESTORE:
        out = out.replace(old, new)
    return out


def patch_file(path: Path) -> bool:
    if path.suffix in {".br", ".gz", ".map"}:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    new = patch_text(text)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    for ext in (".br", ".gz"):
        sibling = Path(str(path) + ext)
        if sibling.is_file():
            sibling.unlink(missing_ok=True)
    return True


def patch_intents() -> int:
    changed = 0
    for root in INTENTS_ROOTS:
        data = root / "data"
        if not data.is_dir():
            continue
        for path in data.glob("*.json"):
            try:
                blob = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            raw = json.dumps(blob, ensure_ascii=False)
            new = patch_text(raw)
            if new == raw:
                continue
            # Keep JSON valid
            path.write_text(
                json.dumps(json.loads(new), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed += 1
            print(f"home-box-brand-assets: intents {path.name}", flush=True)
    return changed


def patch_default_agent_name() -> int:
    changed = 0
    for path in Path("/usr/src/homeassistant").glob(
        "**/components/conversation/default_agent.py"
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new = text.replace('_attr_name = "Home Assistant"', f'_attr_name = "{BRAND}"')
        new = new.replace("_attr_name = 'Home Assistant'", f"_attr_name = '{BRAND}'")
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"home-box-brand-assets: agent name {path}", flush=True)
    return changed


def _core_component_paths(*parts: str) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for root in CORE_ROOTS:
        path = root.joinpath(*parts)
        if path.is_file() and path not in seen:
            seen.add(path)
            found.append(path)
    return found


def patch_logbook_core() -> int:
    """Brand Home Assistant start/stop rows in Activity (logbook)."""
    changed = 0
    logbook_repls = [
        ('LOGBOOK_ENTRY_NAME: "Home Assistant"', f'LOGBOOK_ENTRY_NAME: "{BRAND}"'),
        ("LOGBOOK_ENTRY_NAME: 'Home Assistant'", f"LOGBOOK_ENTRY_NAME: '{BRAND}'"),
        ('LOGBOOK_ENTRY_ICON: "mdi:home-assistant"', 'LOGBOOK_ENTRY_ICON: "mdi:cube-outline"'),
        ("LOGBOOK_ENTRY_ICON: 'mdi:home-assistant'", "LOGBOOK_ENTRY_ICON: 'mdi:cube-outline'"),
    ]
    for path in _core_component_paths("components", "homeassistant", "logbook.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new = text
        for old, repl in logbook_repls:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"home-box-brand-assets: logbook core {path}", flush=True)

    trigger_repls = [
        ('"description": "Home Assistant starting"', f'"description": "{BRAND} starting"'),
        ('"description": "Home Assistant stopping"', f'"description": "{BRAND} stopping"'),
        ("'description': 'Home Assistant starting'", f"'description': '{BRAND} starting'"),
        ("'description': 'Home Assistant stopping'", f"'description': '{BRAND} stopping'"),
    ]
    for path in _core_component_paths(
        "components", "homeassistant", "triggers", "homeassistant.py"
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new = text
        for old, repl in trigger_repls:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(f"home-box-brand-assets: start trigger {path}", flush=True)
    return changed


def patch_frontend_translations(root: Path) -> int:
    """Rewrite logbook HA start/stop copy in shipped locale packs."""
    trans = root / "static" / "translations"
    if not trans.is_dir():
        return 0
    needles = (
        "Home Assistant starting",
        "Home Assistant stopping",
        "Home Assistant started",
        "Home Assistant stopped",
    )
    changed = 0
    for path in trans.glob("*.json"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if not any(n in text for n in needles):
            continue
        new = patch_text(text)
        if new == text:
            continue
        try:
            json.loads(new)
        except Exception as err:
            print(f"home-box-brand-assets: skip invalid {path}: {err}", flush=True)
            continue
        path.write_text(new, encoding="utf-8")
        for ext in (".br", ".gz"):
            sibling = Path(str(path) + ext)
            if sibling.is_file():
                sibling.unlink(missing_ok=True)
        changed += 1
        print(f"home-box-brand-assets: translation {path.name}", flush=True)
    return changed


def patch_pipeline_storage() -> int:
    path = Path("/config/.storage/assist_pipeline.pipelines")
    if not path.is_file():
        return 0
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    data = blob.get("data") if isinstance(blob, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return 0
    changed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("name") == "Home Assistant":
            item["name"] = BRAND
            changed += 1
    if changed:
        path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
        print("home-box-brand-assets: assist pipeline renamed", flush=True)
    return changed


def patch_frontend(root: Path) -> int:
    targets: list[Path] = []
    for name in ("index.html", "authorize.html", "onboarding.html"):
        p = root / name
        if p.is_file():
            targets.append(p)
    for sub in ("frontend_latest", "frontend_es5"):
        d = root / sub
        if not d.is_dir():
            continue
        targets.extend(d.glob("app.*.js"))
        targets.extend(d.glob("onboarding.*.js"))
        targets.extend(d.glob("73524.*.js"))
        for p in d.glob("*.js"):
            try:
                sample = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if (
                "– Home Assistant" in sample
                or 'sidebarTitle:"Home Assistant"' in sample
                or "Hello from Home Assistant" in sample
                or "Home Assistant starting" in sample
                or "Home Assistant stopping" in sample
            ):
                if p not in targets:
                    targets.append(p)

    changed = 0
    for path in targets:
        try:
            if patch_file(path):
                changed += 1
                print(f"home-box-brand-assets: patched {path}", flush=True)
        except Exception as err:
            print(f"home-box-brand-assets: skip {path}: {err}", flush=True)
    changed += patch_frontend_translations(root)
    return changed


def main() -> int:
    changed = 0
    roots = FRONTEND_ROOTS or (
        [Path("/usr/local/lib/python3.14/site-packages/hass_frontend")]
        if Path("/usr/local/lib/python3.14/site-packages/hass_frontend").is_dir()
        else []
    )
    if not roots:
        print("home-box-brand-assets: hass_frontend not found", flush=True)
    for root in roots:
        changed += patch_frontend(root)

    changed += patch_intents()
    changed += patch_default_agent_name()
    changed += patch_logbook_core()
    changed += patch_pipeline_storage()

    print(f"home-box-brand-assets: done changed={changed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

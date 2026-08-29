#!/usr/bin/env python3
"""Patch hass_frontend static assets so product chrome says Home Box.

Safe replacements only — leaves Home Assistant Cloud/Core/Cast/etc.
Run at container start (image entrypoint hook) or image build.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path("/usr/local/lib/python3.14/site-packages/hass_frontend")
BRAND = "Home Box"

# Exact product-chrome replacements (order matters)
REPLACEMENTS: list[tuple[str, str]] = [
    (">Home Assistant</title>", f">{BRAND}</title>"),
    ('content="Home Assistant"', f'content="{BRAND}"'),
    ('alt="Home Assistant"', f'alt="{BRAND}"'),
    ("alt='Home Assistant'", f"alt='{BRAND}'"),
    (" – Home Assistant", f" – {BRAND}"),  # en-dash (panel-title-mixin)
    (" –Home Assistant", f" –{BRAND}"),
    (" - Home Assistant", f" - {BRAND}"),
    # sidebar default title as JS string literals
    ('"Home Assistant"', f'"{BRAND}"'),
    ("'Home Assistant'", f"'{BRAND}'"),
    ("`Home Assistant`", f"`{BRAND}`"),
]

# Restore known compound product names we must NOT brand
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
    (f"www.{BRAND}", "www.home-assistant"),  # unlikely
]


def patch_text(text: str) -> str:
    out = text
    for old, new in REPLACEMENTS:
        out = out.replace(old, new)
    for old, new in RESTORE:
        out = out.replace(old, new)
    return out


def patch_file(path: Path) -> bool:
    raw = path.read_bytes()
    # skip compressed companions
    if path.suffix in {".br", ".gz", ".map"}:
        return False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    new = patch_text(text)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    # invalidate precompressed if present so HA serves patched plain file
    for ext in (".br", ".gz"):
        sibling = Path(str(path) + ext)
        if sibling.is_file():
            sibling.unlink(missing_ok=True)
    return True


def main() -> int:
    if not ROOT.is_dir():
        # try glob for other python versions
        candidates = list(Path("/usr/local/lib").glob("python*/site-packages/hass_frontend"))
        if not candidates:
            print("home-box-brand-assets: hass_frontend not found", flush=True)
            return 0
        root = candidates[0]
    else:
        root = ROOT

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
        # chunk that contained sidebarTitle in this build
        targets.extend(d.glob("73524.*.js"))
        targets.extend(d.glob("*sidebar*.js"))

    # Also scan chunks that contain the title mixin en-dash phrase
    for sub in ("frontend_latest", "frontend_es5"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.js"):
            if p.suffix != ".js":
                continue
            try:
                sample = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "– Home Assistant" in sample or 'sidebarTitle:"Home Assistant"' in sample or "sidebarTitle:'Home Assistant'" in sample:
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

    print(f"home-box-brand-assets: done changed={changed}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Smoke-test HLK-DIO16: connect → read DI/DO → toggle one relay → verify.

From the Home Box repo root:

  docker compose exec homeassistant \\
    python /config/custom_components/hlk_dio16/smoke.py --host 192.168.x.x
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import types
from pathlib import Path


def _load_client():
    """Load the client whether run as a script or package module."""
    try:
        from custom_components.hlk_dio16.client import HlkDio16Client

        return HlkDio16Client
    except ImportError:
        pass

    base = Path(__file__).resolve().parent
    pkg = types.ModuleType("hlk_dio16")
    pkg.__path__ = [str(base)]
    sys.modules["hlk_dio16"] = pkg

    import importlib.util

    for name in ("const", "exceptions", "protocol", "client"):
        spec = importlib.util.spec_from_file_location(
            f"hlk_dio16.{name}", base / f"{name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"hlk_dio16.{name}"] = mod
        setattr(pkg, name, mod)
        assert spec.loader is not None
        spec.loader.exec_module(mod)

    from hlk_dio16.client import HlkDio16Client

    return HlkDio16Client


async def _run(host: str, port: int, channel: int) -> int:
    client_cls = _load_client()
    client = client_cls(host, port, timeout=5.0)
    print(f"Connecting to {host}:{port} ...")
    await client.connect()
    try:
        outputs = await client.read_outputs()
        inputs = await client.read_inputs()
        print(f"Inputs:  {inputs}")
        print(f"Outputs: {outputs}")

        before = bool(outputs.get(channel))
        target = not before
        print(f"Toggling DO{channel:02d}: {before} → {target}")
        after_states = await client.set_output(channel, target)
        after = bool(after_states.get(channel))
        print(f"DO{channel:02d} now: {after}")
        if after != target:
            print("FAIL: output did not match requested state", file=sys.stderr)
            return 1
        await client.set_output(channel, before)
        print("Restored previous state. OK")
        return 0
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="HLK-DIO16 smoke test")
    parser.add_argument("--host", required=True, help="Controller IP address")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--channel", type=int, default=1, help="DO channel 1-16")
    args = parser.parse_args()
    if args.channel < 1 or args.channel > 16:
        parser.error("channel must be 1-16")
    raise SystemExit(asyncio.run(_run(args.host, args.port, args.channel)))


if __name__ == "__main__":
    main()

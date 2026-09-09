"""Reconnect policy unit checks for HLK-DIO16 (no hardware required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "image" / "custom_components" / "hlk_dio16"
if not COMPONENT.is_dir():
    COMPONENT = Path("/config/custom_components/hlk_dio16")
sys.path.insert(0, str(COMPONENT))

from reconnect import ReconnectPolicy  # noqa: E402


def test_success_resets_failures() -> None:
    policy = ReconnectPolicy(
        scan_interval=0.5,
        backoff_start=1.0,
        backoff_max=30.0,
        force_after=3,
    )
    policy.on_failure()
    policy.on_failure()
    assert policy.on_success() == 0.5
    assert policy.failures == 0


def test_backoff_doubles_until_max() -> None:
    policy = ReconnectPolicy(
        scan_interval=0.5,
        backoff_start=1.0,
        backoff_max=8.0,
        force_after=99,
    )
    d1, f1 = policy.on_failure()
    d2, f2 = policy.on_failure()
    d3, f3 = policy.on_failure()
    d4, f4 = policy.on_failure()
    assert (d1, f1) == (1.0, False)
    assert (d2, f2) == (2.0, False)
    assert (d3, f3) == (4.0, False)
    assert (d4, f4) == (8.0, False)
    d5, _ = policy.on_failure()
    assert d5 == 8.0


def test_force_reset_every_n_failures() -> None:
    policy = ReconnectPolicy(
        scan_interval=0.5,
        backoff_start=1.0,
        backoff_max=30.0,
        force_after=3,
    )
    assert policy.on_failure()[1] is False
    assert policy.on_failure()[1] is False
    assert policy.on_failure()[1] is True  # 3rd
    assert policy.on_failure()[1] is False
    assert policy.on_failure()[1] is False
    assert policy.on_failure()[1] is True  # 6th


def main() -> None:
    test_success_resets_failures()
    test_backoff_doubles_until_max()
    test_force_reset_every_n_failures()
    print("hlk_dio16 reconnect checks: OK")


if __name__ == "__main__":
    main()

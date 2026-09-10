"""ha_token resolution checks (no real secrets required)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform"))

from ha_token import _from_secrets  # noqa: E402


def test_reads_bms_ha_token() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "secrets.yaml"
        path.write_text(
            "ha_external_url: http://x\nbms_ha_token: abc.def.ghi\n",
            encoding="utf-8",
        )
        assert _from_secrets(path) == "abc.def.ghi"


def main() -> None:
    test_reads_bms_ha_token()
    print("ha_token checks: OK")


if __name__ == "__main__":
    main()

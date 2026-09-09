"""Home Box Tuya device import UI — CSV / Excel (.xlsx), or checklist for manual add.

Never talks to Tuya cloud. Optional apply uses Home Box WebSocket + long-lived token.
Listen: BMS_TUYA_IMPORT_PORT (default 8098).
"""

from __future__ import annotations

import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tuya_csv import (
    devices_to_csv,
    parse_csv_text,
    parse_xlsx_base64,
    public_device,
)

PORT = int(os.environ.get("BMS_TUYA_IMPORT_PORT", "8098"))
APP_BASE = os.environ.get("PUBLIC_BASE_PATH", "").rstrip("/")
CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
QUEUE_PATH = Path(os.environ.get("BMS_TUYA_IMPORT_QUEUE", str(CONFIG / "tuya_import_queue.json")))
HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("BMS_HA_TOKEN", "").strip()
HA_WS = os.environ.get(
    "BMS_HA_WS",
    HA_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket",
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Home Box — device import</title>
  <style>
    :root { --ink:#1a1f1c; --muted:#5c6b63; --line:#c5d0c8; --acc:#2f6f4e; --warn:#8a6d1d; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:linear-gradient(160deg,#dfe8e2,#eef3ef 45%,#f7f5ef); color:var(--ink); }
    main { max-width:52rem; margin:0 auto; padding:2rem 1.25rem 3rem; }
    h1 { font-size:1.5rem; margin:0 0 .35rem; }
    h2 { font-size:1.05rem; margin:0 0 .65rem; }
    .sub { color:var(--muted); line-height:1.45; margin:0 0 1.25rem; }
    section { background:#fff; border:1px solid var(--line); padding:1.1rem 1.15rem; margin-bottom:1rem; }
    textarea { width:100%; min-height:9rem; font:0.85rem ui-monospace,Consolas,monospace; padding:.55rem; border:1px solid var(--line); }
    button { margin:.35rem .45rem 0 0; padding:.5rem .95rem; border:0; background:var(--acc); color:#fff; font:inherit; cursor:pointer; }
    button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .hint { color:var(--muted); font-size:.85rem; line-height:1.4; }
    .msg { margin-top:.65rem; font-size:.9rem; }
    .err { color:#8b2e2e; }
    table { width:100%; border-collapse:collapse; font-size:.9rem; }
    th, td { text-align:left; padding:.4rem .35rem; border-bottom:1px solid var(--line); vertical-align:top; }
    code { background:#e8eee9; padding:.05em .3em; }
  </style>
</head>
<body>
  <main>
    <h1>Home Box — Tuya Local import</h1>
    <p class="sub">Bulk-import from <strong>CSV</strong> or <strong>Excel (.xlsx)</strong> after sandbox harvest, or add devices one-by-one with <strong>Tuya Local → manual</strong>. This page never uses Tuya cloud.</p>

    <section>
      <h2>CSV / Excel</h2>
      <p class="hint">Columns: <code>name,device_id,local_key,host,protocol_version,type,poll_only</code> — first sheet if Excel.</p>
      <input type="file" id="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
      <label class="hint" for="raw" style="display:block;margin-top:.75rem;">Or paste CSV</label>
      <textarea id="raw" placeholder="name,device_id,local_key,host,..."></textarea>
      <div>
        <button type="button" id="parse">Parse</button>
        <button type="button" class="ghost" id="save">Save inventory on box</button>
        <button type="button" class="ghost" id="apply">Apply on Home Box</button>
        <button type="button" class="ghost" id="clear">Clear inventory</button>
      </div>
      <div class="msg" id="msg"></div>
    </section>

    <section>
      <h2>Inventory</h2>
      <p class="hint" id="tokenHint"></p>
      <div id="tableWrap"><p class="hint">No devices loaded.</p></div>
    </section>

    <section>
      <h2>Manual one-by-one</h2>
      <ol class="hint">
        <li>Home Box → Settings → Devices &amp; services → Add integration → <strong>Tuya Local</strong>.</li>
        <li>Choose <strong>manual</strong> (not cloud).</li>
        <li>Enter device id, IP, local key from your CSV / Excel / sandbox export.</li>
      </ol>
    </section>
  </main>
  <script>
    const APP_BASE = "__APP_BASE__";
    const u = (p) => APP_BASE + p;
    let devices = [];
    const msg = document.getElementById("msg");
    const tableWrap = document.getElementById("tableWrap");
    const rawEl = document.getElementById("raw");

    function setMsg(text, isErr) {
      msg.textContent = text || "";
      msg.className = isErr ? "msg err" : "msg";
    }

    function arrayBufferToBase64(buf) {
      const bytes = new Uint8Array(buf);
      const chunk = 0x8000;
      let binary = "";
      for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
      }
      return btoa(binary);
    }

    function render(list) {
      devices = list || [];
      if (!devices.length) {
        tableWrap.innerHTML = "<p class='hint'>No devices loaded.</p>";
        return;
      }
      let html = "<table><thead><tr><th>Name</th><th>Device id</th><th>Host</th><th>Proto</th><th>Type</th><th>Key</th></tr></thead><tbody>";
      for (const d of devices) {
        html += "<tr><td>" + d.name + "</td><td><code>" + d.device_id + "</code></td><td><code>" + d.host +
          "</code></td><td>" + d.protocol_version + "</td><td>" + (d.type || "—") +
          "</td><td>" + d.local_key_masked + "</td></tr>";
      }
      html += "</tbody></table>";
      tableWrap.innerHTML = html;
    }

    async function refresh() {
      const r = await fetch(u("/api/queue"));
      const j = await r.json();
      render(j.devices || []);
      document.getElementById("tokenHint").textContent = j.ha_token_configured
        ? "Access token is set — Apply can create Tuya Local entries when devices are on the LAN and type is set."
        : "No access token (BMS_HA_TOKEN) — use Save inventory + manual Tuya Local add, or set a long-lived token to Apply.";
    }

    document.getElementById("file").onchange = async (ev) => {
      const f = ev.target.files && ev.target.files[0];
      if (!f) return;
      setMsg("");
      const name = (f.name || "").toLowerCase();
      if (name.endsWith(".xlsx")) {
        const b64 = arrayBufferToBase64(await f.arrayBuffer());
        const r = await fetch(u("/api/parse"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ xlsx_base64: b64, filename: f.name }),
        });
        const j = await r.json();
        if (!r.ok) { setMsg((j.errors || [j.error || "Parse failed"]).join("; "), true); return; }
        if (j.csv) rawEl.value = j.csv;
        render(j.devices);
        setMsg("Parsed Excel → " + j.devices.length + " device(s). Save inventory or Apply.");
        return;
      }
      rawEl.value = await f.text();
      setMsg("Loaded " + f.name + " — click Parse.");
    };

    document.getElementById("parse").onclick = async () => {
      setMsg("");
      const r = await fetch(u("/api/parse"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv: rawEl.value }),
      });
      const j = await r.json();
      if (!r.ok) { setMsg((j.errors || [j.error || "Parse failed"]).join("; "), true); return; }
      render(j.devices);
      setMsg("Parsed " + j.devices.length + " device(s). Save inventory or Apply.");
    };

    document.getElementById("save").onclick = async () => {
      setMsg("");
      const r = await fetch(u("/api/queue"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv: rawEl.value }),
      });
      const j = await r.json();
      if (!r.ok) { setMsg((j.errors || [j.error || "Save failed"]).join("; "), true); return; }
      render(j.devices);
      setMsg("Inventory saved on the box.");
    };

    document.getElementById("apply").onclick = async () => {
      setMsg("Applying…");
      const r = await fetch(u("/api/apply"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv: rawEl.value || null }),
      });
      const j = await r.json();
      if (!r.ok) { setMsg(j.error || "Apply failed", true); return; }
      const lines = (j.results || []).map((x) => x.device_id + ": " + x.status + (x.detail ? " (" + x.detail + ")" : ""));
      setMsg(lines.join(" | ") || "Done");
      await refresh();
    };

    document.getElementById("clear").onclick = async () => {
      await fetch(u("/api/queue"), { method: "DELETE" });
      rawEl.value = "";
      render([]);
      setMsg("Cleared.");
    };

    refresh();
  </script>
</body>
</html>
""".replace("__APP_BASE__", APP_BASE)


def _parse_body(body: dict) -> tuple[list[dict], list[str], str]:
    """Return (devices, errors, csv_text)."""
    if body.get("xlsx_base64"):
        devices, errors = parse_xlsx_base64(str(body.get("xlsx_base64") or ""))
        csv_text = devices_to_csv(devices) if devices else ""
        return devices, errors, csv_text
    csv_text = str(body.get("csv") or "")
    devices, errors = parse_csv_text(csv_text)
    return devices, errors, csv_text


def load_queue() -> list[dict]:
    if not QUEUE_PATH.is_file():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("devices") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def save_queue(devices: list[dict]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"v": 1, "devices": devices}
    tmp = QUEUE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(QUEUE_PATH)


def clear_queue() -> None:
    if QUEUE_PATH.is_file():
        QUEUE_PATH.unlink()


def _ws_apply_device(device: dict) -> dict:
    """Best-effort create tuya_local entry via Home Box websocket."""
    try:
        import websocket  # type: ignore
    except ImportError:
        return {
            "device_id": device.get("device_id"),
            "status": "skipped",
            "detail": "websocket-client not installed; rebuild home-box-tuya-import image",
        }

    if not HA_TOKEN:
        return {
            "device_id": device.get("device_id"),
            "status": "skipped",
            "detail": "BMS_HA_TOKEN not set",
        }

    results = {"device_id": device.get("device_id"), "status": "error", "detail": ""}
    msg_id = 0

    def next_id() -> int:
        nonlocal msg_id
        msg_id += 1
        return msg_id

    try:
        ws = websocket.create_connection(
            HA_WS, timeout=45, sslopt={"cert_reqs": ssl.CERT_NONE}
        )
        hello = json.loads(ws.recv())
        if hello.get("type") != "auth_required":
            results["detail"] = "unexpected hello"
            ws.close()
            return results
        ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
        auth = json.loads(ws.recv())
        if auth.get("type") != "auth_ok":
            results["detail"] = "auth failed — check BMS_HA_TOKEN"
            ws.close()
            return results

        def call(payload: dict) -> dict:
            pid = next_id()
            ws.send(json.dumps({"id": pid, **payload}))
            while True:
                raw = json.loads(ws.recv())
                if raw.get("type") == "event":
                    continue
                if raw.get("id") == pid:
                    return raw

        entries = call({"type": "config_entries/get"})
        if entries.get("success"):
            for ent in entries.get("result") or []:
                if ent.get("domain") != "tuya_local":
                    continue
                data = ent.get("data") or {}
                if str(data.get("device_id") or "") == str(device.get("device_id")):
                    results["status"] = "exists"
                    results["detail"] = "already configured"
                    ws.close()
                    return results

        created = call({"type": "config_entries/flow/create", "handler": "tuya_local"})
        if not created.get("success"):
            created = call(
                {
                    "type": "config_entries/flow",
                    "handler": "tuya_local",
                    "show_advanced_options": False,
                }
            )
        if not created.get("success"):
            results["detail"] = str(created.get("error") or created)[:200]
            ws.close()
            return results
        flow = created.get("result") or {}
        flow_id = flow.get("flow_id")

        def progress(data: dict) -> dict:
            return call(
                {
                    "type": "config_entries/flow",
                    "flow_id": flow_id,
                    "handler": "tuya_local",
                    "data": data,
                }
            )

        step = progress({"setup_mode": "manual"})
        if not step.get("success"):
            results["detail"] = "manual mode step failed"
            ws.close()
            return results
        flow = step.get("result") or {}
        flow_id = flow.get("flow_id") or flow_id
        if flow.get("type") == "abort":
            reason = flow.get("reason") or "aborted"
            results["status"] = "exists" if "already" in reason else "error"
            results["detail"] = reason
            ws.close()
            return results

        proto = device.get("protocol_version") or "auto"
        local_data = {
            "device_id": device["device_id"],
            "host": device["host"],
            "local_key": device["local_key"],
            "protocol_version": str(proto),
            "poll_only": bool(device.get("poll_only")),
        }
        step = progress(local_data)
        if not step.get("success"):
            results["detail"] = "local step failed (device offline, wrong key, or LAN blocked)"
            ws.close()
            return results
        flow = step.get("result") or {}
        flow_id = flow.get("flow_id") or flow_id
        if flow.get("type") == "abort":
            reason = flow.get("reason") or "aborted"
            results["status"] = "exists" if "already" in reason else "error"
            results["detail"] = reason
            ws.close()
            return results
        step_id = flow.get("step_id")

        if step_id in ("select_type", "select_type_auto_detected"):
            dtype = (device.get("type") or "").strip()
            if not dtype:
                results["status"] = "needs_manual"
                results["detail"] = "connected; pick type in Home Box UI (CSV type empty)"
                ws.close()
                return results
            type_value = dtype if "||" in dtype else f"{dtype}|||"
            step = progress({"type": type_value})
            if not step.get("success"):
                step = progress({"type": dtype})
            if not step.get("success"):
                results["detail"] = "select_type failed — check type matches a Tuya Local profile"
                ws.close()
                return results
            flow = step.get("result") or {}
            flow_id = flow.get("flow_id") or flow_id
            step_id = flow.get("step_id")

        if step_id == "choose_entities":
            step = progress({"name": device.get("name") or device["device_id"]})
            flow = (step.get("result") or {}) if step.get("success") else {}
            if flow.get("type") == "create_entry" or (
                step.get("success") and not flow.get("step_id")
            ):
                results["status"] = "created"
                results["detail"] = "ok"
            else:
                results["detail"] = "choose_entities failed"
        elif flow.get("type") == "create_entry":
            results["status"] = "created"
            results["detail"] = "ok"
        else:
            results["status"] = "needs_manual"
            results["detail"] = f"stopped at step={step_id or flow.get('type')}"

        ws.close()
    except Exception as err:
        results["detail"] = str(err)[:200]
    return results


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"tuya-import {self.address_string()} {fmt % args}", flush=True)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        if path == "/api/queue":
            devices = load_queue()
            self._json(
                200,
                {
                    "devices": [public_device(d) for d in devices],
                    "count": len(devices),
                    "ha_token_configured": bool(HA_TOKEN),
                    "path": str(QUEUE_PATH),
                },
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
        except Exception as err:
            self._json(400, {"error": f"invalid json: {err}"})
            return

        if path == "/api/parse":
            devices, errors, csv_text = _parse_body(body)
            if errors and not devices:
                self._json(400, {"errors": errors})
                return
            self._json(
                200,
                {
                    "devices": [public_device(d) for d in devices],
                    "errors": errors,
                    "count": len(devices),
                    "csv": csv_text,
                },
            )
            return

        if path == "/api/queue":
            devices, errors, _csv_text = _parse_body(body)
            if errors and not devices:
                self._json(400, {"errors": errors})
                return
            save_queue(devices)
            print(f"tuya-import saved queue count={len(devices)}", flush=True)
            self._json(
                200,
                {"ok": True, "devices": [public_device(d) for d in devices], "errors": errors},
            )
            return

        if path == "/api/apply":
            if body.get("csv") or body.get("xlsx_base64"):
                devices, errors, _csv_text = _parse_body(body)
                if errors and not devices:
                    self._json(400, {"errors": errors})
                    return
                save_queue(devices)
            else:
                devices = load_queue()
            if not devices:
                self._json(400, {"error": "no devices in queue — parse/save CSV or Excel first"})
                return
            if not HA_TOKEN:
                self._json(
                    400,
                    {
                        "error": "BMS_HA_TOKEN not set — save inventory and add manually in Tuya Local",
                    },
                )
                return
            results = [_ws_apply_device(d) for d in devices]
            self._json(200, {"ok": True, "results": results})
            return

        self._json(404, {"error": "not_found"})

    def do_DELETE(self) -> None:
        if self.path.split("?", 1)[0] != "/api/queue":
            self._json(404, {"error": "not_found"})
            return
        clear_queue()
        self._json(200, {"ok": True})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        f"tuya-import http://0.0.0.0:{PORT}/ csv+xlsx+manual (queue={QUEUE_PATH})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()

"""Lab first-run enroll UI for BMS House Box.

Paste the operator QR JSON (or fields). Writes /config/bms_enroll.json.
platform-agent picks it up on the next loop — no rebuild required.

Listen: BMS_ENROLL_UI_PORT (default 8099).
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from enroll_store import clear_enroll, public_status, save_enroll

PORT = int(os.environ.get("BMS_ENROLL_UI_PORT", "8099"))
DEFAULT_PLATFORM = os.environ.get("BMS_PLATFORM_URL", "http://host.docker.internal:8080").rstrip("/")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BMS House Box — enroll</title>
  <style>
    :root { color-scheme: light; --ink:#1a1f1c; --muted:#5c6b63; --line:#c5d0c8; --bg:#eef3ef; --card:#fff; --acc:#2f6f4e; --warn:#8a6d1d; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: linear-gradient(160deg,#dfe8e2,#eef3ef 40%,#f7f5ef); color: var(--ink); min-height: 100vh; }
    main { max-width: 40rem; margin: 0 auto; padding: 2rem 1.25rem 3rem; }
    h1 { font-size: 1.55rem; margin: 0 0 .35rem; letter-spacing: -0.02em; }
    .sub { color: var(--muted); margin: 0 0 1.5rem; line-height: 1.45; }
    section { background: var(--card); border: 1px solid var(--line); padding: 1.1rem 1.15rem; margin-bottom: 1rem; }
    label { display: block; font-size: .85rem; margin: .75rem 0 .3rem; color: var(--muted); }
    input, textarea { width: 100%; padding: .55rem .65rem; border: 1px solid var(--line); font: inherit; background: #fbfcfb; }
    textarea { min-height: 7rem; font-family: ui-monospace, Consolas, monospace; font-size: .85rem; }
    button { margin-top: 1rem; margin-right: .5rem; padding: .55rem 1rem; border: 0; background: var(--acc); color: #fff; font: inherit; cursor: pointer; }
    button.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
    .status { font-size: .92rem; line-height: 1.45; }
    .ok { border-left: 4px solid var(--acc); padding-left: .75rem; }
    .idle { border-left: 4px solid var(--warn); padding-left: .75rem; }
    code { background: #e8eee9; padding: .05em .35em; }
    .msg { margin-top: .75rem; font-size: .9rem; }
    .err { color: #8b2e2e; }
  </style>
</head>
<body>
  <main>
    <h1>BMS House Box enroll</h1>
    <p class="sub">Paste the QR JSON from the operator client page (prepare box). This box then heartbeats with that unique ID. Device-vendor clouds are never used.</p>

    <section id="status" class="status idle">Loading…</section>

    <section>
      <label for="raw">QR JSON (preferred)</label>
      <textarea id="raw" placeholder='{"v":1,"unique_id":"…","enroll_token":"bms_…","ha_hostname":"slug.ha.localhost"}'></textarea>
      <label for="platform">Platform URL (optional override)</label>
      <input id="platform" value="__PLATFORM__" />
      <label for="uid">Or unique ID</label>
      <input id="uid" autocomplete="off" />
      <label for="token">Enroll token</label>
      <input id="token" autocomplete="off" />
      <label for="host">HA hostname</label>
      <input id="host" placeholder="windows-lab.ha.localhost" />
      <button type="button" id="save">Save enroll</button>
      <button type="button" class="ghost" id="clear">Clear enroll</button>
      <div class="msg" id="msg"></div>
    </section>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const msgEl = document.getElementById("msg");

    async function refresh() {
      const r = await fetch("/api/status");
      const s = await r.json();
      if (s.enrolled) {
        statusEl.className = "status ok";
        statusEl.innerHTML = "<strong>Enrolled</strong><br>unique ID <code>" + s.unique_id +
          "</code><br>hostname <code>" + (s.ha_hostname || "—") +
          "</code><br>token " + s.enroll_token_prefix +
          "<br>platform-agent will use this on the next ping.";
      } else {
        statusEl.className = "status idle";
        statusEl.innerHTML = "<strong>Not enrolled</strong> — waiting for operator QR / token. Env fallback may still be active for lab.";
      }
    }

    document.getElementById("save").onclick = async () => {
      msgEl.textContent = "";
      msgEl.className = "msg";
      let body = {};
      const raw = document.getElementById("raw").value.trim();
      if (raw) {
        try { body = JSON.parse(raw); }
        catch (e) { msgEl.textContent = "QR JSON is not valid JSON"; msgEl.className = "msg err"; return; }
      } else {
        body = {
          unique_id: document.getElementById("uid").value.trim(),
          enroll_token: document.getElementById("token").value.trim(),
          ha_hostname: document.getElementById("host").value.trim(),
        };
      }
      const platform = document.getElementById("platform").value.trim();
      if (platform) body.platform_url = platform;
      const r = await fetch("/api/enroll", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const out = await r.json();
      if (!r.ok) { msgEl.textContent = out.error || "Save failed"; msgEl.className = "msg err"; return; }
      msgEl.textContent = "Saved. Agent picks this up within one poll interval.";
      await refresh();
    };

    document.getElementById("clear").onclick = async () => {
      await fetch("/api/enroll", { method: "DELETE" });
      msgEl.textContent = "Cleared.";
      await refresh();
    };

    refresh();
  </script>
</body>
</html>
""".replace("__PLATFORM__", DEFAULT_PLATFORM)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"enroll-ui {self.address_string()} {fmt % args}", flush=True)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj).encode()
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/status":
            self._json(200, public_status())
            return
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/enroll":
            self._json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        try:
            if ctype == "application/x-www-form-urlencoded":
                form = parse_qs(raw.decode("utf-8", errors="replace"))
                payload = {k: (v[0] if v else "") for k, v in form.items()}
            else:
                payload = json.loads(raw.decode("utf-8") or "{}")
            saved = save_enroll(payload)
        except ValueError as err:
            self._json(400, {"error": str(err)})
            return
        except Exception as err:
            self._json(400, {"error": f"invalid body: {err}"})
            return
        print(f"enroll-ui saved unique_id={saved.get('unique_id')}", flush=True)
        self._json(200, {"ok": True, "status": public_status()})

    def do_DELETE(self) -> None:
        if self.path.split("?", 1)[0] != "/api/enroll":
            self._json(404, {"error": "not_found"})
            return
        clear_enroll()
        self._json(200, {"ok": True, "status": public_status()})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"enroll-ui http://0.0.0.0:{PORT}/ (writes bms_enroll.json)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

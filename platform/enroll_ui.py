"""Lab first-run enroll UI for Home Box.

1) Scan/paste BMS QR (no passwords in QR)
2) Verify BMS hello
3) Set Home Box owner credentials locally (or reset when BMS allow_password_reset)

Listen: BMS_ENROLL_UI_PORT (default 8099).
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from bms_runtime import load_runtime
from enroll_store import clear_enroll, load_enroll, public_status, save_enroll

PORT = int(os.environ.get("BMS_ENROLL_UI_PORT", "8099"))
DEFAULT_PLATFORM = os.environ.get("BMS_PLATFORM_URL", "http://host.docker.internal:8080").rstrip("/")
HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
STATIC_DIR = Path(os.environ.get("BMS_ENROLL_STATIC", "/app/static"))

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Home Box — enroll</title>
  <style>
    :root { color-scheme: light; --ink:#1a1f1c; --muted:#5c6b63; --line:#c5d0c8; --bg:#eef3ef; --card:#fff; --acc:#2f6f4e; --warn:#8a6d1d; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: linear-gradient(160deg,#dfe8e2,#eef3ef 40%,#f7f5ef); color: var(--ink); min-height: 100vh; }
    main { max-width: 40rem; margin: 0 auto; padding: 2rem 1.25rem 3rem; }
    h1 { font-size: 1.55rem; margin: 0 0 .35rem; letter-spacing: -0.02em; }
    h2 { font-size: 1.05rem; margin: 0 0 .65rem; }
    .sub { color: var(--muted); margin: 0 0 1.5rem; line-height: 1.45; }
    section { background: var(--card); border: 1px solid var(--line); padding: 1.1rem 1.15rem; margin-bottom: 1rem; }
    section.hidden { display: none; }
    label { display: block; font-size: .85rem; margin: .75rem 0 .3rem; color: var(--muted); }
    input, textarea, select { width: 100%; padding: .55rem .65rem; border: 1px solid var(--line); font: inherit; background: #fbfcfb; }
    textarea { min-height: 7rem; font-family: ui-monospace, Consolas, monospace; font-size: .85rem; }
    button { margin-top: 1rem; margin-right: .5rem; padding: .55rem 1rem; border: 0; background: var(--acc); color: #fff; font: inherit; cursor: pointer; }
    button.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .status { font-size: .92rem; line-height: 1.45; }
    .ok { border-left: 4px solid var(--acc); padding-left: .75rem; }
    .idle { border-left: 4px solid var(--warn); padding-left: .75rem; }
    code { background: #e8eee9; padding: .05em .35em; }
    .msg { margin-top: .75rem; font-size: .9rem; }
    .err { color: #8b2e2e; }
    .hint { color: var(--muted); font-size: .85rem; line-height: 1.4; margin: .35rem 0 0; }
    .scan-wrap { position: relative; background: #111; overflow: hidden; aspect-ratio: 4/3; max-height: 320px; }
    .scan-wrap video, .scan-wrap canvas { width: 100%; height: 100%; object-fit: cover; display: block; }
    .scan-wrap canvas { position: absolute; inset: 0; pointer-events: none; }
    .scan-wrap.hidden { display: none; }
    .row { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin-top: .75rem; }
    .row button { margin-top: 0; }
    .steps { font-size: .85rem; color: var(--muted); margin-bottom: 1rem; }
  </style>
  <script src="/static/jsQR.min.js"></script>
</head>
<body>
  <main>
    <h1>Home Box enroll</h1>
    <p class="sub">Scan the BMS QR (unique ID + enroll token only — never a password). After BMS hello succeeds, set your Home Box admin login on this page.</p>
    <p class="steps">1 · QR → 2 · BMS hello → 3 · Home Box admin password (local)</p>

    <section id="status" class="status idle">Loading…</section>

    <section id="secEnroll">
      <h2>1. Scan BMS QR</h2>
      <p class="hint">Point the camera at the QR from <strong>Prepare box</strong>. Frames stay in this browser.</p>
      <label for="camera">Camera</label>
      <select id="camera"></select>
      <div class="row">
        <button type="button" id="startScan">Start camera</button>
        <button type="button" class="ghost" id="stopScan" disabled>Stop</button>
      </div>
      <div id="scanWrap" class="scan-wrap hidden" style="margin-top: .85rem;">
        <video id="video" playsinline muted></video>
        <canvas id="overlay"></canvas>
      </div>
      <canvas id="capture" style="display:none;"></canvas>
      <div class="msg" id="scanMsg"></div>

      <h2 style="margin-top:1.25rem;">Or paste</h2>
      <label for="raw">QR JSON</label>
      <textarea id="raw" placeholder='{"v":1,"unique_id":"…","enroll_token":"bms_…","ha_hostname":"slug.ha.localhost"}'></textarea>
      <label for="platform">Platform URL (optional)</label>
      <input id="platform" value="__PLATFORM__" />
      <label for="uid">Or unique ID</label>
      <input id="uid" autocomplete="off" />
      <label for="token">Enroll token</label>
      <input id="token" autocomplete="off" />
      <label for="host">HA hostname</label>
      <input id="host" placeholder="windows-lab.ha.localhost" />
      <button type="button" id="save">Save enroll &amp; hello BMS</button>
      <button type="button" class="ghost" id="clear">Clear enroll</button>
      <div class="msg" id="msg"></div>
    </section>

    <section id="secOwner" class="hidden">
      <h2>2. Home Box admin setup</h2>
      <p class="hint">Create the owner login for this box. The password is stored only in Home Box — not in BMS and not in the QR.</p>
      <label for="ownerName">Display name</label>
      <input id="ownerName" autocomplete="name" />
      <label for="ownerUser">Username</label>
      <input id="ownerUser" autocomplete="username" />
      <label for="ownerPass">Password (min 8)</label>
      <input id="ownerPass" type="password" autocomplete="new-password" />
      <label for="ownerPass2">Confirm password</label>
      <input id="ownerPass2" type="password" autocomplete="new-password" />
      <button type="button" id="createOwner">Create Home Box admin</button>
      <div class="msg" id="ownerMsg"></div>
    </section>

    <section id="secReset" class="hidden">
      <h2>Reset Home Box password</h2>
      <p class="hint">BMS staff turned on <strong>Allow Home Box password reset</strong>. Choose a new password here — BMS will not see it.</p>
      <label for="resetUser">Username</label>
      <input id="resetUser" autocomplete="username" />
      <label for="resetPass">New password (min 8)</label>
      <input id="resetPass" type="password" autocomplete="new-password" />
      <label for="resetPass2">Confirm</label>
      <input id="resetPass2" type="password" autocomplete="new-password" />
      <button type="button" id="doReset">Set new password</button>
      <div class="msg" id="resetMsg"></div>
    </section>

    <section id="secDone" class="hidden">
      <h2>Ready</h2>
      <p class="hint" id="doneHint">Open Home Box and sign in with the username you set.</p>
      <p><a id="haLink" href="http://127.0.0.1:8123" target="_blank" rel="noopener">Open Home Box UI</a></p>
    </section>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const msgEl = document.getElementById("msg");
    const scanMsg = document.getElementById("scanMsg");
    const ownerMsg = document.getElementById("ownerMsg");
    const resetMsg = document.getElementById("resetMsg");
    const video = document.getElementById("video");
    const overlay = document.getElementById("overlay");
    const capture = document.getElementById("capture");
    const scanWrap = document.getElementById("scanWrap");
    const cameraSel = document.getElementById("camera");
    let stream = null;
    let raf = 0;
    let scanning = false;
    let lastSavedKey = "";

    function setMsg(el, text, isErr) {
      el.textContent = text || "";
      el.className = isErr ? "msg err" : "msg";
    }

    function show(id, on) {
      document.getElementById(id).classList.toggle("hidden", !on);
    }

    async function refresh() {
      const r = await fetch("/api/status");
      const s = await r.json();
      if (s.enrolled) {
        statusEl.className = "status ok";
        statusEl.innerHTML = "<strong>Enrolled</strong><br>unique ID <code>" + s.unique_id +
          "</code><br>hostname <code>" + (s.ha_hostname || "—") +
          "</code><br>BMS hello: <code>" + (s.bms_hello || "—") +
          "</code><br>password reset flag: <code>" + (s.allow_password_reset ? "on" : "off") + "</code>";
        if (s.ha_hostname) {
          document.getElementById("haLink").href = "http://" + s.ha_hostname.replace(/^https?:\/\//, "") + ":8080";
        }
      } else {
        statusEl.className = "status idle";
        statusEl.innerHTML = "<strong>Not enrolled</strong> — scan the BMS QR or paste the token.";
      }
      await refreshOwnerPanels(s);
    }

    async function refreshOwnerPanels(status) {
      if (!status || !status.enrolled) {
        show("secOwner", false);
        show("secReset", false);
        show("secDone", false);
        return;
      }
      if (status.bms_hello !== "ok") {
        show("secOwner", false);
        show("secReset", false);
        return;
      }
      let owner;
      try {
        const r = await fetch("/api/owner-status");
        owner = await r.json();
      } catch (e) {
        owner = { ok: false };
      }
      const hasOwner = !!(owner && owner.has_owner);
      const resetOn = !!(status.allow_password_reset || (owner && owner.allow_password_reset));
      show("secOwner", !hasOwner);
      show("secReset", hasOwner && resetOn);
      show("secDone", hasOwner && !resetOn);
      if (owner && owner.users && owner.users.length) {
        const u = owner.users.find((x) => x.is_owner) || owner.users[0];
        if (u && u.username) document.getElementById("resetUser").value = u.username;
        document.getElementById("doneHint").textContent =
          "Sign in to Home Box as " + (u.username || u.name || "owner") + ". Password is only on this box.";
      }
    }

    function fillFromPayload(body) {
      document.getElementById("raw").value = JSON.stringify(body);
      if (body.unique_id) document.getElementById("uid").value = body.unique_id;
      if (body.enroll_token) document.getElementById("token").value = body.enroll_token;
      if (body.ha_hostname) document.getElementById("host").value = body.ha_hostname;
      if (body.platform_url) document.getElementById("platform").value = body.platform_url;
    }

    async function savePayload(body, source) {
      const platform = document.getElementById("platform").value.trim();
      if (platform) body.platform_url = platform;
      const r = await fetch("/api/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const out = await r.json();
      if (!r.ok) throw new Error(out.error || "Save failed");
      fillFromPayload(body);
      setMsg(msgEl, "Saved from " + source + ". Checking BMS hello…");
      setMsg(scanMsg, "QR accepted (" + source + ").");
      const hello = await fetch("/api/hello", { method: "POST" });
      const helloBody = await hello.json();
      if (!hello.ok) throw new Error(helloBody.error || "BMS hello failed");
      setMsg(msgEl, "BMS hello OK. Continue with Home Box admin setup below.");
      await refresh();
      return out;
    }

    function parseQrText(text) {
      const trimmed = (text || "").trim();
      if (!trimmed) throw new Error("Empty QR");
      let body;
      try { body = JSON.parse(trimmed); }
      catch (e) { throw new Error("QR is not BMS enroll JSON"); }
      if (!body || typeof body !== "object") throw new Error("QR payload must be an object");
      if (!body.enroll_token || !(body.unique_id || body.appliance_uid)) {
        throw new Error("QR missing enroll_token or unique_id");
      }
      if (body.password || body.username && body.enroll_token && body.password) {
        /* ignore any accidental credential fields — never use them */
      }
      delete body.password;
      delete body.user_password;
      return body;
    }

    async function listCameras() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cams = devices.filter((d) => d.kind === "videoinput");
      const prev = cameraSel.value;
      cameraSel.innerHTML = "";
      cams.forEach((d, i) => {
        const opt = document.createElement("option");
        opt.value = d.deviceId;
        opt.textContent = d.label || ("Camera " + (i + 1));
        cameraSel.appendChild(opt);
      });
      if (!cams.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No camera found";
        cameraSel.appendChild(opt);
      } else if (prev) cameraSel.value = prev;
      else {
        const back = cams.find((d) => /back|rear|environment/i.test(d.label || ""));
        if (back) cameraSel.value = back.deviceId;
      }
    }

    function stopScan() {
      scanning = false;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
      video.srcObject = null;
      scanWrap.classList.add("hidden");
      document.getElementById("startScan").disabled = false;
      document.getElementById("stopScan").disabled = true;
      const ctx = overlay.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
    }

    function drawBox(loc) {
      const ctx = overlay.getContext("2d");
      overlay.width = video.videoWidth;
      overlay.height = video.videoHeight;
      ctx.clearRect(0, 0, overlay.width, overlay.height);
      if (!loc) return;
      ctx.strokeStyle = "#3ecf8e";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(loc.topLeftCorner.x, loc.topLeftCorner.y);
      ctx.lineTo(loc.topRightCorner.x, loc.topRightCorner.y);
      ctx.lineTo(loc.bottomRightCorner.x, loc.bottomRightCorner.y);
      ctx.lineTo(loc.bottomLeftCorner.x, loc.bottomLeftCorner.y);
      ctx.closePath();
      ctx.stroke();
    }

    async function onDecoded(text) {
      let body;
      try { body = parseQrText(text); }
      catch (e) { setMsg(scanMsg, e.message, true); return; }
      const key = (body.unique_id || body.appliance_uid) + "|" + body.enroll_token;
      if (key === lastSavedKey) return;
      lastSavedKey = key;
      try {
        await savePayload(body, "camera scan");
        stopScan();
      } catch (e) {
        lastSavedKey = "";
        setMsg(scanMsg, e.message || String(e), true);
      }
    }

    function tick() {
      if (!scanning) return;
      if (video.readyState >= 2 && typeof jsQR === "function") {
        const w = video.videoWidth, h = video.videoHeight;
        if (w && h) {
          capture.width = w; capture.height = h;
          const ctx = capture.getContext("2d", { willReadFrequently: true });
          ctx.drawImage(video, 0, 0, w, h);
          const image = ctx.getImageData(0, 0, w, h);
          const code = jsQR(image.data, image.width, image.height, { inversionAttempts: "dontInvert" });
          if (code) { drawBox(code.location); onDecoded(code.data); return; }
          drawBox(null);
        }
      }
      raf = requestAnimationFrame(tick);
    }

    async function startScan() {
      setMsg(scanMsg, "");
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMsg(scanMsg, "This browser cannot open a camera. Use paste instead.", true);
        return;
      }
      if (typeof jsQR !== "function") {
        setMsg(scanMsg, "QR library failed to load.", true);
        return;
      }
      stopScan();
      const deviceId = cameraSel.value;
      const constraints = {
        audio: false,
        video: deviceId
          ? { deviceId: { exact: deviceId }, facingMode: { ideal: "environment" } }
          : { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
      };
      try { stream = await navigator.mediaDevices.getUserMedia(constraints); }
      catch (e) {
        setMsg(scanMsg, "Camera permission denied. Paste the QR JSON instead.", true);
        return;
      }
      video.srcObject = stream;
      await video.play();
      scanWrap.classList.remove("hidden");
      scanning = true;
      document.getElementById("startScan").disabled = true;
      document.getElementById("stopScan").disabled = false;
      await listCameras();
      setMsg(scanMsg, "Scanning… hold the BMS QR steady.");
      raf = requestAnimationFrame(tick);
    }

    document.getElementById("startScan").onclick = startScan;
    document.getElementById("stopScan").onclick = () => { stopScan(); setMsg(scanMsg, "Camera stopped."); };

    document.getElementById("save").onclick = async () => {
      setMsg(msgEl, "");
      let body = {};
      const raw = document.getElementById("raw").value.trim();
      if (raw) {
        try { body = parseQrText(raw); }
        catch (e) { setMsg(msgEl, e.message, true); return; }
      } else {
        body = {
          unique_id: document.getElementById("uid").value.trim(),
          enroll_token: document.getElementById("token").value.trim(),
          ha_hostname: document.getElementById("host").value.trim(),
        };
      }
      try { await savePayload(body, "form"); }
      catch (e) { setMsg(msgEl, e.message || String(e), true); }
    };

    document.getElementById("clear").onclick = async () => {
      await fetch("/api/enroll", { method: "DELETE" });
      lastSavedKey = "";
      setMsg(msgEl, "Cleared.");
      setMsg(scanMsg, "");
      await refresh();
    };

    document.getElementById("createOwner").onclick = async () => {
      setMsg(ownerMsg, "");
      const name = document.getElementById("ownerName").value.trim();
      const username = document.getElementById("ownerUser").value.trim();
      const password = document.getElementById("ownerPass").value;
      const password2 = document.getElementById("ownerPass2").value;
      if (password !== password2) { setMsg(ownerMsg, "Passwords do not match.", true); return; }
      const r = await fetch("/api/owner", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, username, password }),
      });
      const out = await r.json();
      if (!r.ok) { setMsg(ownerMsg, out.error || out.hint || "Create failed", true); return; }
      setMsg(ownerMsg, "Admin created. Username: " + out.username + ". Password stays on this box.");
      document.getElementById("ownerPass").value = "";
      document.getElementById("ownerPass2").value = "";
      await refresh();
    };

    document.getElementById("doReset").onclick = async () => {
      setMsg(resetMsg, "");
      const username = document.getElementById("resetUser").value.trim();
      const password = document.getElementById("resetPass").value;
      const password2 = document.getElementById("resetPass2").value;
      if (password !== password2) { setMsg(resetMsg, "Passwords do not match.", true); return; }
      const r = await fetch("/api/password-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const out = await r.json();
      if (!r.ok) { setMsg(resetMsg, out.error || out.hint || "Reset failed", true); return; }
      setMsg(resetMsg, "Password updated for " + out.username + ". Tell BMS staff they can turn the reset switch off.");
      document.getElementById("resetPass").value = "";
      document.getElementById("resetPass2").value = "";
    };

    listCameras().catch(() => {});
    refresh();
    setInterval(refresh, 15000);
  </script>
</body>
</html>
""".replace("__PLATFORM__", DEFAULT_PLATFORM)


def _bms_hello() -> dict:
    data = load_enroll()
    if not data:
        return {"ok": False, "error": "not_enrolled"}
    platform = str(data.get("platform_url") or DEFAULT_PLATFORM).rstrip("/")
    token = str(data.get("enroll_token") or "").strip()
    req = urllib.request.Request(
        f"{platform}/api/v1/ingest/subscription/",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            snap = json.loads(resp.read().decode())
        return {
            "ok": True,
            "bms_hello": "ok",
            "slug": (snap.get("household") or {}).get("slug"),
            "handover_state": (snap.get("machine") or {}).get("handover_state"),
            "allow_password_reset": bool((snap.get("machine") or {}).get("allow_password_reset")),
            "unique_id": snap.get("unique_id") or snap.get("appliance_uid"),
        }
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")[:300]
        return {"ok": False, "error": f"BMS HTTP {err.code}: {body}", "bms_hello": "failed"}
    except Exception as err:
        return {"ok": False, "error": str(err), "bms_hello": "failed"}


def _ha_proxy(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = load_enroll()
    if not data:
        return 400, {"ok": False, "error": "not_enrolled"}
    token = str(data.get("enroll_token") or "").strip()
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else {"ok": True})
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {"error": raw}
        except Exception:
            parsed = {"error": raw[:300]}
        if not isinstance(parsed, dict):
            parsed = {"error": str(parsed)}
        parsed.setdefault("ok", False)
        return err.code, parsed
    except Exception as err:
        return 502, {"ok": False, "error": f"HA unreachable: {err}"}


def enriched_status() -> dict:
    st = public_status()
    runtime = load_runtime() or {}
    st["allow_password_reset"] = bool(
        runtime.get("allow_password_reset")
        or ((runtime.get("machine") or {}).get("allow_password_reset"))
    )
    if st.get("enrolled"):
        hello = _bms_hello()
        st["bms_hello"] = hello.get("bms_hello") or ("ok" if hello.get("ok") else "failed")
        if hello.get("ok"):
            st["allow_password_reset"] = bool(
                hello.get("allow_password_reset") or st["allow_password_reset"]
            )
            st["handover_state"] = hello.get("handover_state")
        else:
            st["bms_hello_error"] = hello.get("error")
    else:
        st["bms_hello"] = "n/a"
    return st


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

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype == "application/x-www-form-urlencoded":
            form = parse_qs(raw.decode("utf-8", errors="replace"))
            return {k: (v[0] if v else "") for k, v in form.items()}
        return json.loads(raw.decode("utf-8") or "{}")

    def _safe_static(self, url_path: str) -> Path | None:
        rel = unquote(url_path[len("/static/") :])
        if not rel or ".." in rel.replace("\\\\", "/").split("/"):
            return None
        path = (STATIC_DIR / rel).resolve()
        try:
            path.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(200, enriched_status())
            return
        if path == "/api/owner-status":
            code, body = _ha_proxy("GET", "/api/home_box/owner_status")
            self._json(code, body)
            return
        if path.startswith("/static/"):
            file_path = self._safe_static(path)
            if not file_path:
                self._json(404, {"error": "not_found"})
                return
            data = file_path.read_bytes()
            ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self._send(200, data, ctype)
            return
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/enroll":
            try:
                payload = self._read_json()
                # Strip any credential fields if a bad QR/tool included them
                for bad in ("password", "user_password", "ha_password", "admin_password"):
                    payload.pop(bad, None)
                saved = save_enroll(payload)
            except ValueError as err:
                self._json(400, {"error": str(err)})
                return
            except Exception as err:
                self._json(400, {"error": f"invalid body: {err}"})
                return
            print(f"enroll-ui saved unique_id={saved.get('unique_id')}", flush=True)
            self._json(200, {"ok": True, "status": enriched_status()})
            return
        if path == "/api/hello":
            self._json(200 if _bms_hello().get("ok") else 502, _bms_hello())
            return
        if path == "/api/owner":
            try:
                payload = self._read_json()
            except Exception as err:
                self._json(400, {"error": str(err)})
                return
            code, body = _ha_proxy("POST", "/api/home_box/owner", payload)
            self._json(code, body)
            return
        if path == "/api/password-reset":
            try:
                payload = self._read_json()
            except Exception as err:
                self._json(400, {"error": str(err)})
                return
            code, body = _ha_proxy("POST", "/api/home_box/password_reset", payload)
            self._json(code, body)
            return
        self._json(404, {"error": "not_found"})

    def do_DELETE(self) -> None:
        if urlparse(self.path).path != "/api/enroll":
            self._json(404, {"error": "not_found"})
            return
        clear_enroll()
        self._json(200, {"ok": True, "status": enriched_status()})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        f"enroll-ui http://0.0.0.0:{PORT}/ qr→hello→owner/reset (ha={HA_URL})",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()

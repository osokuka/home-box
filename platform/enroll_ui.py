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

from bms_runtime import load_runtime, runtime_matches_uid
from enroll_store import (
    clear_admin_bootstrap,
    clear_enroll,
    has_admin_bootstrap,
    load_admin_bootstrap,
    load_enroll,
    public_status,
    save_enroll,
)
from wg_store import apply_wireguard, has_wg_conf

PORT = int(os.environ.get("BMS_ENROLL_UI_PORT", "8099"))
DEFAULT_PLATFORM = os.environ.get("BMS_PLATFORM_URL", "").strip().rstrip("/")
HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
STATIC_DIR = Path(os.environ.get("BMS_ENROLL_STATIC", "/app/static"))
HA_OPEN_URL = os.environ.get("HOME_BOX_OPEN_URL", "http://127.0.0.1:8123").rstrip("/")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


ALLOW_RESET = _env_flag("ENROLL_ALLOW_RESET", "0")

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
    .countdown { font-size: 3.5rem; font-weight: 600; letter-spacing: -0.04em; line-height: 1; margin: .75rem 0 .35rem; color: var(--acc); }
    .countdown-sub { color: var(--muted); font-size: .95rem; line-height: 1.45; margin: 0; }
  </style>
  <script src="/static/jsQR.min.js"></script>
</head>
<body>
  <main>
    <h1>Home Box enroll</h1>
    <p class="sub">Scan the BMS QR (enroll + optional WireGuard + optional one-time admin). After BMS is reachable, admin is created from the QR when present, otherwise you set the password here.</p>
    <p class="steps">1 · QR (+ WG + admin) → 2 · Wait for BMS (standby→ok) → 3 · Admin → public hostname</p>

    <section id="status" class="status idle">Loading…</section>

    <section id="secWait" class="hidden">
      <h2>Connecting to BMS</h2>
      <p class="countdown" id="countdownNum">45</p>
      <p class="countdown-sub" id="countdownHint">Applying WireGuard keys and waiting until BMS is reachable…</p>
      <div class="msg" id="waitMsg"></div>
      <div class="row" id="waitActions" style="display:none;">
        <button type="button" id="retryWait">Retry wait</button>
        <button type="button" class="ghost" id="skipToEnroll">Continue setup</button>
      </div>
    </section>

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
      <textarea id="raw" placeholder='{"v":2,"unique_id":"…","enroll_token":"bms_…","ha_hostname":"slug.ha.…","wireguard":{"role":"box","config":"[Interface]…"}}'></textarea>
      <label for="platform">Platform URL (optional override — leave empty to use QR)</label>
      <input id="platform" value="" placeholder="from QR, e.g. http://10.10.0.1" />
      <label for="uid">Or unique ID</label>
      <input id="uid" autocomplete="off" />
      <label for="token">Enroll token</label>
      <input id="token" autocomplete="off" />
      <label for="host">HA hostname</label>
      <input id="host" placeholder="windows-lab.ha.localhost" />
      <button type="button" id="save">Save enroll &amp; connect</button>
      <button type="button" class="ghost hidden" id="clear">Clear enroll (tech)</button>
      <div class="msg" id="msg"></div>
    </section>

    <section id="secOwner" class="hidden">
      <h2>3. Home Box admin registration</h2>
      <p class="hint">Create the client admin login if the QR did not include one-time <code>admin</code> credentials. Password stays on this box.</p>
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
      <p><a id="haLink" href="__HA_OPEN__" target="_blank" rel="noopener">Open Home Box UI</a></p>
    </section>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const msgEl = document.getElementById("msg");
    const scanMsg = document.getElementById("scanMsg");
    const ownerMsg = document.getElementById("ownerMsg");
    const resetMsg = document.getElementById("resetMsg");
    const waitMsg = document.getElementById("waitMsg");
    const video = document.getElementById("video");
    const overlay = document.getElementById("overlay");
    const capture = document.getElementById("capture");
    const scanWrap = document.getElementById("scanWrap");
    const cameraSel = document.getElementById("camera");
    let stream = null;
    let raf = 0;
    let scanning = false;
    let lastSavedKey = "";
    let waitAbort = false;
    const BMS_READY_WAIT_SECONDS = 300;

    function setMsg(el, text, isErr) {
      el.textContent = text || "";
      el.className = isErr ? "msg err" : "msg";
    }

    function show(id, on) {
      document.getElementById(id).classList.toggle("hidden", !on);
    }

    function enterWaitMode(hint) {
      waitAbort = false;
      show("secWait", true);
      show("secEnroll", false);
      show("secOwner", false);
      show("secReset", false);
      show("secDone", false);
      document.getElementById("waitActions").style.display = "none";
      document.getElementById("countdownNum").textContent = String(BMS_READY_WAIT_SECONDS);
      document.getElementById("countdownHint").textContent =
        hint || "Applying WireGuard keys and waiting until BMS is ready…";
      setMsg(waitMsg, "");
    }

    function leaveWaitMode() {
      waitAbort = true;
      show("secWait", false);
      // Never reopen QR enroll after identity is saved (unless tech reset).
    }

    async function pollHelloOnce() {
      const hello = await fetch("/api/hello", { method: "POST" });
      const helloBody = await hello.json().catch(() => ({}));
      const state = String((helloBody && helloBody.bms_hello) || "").toLowerCase();
      const reachable = !!(helloBody && (helloBody.reachable || state === "standby" || state === "ok"));
      return {
        ready: !!(helloBody && helloBody.ok && state === "ok"),
        standby: state === "standby",
        reachable: reachable,
        body: helloBody,
      };
    }

    async function waitForBms(seconds) {
      const total = seconds || BMS_READY_WAIT_SECONDS;
      const numEl = document.getElementById("countdownNum");
      const hintEl = document.getElementById("countdownHint");
      const actions = document.getElementById("waitActions");
      actions.style.display = "none";
      const deadline = Date.now() + total * 1000;
      let sawStandby = false;
      while (!waitAbort && Date.now() < deadline) {
        const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        numEl.textContent = String(left);
        try {
          const r = await pollHelloOnce();
          if (r.ready) {
            numEl.textContent = "0";
            setMsg(waitMsg, (r.body && r.body.notification) || "BMS ready (ok). Continuing…");
            hintEl.textContent = "BMS reported ok.";
            return true;
          }
          if (r.standby) {
            sawStandby = true;
            const note = (r.body && r.body.notification) ||
              "Standby: BMS is finishing backend setup. Stay on this page.";
            setMsg(waitMsg, note);
            hintEl.textContent = "Standby — waiting for BMS ok… " + left + "s remaining.";
          } else if (r.reachable) {
            setMsg(waitMsg, "BMS reachable; waiting for ready (ok)…");
            hintEl.textContent = "Waiting for BMS ok… " + left + "s remaining.";
          } else {
            const err = (r.body && r.body.error) || "Still waiting for BMS…";
            setMsg(waitMsg, sawStandby ? ("Lost BMS briefly: " + err) : err);
            hintEl.textContent = "Waiting for BMS over WireGuard… " + left + "s remaining.";
          }
        } catch (e) {
          setMsg(waitMsg, "Still waiting: " + (e.message || String(e)));
          hintEl.textContent = "Waiting for BMS… " + left + "s remaining.";
        }
        await new Promise((res) => setTimeout(res, 1000));
      }
      if (waitAbort) return false;
      numEl.textContent = "0";
      hintEl.textContent = sawStandby
        ? "BMS stayed on standby (no ok) within " + total + " seconds."
        : "BMS not ready within " + total + " seconds.";
      setMsg(waitMsg, "Timed out. Check WireGuard / BMS edge, then retry.", true);
      actions.style.display = "flex";
      return false;
    }

    async function tryQrAdminBootstrap(doRedirect) {
      try {
        const boot = await fetch("/api/owner-bootstrap", { method: "POST" });
        const bootBody = await boot.json().catch(() => ({}));
        if (boot.ok && bootBody && bootBody.ok && !bootBody.skipped) {
          if (doRedirect === false) {
            setMsg(msgEl, "Admin created from QR. Waiting for BMS ok before redirect…");
            return "bootstrapped";
          }
          setMsg(msgEl, "Admin created from QR. Redirecting…");
          const dest = bootBody.redirect || publicRedirectUrl(await refresh() || {});
          try { window.location.replace(dest); } catch (e) {}
          return true;
        }
      } catch (e) {}
      return false;
    }

    async function afterBmsOk() {
      show("secWait", false);
      show("secEnroll", false);
      // Ready (ok) only — never redirect on standby.
      if (await tryQrAdminBootstrap(true)) return;
      setMsg(msgEl, "BMS hello OK. Register the Home Box admin below.");
      await refresh();
      show("secOwner", true);
      const owner = document.getElementById("secOwner");
      owner.scrollIntoView({ behavior: "smooth", block: "start" });
      try { location.hash = "admin"; } catch (e) {}
      try { document.getElementById("ownerUser").focus(); } catch (e) {}
    }

    function publicRedirectUrl(s) {
      // QR / enroll ha_hostname is source of truth — never prefer a stale BMS cache host.
      const host = String((s && (s.ha_hostname || s.bms_ha_hostname)) || "")
        .replace(/^https?:\/\//, "")
        .split("/")[0]
        .trim();
      if (host) return "https://" + host;
      return "__HA_OPEN__";
    }

    async function refresh() {
      const r = await fetch("/api/status");
      const s = await r.json();
      const allowReset = !!s.allow_reset;
      show("clear", allowReset);
      const wg = s.wireguard || {};
      const wgLine = wg.configured
        ? ("<br>WireGuard: <code>saved</code> " + (wg.address || "") +
           (wg.endpoint ? (" → <code>" + wg.endpoint + "</code>") : "") +
           "<br><span class='hint'>" + (wg.apply_hint || "") + "</span>")
        : "<br>WireGuard: <code>not in QR</code>";
      const pub = publicRedirectUrl(s);
      document.getElementById("haLink").href = pub;
      document.getElementById("haLink").textContent = "Open " + (s.ha_hostname || s.bms_ha_hostname || "Home Box");

      if (s.enrolled) {
        statusEl.className = "status ok";
        statusEl.innerHTML = "<strong>Enrolled</strong> — admin setup only<br>unique ID <code>" + s.unique_id +
          "</code><br>hostname <code>" + (s.ha_hostname || s.bms_ha_hostname || "—") +
          "</code><br>platform_url <code>" + (s.platform_url || "—") +
          "</code><br>BMS hello: <code>" + (s.bms_hello || "—") +
          "</code>" + (s.notification ? (" — " + s.notification) : "") +
          (s.bms_hello_error ? (" <span class='err'>" + s.bms_hello_error + "</span>") : "") +
          wgLine;
        // Never show QR enroll again after identity is saved.
        show("secEnroll", false);
        if (!document.getElementById("secWait").classList.contains("hidden")) {
          return s;
        }
        if (s.bms_hello !== "ok") {
          enterWaitMode(
            s.bms_hello === "standby"
              ? ((s.notification) || "Standby: waiting for BMS ok…")
              : "Reconnecting to BMS…"
          );
          const ok = await waitForBms(BMS_READY_WAIT_SECONDS);
          if (ok) await afterBmsOk();
          return s;
        }
        await refreshOwnerPanels(s);
        return s;
      }

      statusEl.className = "status idle";
      statusEl.innerHTML = "<strong>Not enrolled</strong> — scan the BMS QR from a phone on the LAN." + wgLine;
      if (!document.getElementById("secWait").classList.contains("hidden")) {
        return s;
      }
      show("secEnroll", true);
      show("secOwner", false);
      show("secReset", false);
      show("secDone", false);
      return s;
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
        show("secDone", false);
        return;
      }
      // If QR admin is still pending (e.g. hello failed during countdown), apply now.
      if (status.admin_bootstrap) {
        if (await tryQrAdminBootstrap(true)) return;
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
      show("secEnroll", false);
      show("secWait", false);
      if (hasOwner && !resetOn) {
        show("secOwner", false);
        show("secReset", false);
        show("secDone", true);
        const dest = publicRedirectUrl(status);
        document.getElementById("doneHint").textContent =
          "Admin is set. Redirecting to " + dest + " …";
        // Only redirect when BMS hello is ok (caller already gated).
        try { window.location.replace(dest); } catch (e) {}
        return;
      }
      show("secOwner", !hasOwner);
      show("secReset", hasOwner && resetOn);
      show("secDone", false);
      if (!hasOwner) {
        try { location.hash = "admin"; } catch (e) {}
        try { document.getElementById("ownerUser").focus(); } catch (e) {}
      }
      if (owner && owner.users && owner.users.length) {
        const u = owner.users.find((x) => x.is_owner) || owner.users[0];
        if (u && u.username) document.getElementById("resetUser").value = u.username;
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
      // QR platform_url wins. Form only fills when QR omitted it (never clobber with lab default).
      const platformField = document.getElementById("platform").value.trim();
      const fromQr = (body.platform_url || "").trim();
      if (fromQr) {
        body.platform_url = fromQr.replace(/\/$/, "");
      } else if (platformField) {
        body.platform_url = platformField.replace(/\/$/, "");
      } else {
        delete body.platform_url;
      }
      const r = await fetch("/api/enroll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const out = await r.json();
      if (!r.ok) throw new Error(out.error || "Save failed");
      fillFromPayload(body);
      const st = (out && out.status) || {};
      const savedPlatform = (st.platform_url || body.platform_url || "");
      const hasWg = !!(body.wireguard || (st.wireguard && st.wireguard.configured));
      setMsg(msgEl, "Saved from " + source + (savedPlatform ? (". platform_url=" + savedPlatform) : "."));
      setMsg(scanMsg, "QR accepted (" + source + ").");

      if (hasWg) {
        enterWaitMode("Restarting WireGuard with keys from the QR…");
        try {
          const apply = await fetch("/api/wg/apply", { method: "POST" });
          const applyBody = await apply.json().catch(() => ({}));
          const hint = (applyBody && applyBody.hint) || "";
          document.getElementById("countdownHint").textContent =
            (applyBody && applyBody.mode === "restarted")
              ? "WireGuard restarted. Waiting for BMS…"
              : ("WireGuard keys saved. " + (hint || "Waiting for BMS…"));
          setMsg(waitMsg, hint || "");
        } catch (e) {
          setMsg(waitMsg, "WG apply call failed; still waiting for BMS. " + (e.message || ""), true);
        }
        const ok = await waitForBms(BMS_READY_WAIT_SECONDS);
        if (ok) await afterBmsOk();
        return out;
      }

      setMsg(msgEl, "Saved from " + source + ". Checking BMS hello…");
      enterWaitMode("Waiting for BMS ready (ok)…");
      const ok = await waitForBms(BMS_READY_WAIT_SECONDS);
      if (ok) await afterBmsOk();
      else throw new Error("BMS hello did not become ok in time");
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
      if (body.password && !body.admin) {
        /* top-level password without admin{} is ignored */
      }
      delete body.password;
      delete body.user_password;
      // Keep body.admin { username, password } for one-time bootstrap.
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
      const r = await fetch("/api/enroll", { method: "DELETE" });
      const out = await r.json().catch(() => ({}));
      if (!r.ok) {
        setMsg(msgEl, out.error || "Clear blocked", true);
        return;
      }
      lastSavedKey = "";
      leaveWaitMode();
      setMsg(msgEl, "Cleared.");
      setMsg(scanMsg, "");
      await refresh();
    };

    document.getElementById("retryWait").onclick = async () => {
      enterWaitMode("Retrying WireGuard apply and BMS wait…");
      try {
        await fetch("/api/wg/apply", { method: "POST" });
      } catch (e) {}
      const ok = await waitForBms(BMS_READY_WAIT_SECONDS);
      if (ok) await afterBmsOk();
    };

    document.getElementById("skipToEnroll").onclick = async () => {
      leaveWaitMode();
      const s = await refresh();
      if (s && s.enrolled) {
        if (s.bms_hello === "ok") await afterBmsOk();
        else {
          enterWaitMode(
            s.bms_hello === "standby"
              ? ((s.notification) || "Standby: waiting for BMS ok…")
              : "Still waiting for BMS…"
          );
          const ok = await waitForBms(BMS_READY_WAIT_SECONDS);
          if (ok) await afterBmsOk();
        }
        return;
      }
      show("secEnroll", true);
      setMsg(msgEl, "Scan the BMS QR to continue.");
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
      setMsg(ownerMsg, "Admin created. Checking BMS ready before redirect…");
      document.getElementById("ownerPass").value = "";
      document.getElementById("ownerPass2").value = "";
      enterWaitMode("Waiting for BMS ok before opening public URL…");
      const ready = await waitForBms(BMS_READY_WAIT_SECONDS);
      if (!ready) {
        setMsg(ownerMsg, "Admin saved locally, but BMS did not report ok yet. Retry wait.", true);
        return;
      }
      const dest = publicRedirectUrl(await refresh() || {});
      setMsg(ownerMsg, "BMS ok. Redirecting…");
      try { window.location.replace(dest); } catch (e) {}
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
""".replace("__HA_OPEN__", HA_OPEN_URL)


def _bms_hello() -> dict:
    from bms_fetch import bms_hello

    return bms_hello()


def _public_redirect_url(st: dict) -> str:
    """Redirect target from current enroll QR hostname (not stale runtime)."""
    host = str(st.get("ha_hostname") or st.get("bms_ha_hostname") or "").strip()
    host = host.replace("https://", "").replace("http://", "").split("/")[0].strip()
    if host:
        return f"https://{host}"
    return HA_OPEN_URL


def _enroll_locked() -> bool:
    """True after first successful QR save — QR enroll UI must not reopen."""
    return load_enroll() is not None and not ALLOW_RESET


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
    enroll = load_enroll() or {}
    enroll_uid = str(enroll.get("unique_id") or st.get("unique_id") or "").strip()
    qr_host = str(enroll.get("ha_hostname") or st.get("ha_hostname") or "").strip()

    # Runtime only for same unique_id (never a previous box's hostname).
    runtime = load_runtime() or {}
    if not runtime_matches_uid(enroll_uid):
        runtime = {}

    st["allow_reset"] = ALLOW_RESET
    st["allow_password_reset"] = bool(
        runtime.get("allow_password_reset")
        or ((runtime.get("machine") or {}).get("allow_password_reset"))
    )
    # QR ha_hostname wins for redirect / display.
    if qr_host:
        st["ha_hostname"] = qr_host

    live_host = ""
    if st.get("enrolled"):
        hello = _bms_hello()
        state = hello.get("bms_hello") or ("ok" if hello.get("ok") else "failed")
        st["bms_hello"] = state
        if hello.get("notification"):
            st["notification"] = hello.get("notification")
        if hello.get("reachable") or state in ("ok", "standby"):
            st["allow_password_reset"] = bool(
                hello.get("allow_password_reset") or st["allow_password_reset"]
            )
            st["handover_state"] = hello.get("handover_state")
            hello_uid = str(hello.get("unique_id") or "").strip()
            # Accept live hostname only when it belongs to this QR enroll.
            if hello_uid and hello_uid == enroll_uid:
                live_host = str(hello.get("ha_hostname") or "").strip()
        if state == "failed":
            st["bms_hello_error"] = hello.get("error")

        if live_host and not qr_host:
            st["ha_hostname"] = live_host
            st["bms_ha_hostname"] = live_host
        elif qr_host:
            st["bms_ha_hostname"] = qr_host
        elif live_host:
            st["bms_ha_hostname"] = live_host

        redirect = _public_redirect_url(st)
        st["public_url"] = redirect
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
            if _enroll_locked():
                self._json(
                    403,
                    {
                        "ok": False,
                        "error": "enroll_locked",
                        "hint": "Box already enrolled. QR enroll is closed. Set ENROLL_ALLOW_RESET=1 only for technician retest.",
                    },
                )
                return
            try:
                payload = self._read_json()
                # Strip loose top-level secrets; nested admin{} is handled by save_enroll.
                for bad in ("user_password", "ha_password"):
                    payload.pop(bad, None)
                if "admin" not in payload and "owner" not in payload:
                    payload.pop("password", None)
                    payload.pop("admin_password", None)
                    payload.pop("owner_password", None)
                saved = save_enroll(payload)
            except ValueError as err:
                self._json(400, {"error": str(err)})
                return
            except Exception as err:
                self._json(400, {"error": f"invalid body: {err}"})
                return
            print(
                f"enroll-ui saved unique_id={saved.get('unique_id')} "
                f"admin_bootstrap={saved.get('admin_bootstrap')}",
                flush=True,
            )
            self._json(200, {"ok": True, "status": enriched_status()})
            return
        if path == "/api/hello":
            hello = _bms_hello()
            # 200 while reachable (standby or ok); 502 only when unreachable/failed.
            code = 200 if hello.get("reachable") or hello.get("bms_hello") in ("ok", "standby") else 502
            self._json(code, hello)
            return
        if path == "/api/owner-bootstrap":
            creds = load_admin_bootstrap()
            if not creds:
                self._json(200, {"ok": True, "skipped": True, "reason": "no_admin_in_qr"})
                return
            code, body = _ha_proxy(
                "POST",
                "/api/home_box/owner",
                {
                    "name": creds["name"],
                    "username": creds["username"],
                    "password": creds["password"],
                    "bootstrap": True,
                },
            )
            if code < 400 and isinstance(body, dict) and body.get("ok", True) is not False:
                clear_admin_bootstrap()
                # Mark enroll file flag cleared
                data = load_enroll()
                if data and data.get("admin_bootstrap"):
                    data["admin_bootstrap"] = False
                    try:
                        from enroll_store import enroll_path

                        enroll_path().write_text(
                            json.dumps(data, indent=2) + "\n", encoding="utf-8"
                        )
                    except Exception:
                        pass
                if isinstance(body, dict):
                    body["ok"] = True
                    st = enriched_status()
                    body["redirect"] = _public_redirect_url(st)
                    body["username"] = creds["username"]
                    print(
                        f"enroll-ui admin bootstrap ok user={creds['username']} "
                        f"redirect={body['redirect']}",
                        flush=True,
                    )
            else:
                if isinstance(body, dict):
                    body.setdefault("ok", False)
                print(
                    f"enroll-ui admin bootstrap failed code={code}",
                    flush=True,
                )
            self._json(code if code >= 400 else 200, body if isinstance(body, dict) else {"ok": False})
            return
        if path == "/api/wg/apply":
            if not has_wg_conf():
                self._json(400, {"ok": False, "error": "no_wg_conf"})
                return
            result = apply_wireguard()
            code = 200 if result.get("ok") else 500
            print(
                f"enroll-ui wg/apply mode={result.get('mode')} exit={result.get('exit_code')}",
                flush=True,
            )
            self._json(code, result)
            return
        if path == "/api/owner":
            try:
                payload = self._read_json()
            except Exception as err:
                self._json(400, {"error": str(err)})
                return
            code, body = _ha_proxy("POST", "/api/home_box/owner", payload)
            if code < 400 and isinstance(body, dict):
                body["redirect"] = _public_redirect_url(enriched_status())
                print(
                    f"enroll-ui owner created redirect={body.get('redirect')}",
                    flush=True,
                )
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
        if _enroll_locked():
            self._json(
                403,
                {
                    "ok": False,
                    "error": "enroll_locked",
                    "hint": "Clear enroll disabled after first enroll. Technician: ENROLL_ALLOW_RESET=1 then restart enroll-ui.",
                },
            )
            return
        clear_enroll()
        self._json(200, {"ok": True, "status": enriched_status()})


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(
        f"enroll-ui http://0.0.0.0:{PORT}/ lan-qr→wg→admin→https://slug.bms… reset={ALLOW_RESET}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
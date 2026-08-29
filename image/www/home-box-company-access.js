class HomeBoxCompanyAccess extends HTMLElement {
  _hass;
  _busy = false;

  connectedCallback() {
    this.render();
    this.refresh();
  }

  set hass(val) {
    this._hass = val;
    if (this.isConnected) this.refresh();
  }

  get hass() {
    return this._hass;
  }

  async api(method, path, body) {
    if (!this._hass) throw new Error("Not signed in");
    const token = this._hass.auth.data.access_token;
    const r = await fetch(path, {
      method,
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || data.hint || "Request failed");
    return data;
  }

  async refresh() {
    const status = this.querySelector("#shareStatus");
    const toggle = this.querySelector("#shareToggle");
    const grants = this.querySelector("#grantList");
    if (!status || !this._hass) return;
    try {
      const data = await this.api("GET", "/api/home_box/limited_share");
      const on = !!data.limited_share_enabled;
      status.textContent = on
        ? "Limited share is ON — status/support data may leave this box toward BMS. No company sees it until you grant them in BMS."
        : "Limited share is OFF — nothing is posted for companies.";
      status.className = on ? "ok" : "warn";
      if (toggle) toggle.checked = on;
      if (grants) {
        const list = data.active_company_grants || [];
        if (!list.length) {
          grants.innerHTML =
            "<p class='muted'>No company grants visible yet. After you enable limited share, grant a company in BMS.</p>";
        } else {
          grants.innerHTML =
            "<ul>" +
            list
              .map(
                (g) =>
                  "<li>" +
                  (g.company_name || g.company_slug || g.company_id || "company") +
                  " — domains: " +
                  ((g.domains || []).join(", ") || "—") +
                  "</li>"
              )
              .join("") +
            "</ul>";
        }
      }
    } catch (e) {
      status.textContent = "Could not load share status: " + (e.message || e);
      status.className = "warn";
    }
  }

  async onToggle(ev) {
    if (this._busy || !this._hass) return;
    this._busy = true;
    const msg = this.querySelector("#shareMsg");
    const enabled = !!ev.target.checked;
    try {
      await this.api("POST", "/api/home_box/limited_share", { enabled });
      if (msg) {
        msg.textContent = enabled
          ? "Enabled. Next: in BMS, share with the company you agreed with."
          : "Disabled. Status/support will stop posting.";
        msg.className = "msg";
      }
      await this.refresh();
    } catch (e) {
      if (msg) {
        msg.textContent = e.message || String(e);
        msg.className = "msg err";
      }
      ev.target.checked = !enabled;
    } finally {
      this._busy = false;
    }
  }

  render() {
    this.innerHTML = `
      <style>
        :host { display: block; padding: 24px; max-width: 44rem; font-family: system-ui, sans-serif; line-height: 1.45; color: #1a1f1c; }
        h1 { font-size: 1.4rem; margin: 0 0 0.5rem; }
        h2 { font-size: 1.1rem; margin: 1.4rem 0 0.45rem; }
        code { background: #e8eee9; padding: 0.1em 0.35em; }
        ol, ul { padding-left: 1.2rem; }
        .warn { border-left: 4px solid #c4a35a; padding-left: 12px; }
        .ok { border-left: 4px solid #2f6f4e; padding-left: 12px; }
        .brand { display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; }
        .brand img { height: 40px; }
        .row { display: flex; align-items: center; gap: 12px; margin: 1rem 0; padding: 0.85rem 1rem; background: #f4f7f5; border: 1px solid #c5d0c8; }
        .row label { font-weight: 600; flex: 1; }
        .muted { color: #5c6b63; font-size: 0.92rem; }
        .msg { margin-top: 0.5rem; font-size: 0.9rem; }
        .err { color: #8b2e2e; }
        input[type=checkbox] { width: 1.25rem; height: 1.25rem; }
      </style>
      <div class="brand">
        <img src="/local/home-box-logo.svg" alt="Home Box" />
      </div>
      <h1>Company access</h1>

      <h2>Limited share (this box)</h2>
      <p class="warn" id="shareStatus">Loading…</p>
      <p class="muted">
        Limited share sends only <strong>device status</strong> and <strong>support activity</strong>
        (faults / unreachable signals for efficiency troubleshooting).
        It never gives companies on/off control from BMS.
      </p>
      <div class="row">
        <label for="shareToggle">Allow limited share to BMS</label>
        <input type="checkbox" id="shareToggle" />
      </div>
      <p class="muted">
        Turning this on does <strong>not</strong> share with any company yet.
        You (or the household owner) must also grant the company in BMS.
      </p>
      <div class="msg" id="shareMsg"></div>

      <h2>Company grants (from BMS)</h2>
      <div id="grantList"><p class="muted">Loading…</p></div>

      <h2>If a technician needs to look inside Home Box</h2>
      <ol>
        <li>Settings → People → Add person.</li>
        <li>Enable login. Do <strong>not</strong> make them Administrator.</li>
        <li>Give them a password yourself. Do not reuse yours.</li>
        <li>They open the household URL. Remote VPN comes later.</li>
      </ol>
      <p class="muted">
        Platform limited share and a Home Box login are separate. Revoking one does not revoke the other.
      </p>
    `;
    const toggle = this.querySelector("#shareToggle");
    if (toggle) toggle.addEventListener("change", (ev) => this.onToggle(ev));
  }
}
customElements.define("home-box-company-access", HomeBoxCompanyAccess);

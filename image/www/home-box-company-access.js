class HomeBoxCompanyAccess extends HTMLElement {
  _hass;
  _busy = false;
  _available = [];
  _selected = new Set();

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
    const sensorBox = this.querySelector("#sensorList");
    if (!status || !this._hass) return;
    try {
      const data = await this.api("GET", "/api/home_box/limited_share");
      const on = !!data.limited_share_enabled;
      status.textContent = on
        ? "Sensory share is ON — selected sensors / HVAC status may leave this box toward BMS when the feed is positive. No company sees it until you grant them in BMS."
        : "Sensory share is OFF — nothing is posted for companies.";
      status.className = on ? "ok" : "warn";
      if (toggle) toggle.checked = on;

      this._available = Array.isArray(data.available_sensors)
        ? data.available_sensors
        : [];
      this._selected = new Set(
        (data.sensor_entities || []).map((e) => String(e).toLowerCase())
      );
      if (sensorBox) this.renderSensors(sensorBox);

      if (grants) {
        const list = data.active_company_grants || [];
        if (!list.length) {
          grants.innerHTML =
            "<p class='muted'>No company grants visible yet. After you enable share, grant a company in BMS (security, HVAC, …).</p>";
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

  renderSensors(host) {
    if (!this._available.length) {
      host.innerHTML =
        "<p class='muted'>No binary sensors found yet. Add HLK-DIO16 (or other) sensors first.</p>";
      return;
    }
    host.innerHTML = this._available
      .map((s) => {
        const id = String(s.entity_id || "").toLowerCase();
        const checked = this._selected.has(id) ? "checked" : "";
        const label = s.name || id;
        return (
          "<label class='sensor'>" +
          "<input type='checkbox' data-eid='" +
          id +
          "' " +
          checked +
          "/>" +
          "<span>" +
          label +
          " <code>" +
          id +
          "</code></span>" +
          "</label>"
        );
      })
      .join("");
    host.querySelectorAll("input[type=checkbox]").forEach((el) => {
      el.addEventListener("change", () => this.onSensorChange());
    });
  }

  selectedSensors() {
    return Array.from(this._selected);
  }

  async onSensorChange() {
    const host = this.querySelector("#sensorList");
    if (!host) return;
    this._selected = new Set();
    host.querySelectorAll("input[type=checkbox]").forEach((el) => {
      if (el.checked) this._selected.add(el.getAttribute("data-eid"));
    });
    if (this._busy || !this._hass) return;
    this._busy = true;
    const msg = this.querySelector("#shareMsg");
    try {
      const toggle = this.querySelector("#shareToggle");
      await this.api("POST", "/api/home_box/limited_share", {
        enabled: !!(toggle && toggle.checked),
        sensor_entities: this.selectedSensors(),
      });
      if (msg) {
        msg.textContent =
          "Saved sensor allowlist (" + this._selected.size + " selected).";
        msg.className = "msg";
      }
    } catch (e) {
      if (msg) {
        msg.textContent = e.message || String(e);
        msg.className = "msg err";
      }
    } finally {
      this._busy = false;
    }
  }

  async onToggle(ev) {
    if (this._busy || !this._hass) return;
    this._busy = true;
    const msg = this.querySelector("#shareMsg");
    const enabled = !!ev.target.checked;
    try {
      await this.api("POST", "/api/home_box/limited_share", {
        enabled,
        sensor_entities: this.selectedSensors(),
      });
      if (msg) {
        msg.textContent = enabled
          ? "Enabled. Feed posts only when positive (active sensor / active HVAC). Next: grant the company in BMS."
          : "Disabled. Sensory feed will stop posting.";
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
        code { background: #e8eee9; padding: 0.1em 0.35em; font-size: 0.85em; }
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
        #sensorList { display: flex; flex-direction: column; gap: 0.45rem; margin: 0.75rem 0 1rem; }
        .sensor { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.45rem 0.6rem; background: #f4f7f5; border: 1px solid #c5d0c8; }
        .sensor span { flex: 1; font-size: 0.92rem; }
      </style>
      <div class="brand">
        <img src="/local/home-box-logo.svg" alt="Home Box" />
      </div>
      <h1>Company access</h1>

      <h2>Sensory share (this box)</h2>
      <p class="warn" id="shareStatus">Loading…</p>
      <p class="muted">
        This box only chooses <strong>what</strong> may leave (sensors you select + HVAC status).
        You choose <strong>who</strong> sees it in BMS. Relays/switches are never shared.
        The feed agent checks every few seconds and posts only when the feed is <strong>positive</strong>
        (an active sensor or active HVAC mode) — idle feeds are not pushed.
      </p>
      <div class="row">
        <label for="shareToggle">Allow sensory share to BMS</label>
        <input type="checkbox" id="shareToggle" />
      </div>

      <h2>Sensors to include</h2>
      <p class="muted">HLK digital inputs and other binary sensors. Leave unchecked to omit.</p>
      <div id="sensorList"><p class="muted">Loading…</p></div>
      <div class="msg" id="shareMsg"></div>

      <h2>Company grants (from BMS)</h2>
      <div id="grantList"><p class="muted">Loading…</p></div>
    `;
    const toggle = this.querySelector("#shareToggle");
    if (toggle) toggle.addEventListener("change", (ev) => this.onToggle(ev));
  }
}
customElements.define("home-box-company-access", HomeBoxCompanyAccess);

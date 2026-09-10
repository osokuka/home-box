class HomeBoxCompanyAccess extends HTMLElement {
  _hass;
  _busy = false;
  _dirty = false;
  _available = [];
  /** @type {string[]} */
  _categories = [];
  /** @type {Map<string, string>} entity_id -> category slug */
  _classifications = new Map();
  /** @type {Set<string>} */
  _selected = new Set();
  _shareOn = false;
  _savedSnapshot = "";

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.render();
    this.refresh();
  }

  /** @param {string} sel */
  $(sel) {
    return (this.shadowRoot || this).querySelector(sel);
  }

  /** @param {string} sel */
  $$(sel) {
    return (this.shadowRoot || this).querySelectorAll(sel);
  }

  set hass(val) {
    this._hass = val;
    if (this.isConnected) this.refresh();
  }

  get hass() {
    return this._hass;
  }

  slug(raw) {
    return String(raw || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
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

  snapshot() {
    const sensors = [...this._selected]
      .sort()
      .map((id) => id + ":" + (this._classifications.get(id) || ""));
    return JSON.stringify({
      on: this._shareOn,
      cats: [...this._categories].sort(),
      sensors,
    });
  }

  markDirty() {
    this._dirty = this.snapshot() !== this._savedSnapshot;
    this.syncChrome();
  }

  syncChrome() {
    const saveBtn = this.$("#saveBtn");
    const discardBtn = this.$("#discardBtn");
    const dirty = this.$("#dirtyBadge");
    const bar = this.$("#saveBar");
    if (saveBtn) {
      saveBtn.disabled = this._busy || !this._dirty;
      saveBtn.textContent = this._busy ? "Saving…" : "Save changes";
    }
    if (discardBtn) discardBtn.disabled = this._busy || !this._dirty;
    if (dirty) {
      dirty.hidden = !this._dirty;
      dirty.textContent = this._dirty ? "Unsaved changes" : "";
    }
    if (bar) bar.classList.toggle("active", this._dirty);
    const status = this.$("#shareStatus");
    if (status && !status.classList.contains("err-load")) {
      status.textContent = this._shareOn
        ? "Sensory share is ON after you save. Selected sensors leave with the category you assign. Companies still need a BMS grant."
        : "Sensory share is OFF after you save — nothing is posted for companies.";
      status.className = this._shareOn ? "banner ok" : "banner warn";
    }
  }

  async refresh() {
    const status = this.$("#shareStatus");
    if (!status || !this._hass) return;
    try {
      const data = await this.api("GET", "/api/home_box/limited_share");
      this._shareOn = !!data.limited_share_enabled;
      this._available = Array.isArray(data.available_sensors)
        ? data.available_sensors
        : [];

      this._selected = new Set();
      this._classifications = new Map();
      const saved = Array.isArray(data.sensors) ? data.sensors : [];
      for (const row of saved) {
        const id = String((row && row.entity_id) || "").toLowerCase();
        if (!id) continue;
        this._selected.add(id);
        this._classifications.set(id, this.slug((row && row.system) || ""));
      }
      for (const eid of data.sensor_entities || []) {
        const id = String(eid).toLowerCase();
        if (!this._selected.has(id)) this._selected.add(id);
        if (!this._classifications.has(id)) this._classifications.set(id, "");
      }

      const fromApi = Array.isArray(data.categories) ? data.categories : [];
      const cats = new Set();
      for (const c of fromApi) {
        const s = this.slug(c);
        if (s) cats.add(s);
      }
      for (const v of this._classifications.values()) {
        if (v) cats.add(v);
      }
      this._categories = [...cats].sort();

      this._savedSnapshot = this.snapshot();
      this._dirty = false;
      this.renderCategories();
      this.renderSensors();
      this.renderGrants(
        data.bms_manage_url || "",
        data.household_name || ""
      );
      const toggle = this.$("#shareToggle");
      if (toggle) toggle.checked = this._shareOn;
      this.setMsg("");
      this.syncChrome();
    } catch (e) {
      status.textContent = "Could not load share status: " + (e.message || e);
      status.className = "banner warn err-load";
    }
  }

  renderCategories() {
    const host = this.$("#categoryList");
    if (!host) return;
    if (!this._categories.length) {
      host.innerHTML =
        "<p class='muted empty'>No categories yet. Add one below (domain or location).</p>";
      return;
    }
    host.innerHTML = this._categories
      .map(
        (c) =>
          "<span class='chip' data-cat='" +
          this.escapeHtml(c) +
          "'>" +
          "<span class='chip-label'>" +
          this.escapeHtml(c) +
          "</span>" +
          "<button type='button' class='chip-x' data-remove='" +
          this.escapeHtml(c) +
          "' title='Remove category' aria-label='Remove " +
          this.escapeHtml(c) +
          "'>×</button>" +
          "</span>"
      )
      .join("");
    host.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cat = btn.getAttribute("data-remove");
        this._categories = this._categories.filter((c) => c !== cat);
        for (const [eid, val] of [...this._classifications.entries()]) {
          if (val === cat) this._classifications.set(eid, "");
        }
        this.renderCategories();
        this.renderSensors();
        this.markDirty();
      });
    });
  }

  addCategory() {
    const input = this.$("#newCategory");
    if (!input) return;
    const cat = this.slug(input.value);
    if (!cat) {
      this.setMsg("Enter a category name (e.g. security, kitchen).", true);
      return;
    }
    if (!this._categories.includes(cat)) {
      this._categories = [...this._categories, cat].sort();
    }
    input.value = "";
    this.renderCategories();
    this.renderSensors();
    this.markDirty();
    this.setMsg("Category “" + cat + "” added — click Save changes when ready.");
  }

  categoryOptions(selected) {
    const opts = [
      "<option value=''>" +
        (selected ? "Choose category…" : "— not set —") +
        "</option>",
    ];
    for (const c of this._categories) {
      opts.push(
        "<option value='" +
          this.escapeHtml(c) +
          "'" +
          (c === selected ? " selected" : "") +
          ">" +
          this.escapeHtml(c) +
          "</option>"
      );
    }
    if (selected && !this._categories.includes(selected)) {
      opts.push(
        "<option value='" +
          this.escapeHtml(selected) +
          "' selected>" +
          this.escapeHtml(selected) +
          " (missing from list)</option>"
      );
    }
    return opts.join("");
  }

  renderSensors() {
    const host = this.$("#sensorList");
    const countEl = this.$("#selectedCount");
    if (countEl) {
      countEl.textContent =
        this._selected.size +
        " of " +
        this._available.length +
        " selected for share";
    }
    if (!host) return;
    if (!this._available.length) {
      host.innerHTML =
        "<p class='muted empty'>No binary sensors found yet. Add HLK-DIO16 (or other) sensors first.</p>";
      return;
    }
    const filter = String(
      (this.$("#sensorFilter") || {}).value || ""
    )
      .trim()
      .toLowerCase();
    const rows = this._available.filter((s) => {
      if (!filter) return true;
      const id = String(s.entity_id || "").toLowerCase();
      const name = String(s.name || "").toLowerCase();
      return id.includes(filter) || name.includes(filter);
    });
    if (!rows.length) {
      host.innerHTML = "<p class='muted empty'>No sensors match this filter.</p>";
      return;
    }
    host.innerHTML = rows
      .map((s) => {
        const id = String(s.entity_id || "").toLowerCase();
        const on = this._selected.has(id);
        const cat = this._classifications.get(id) || "";
        const label = s.name || id;
        const state = s.state != null ? String(s.state) : "";
        return (
          "<div class='sensor" +
          (on ? " on" : "") +
          "' data-row='" +
          this.escapeHtml(id) +
          "'>" +
          "<label class='check'>" +
          "<input type='checkbox' data-eid='" +
          this.escapeHtml(id) +
          "' " +
          (on ? "checked" : "") +
          "/>" +
          "<span class='meta'>" +
          "<span class='name'>" +
          this.escapeHtml(label) +
          "</span>" +
          "<code class='eid'>" +
          this.escapeHtml(id) +
          "</code>" +
          (state
            ? "<span class='state' data-state='" +
              this.escapeHtml(state) +
              "'>" +
              this.escapeHtml(state) +
              "</span>"
            : "") +
          "</span>" +
          "</label>" +
          "<label class='classify'>" +
          "<span>Category</span>" +
          "<select data-sys='" +
          this.escapeHtml(id) +
          "' " +
          (on ? "" : "disabled ") +
          ">" +
          this.categoryOptions(cat) +
          "</select>" +
          "</label>" +
          "</div>"
        );
      })
      .join("");

    host.querySelectorAll("input[type=checkbox]").forEach((el) => {
      el.addEventListener("change", () => {
        const id = el.getAttribute("data-eid");
        if (el.checked) this._selected.add(id);
        else {
          this._selected.delete(id);
        }
        const sel = host.querySelector("select[data-sys='" + id + "']");
        if (sel) sel.disabled = !el.checked;
        const row = host.querySelector("[data-row='" + id + "']");
        if (row) row.classList.toggle("on", el.checked);
        this.markDirty();
        if (countEl) {
          countEl.textContent =
            this._selected.size +
            " of " +
            this._available.length +
            " selected for share";
        }
      });
    });
    host.querySelectorAll("select[data-sys]").forEach((el) => {
      el.addEventListener("change", () => {
        const id = el.getAttribute("data-sys");
        const val = this.slug(el.value);
        this._classifications.set(id, val);
        if (val && !this._categories.includes(val)) {
          this._categories = [...this._categories, val].sort();
          this.renderCategories();
        }
        this.markDirty();
      });
    });
  }

  renderGrants(manageUrl, householdName) {
    const grants = this.$("#grantList");
    if (!grants) return;
    const url = String(manageUrl || "").trim();
    const title = householdName
      ? "Open BMS for " + householdName
      : "Open BMS to manage sharing";
    if (!url) {
      grants.innerHTML =
        "<p class='muted'>BMS portal URL is not configured on this box.</p>";
      return;
    }
    grants.innerHTML =
      "<a class='bms-link' href='" +
      this.escapeHtml(url) +
      "' target='_blank' rel='noopener noreferrer'>" +
      this.escapeHtml(title) +
      "</a>" +
      "<p class='muted'>Who sees your sensors is chosen in BMS — not on this box. " +
      "Use the link above to add or revoke companies.</p>";
  }

  draftSensors() {
    const out = [];
    for (const id of this._selected) {
      out.push({
        entity_id: id,
        system: this._classifications.get(id) || "",
      });
    }
    return out;
  }

  setMsg(text, isErr) {
    const msg = this.$("#shareMsg");
    if (!msg) return;
    msg.textContent = text || "";
    msg.className = "msg" + (isErr ? " err" : text ? " ok-msg" : "");
  }

  async onSave() {
    if (this._busy || !this._hass || !this._dirty) return;
    const sensors = this.draftSensors();
    const missing = sensors.filter((s) => !s.system);
    if (missing.length) {
      this.setMsg(
        "Assign a category to every selected sensor before saving (" +
          missing.length +
          " missing).",
        true
      );
      return;
    }
    this._busy = true;
    this.syncChrome();
    try {
      const data = await this.api("POST", "/api/home_box/limited_share", {
        enabled: this._shareOn,
        sensors,
        categories: this._categories,
      });
      this._savedSnapshot = this.snapshot();
      this._dirty = false;
      const tokenNote =
        data && data.ha_token_status === "ha_token_created"
          ? " Local HA read token created for the sensory feed."
          : "";
      await this.refresh();
      this.setMsg(
        "Saved. " +
          sensors.length +
          " sensor(s) will sync to BMS with your categories." +
          tokenNote
      );
    } catch (e) {
      this.setMsg(e.message || String(e), true);
    } finally {
      this._busy = false;
      this.syncChrome();
    }
  }

  async onDiscard() {
    if (this._busy || !this._dirty) return;
    await this.refresh();
    this.setMsg("Discarded unsaved changes.");
  }

  render() {
    const root = this.shadowRoot || this;
    root.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          color-scheme: light;
          background: #e8efe9;
          min-height: 100vh;
          font-family: "Segoe UI", ui-sans-serif, system-ui, sans-serif;
          line-height: 1.45;
          color: #14201a;
        }
        *, *::before, *::after { box-sizing: border-box; }
        .shell {
          width: 100%;
          min-height: 100vh;
          background:
            radial-gradient(ellipse 70% 45% at 50% 0%, #d8ebe0 0%, transparent 55%),
            linear-gradient(180deg, #f3f7f4 0%, #e8efe9 100%);
          padding: 1.5rem 1.25rem 6rem;
        }
        .page {
          width: 100%;
          max-width: 48rem;
          margin: 0 auto;
        }
        h1 { font-size: 1.55rem; margin: 0 0 0.35rem; letter-spacing: -0.02em; color: #14201a; }
        h2 { font-size: 1.05rem; margin: 0 0 0.4rem; font-weight: 650; color: #14201a; }
        h3 { font-size: 0.92rem; margin: 0 0 0.45rem; font-weight: 650; color: #2a3d33; }
        code, .eid {
          font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
          font-size: 0.78rem;
          background: #e2ebe5;
          color: #14201a;
          padding: 0.12em 0.4em;
          border-radius: 3px;
          word-break: break-all;
        }
        .brand { display: flex; align-items: center; gap: 12px; margin-bottom: 0.75rem; }
        .brand img { height: 36px; }
        .lede { color: #4a5c52; font-size: 0.95rem; margin: 0 0 1.1rem; }
        .banner {
          margin: 0 0 1rem;
          padding: 0.7rem 0.85rem;
          border-radius: 6px;
          border: 1px solid transparent;
          font-size: 0.92rem;
        }
        .banner.ok { background: #e4f2ea; border-color: #9fc4ae; color: #1e4d34; }
        .banner.warn { background: #f7f0e0; border-color: #d4bc7a; color: #5c4a1e; }
        .section {
          margin: 0 0 1.15rem;
          padding: 1rem 1.05rem 1.1rem;
          background: #ffffff;
          border: 1px solid #c5d4cb;
          border-radius: 8px;
          box-shadow: 0 1px 2px rgba(20, 40, 30, 0.04);
        }
        .section-head {
          display: flex; flex-wrap: wrap; align-items: baseline;
          justify-content: space-between; gap: 0.4rem 1rem; margin-bottom: 0.55rem;
        }
        .muted { color: #5c6b63; font-size: 0.9rem; margin: 0 0 0.65rem; }
        .empty { margin: 0.35rem 0; }
        .row-toggle {
          display: flex; align-items: center; gap: 12px;
          padding: 0.65rem 0.75rem; background: #eef4f0; border-radius: 6px;
          border: 1px solid #c5d4cb;
        }
        .row-toggle label { font-weight: 650; flex: 1; color: #14201a; }
        input[type=checkbox] {
          width: 1.2rem; height: 1.2rem; accent-color: #2f6f4e; color-scheme: light;
        }
        .cat-add { display: flex; gap: 0.45rem; margin-top: 0.65rem; flex-wrap: wrap; }
        input[type=text],
        input[type=search],
        select,
        select option {
          color: #14201a !important;
          -webkit-text-fill-color: #14201a !important;
          background-color: #ffffff !important;
          color-scheme: light;
        }
        .cat-add input[type=text],
        .filter input[type=search],
        .classify select {
          flex: 1;
          min-width: 10rem;
          width: 100%;
          padding: 0.5rem 0.6rem;
          border: 1px solid #8fad9a;
          border-radius: 5px;
          font: inherit;
          font-size: 0.95rem;
          line-height: 1.3;
          background-color: #ffffff !important;
          color: #14201a !important;
          -webkit-text-fill-color: #14201a !important;
        }
        .classify select:disabled {
          opacity: 0.55;
          background-color: #eef2ef !important;
          color: #2f6f4e !important;
          -webkit-text-fill-color: #2f6f4e !important;
        }
        .classify select option {
          background-color: #ffffff !important;
          color: #14201a !important;
        }
        .btn {
          appearance: none; border: 1px solid #2f6f4e; background: #2f6f4e; color: #fff;
          font: inherit; font-weight: 600; padding: 0.45rem 0.85rem; border-radius: 5px;
          cursor: pointer;
        }
        .btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .btn.secondary { background: #ffffff; color: #1e4d34; border-color: #8fad9a; }
        .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; min-height: 1.75rem; }
        .chip {
          display: inline-flex; align-items: center; gap: 0.25rem;
          padding: 0.2rem 0.25rem 0.2rem 0.55rem; background: #dceae2;
          border: 1px solid #a8c4b4; border-radius: 999px; font-size: 0.86rem; font-weight: 600;
          color: #1e4d34;
        }
        .chip-x {
          border: 0; background: transparent; color: #2f6f4e; cursor: pointer;
          font-size: 1.05rem; line-height: 1; padding: 0 0.35rem; border-radius: 999px;
        }
        .chip-x:hover { background: #c5ddd0; }
        .toolbar {
          display: flex; flex-wrap: wrap; gap: 0.55rem; align-items: center;
          margin-bottom: 0.65rem;
        }
        .filter { flex: 1; min-width: 12rem; }
        .count { font-size: 0.86rem; color: #2f6f4e; font-weight: 600; }
        #sensorList { display: flex; flex-direction: column; gap: 0.45rem; }
        .sensor {
          display: grid; grid-template-columns: 1fr minmax(10rem, 12rem);
          gap: 0.55rem 0.75rem; align-items: center;
          padding: 0.65rem 0.7rem; background: #f7faf8;
          border: 1px solid #c5d4cb; border-radius: 6px;
        }
        .sensor.on { background: #eef6f1; border-color: #8fb89d; }
        .check { display: flex; gap: 0.65rem; align-items: flex-start; margin: 0; color: #14201a; }
        .meta { display: flex; flex-direction: column; gap: 0.2rem; min-width: 0; }
        .name { font-weight: 650; font-size: 0.95rem; color: #14201a; }
        .state {
          display: inline-block; width: fit-content; font-size: 0.75rem; font-weight: 650;
          text-transform: uppercase; letter-spacing: 0.03em;
          padding: 0.1rem 0.4rem; border-radius: 3px; background: #dde6e1; color: #3d5247;
        }
        .state[data-state="on"] { background: #cfe8d8; color: #1e4d34; }
        .state[data-state="off"] { background: #e4e8e5; color: #5c6b63; }
        .classify {
          display: flex; flex-direction: column; gap: 0.25rem; margin: 0;
          font-size: 0.78rem; color: #2f6f4e; font-weight: 650;
        }
        .grants { margin: 0.35rem 0 0; padding-left: 1.15rem; color: #14201a; }
        .grants li { margin: 0.25rem 0; }
        .bms-link {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          margin: 0.15rem 0 0.55rem;
          padding: 0.65rem 0.9rem;
          background: #2f6f4e;
          color: #ffffff !important;
          -webkit-text-fill-color: #ffffff;
          font-weight: 650;
          font-size: 0.98rem;
          text-decoration: none;
          border-radius: 6px;
          border: 1px solid #255a3f;
        }
        .bms-link:hover { background: #255a3f; }
        .bms-link::after { content: "↗"; font-size: 0.9em; opacity: 0.9; }
        .msg { min-height: 1.25rem; margin: 0.35rem 0 0.75rem; font-size: 0.9rem; color: #14201a; }
        .msg.ok-msg { color: #1e4d34; font-weight: 600; }
        .msg.err { color: #8b2e2e; font-weight: 600; }
        #saveBar {
          position: sticky;
          bottom: 0;
          margin-top: 1rem;
          padding: 0.85rem 1rem;
          display: flex; flex-wrap: wrap; gap: 0.55rem; align-items: center;
          background: #1a2e24; color: #e8f2ec; border: 1px solid #2f4a3c;
          border-radius: 8px;
        }
        #saveBar.active { box-shadow: 0 8px 24px rgba(20, 40, 30, 0.22); }
        #dirtyBadge { flex: 1; font-size: 0.88rem; font-weight: 650; color: #f0d9a0; }
        #saveBar .btn { border-color: #3d8f64; color: #fff; }
        #saveBar .btn.secondary {
          background: transparent; color: #e8f2ec; border-color: #5a7568;
          -webkit-text-fill-color: #e8f2ec;
        }
        @media (max-width: 560px) {
          .sensor { grid-template-columns: 1fr; }
          .shell { padding: 1rem 0.85rem 5rem; }
        }
      </style>

      <div class="shell">
        <div class="page">
          <div class="brand">
            <img src="/local/home-box-logo.svg" alt="Home Box" />
          </div>
          <h1>Company access</h1>
          <p class="lede">
            Choose which sensors leave this box, organize them into your own categories
            (domain or location), then <strong>Save</strong>. Companies only see data after a BMS grant.
            Relays and switches are never shared.
          </p>

          <p class="banner warn" id="shareStatus">Loading…</p>

          <section class="section" aria-labelledby="share-heading">
            <h2 id="share-heading">1. Sensory share</h2>
            <p class="muted">Master switch for this Home Box. When you enable and save, Home Box creates a local read token so the sensory feed can use friendly names and live states — no separate setup.</p>
            <div class="row-toggle">
              <label for="shareToggle">Allow sensory share to BMS</label>
              <input type="checkbox" id="shareToggle" />
            </div>
          </section>

          <section class="section" aria-labelledby="cat-heading">
            <div class="section-head">
              <h2 id="cat-heading">2. Categories</h2>
            </div>
            <p class="muted">
              Create labels once, then assign them to sensors. Use domains
              (<code>hvac</code>, <code>security</code>) or locations (<code>kitchen</code>, <code>front-door</code>).
            </p>
            <h3>Your categories</h3>
            <div class="chips" id="categoryList"></div>
            <div class="cat-add">
              <input type="text" id="newCategory" placeholder="New category name" autocomplete="off" />
              <button type="button" class="btn secondary" id="addCategoryBtn">Add category</button>
            </div>
          </section>

          <section class="section" aria-labelledby="sensor-heading">
            <div class="section-head">
              <h2 id="sensor-heading">3. Sensors for share</h2>
              <span class="count" id="selectedCount">—</span>
            </div>
            <p class="muted">Check sensors to include, then pick a category for each. Unchecked sensors stay on the box only.</p>
            <div class="toolbar">
              <div class="filter">
                <input type="search" id="sensorFilter" placeholder="Filter by name or entity id" />
              </div>
            </div>
            <div id="sensorList"><p class="muted">Loading…</p></div>
          </section>

          <section class="section" aria-labelledby="grant-heading">
            <h2 id="grant-heading">Who can see this data</h2>
            <p class="muted">Companies are granted access in BMS. This box only chooses which sensors leave.</p>
            <div id="grantList"><p class="muted">Loading…</p></div>
          </section>

          <div class="msg" id="shareMsg" role="status"></div>

          <div id="saveBar" aria-live="polite">
            <span id="dirtyBadge" hidden></span>
            <button type="button" class="btn secondary" id="discardBtn" disabled>Discard</button>
            <button type="button" class="btn" id="saveBtn" disabled>Save changes</button>
          </div>
        </div>
      </div>
    `;

    const toggle = this.$("#shareToggle");
    if (toggle) {
      toggle.addEventListener("change", () => {
        this._shareOn = !!toggle.checked;
        this.markDirty();
      });
    }
    const addBtn = this.$("#addCategoryBtn");
    if (addBtn) addBtn.addEventListener("click", () => this.addCategory());
    const newCat = this.$("#newCategory");
    if (newCat) {
      newCat.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          this.addCategory();
        }
      });
    }
    const filter = this.$("#sensorFilter");
    if (filter) {
      filter.addEventListener("input", () => this.renderSensors());
    }
    const saveBtn = this.$("#saveBtn");
    if (saveBtn) saveBtn.addEventListener("click", () => this.onSave());
    const discardBtn = this.$("#discardBtn");
    if (discardBtn) discardBtn.addEventListener("click", () => this.onDiscard());
  }
}
customElements.define("home-box-company-access", HomeBoxCompanyAccess);

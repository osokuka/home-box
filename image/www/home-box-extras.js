/**
 * Home Box "Extras" — replaces the stock Home Assistant Apps / add-on store page.
 * Home Box runs HA Core only (no Supervisor / HA OS apps).
 */
class HomeBoxExtras extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 1.5rem 1.25rem 2.5rem;
          max-width: 40rem;
          margin: 0 auto;
          font-family: "Segoe UI", ui-sans-serif, system-ui, sans-serif;
          line-height: 1.45;
          color: #14201a;
          background:
            radial-gradient(ellipse 70% 45% at 50% 0%, #d8ebe0 0%, transparent 55%),
            linear-gradient(180deg, #f3f7f4 0%, #e8efe9 100%);
          min-height: 100%;
          box-sizing: border-box;
        }
        * { box-sizing: border-box; }
        .brand { margin-bottom: 0.85rem; }
        .brand img { height: 36px; }
        h1 { font-size: 1.45rem; margin: 0 0 0.4rem; letter-spacing: -0.02em; }
        h2 { font-size: 1.05rem; margin: 1.25rem 0 0.4rem; }
        p { margin: 0 0 0.75rem; color: #4a5c52; }
        .card {
          padding: 1rem 1.05rem;
          background: #fff;
          border: 1px solid #c5d4cb;
          border-radius: 8px;
          margin: 0.85rem 0;
        }
        ul { margin: 0.35rem 0 0; padding-left: 1.2rem; color: #2a3d33; }
        li { margin: 0.3rem 0; }
        a {
          color: #2f6f4e;
          font-weight: 650;
          text-decoration: none;
        }
        a:hover { text-decoration: underline; }
        .warn {
          border-left: 4px solid #c4a35a;
          padding: 0.55rem 0.75rem;
          background: #f7f0e0;
          color: #5c4a1e;
          border-radius: 0 6px 6px 0;
        }
      </style>
      <div class="brand">
        <img src="/local/home-box-logo.svg" alt="Home Box" />
      </div>
      <h1>Extras on Home Box</h1>
      <p>
        Home Box is a locked-down household appliance. Extra capability is built into
        this product — not an open Home Assistant app store.
      </p>

      <div class="card">
        <h2>What you use instead</h2>
        <ul>
          <li><a href="/getting-started">Getting started</a> — takeover and day-to-day use</li>
          <li><a href="/company-access">Company access</a> — sensory share to BMS</li>
          <li><a href="/enroll/">Enroll</a> — wire the box to BMS (lab / reclaim)</li>
          <li><a href="/import/">Device import</a> — Tuya Local CSV / Excel</li>
        </ul>
      </div>

      <p class="warn">
        The Home Assistant Operating System app store is not part of Home Box.
        That page is blocked so the product stays local, private, and under your control.
      </p>
    `;
  }
}
customElements.define("home-box-extras", HomeBoxExtras);

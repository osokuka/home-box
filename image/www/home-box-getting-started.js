/**
 * Home Box Getting started — same visual language as Company access.
 * Shadow DOM so HA dark theme cannot wash out the page.
 */
class HomeBoxGettingStarted extends HTMLElement {
  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this.render();
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
          padding: 1.5rem 1.25rem 3rem;
        }
        .page {
          width: 100%;
          max-width: 48rem;
          margin: 0 auto;
        }
        h1 {
          font-size: 1.55rem;
          margin: 0 0 0.35rem;
          letter-spacing: -0.02em;
          color: #14201a;
        }
        h2 {
          font-size: 1.05rem;
          margin: 0 0 0.4rem;
          font-weight: 650;
          color: #14201a;
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 0.75rem;
        }
        .brand img { height: 36px; }
        .lede {
          color: #4a5c52;
          font-size: 0.95rem;
          margin: 0 0 1.1rem;
        }
        .banner {
          margin: 0 0 1rem;
          padding: 0.7rem 0.85rem;
          border-radius: 6px;
          border: 1px solid transparent;
          font-size: 0.92rem;
        }
        .banner.ok {
          background: #e4f2ea;
          border-color: #9fc4ae;
          color: #1e4d34;
        }
        .banner.warn {
          background: #f7f0e0;
          border-color: #d4bc7a;
          color: #5c4a1e;
        }
        .section {
          margin: 0 0 1.15rem;
          padding: 1rem 1.05rem 1.1rem;
          background: #ffffff;
          border: 1px solid #c5d4cb;
          border-radius: 8px;
          box-shadow: 0 1px 2px rgba(20, 40, 30, 0.04);
        }
        .muted {
          color: #5c6b63;
          font-size: 0.9rem;
          margin: 0 0 0.65rem;
        }
        ol.steps, ul.links {
          margin: 0.35rem 0 0;
          padding-left: 1.25rem;
          color: #14201a;
        }
        ol.steps li, ul.links li {
          margin: 0.45rem 0;
        }
        code {
          font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
          font-size: 0.78rem;
          background: #e2ebe5;
          color: #14201a;
          padding: 0.12em 0.4em;
          border-radius: 3px;
          word-break: break-all;
        }
        a {
          color: #2f6f4e;
          font-weight: 650;
          text-decoration: none;
        }
        a:hover { text-decoration: underline; }
        .cta-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-top: 0.75rem;
        }
        .cta {
          display: inline-flex;
          align-items: center;
          padding: 0.5rem 0.85rem;
          background: #2f6f4e;
          color: #ffffff !important;
          -webkit-text-fill-color: #ffffff;
          border-radius: 5px;
          font-weight: 650;
          font-size: 0.92rem;
          text-decoration: none !important;
          border: 1px solid #255a3f;
        }
        .cta:hover { background: #255a3f; }
        .cta.secondary {
          background: #ffffff;
          color: #1e4d34 !important;
          -webkit-text-fill-color: #1e4d34;
          border-color: #8fad9a;
        }
        .cta.secondary:hover { background: #eef4f0; }
        @media (max-width: 560px) {
          .shell { padding: 1rem 0.85rem 2.5rem; }
        }
      </style>

      <div class="shell">
        <div class="page">
          <div class="brand">
            <img src="/local/home-box-logo.svg" alt="Home Box" />
          </div>
          <h1>Getting started</h1>
          <p class="lede">
            Your household appliance for local control. Day-to-day use stays on this box —
            no Tuya cloud, Nabu Casa, or Smart Life.
          </p>

          <p class="banner ok">
            You are on <strong>Home Box</strong>. Open-source Home Assistant Core powers the engine
            under the hood (see NOTICE) — the product surface is Home Box.
          </p>

          <section class="section" aria-labelledby="takeover-heading">
            <h2 id="takeover-heading">1. Takeover checklist</h2>
            <p class="muted">Confirm you own the box before day-to-day use.</p>
            <ol class="steps">
              <li>Open Home Box on your household URL (LAN or <code>https://…scardustech.com</code>).</li>
              <li>Sign in with <strong>your</strong> owner account — not an installer password you do not control.</li>
              <li>Confirm rooms and devices you expect are visible.</li>
              <li>Optional: add household members under Settings → People.</li>
              <li>Tell BMS when takeover is done so they can mark the box <code>taken_over</code>.</li>
            </ol>
            <p class="banner warn" style="margin-top:0.85rem;margin-bottom:0;">
              Takeover does not cancel the subscription. The box stays enrolled with BMS for status sharing.
            </p>
          </section>

          <section class="section" aria-labelledby="where-heading">
            <h2 id="where-heading">2. Where things live</h2>
            <p class="muted">Use these Home Box surfaces — not a Home Assistant app store.</p>
            <ul class="links">
              <li><a href="/getting-started">Getting started</a> — this page</li>
              <li><a href="/company-access">Company access</a> — sensory share to BMS (you choose sensors; companies are granted in BMS)</li>
              <li><a href="/extras">Extras</a> — what Home Box includes instead of HA add-ons</li>
              <li><a href="/enroll/">Enroll</a> — wire / reclaim the box with a BMS QR</li>
              <li><a href="/import/">Device import</a> — Tuya Local CSV / Excel</li>
            </ul>
            <div class="cta-row">
              <a class="cta" href="/company-access">Open Company access</a>
              <a class="cta secondary" href="/extras">Open Extras</a>
            </div>
          </section>

          <section class="section" aria-labelledby="iot-heading">
            <h2 id="iot-heading">3. Add more IoT (local only)</h2>
            <p class="muted">Devices talk to this box on the house LAN — never through vendor clouds from here.</p>
            <ol class="steps">
              <li>Confirm the box is online on the BMS platform.</li>
              <li>Prefer local protocols: Zigbee, Matter, <strong>Tuya Local</strong> (never Core “Tuya” cloud).</li>
              <li>For Tuya Wi‑Fi: use <a href="/import/">Device import</a> or add Tuya Local manually (IP + device id + local key). Close Smart Life first.</li>
              <li>Name devices clearly (e.g. heat pump, living room).</li>
              <li>Confirm they stay available with <strong>no vendor cloud</strong> on the IoT VLAN.</li>
            </ol>
            <p class="banner warn" style="margin-top:0.85rem;margin-bottom:0;">
              Never create a Tuya / Smart Life / Xiaomi cloud account as a Home Box step.
              Sandbox cloud registration happens off this box.
            </p>
            <div class="cta-row">
              <a class="cta secondary" href="/import/">Open device import</a>
            </div>
          </section>

          <section class="section" aria-labelledby="help-heading">
            <h2 id="help-heading">4. Get help</h2>
            <p class="muted" style="margin-bottom:0;">
              Contact BMS support through your contract — not Tuya or Xiaomi support as the remote path.
            </p>
          </section>
        </div>
      </div>
    `;
  }
}
customElements.define("home-box-getting-started", HomeBoxGettingStarted);

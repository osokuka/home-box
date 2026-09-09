/**
 * Home Box Extras — replaces the stock HA Apps / add-on store.
 * Same visual language as Company access / Getting started (shadow DOM).
 */
class HomeBoxExtras extends HTMLElement {
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
        ul.links {
          margin: 0.35rem 0 0;
          padding-left: 1.25rem;
          color: #14201a;
        }
        ul.links li { margin: 0.45rem 0; }
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
          <h1>Extras</h1>
          <p class="lede">
            Home Box is a locked-down household appliance. Extra capability is built into
            this product — not an open Home Assistant app store.
          </p>

          <p class="banner ok">
            You are on <strong>Home Box</strong>. The Home Assistant Operating System app store
            is not part of this product.
          </p>

          <section class="section" aria-labelledby="instead-heading">
            <h2 id="instead-heading">1. What you use instead</h2>
            <p class="muted">These are the Home Box surfaces for setup and sharing.</p>
            <ul class="links">
              <li><a href="/getting-started">Getting started</a> — takeover and day-to-day use</li>
              <li><a href="/company-access">Company access</a> — sensory share to BMS</li>
              <li><a href="/enroll/">Enroll</a> — wire / reclaim the box with a BMS QR</li>
              <li><a href="/import/">Device import</a> — Tuya Local CSV / Excel</li>
            </ul>
            <div class="cta-row">
              <a class="cta" href="/getting-started">Open Getting started</a>
              <a class="cta secondary" href="/company-access">Open Company access</a>
            </div>
          </section>

          <section class="section" aria-labelledby="tools-heading">
            <h2 id="tools-heading">2. Lab & reclaim tools</h2>
            <p class="muted">Same host port as Home Box — paths under the gateway.</p>
            <ul class="links">
              <li><a href="/enroll/">/enroll/</a> — enroll or reclaim with a BMS QR</li>
              <li><a href="/import/">/import/</a> — import Tuya Local devices from CSV / Excel</li>
            </ul>
            <div class="cta-row">
              <a class="cta secondary" href="/enroll/">Open Enroll</a>
              <a class="cta secondary" href="/import/">Open Device import</a>
            </div>
          </section>

          <section class="section" aria-labelledby="why-heading">
            <h2 id="why-heading">3. Why the HA Apps page is blocked</h2>
            <p class="muted" style="margin-bottom:0.65rem;">
              Home Box runs a locked Core engine without Supervisor add-ons. That keeps
              the house local and private. If you opened Settings → Apps, you were sent here
              on purpose.
            </p>
            <p class="banner warn" style="margin-bottom:0;">
              Do not install Home Assistant OS apps on this appliance. Use Getting started,
              Company access, Enroll, and Device import instead.
            </p>
          </section>
        </div>
      </div>
    `;
  }
}
customElements.define("home-box-extras", HomeBoxExtras);

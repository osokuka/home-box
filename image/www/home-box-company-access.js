class HomeBoxCompanyAccess extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <style>
        :host { display: block; padding: 24px; max-width: 44rem; font-family: system-ui, sans-serif; line-height: 1.45; color: #1a1f1c; }
        h1 { font-size: 1.4rem; margin: 0 0 0.5rem; }
        h2 { font-size: 1.1rem; margin: 1.4rem 0 0.45rem; }
        code { background: #e8eee9; padding: 0.1em 0.35em; }
        ol { padding-left: 1.2rem; }
        .warn { border-left: 4px solid #c4a35a; padding-left: 12px; }
        .brand { display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; }
        .brand img { height: 40px; }
      </style>
      <div class="brand">
        <img src="/local/home-box-logo.svg" alt="Home Box" />
      </div>
      <h1>Company access</h1>
      <p class="warn">
        BMS staff do not create Home Box logins for HVAC or other trades.
        You own this house. You decide who can open it.
      </p>
      <p>
        Day-to-day, companies only get <strong>read-only status</strong> through our platform
        (temperatures, on/off state). They cannot turn devices on or off that way.
      </p>
      <h2>If a technician needs to look inside Home Box</h2>
      <ol>
        <li>Settings → People → Add person.</li>
        <li>Enable login. Do <strong>not</strong> make them Administrator.</li>
        <li>Give them a password yourself. Do not reuse yours.</li>
        <li>They open the household URL (lab: <code>http://windows-lab.ha.localhost:8080</code>). Remote VPN comes later.</li>
        <li>For <strong>view only</strong> (no on/off), after the user exists ask us for the read-only group helper —
            or stop Home Box and set that user’s <code>group_ids</code> to <code>["system-read-only"]</code> in
            <code>config/.storage/auth</code>, then start again. We still will not set the password.</li>
      </ol>
      <p>
        To take access back: Settings → People → remove the person / disable the login.
        Revoking platform sharing is separate and does not delete this Home Box user.
      </p>
    `;
  }
}
customElements.define("home-box-company-access", HomeBoxCompanyAccess);

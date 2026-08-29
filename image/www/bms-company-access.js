class BmsCompanyAccess extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <style>
        :host { display: block; padding: 24px; max-width: 44rem; font-family: system-ui, sans-serif; line-height: 1.45; }
        h1 { font-size: 1.4rem; }
        code { background: #eee; padding: 0.1em 0.35em; }
        ol { padding-left: 1.2rem; }
        .warn { border-left: 4px solid #c4a35a; padding-left: 12px; }
      </style>
      <h1>Company access (Home Box owner)</h1>
      <p class="warn">
        BMS staff do not create Home Box logins for HVAC or other trades.
        You own this house. You decide who can open it.
      </p>
      <p>
        Day-to-day, companies only get <strong>read-only status</strong> through our platform
        (temperatures, on/off state). They cannot turn devices on or off that way.
      </p>
      <p>
        If a technician needs to look around in Home Box itself, you create their account:
      </p>
      <ol>
        <li>Settings → People → Add person.</li>
        <li>Enable login. Do <strong>not</strong> make them Administrator.</li>
        <li>Give them a password yourself. Do not reuse yours.</li>
        <li>They open the same household hostname as the rest of BMS
            (lab: <code>http://windows-lab.ha.localhost:8080</code>). WireGuard is later.</li>
        <li>A normal non-admin user can still toggle devices. For <strong>view only</strong>
            (no on/off), after the user exists, stop Home Assistant and in
            <code>config/.storage/auth</code> set that user’s
            <code>group_ids</code> to <code>["system-read-only"]</code>, then start it again.
            Or ask us for a scripted helper later — we still will not set the password.</li>
      </ol>
      <p>
        To take access back: Settings → People → remove the person / disable the login.
        Revoking platform sharing is separate and does not delete this HA user.
      </p>
    `;
  }
}
customElements.define("bms-company-access", BmsCompanyAccess);

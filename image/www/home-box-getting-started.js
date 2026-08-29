class HomeBoxGettingStarted extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <style>
        :host { display: block; padding: 24px; max-width: 48rem; font-family: system-ui, sans-serif; line-height: 1.45; color: #1a1f1c; }
        h1 { font-size: 1.4rem; margin: 0 0 0.5rem; }
        h2 { font-size: 1.1rem; margin: 1.35rem 0 0.4rem; }
        code { background: #e8eee9; padding: 0.1em 0.35em; }
        ol, ul { padding-left: 1.2rem; }
        .warn { border-left: 4px solid #c4a35a; padding-left: 12px; }
        .ok { border-left: 4px solid #2f6f4e; padding-left: 12px; }
        .brand { margin-bottom: 1rem; }
        .brand img { height: 40px; }
      </style>
      <div class="brand"><img src="/local/home-box-logo.svg" alt="Home Box" /></div>
      <h1>Getting started</h1>
      <p class="ok">This is <strong>Home Box</strong>. The engine underneath is Home Assistant Core (open source). You do not need Tuya cloud, Nabu Casa, or Smart Life for day-to-day use.</p>

      <h2>1. Takeover checklist</h2>
      <ol>
        <li>Open Home Box on your household URL (lab: <code>http://windows-lab.ha.localhost:8080</code> or LAN <code>http://192.168.0.10:8123</code>).</li>
        <li>Sign in with <strong>your</strong> owner account (not a leftover installer password you do not control).</li>
        <li>Confirm you can see rooms/devices already paired.</li>
        <li>Optional: add household members under Settings → People.</li>
        <li>Tell BMS staff when takeover is done so they can mark the box <code>taken_over</code> on the platform.</li>
      </ol>
      <p class="warn">Takeover does not cancel the subscription. The box stays enrolled with BMS for status sharing.</p>

      <h2>2. Where things live</h2>
      <ul>
        <li>Home Box UI — this screen and the sidebar.</li>
        <li>Company monitoring — only after you enable <strong>Limited share</strong> on Company access <em>and</em> grant that company in BMS (status/support only, no on/off).</li>
        <li>Enroll / re-enroll lab tools — <code>http://127.0.0.1:8099/</code> (QR from BMS).</li>
        <li>Tuya device CSV import — <code>http://127.0.0.1:8098/</code>.</li>
      </ul>

      <h2>3. Add more IoT (local only)</h2>
      <ol>
        <li>Confirm the box is online on the BMS platform.</li>
        <li>Prefer local protocols: Zigbee, Matter, <strong>Tuya Local</strong> (never Core “Tuya” cloud).</li>
        <li>For Tuya Wi‑Fi: import CSV or add Tuya Local → manual (IP + device id + local key). Close Smart Life first.</li>
        <li>Name devices clearly (e.g. heat pump, living room).</li>
        <li>Confirm they stay available with <strong>no vendor cloud</strong> on the IoT VLAN.</li>
      </ol>
      <p class="warn">Never create a Tuya/Smart Life/Xiaomi cloud account as a Home Box step. Sandbox cloud registration happens off this box.</p>

      <h2>4. Get help</h2>
      <p>Contact BMS support through your contract — not Tuya or Xiaomi support as the remote path.</p>
    `;
  }
}
customElements.define("home-box-getting-started", HomeBoxGettingStarted);

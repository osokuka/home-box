/**
 * Home Box surface branding for the HA frontend (no Core fork).
 * Loaded via frontend.extra_module_url.
 * Replaces visible "Home Assistant" product chrome with "Home Box".
 */
const BRAND = "Home Box";
const HA_NAME = /Home Assistant/g;

function brandTitle() {
  const t = document.title || "";
  if (HA_NAME.test(t) || !t.trim()) {
    document.title = (t || BRAND).replace(HA_NAME, BRAND) || BRAND;
  } else if (t === "Home" || t.startsWith("Home –") || t.startsWith("Home -")) {
    document.title = t.replace(/^Home\b/, BRAND);
  }
}

function setMeta() {
  let app = document.querySelector('meta[name="application-name"]');
  if (!app) {
    app = document.createElement("meta");
    app.setAttribute("name", "application-name");
    document.head.appendChild(app);
  }
  app.setAttribute("content", BRAND);

  let apple = document.querySelector('meta[name="apple-mobile-web-app-title"]');
  if (!apple) {
    apple = document.createElement("meta");
    apple.setAttribute("name", "apple-mobile-web-app-title");
    document.head.appendChild(apple);
  }
  apple.setAttribute("content", BRAND);
}

function patchNodeText(root) {
  if (!root) return;
  const titles = root.querySelectorAll?.(".title, .main-title, .header .name") || [];
  titles.forEach((el) => {
    if (el.childElementCount === 0 && HA_NAME.test(el.textContent || "")) {
      el.textContent = (el.textContent || "").replace(HA_NAME, BRAND);
    }
  });
}

function patchSidebar() {
  document.querySelectorAll("ha-sidebar").forEach((el) => {
    try {
      el.sidebarTitle = BRAND;
      el.setAttribute("sidebar-title", BRAND);
    } catch (_) {
      /* ignore */
    }
    if (el.shadowRoot) {
      patchNodeText(el.shadowRoot);
      const title = el.shadowRoot.querySelector(".title");
      if (title) title.textContent = BRAND;
    }
  });
}

function patchLogin() {
  document.querySelectorAll("ha-authorize, ha-login-form, home-assistant").forEach((el) => {
    if (el.shadowRoot) patchNodeText(el.shadowRoot);
  });
  // Visible headings on authorize card
  document.querySelectorAll("h1, h2, .card-header").forEach((el) => {
    if (HA_NAME.test(el.textContent || "")) {
      el.textContent = (el.textContent || "").replace(HA_NAME, BRAND);
    }
  });
}

function patchDeep(node) {
  if (!node) return;
  if (node.nodeType === Node.ELEMENT_NODE) {
    if (node.shadowRoot) {
      patchNodeText(node.shadowRoot);
      patchDeepWalk(node.shadowRoot);
    }
  }
}

function patchDeepWalk(root) {
  root.querySelectorAll?.("*").forEach((el) => {
    if (el.shadowRoot) {
      patchNodeText(el.shadowRoot);
      patchDeepWalk(el.shadowRoot);
    }
  });
}

function apply() {
  brandTitle();
  setMeta();
  patchSidebar();
  patchLogin();
  patchDeep(document.body);
}

apply();
setInterval(apply, 1500);

const obs = new MutationObserver(() => apply());
if (document.body) {
  obs.observe(document.body, { childList: true, subtree: true, characterData: true });
} else {
  document.addEventListener("DOMContentLoaded", () => {
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
    apply();
  });
}

window.addEventListener("location-changed", apply);
window.addEventListener("popstate", apply);

console.info("[home-box-brand] product chrome →", BRAND);

/**
 * Home Box product chrome (minimal).
 * Asset patches already brand most UI strings.
 * This module keeps the tab title + sidebar label stable, and diverts the
 * stock Home Assistant Apps / add-on store routes to Home Box Extras.
 * Do NOT rewrite arbitrary DOM — that breaks Settings dialogs (People, etc.).
 */
const BRAND = "Home Box";
const HA_RE = /Home Assistant/g;
const APPS_RE = /^\/config\/apps(\/|$)/i;
const EXTRAS_PATH = "/extras";

(function patchDocumentTitle() {
  const desc = Object.getOwnPropertyDescriptor(Document.prototype, "title");
  if (!desc?.set || !desc?.get) return;
  Object.defineProperty(document, "title", {
    configurable: true,
    enumerable: true,
    get() {
      return desc.get.call(this);
    },
    set(value) {
      desc.set.call(this, String(value ?? "").replace(HA_RE, BRAND) || BRAND);
    },
  });
  document.title = document.title;
})();

function paintSidebarTitle(el) {
  if (!el?.shadowRoot) return;
  const title = el.shadowRoot.querySelector(".title");
  if (title && title.textContent !== BRAND) {
    title.textContent = BRAND;
  }
}

function forceSidebar(el) {
  if (!el) return;
  try {
    if (el.sidebarTitle !== BRAND) {
      el.sidebarTitle = BRAND;
      el.setAttribute("sidebar-title", BRAND);
    }
  } catch (_) {
    /* ignore */
  }
  paintSidebarTitle(el);
}

function divertHaAppsRoute() {
  const path = location.pathname || "";
  if (!APPS_RE.test(path)) return false;
  location.replace(EXTRAS_PATH);
  return true;
}

customElements.whenDefined("ha-sidebar").then(() => {
  const Ctor = customElements.get("ha-sidebar");
  if (!Ctor?.prototype) return;
  const proto = Ctor.prototype;
  const origConnected = proto.connectedCallback;
  proto.connectedCallback = function connectedCallback() {
    if (typeof origConnected === "function") origConnected.call(this);
    this.sidebarTitle = BRAND;
    this.setAttribute("sidebar-title", BRAND);
    queueMicrotask(() => paintSidebarTitle(this));
  };
  const origUpdated = proto.updated;
  proto.updated = function updated(changed) {
    if (typeof origUpdated === "function") origUpdated.call(this, changed);
    paintSidebarTitle(this);
  };
  document.querySelectorAll("ha-sidebar").forEach(forceSidebar);
});

// Occasional sidebar refresh only (no MutationObserver / no global text rewrite)
setInterval(() => {
  document.querySelectorAll("ha-sidebar").forEach(forceSidebar);
}, 3000);

// Divert stock HA Apps routes as soon as this module loads, and on SPA navigations.
divertHaAppsRoute();
window.addEventListener("popstate", divertHaAppsRoute);
const _pushState = history.pushState.bind(history);
const _replaceState = history.replaceState.bind(history);
history.pushState = function pushState(state, title, url) {
  const ret = _pushState(state, title, url);
  queueMicrotask(divertHaAppsRoute);
  return ret;
};
history.replaceState = function replaceState(state, title, url) {
  const ret = _replaceState(state, title, url);
  queueMicrotask(divertHaAppsRoute);
  return ret;
};

console.info("[home-box-brand] minimal chrome →", BRAND, "(apps → extras)");

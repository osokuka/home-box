/**
 * Home Box product chrome — survives HA frontend rewrites.
 * panel-title-mixin sets document.title to "… – Home Assistant".
 * ha-sidebar defaults sidebarTitle to "Home Assistant".
 */
const BRAND = "Home Box";
const HA_RE = /Home Assistant/g;

function brandize(text) {
  return String(text ?? "").replace(HA_RE, BRAND);
}

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
      desc.set.call(this, brandize(value) || BRAND);
    },
  });
  document.title = document.title;
})();

function setMeta() {
  for (const [name, content] of [
    ["application-name", BRAND],
    ["apple-mobile-web-app-title", BRAND],
  ]) {
    let el = document.querySelector(`meta[name="${name}"]`);
    if (!el) {
      el = document.createElement("meta");
      el.setAttribute("name", name);
      document.head.appendChild(el);
    }
    el.setAttribute("content", content);
  }
}

function patchLaunchScreen() {
  const screen = document.getElementById("ha-launch-screen");
  if (!screen) return;
  const logo = screen.querySelector("img.ha-logo, .ha-logo");
  if (logo && !logo.dataset.hbLogo) {
    logo.dataset.hbLogo = "1";
    logo.setAttribute("alt", BRAND);
    logo.setAttribute("src", "/local/home-box-logo.svg");
    logo.style.width = "120px";
    logo.style.height = "auto";
  }
  screen.querySelectorAll("*").forEach((el) => {
    if (el.childElementCount === 0 && HA_RE.test(el.textContent || "")) {
      el.textContent = brandize(el.textContent);
    }
  });
}

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

function patchAllSidebars() {
  document.querySelectorAll("ha-sidebar").forEach(forceSidebar);
}

function apply() {
  setMeta();
  patchLaunchScreen();
  patchAllSidebars();
  if (HA_RE.test(document.title || "")) {
    document.title = brandize(document.title);
  }
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

  // After Lit paints, overwrite the visible label (do not set property here — avoids loops)
  const origUpdated = proto.updated;
  proto.updated = function updated(changed) {
    if (typeof origUpdated === "function") origUpdated.call(this, changed);
    paintSidebarTitle(this);
  };

  patchAllSidebars();
});

setMeta();
apply();

let n = 0;
const boot = setInterval(() => {
  apply();
  if (++n >= 50) clearInterval(boot);
}, 200);
setInterval(apply, 2000);

const obs = new MutationObserver(() => apply());
const startObs = () => {
  obs.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
};
if (document.body) startObs();
else document.addEventListener("DOMContentLoaded", startObs);

window.addEventListener("location-changed", apply);
window.addEventListener("popstate", apply);

console.info("[home-box-brand] active →", BRAND);

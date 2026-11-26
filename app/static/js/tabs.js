/* Page tabs in the top bar, as in a browser. A tab opens only with + and
   starts on Home; every page gone to stays in the tab it was opened in (the
   tab takes its name); clicking a tab goes back to its page; × closes one.
   The tabs are kept in this browser for this login; which one is open, for
   each browser window. Nothing goes to the server. */
(function () {
  var strip = document.getElementById("erp-tabs");
  if (!strip) return;
  var USER = strip.dataset.user || "";
  var KEY = "bos-tabs:" + USER, ON = "bos-tab-on:" + USER;
  var HOME = strip.dataset.home || "/";
  var MAX = 8;

  function read(store, key, fallback) {
    try { var v = store.getItem(key); return v === null ? fallback : v; } catch (e) { return fallback; }
  }
  function write(store, key, value) {
    try { store.setItem(key, value); } catch (e) { /* private window: the tabs last this page */ }
  }
  function load() {
    try { var v = JSON.parse(read(localStorage, KEY, "[]")); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  }
  function keep() { write(localStorage, KEY, JSON.stringify(tabs)); }
  function open(id) { write(sessionStorage, ON, id); }
  function newId() { return "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

  // this page's name: Home for the dashboard, else the page title, with the programme code
  function nameOf(path) {
    if (path === HOME || path === HOME.replace(/\/$/, "")) return "Home";
    var t = (document.title || "").split(" · ")[0].split(" — ")[0].trim() || "Page";
    var m = path.match(/\/stage\/prog_[a-z0-9_]+\/([A-Za-z0-9-]+)/);
    if (m) t += " · " + m[1];
    return t.length > 34 ? t.slice(0, 33) + "…" : t;
  }

  var tabs = load().filter(function (t) { return t && t.id && t.url; });
  // the sign-in steps are not pages a tab keeps
  if (/\/(who|terms|intro|login|logout)(\/|$)/.test(location.pathname)) return;

  var here = location.pathname + location.search;
  var onId = read(sessionStorage, ON, "");
  var cur = tabs.find(function (t) { return t.id === onId; }) || tabs[0];
  if (!cur) {
    cur = { id: newId() };
    tabs.push(cur);
  }
  // this page belongs to the open tab: it takes the page and its name
  cur.url = here;
  cur.title = nameOf(location.pathname);
  open(cur.id);
  keep();

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function go(t) {
    open(t.id);
    keep();
    location.href = t.url;
  }
  function draw() {
    strip.textContent = "";
    tabs.forEach(function (t, i) {
      var on = t.id === cur.id;
      var tab = el("div", "erp-tab" + (on ? " is-on" : ""));
      var a = el("a", "erp-tab-link", t.title);
      a.href = t.url;
      a.title = t.title;
      if (on) a.setAttribute("aria-current", "page");
      a.addEventListener("click", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;   // the browser's own new tab
        e.preventDefault();
        if (!on) go(t);
      });
      tab.appendChild(a);
      var x = el("button", "erp-tab-x", "×");
      x.type = "button";
      x.title = "Close " + t.title;
      x.setAttribute("aria-label", "Close " + t.title);
      x.addEventListener("click", function () {
        tabs.splice(i, 1);
        if (!on) { keep(); draw(); return; }
        // the open tab closed: the one beside it opens, or a fresh Home tab
        var next = tabs[i] || tabs[i - 1];
        if (!next) { next = { id: newId(), url: HOME, title: "Home" }; tabs.push(next); }
        go(next);
      });
      tab.appendChild(x);
      strip.appendChild(tab);
    });
    if (tabs.length < MAX) {
      var plus = el("button", "erp-tab-new", "+");
      plus.type = "button";
      plus.title = "New tab — opens on Home";
      plus.setAttribute("aria-label", "New tab — opens on Home");
      plus.addEventListener("click", function () {
        var t = { id: newId(), url: HOME, title: "Home" };
        tabs.push(t);
        go(t);
      });
      strip.appendChild(plus);
    }
  }
  draw();
  strip.hidden = false;
  var shown = strip.querySelector(".erp-tab.is-on");
  if (shown && shown.scrollIntoView) shown.scrollIntoView({ block: "nearest", inline: "nearest" });
  var name = document.querySelector(".erp-bar-name");
  if (name) name.hidden = true;
})();

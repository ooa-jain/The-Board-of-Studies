/* Page tabs in the top bar: every page opened becomes a tab (Home,
   Curriculum · BCAAIN, Reports …), as in a browser. × closes one, + opens
   Home. Kept in this browser for this login only; nothing goes to the server. */
(function () {
  var strip = document.getElementById("erp-tabs");
  if (!strip) return;
  var KEY = "bos-tabs:" + (strip.dataset.user || "");
  var HOME = strip.dataset.home || "/";
  var MAX = 6;

  function load() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v : []; }
    catch (e) { return []; }
  }
  function keep(tabs) {
    try { localStorage.setItem(KEY, JSON.stringify(tabs)); } catch (e) { /* private window: tabs last this page */ }
  }
  // this page's name: Home for the dashboard, else the page title, with the programme code
  function nameOf(path) {
    if (path === HOME || path === HOME.replace(/\/$/, "")) return "Home";
    var t = (document.title || "").split(" · ")[0].split(" — ")[0].trim() || "Page";
    var m = path.match(/\/stage\/prog_[a-z0-9_]+\/([A-Za-z0-9-]+)/);
    if (m) t += " · " + m[1];
    return t.length > 34 ? t.slice(0, 33) + "…" : t;
  }

  var here = location.pathname + location.search;
  // the sign-in steps are not pages to come back to
  var passing = /\/(who|terms|intro|login|logout)(\/|$)/.test(location.pathname);
  var tabs = load().filter(function (t) { return t && t.url && !/\/(who|terms|intro|login|logout)(\/|\?|$)/.test(t.url); });
  if (passing) { keep(tabs); return; }
  var mine = tabs.find(function (t) { return t.url === here; });
  if (mine) mine.title = nameOf(location.pathname);
  else tabs.push({ url: here, title: nameOf(location.pathname) });
  // too many: the oldest that is not this page goes
  while (tabs.length > MAX) {
    var i = tabs.findIndex(function (t) { return t.url !== here; });
    tabs.splice(i < 0 ? 0 : i, 1);
  }
  keep(tabs);

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function draw() {
    strip.textContent = "";
    tabs.forEach(function (t, i) {
      var on = t.url === here;
      var tab = el("div", "erp-tab" + (on ? " is-on" : ""));
      var a = el("a", "erp-tab-link", t.title);
      a.href = t.url;
      a.title = t.title;
      if (on) a.setAttribute("aria-current", "page");
      tab.appendChild(a);
      var x = el("button", "erp-tab-x", "×");
      x.type = "button";
      x.title = "Close " + t.title;
      x.setAttribute("aria-label", "Close " + t.title);
      x.addEventListener("click", function () {
        tabs.splice(i, 1);
        keep(tabs);
        if (on) {
          // closing this page's tab: go to the one beside it, or Home
          var next = tabs[i] || tabs[i - 1];
          location.href = next ? next.url : HOME;
        } else {
          draw();
        }
      });
      tab.appendChild(x);
      strip.appendChild(tab);
    });
    var plus = el("a", "erp-tab-new", "+");
    plus.href = HOME;
    plus.title = "New tab — Home";
    plus.setAttribute("aria-label", "New tab — Home");
    strip.appendChild(plus);
  }
  draw();
  strip.hidden = false;
  var on = strip.querySelector(".erp-tab.is-on");
  if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  var name = document.querySelector(".erp-bar-name");
  if (name) name.hidden = true;
})();

/* Light and dark: the switch on every page.

   The choice is kept on this browser (bos.theme); until someone chooses,
   the portal follows the computer's own setting. Switching spreads the new
   look out from the switch in a circle (where the browser can animate a
   page change), and tells anything drawn on a canvas — Flow 3D — to repaint
   in the new colours ("themechange"). */
(function () {
  "use strict";
  var KEY = "bos.theme", root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function current() { return root.getAttribute("data-theme") === "dark" ? "dark" : "light"; }
  function chosen() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }

  function paint() {
    var dark = current() === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      var words = dark ? "Switch to light mode" : "Switch to dark mode";
      b.setAttribute("aria-pressed", dark ? "true" : "false");
      b.setAttribute("aria-label", words);
      b.title = words;
    });
    // the university's logo: the light one, made for dark grounds, in dark mode
    document.querySelectorAll('img[src*="/img/jain-logo"]').forEach(function (img) {
      var src = img.getAttribute("src");
      var want = dark ? src.replace("/img/jain-logo.png", "/img/jain-logo-light.png")
                      : src.replace("/img/jain-logo-light.png", "/img/jain-logo.png");
      if (want !== src) img.setAttribute("src", want);
    });
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#0b0f16" : "#091324");
  }

  function apply(next, keep) {
    root.setAttribute("data-theme", next);
    if (keep) { try { localStorage.setItem(KEY, next); } catch (e) { /* this visit only */ } }
    paint();
    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: next } }));
  }

  function toggle(btn) {
    var next = current() === "dark" ? "light" : "dark";
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || still) { apply(next, true); return; }
    var r = btn.getBoundingClientRect();
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    var end = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    root.classList.add("theme-turning");
    var t = document.startViewTransition(function () { apply(next, true); });
    t.ready.then(function () {
      root.animate({ clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + end + "px at " + x + "px " + y + "px)"] },
                   { duration: 650, easing: "cubic-bezier(.65, 0, .35, 1)", pseudoElement: "::view-transition-new(root)" });
    }).catch(function () {});
    t.finished.then(function () { root.classList.remove("theme-turning"); },
                    function () { root.classList.remove("theme-turning"); });
  }

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (b) { e.preventDefault(); toggle(b); }
  });
  // following the computer, until a choice is made here
  if (mq && mq.addEventListener) {
    mq.addEventListener("change", function (e) { if (!chosen()) apply(e.matches ? "dark" : "light", false); });
  }
  // printing is always on white paper
  window.addEventListener("beforeprint", function () { root.setAttribute("data-print-was", current()); root.setAttribute("data-theme", "light"); });
  window.addEventListener("afterprint", function () {
    var was = root.getAttribute("data-print-was");
    if (was) { root.setAttribute("data-theme", was); root.removeAttribute("data-print-was"); }
  });
  paint();
})();

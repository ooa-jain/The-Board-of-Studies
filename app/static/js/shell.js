/* The left menu (after Aceternity UI's sidebar).

   Wide screens: the menu is open with its labels, or collapsed to a rail of
   icons — the button at its top switches between the two, the width and the
   labels animating as they go. Hovering never opens or closes it: it stays as
   it was left, and the choice is remembered on this computer. Collapsed, each
   icon shows its name on hover.

   Phones: the menu button opens the menu as a full-screen panel sliding in
   from the left; the X, Escape or following a link closes it. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "bos.side";
  var collapse = document.getElementById("side-collapse");
  var nav = document.getElementById("topnav");
  var toggle = document.getElementById("nav-toggle");

  function setCollapsed(on, remember) {
    root.classList.toggle("side-collapsed", on);
    if (collapse) {
      collapse.setAttribute("aria-expanded", on ? "false" : "true");
      var label = on ? "Expand the menu" : "Collapse the menu";
      collapse.title = label;
      var sr = collapse.querySelector(".sr-only");
      if (sr) sr.textContent = label;
    }
    if (remember) {
      try { localStorage.setItem(KEY, on ? "collapsed" : "open"); } catch (e) { /* private window */ }
    }
  }

  // the state the head script set before the first paint, now with its labels
  setCollapsed(root.classList.contains("side-collapsed"), false);
  // let the first paint settle before widths animate, so a collapsed menu
  // does not slide shut on every page
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { root.classList.add("side-ready"); });
  });

  if (collapse) {
    collapse.addEventListener("click", function () {
      setCollapsed(!root.classList.contains("side-collapsed"), true);
    });
  }
  // [ on the keyboard, outside a text box, does the same
  document.addEventListener("keydown", function (e) {
    if (e.key !== "[" || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (window.innerWidth <= 900) return;
    setCollapsed(!root.classList.contains("side-collapsed"), true);
  });

  // phones: the X inside the full-screen menu closes it
  if (nav && toggle) {
    nav.addEventListener("click", function (e) {
      if (e.target.closest("[data-side-close]")) { toggle.click(); return; }
      if (e.target.closest("a[href]") && nav.dataset.open === "true") {
        nav.dataset.open = "false";
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }
})();

/* =========================================================================
   The branched stage menu.

   The markup already works on its own: every group is a button with
   aria-expanded, every stage is a link, and with JavaScript off the open
   groups stay open. This file adds the two things that need scripting — the
   fold, and re-drawing the branch lines when a group opens, so the lines are
   drawn each time rather than only on the first paint.
   ========================================================================= */
(function () {
  "use strict";

  var nav = document.querySelector("[data-branch]");
  if (!nav) return;

  var FOLD_VAR = "--draw";

  function ms(el, name, fallback) {
    var v = getComputedStyle(el).getPropertyValue(name).trim();
    var n = parseFloat(v);
    if (isNaN(n)) return fallback;
    return /ms$/.test(v) ? n : n * 1000;
  }

  /* Re-running a CSS animation needs the class off, a reflow, then the class
     on again; there is no other way to rewind one. */
  function draw(list) {
    var rows = list.querySelectorAll(".branch-row").length;
    var unit = ms(list, FOLD_VAR, 400);
    list.classList.remove("is-drawing");
    void list.offsetWidth;
    list.classList.add("is-drawing");
    window.setTimeout(function () {
      list.classList.remove("is-drawing");
    }, unit * (rows / 5 + 1.2) + 80);
  }

  function setOpen(btn, list, open) {
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    list.dataset.open = open ? "true" : "false";
    if (open) draw(list);
  }

  nav.addEventListener("click", function (e) {
    var btn = e.target.closest(".branch-parent");
    if (!btn) return;
    var list = document.getElementById(btn.getAttribute("aria-controls"));
    if (!list) return;
    setOpen(btn, list, btn.getAttribute("aria-expanded") !== "true");
  });

  // draw the group you are already inside, and bring it into view inside the
  // panel's own scroll box
  Array.prototype.forEach.call(
    nav.querySelectorAll('.branch-children[data-open="true"]'),
    function (list) { draw(list); }
  );

  var here = nav.querySelector(".branch-row.is-here");
  var box = nav.querySelector(".scroll-300");
  if (here && box && box.scrollHeight > box.clientHeight) {
    box.scrollTop = Math.max(0, here.offsetTop - box.clientHeight / 2);
  }
})();

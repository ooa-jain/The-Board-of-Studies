/* One tooltip for every chart mark on the Office's pages. A mark carries
   data-tip="value|what|detail"; hovering or focusing it shows the value
   first, then what it is. Text only, through textContent. Listens on the
   page rather than on each mark, so marks swapped in by the live home
   (js/admin-live.js) work too. */
(function () {
  if (!document.querySelector("[data-tip]")) return;
  var tip = document.createElement("div");
  tip.className = "cx-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  var v = document.createElement("b"), w = document.createElement("span"), d = document.createElement("small");
  tip.appendChild(v); tip.appendChild(w); tip.appendChild(d);
  document.body.appendChild(tip);
  var hot = null;

  function show(el, x, y) {
    var parts = (el.getAttribute("data-tip") || "").split("|");
    v.textContent = parts[0] || "";
    w.textContent = parts[1] || "";
    d.textContent = parts[2] || "";
    d.hidden = !parts[2];
    tip.hidden = false;
    var r = tip.getBoundingClientRect();
    var left = Math.min(window.innerWidth - r.width - 8, Math.max(8, x - r.width / 2));
    var top = y - r.height - 12;
    if (top < 8) top = y + 18;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
    if (hot && hot !== el) hot.classList.remove("is-hot");
    hot = el;
    el.classList.add("is-hot");
  }
  function hide() { tip.hidden = true; if (hot) hot.classList.remove("is-hot"); hot = null; }

  document.addEventListener("pointermove", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el) show(el, e.clientX, e.clientY); else if (hot) hide();
  });
  document.addEventListener("focusin", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (!el) return;
    var r = el.getBoundingClientRect();
    show(el, r.left + r.width / 2, r.top);
  });
  document.addEventListener("focusout", function (e) {
    if (e.target.closest && e.target.closest("[data-tip]")) hide();
  });
  window.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
})();

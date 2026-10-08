/* One tooltip for every chart mark on the Office's pages. A mark carries
   data-tip="value|what|detail"; hovering or focusing it shows the value
   first, then what it is. Text only, through textContent. */
(function () {
  var marks = document.querySelectorAll("[data-tip]");
  if (!marks.length) return;
  var tip = document.createElement("div");
  tip.className = "cx-tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  var v = document.createElement("b"), w = document.createElement("span"), d = document.createElement("small");
  tip.appendChild(v); tip.appendChild(w); tip.appendChild(d);
  document.body.appendChild(tip);

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
    el.classList.add("is-hot");
  }
  function hide(el) { tip.hidden = true; if (el) el.classList.remove("is-hot"); }

  marks.forEach(function (el) {
    el.addEventListener("pointermove", function (e) { show(el, e.clientX, e.clientY); });
    el.addEventListener("pointerleave", function () { hide(el); });
    el.addEventListener("focus", function () {
      var r = el.getBoundingClientRect();
      show(el, r.left + r.width / 2, r.top);
    });
    el.addEventListener("blur", function () { hide(el); });
  });
  window.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
})();

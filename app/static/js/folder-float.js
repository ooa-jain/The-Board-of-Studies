/* =========================================================================
   FolderFloat.

   A folder that opens and fans its papers out. The markup it upgrades is an
   ordinary list, so with the script blocked, or before it runs, the same
   words are on the page and readable — the folder is decoration over a list,
   not a replacement for one.

   The numbers come from the specification and are read off the element:
   width, height, radius, spread, lift, tilt, flapAngle, restAngle,
   openDuration, stagger, bounce, drift, trigger, closeOnSelect. The greys in
   the specification are for a dark page; here the folder takes the JAIN navy
   and the papers the warm ivory.

   It opens on hover, on focus and on click — hover alone would leave it shut
   for anybody on a touchscreen or a keyboard.
   ========================================================================= */
(function () {
  "use strict";

  var REDUCED = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function num(el, name, fallback) {
    var v = parseFloat(el.dataset[name]);
    return isNaN(v) ? fallback : v;
  }

  function build(root) {
    var list = root.querySelector(".folder-items");
    if (!list) return;

    var o = {
      width: num(root, "width", 200),
      height: num(root, "height", 148),
      radius: num(root, "radius", 14),
      spread: num(root, "spread", 180),
      lift: num(root, "lift", 26),
      tilt: num(root, "tilt", 8),
      flapAngle: num(root, "flapAngle", 34),
      restAngle: num(root, "restAngle", 16),
      openDuration: num(root, "openDuration", 520),
      stagger: num(root, "stagger", 45),
      bounce: num(root, "bounce", 0.3),
      drift: num(root, "drift", 0.5),
      trigger: root.dataset.trigger || "hover",
      closeOnSelect: root.dataset.closeOnSelect !== "false"
    };

    var papers = Array.prototype.slice.call(list.children);
    if (!papers.length) return;

    /* ---- the shell ---- */
    root.style.setProperty("--fw", o.width + "px");
    root.style.setProperty("--fh", o.height + "px");
    root.style.setProperty("--fr", o.radius + "px");
    root.style.setProperty("--flap", o.flapAngle + "deg");
    root.style.setProperty("--rest", o.restAngle + "deg");
    root.style.setProperty("--dur", o.openDuration + "ms");
    // bounce becomes the overshoot of the easing curve
    root.style.setProperty("--ease",
      "cubic-bezier(.34," + (1 + o.bounce * 1.9) + ",.5," + (1 - o.bounce * 0.3) + ")");

    var stage = document.createElement("div");
    stage.className = "folder-stage";

    var back = document.createElement("span");
    back.className = "folder-back";
    back.setAttribute("aria-hidden", "true");

    var front = document.createElement("span");
    front.className = "folder-front";
    front.setAttribute("aria-hidden", "true");

    var tab = document.createElement("span");
    tab.className = "folder-tab";
    tab.setAttribute("aria-hidden", "true");

    /* ---- the papers ----
       Each one is laid across an arc: spread wide, lift high, tilt turned.
       The middle paper rises highest, which is what makes it read as a fan
       rather than a staircase.

       The spread is a ceiling rather than a fixed width. Six papers fanned
       across a narrow column would sit on top of each other and none of them
       could be read, so the fan takes the room it has and no more — on a
       phone that means a neat stack. */
    var n = papers.length;
    var PAPER = 150;

    function layout() {
      var room = root.getBoundingClientRect().width || o.spread + PAPER;
      var spread = Math.max(0, Math.min(o.spread, room - PAPER - 16));
      papers.forEach(function (li, i) {
        var t = n === 1 ? 0.5 : i / (n - 1);     // 0..1 across the fan
        var arc = Math.sin(t * Math.PI);          // 0 at the ends, 1 in the middle
        li.style.setProperty("--px", ((t - 0.5) * spread).toFixed(1) + "px");
        li.style.setProperty("--py", (-(o.lift + arc * o.lift * 0.55)).toFixed(1) + "px");
        li.style.setProperty("--prot", ((t - 0.5) * 2 * o.tilt).toFixed(2) + "deg");
      });
    }

    papers.forEach(function (li, i) {
      li.className = "folder-paper";
      li.style.setProperty("--pdelay", (i * o.stagger) + "ms");
      li.style.zIndex = String(10 + i);

      // a paper is a button: it can be chosen, and reached by keyboard
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "folder-paper-btn";
      while (li.firstChild) btn.appendChild(li.firstChild);
      li.appendChild(btn);
      btn.addEventListener("click", function () {
        select(li, i, btn);
      });
    });

    list.classList.add("is-fanned");
    stage.appendChild(back);
    stage.appendChild(tab);
    stage.appendChild(list);
    stage.appendChild(front);

    var label = document.createElement("div");
    label.className = "folder-label";
    label.innerHTML = "";
    var strong = document.createElement("strong");
    strong.textContent = root.dataset.label || "";
    var small = document.createElement("span");
    small.textContent = root.dataset.sublabel || "";
    label.appendChild(strong);
    label.appendChild(small);

    /* The whole folder is one control: it says what it does, and it opens
       from the keyboard as well as from a pointer. */
    var opener = document.createElement("button");
    opener.type = "button";
    opener.className = "folder-open-btn";
    opener.setAttribute("aria-expanded", "false");
    opener.appendChild(label);

    var chosen = document.createElement("p");
    chosen.className = "folder-chosen";
    chosen.setAttribute("role", "status");
    chosen.setAttribute("aria-live", "polite");

    root.textContent = "";
    root.appendChild(stage);
    root.appendChild(opener);
    root.appendChild(chosen);

    /* ---- open and shut ----
       Three things can hold it open: the pointer over it, the focus inside
       it, and the button having been pressed. Keeping them as separate facts
       and deriving "open" from all three is what stops a click on a folder
       already opened by the pointer from shutting it again. */
    var hovering = false, focused = false, pinned = false;
    var open = null;

    function refresh() {
      var next = hovering || focused || pinned;
      if (open === next) return;
      open = next;
      root.classList.toggle("is-open", open);
      opener.setAttribute("aria-expanded", open ? "true" : "false");
      papers.forEach(function (li) {
        li.querySelector(".folder-paper-btn").tabIndex = open ? 0 : -1;
      });
    }

    function setOpen(next) {
      pinned = next;
      if (!next) { hovering = false; focused = false; }
      refresh();
    }
    refresh();

    function select(li, i, btn) {
      var name = (li.querySelector(".folder-item-name") || btn).textContent.trim();
      var where = li.dataset.stage || "";
      chosen.textContent = where ? name + " — filed at " + where : name;
      root.querySelectorAll(".folder-paper.is-chosen")
          .forEach(function (x) { x.classList.remove("is-chosen"); });
      li.classList.add("is-chosen");
      if (o.closeOnSelect) setOpen(false);
      opener.focus();
    }

    if (o.trigger === "hover") {
      root.addEventListener("pointerenter", function () { hovering = true; refresh(); });
      root.addEventListener("pointerleave", function () { hovering = false; refresh(); });
    }
    opener.addEventListener("click", function () { pinned = !pinned; refresh(); });
    root.addEventListener("focusin", function () { focused = true; refresh(); });
    root.addEventListener("focusout", function (e) {
      if (!root.contains(e.relatedTarget)) { focused = false; refresh(); }
    });
    root.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && open) { setOpen(false); opener.focus(); }
    });

    /* ---- the idle drift ----
       physics: the shut folder breathes very slightly, so the page does not
       look frozen. Off entirely when motion is not wanted. */
    layout();
    var relayout;
    window.addEventListener("resize", function () {
      window.clearTimeout(relayout);
      relayout = window.setTimeout(layout, 150);
    });

    if (o.drift && !REDUCED) {
      root.style.setProperty("--drift", (o.drift * 5).toFixed(2) + "px");
      root.classList.add("has-drift");
    }
  }

  document.querySelectorAll("[data-folder]").forEach(build);
})();

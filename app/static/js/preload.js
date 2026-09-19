/* =========================================================================
   The loading screen.

   It covers the home page on every load, spells the university and the
   office out of particles, and waits to be let past. Three rules it obeys:

     · ten seconds is the longest it will ever hold, not a sentence to serve:
       a click anywhere, or Enter, or Escape, goes straight in, and the page
       keeps loading underneath the whole time;
     · it never traps anybody: the hard cap lifts it even if the page itself
       never finishes loading;
     · with JavaScript off it is never shown at all (the markup is hidden
       until this file reveals it), and with reduced motion the words are
       drawn in place rather than flown in.
   ========================================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var el = document.getElementById("preload");
  if (!el) return;

  var SHOW = 10000;      // the longest the curtain holds by itself
  var FADE = 560;        // matches the CSS transition
  var HARD_CAP = 12000;  // nothing keeps the page covered longer than this

  var canvas = el.querySelector(".preload-canvas");
  var engine = null;
  var gone = false;

  /* performance.now() is milliseconds since the navigation started, so the
     three seconds are counted from the refresh rather than from whenever this
     file happened to run. On a slow connection that makes the curtain shorter,
     not the page slower. */
  var since = (window.performance && performance.now)
    ? function () { return performance.now(); }
    : (function (t0) { return function () { return Date.now() - t0; }; })(Date.now());

  function dismiss() {
    if (gone) return;
    gone = true;
    el.classList.add("is-done");
    root.classList.remove("is-preloading");
    window.setTimeout(function () {
      if (engine) engine.destroy();
      if (el.parentNode) el.parentNode.removeChild(el);
    }, FADE);
    window.removeEventListener("keydown", skip);
    el.removeEventListener("click", skip);
  }

  function skip(e) {
    // Tab should reach the page underneath, not be swallowed as a skip.
    if (e && e.type === "keydown" && e.key === "Tab") return;
    dismiss();
  }

  /* The invitation only appears once there is something to look at, so it
     does not flash up before the words have formed. */
  function offerTheWayIn() {
    el.classList.add("is-ready");
    var enter = el.querySelector(".preload-enter");
    if (enter) enter.removeAttribute("tabindex");
  }

  /* Ten seconds from the refresh — time the page spends loading is time
     already served, not ten seconds added on top of it. Nobody should have to
     wait it out, so the way in is on the screen from the moment the words
     land. */
  var wantLoad = document.readyState !== "complete";
  var pending = wantLoad ? 2 : 1;
  function ready() {
    if (--pending > 0) return;
    window.setTimeout(dismiss, Math.max(0, SHOW - since()));
  }
  if (wantLoad) window.addEventListener("load", ready);

  window.addEventListener("keydown", skip);
  el.addEventListener("click", skip);
  window.setTimeout(dismiss, Math.max(600, HARD_CAP - since()));

  function mount() {
    if (gone || !canvas || !window.ParticleText) { dismiss(); return; }

    engine = window.ParticleText(canvas, {
      lines: [
        { text: "JAIN", fontSize: "clamp(3.5rem, 15vw, 9rem)", fontWeight: 800,
          fontFamily: 'inherit', letterSpacing: "-0.02em", density: 4,
          particleSize: 2.2 },
        /* Sampled every pixel, not every second one: at this size a coarser
           grid drops whole strokes and the words stop being words. The
           particles are a shade wider than their cell so the strokes join
           up rather than reading as dots. */
        { text: "(Deemed-to-be University)", fontSize: "clamp(1.05rem, 3.6vw, 1.75rem)",
          fontWeight: 600, letterSpacing: "0.02em", lineHeight: 1.5,
          density: 1, particleSize: 1.5 },
        { text: "Office of Academics", fontSize: "clamp(.85rem, 2.6vw, 1.15rem)",
          fontWeight: 700, letterSpacing: "0.3em", lineHeight: 1.7,
          gapAbove: "1rem", textTransform: "uppercase",
          density: 1, particleSize: 1.5 },
      ],
      // the brief's greys swapped for the university's own two colours: the
      // particles fly in the roundel gold and settle to the warm ivory
      color: "#f5f1e8",
      highlightColor: "#eebd1b",
      fontFamily: '"Bricolage Grotesque", "Inter", system-ui, sans-serif',
      scatter: 190,
      gatherDuration: 1600,
      stagger: 420,
      pointerRepel: 42,
      repelRadius: 120,
      idleDrift: 0.8,
      glow: true,
      onSettle: function () { offerTheWayIn(); ready(); }
    });

    el.classList.add("is-live");
  }

  /* Sampling the letters before the display face arrives would trace the
     fallback, so give the font a moment — but only a moment. */
  if (document.fonts && document.fonts.load) {
    var waited = false;
    var go = function () { if (!waited) { waited = true; mount(); } };
    window.setTimeout(go, 700);
    document.fonts.load('800 120px "Bricolage Grotesque"').then(go, go);
  } else {
    mount();
  }
})();

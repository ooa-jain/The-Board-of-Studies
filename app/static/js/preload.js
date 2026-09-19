/* =========================================================================
   The loading screen.

   It covers the home page while the fonts and the page settle, spells the
   university and the office out of particles, and then gets out of the way.
   Three rules it obeys:

     · it never traps anybody — a click, a key, the load event or a hard
       four-second cap all dismiss it, whichever comes first;
     · it shows once a session, so coming back to the home page is instant;
     · with JavaScript off it is never shown at all (the markup is hidden
       until this file reveals it), and with reduced motion the words are
       drawn in place rather than flown in.
   ========================================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var el = document.getElementById("preload");
  if (!el) return;

  var HOLD = 420;       // after the words land, before the curtain lifts
  var FADE = 560;       // matches the CSS transition
  var HARD_CAP = 4200;  // nothing keeps the page covered longer than this

  var canvas = el.querySelector(".preload-canvas");
  var engine = null;
  var gone = false;
  var started = Date.now();

  function dismiss() {
    if (gone) return;
    gone = true;
    el.classList.add("is-done");
    root.classList.remove("is-preloading");
    try { sessionStorage.setItem("ooa.preloaded", "1"); } catch (e) { /* private mode */ }
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

  /* Both the animation and the page have to be ready; the cap wins regardless. */
  var wantLoad = document.readyState !== "complete";
  var pending = wantLoad ? 2 : 1;
  function ready() { if (--pending <= 0) window.setTimeout(dismiss, HOLD); }
  if (wantLoad) window.addEventListener("load", ready);

  window.addEventListener("keydown", skip);
  el.addEventListener("click", skip);
  window.setTimeout(dismiss, HARD_CAP);

  function mount() {
    if (gone || !canvas || !window.ParticleText) { dismiss(); return; }

    engine = window.ParticleText(canvas, {
      lines: [
        { text: "JAIN", fontSize: "clamp(3.5rem, 15vw, 9rem)", fontWeight: 800,
          fontFamily: 'inherit', letterSpacing: "-0.02em", density: 4,
          particleSize: 2.2 },
        { text: "(Deemed-to-be University)", fontSize: "clamp(1rem, 3.4vw, 1.6rem)",
          fontWeight: 600, letterSpacing: "0.02em", lineHeight: 1.5,
          density: 2, particleSize: 1.7 },
        { text: "Office of Academics", fontSize: "clamp(.78rem, 2.4vw, 1.05rem)",
          fontWeight: 600, letterSpacing: "0.34em", lineHeight: 1.6,
          gapAbove: "0.9rem", textTransform: "uppercase",
          density: 2, particleSize: 1.6 },
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
      onSettle: ready
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

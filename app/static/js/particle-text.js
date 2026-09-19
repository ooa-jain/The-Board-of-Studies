/* =========================================================================
   Particle text.

   Words are rasterised to an offscreen canvas, sampled on a grid, and each
   sampled pixel becomes a particle that starts scattered and gathers into
   place. The particles fly in gold and settle to ivory, so the lockup
   assembles in the university's own two colours.

   Written against the same knobs as the React component this was specified
   from — particleSize, density, scatter, gatherDuration, stagger,
   pointerRepel, repelRadius, idleDrift, glow — so the numbers in the brief
   mean here what they mean there.

   Nothing here is content: the canvas is aria-hidden and the words are also
   in the DOM for a screen reader. If the browser prefers reduced motion the
   letters are simply drawn where they belong, once.
   ========================================================================= */
(function (global) {
  "use strict";

  var REDUCED = global.matchMedia
    && global.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------------ colour --- */

  function rgb(hex) {
    var h = String(hex).replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  /* A short ramp between the two brand colours. Particles pick the nearest
     step rather than an exact blend, so the fill style changes a handful of
     times per frame instead of once per particle. */
  function ramp(from, to, steps) {
    var a = rgb(from), b = rgb(to), out = [];
    for (var i = 0; i < steps; i++) {
      var t = steps === 1 ? 1 : i / (steps - 1);
      out.push("rgb(" + Math.round(a[0] + (b[0] - a[0]) * t) + ","
                      + Math.round(a[1] + (b[1] - a[1]) * t) + ","
                      + Math.round(a[2] + (b[2] - a[2]) * t) + ")");
    }
    return out;
  }

  /* ------------------------------------------------------------ lengths ---
     Accepts what CSS would: 96, "96px", "3.5rem", "13vw", and
     clamp(min, preferred, max). Keeping the clamp means the display size in
     the brief survives verbatim instead of being re-guessed in pixels. */

  function px(value) {
    if (typeof value === "number") return value;
    var v = String(value).trim();

    var clamp = /^clamp\(([^,]+),([^,]+),([^)]+)\)$/i.exec(v);
    if (clamp) {
      return Math.min(Math.max(px(clamp[1]), px(clamp[2])), px(clamp[3]));
    }
    var num = parseFloat(v);
    if (isNaN(num)) return 0;
    if (/rem$/i.test(v) || /em$/i.test(v)) {
      var root = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      return num * root;
    }
    if (/vw$/i.test(v)) return num * global.innerWidth / 100;
    if (/vh$/i.test(v)) return num * global.innerHeight / 100;
    return num;
  }

  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

  /* ---------------------------------------------------------------- run --- */

  function ParticleText(canvas, options) {
    var o = {
      lines: [],                     // [{ text, fontSize, fontWeight, ... }]
      particleSize: 2.2,
      density: 4,                    // sample every N px of the rasterised text
      color: "#f5f1e8",
      highlightColor: "#eebd1b",
      scatter: 190,
      gatherDuration: 1600,
      stagger: 420,
      pointerRepel: 42,
      repelRadius: 120,
      idleDrift: 0.8,
      glow: true,
      fontFamily: 'Inter, system-ui, sans-serif',
      fontWeight: 800,
      onSettle: null
    };
    for (var k in (options || {})) if (options[k] !== undefined) o[k] = options[k];

    var ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return { destroy: function () {} };

    var SHADES = ramp(o.highlightColor, o.color, 9);
    var canFilter = "filter" in ctx;

    var W = 0, H = 0, dpr = 1;
    var parts = [];
    var pointer = { x: -9999, y: -9999 };
    var t0 = 0, raf = 0, settled = false, dead = false;

    /* ---- rasterise, then sample ---- */

    function build() {
      var rect = canvas.getBoundingClientRect();
      W = Math.max(1, Math.round(rect.width));
      H = Math.max(1, Math.round(rect.height));
      dpr = Math.min(global.devicePixelRatio || 1, 2);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      var off = document.createElement("canvas");
      off.width = W; off.height = H;
      var oc = off.getContext("2d");
      oc.textAlign = "center";
      oc.textBaseline = "middle";

      // measure first, so the block can be centred as a whole
      var rows = o.lines.map(function (l) {
        var size = px(l.fontSize || 64);
        return {
          text: l.text || "",
          size: size,
          weight: l.fontWeight || o.fontWeight,
          spacing: l.letterSpacing || "0",
          lead: (l.lineHeight || 1.06) * size,
          gap: l.gapAbove === undefined ? 0 : px(l.gapAbove),
          density: Math.max(1, l.density || o.density),
          dot: l.particleSize || o.particleSize,
          transform: l.textTransform || "none"
        };
      });

      var total = rows.reduce(function (sum, r) { return sum + r.lead + r.gap; }, 0);
      var y = (H - total) / 2;
      var bands = [];

      rows.forEach(function (r) {
        y += r.gap;
        var text = r.transform === "uppercase" ? r.text.toUpperCase() : r.text;
        oc.font = r.weight + " " + r.size + "px " + o.fontFamily;
        if ("letterSpacing" in oc) oc.letterSpacing = r.spacing;

        // shrink a line that would run past the edges rather than clip it
        var pad = 24;
        var wide = oc.measureText(text).width;
        if (wide > W - pad * 2 && wide > 0) {
          r.size = Math.max(11, r.size * (W - pad * 2) / wide);
          oc.font = r.weight + " " + r.size + "px " + o.fontFamily;
        }

        var mid = y + r.lead / 2;
        oc.fillStyle = "#fff";
        oc.fillText(text, W / 2, mid);
        bands.push({ top: Math.max(0, Math.floor(y)),
                     bottom: Math.min(H, Math.ceil(y + r.lead)),
                     step: r.density, dot: r.dot });
        y += r.lead;
      });

      var data = oc.getImageData(0, 0, W, H).data;
      parts = [];
      bands.forEach(function (b) {
        for (var py = b.top; py < b.bottom; py += b.step) {
          for (var pxx = 0; pxx < W; pxx += b.step) {
            if (data[(py * W + pxx) * 4 + 3] < 128) continue;
            var angle = Math.random() * Math.PI * 2;
            var reach = o.scatter * (0.35 + Math.random() * 0.65);
            parts.push({
              tx: pxx, ty: py, dot: b.dot,
              sx: pxx + Math.cos(angle) * reach,
              sy: py + Math.sin(angle) * reach * 0.72,
              // the sweep runs left to right across the words
              delay: o.stagger * (pxx / W) + Math.random() * o.stagger * 0.18,
              phase: Math.random() * Math.PI * 2
            });
          }
        }
      });
    }

    /* ---- draw ---- */

    function paintStatic() {
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = o.color;
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        ctx.fillRect(p.tx, p.ty, p.dot, p.dot);
      }
      bloom();
    }

    function bloom() {
      if (!o.glow || !canFilter) return;
      ctx.save();
      ctx.filter = "blur(7px)";
      ctx.globalCompositeOperation = "lighter";
      ctx.globalAlpha = 0.5;
      ctx.drawImage(canvas, 0, 0, W, H);
      ctx.restore();
    }

    function frame(ts) {
      if (dead) return;
      if (!t0) t0 = ts;
      var el = ts - t0;
      var done = true;

      ctx.clearRect(0, 0, W, H);

      var shade = -1;
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        var t = (el - p.delay) / o.gatherDuration;
        if (t < 0) { done = false; continue; }
        if (t < 1) done = false; else t = 1;

        var e = easeOut(t);
        var x = p.sx + (p.tx - p.sx) * e;
        var y = p.sy + (p.ty - p.sy) * e;

        if (t === 1 && o.idleDrift) {
          x += Math.cos(el / 1100 + p.phase) * o.idleDrift * 0.6;
          y += Math.sin(el / 900 + p.phase) * o.idleDrift;
        }

        // the pointer pushes the nearest particles aside, and they fall back
        // as it moves on
        if (o.pointerRepel) {
          var dx = x - pointer.x, dy = y - pointer.y;
          var d2 = dx * dx + dy * dy;
          if (d2 < o.repelRadius * o.repelRadius && d2 > 0.01) {
            var d = Math.sqrt(d2);
            var push = o.pointerRepel * Math.pow(1 - d / o.repelRadius, 2);
            x += dx / d * push;
            y += dy / d * push;
          }
        }

        var want = Math.min(SHADES.length - 1, (e * (SHADES.length - 1)) | 0);
        if (want !== shade) { shade = want; ctx.fillStyle = SHADES[want]; }
        ctx.fillRect(x, y, p.dot, p.dot);
      }

      bloom();

      if (done && !settled) {
        settled = true;
        if (typeof o.onSettle === "function") o.onSettle();
      }
      raf = global.requestAnimationFrame(frame);
    }

    /* ---- wiring ---- */

    function move(e) {
      var r = canvas.getBoundingClientRect();
      var pt = e.touches ? e.touches[0] : e;
      pointer.x = pt.clientX - r.left;
      pointer.y = pt.clientY - r.top;
    }
    function leave() { pointer.x = pointer.y = -9999; }

    var resizeTimer = 0;
    function onResize() {
      global.clearTimeout(resizeTimer);
      resizeTimer = global.setTimeout(function () {
        if (dead) return;
        build();
        if (REDUCED) paintStatic();
      }, 150);
    }

    build();
    if (REDUCED) {
      paintStatic();
      if (typeof o.onSettle === "function") o.onSettle();
    } else {
      global.addEventListener("pointermove", move, { passive: true });
      global.addEventListener("pointerleave", leave, { passive: true });
      raf = global.requestAnimationFrame(frame);
    }
    global.addEventListener("resize", onResize);

    return {
      destroy: function () {
        dead = true;
        global.cancelAnimationFrame(raf);
        global.clearTimeout(resizeTimer);
        global.removeEventListener("pointermove", move);
        global.removeEventListener("pointerleave", leave);
        global.removeEventListener("resize", onResize);
        parts = [];
      }
    };
  }

  ParticleText.reducedMotion = REDUCED;
  global.ParticleText = ParticleText;
})(window);

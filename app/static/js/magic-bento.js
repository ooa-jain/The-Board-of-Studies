/* ==========================================================================
   MagicBento, without React.

   The effects of the MagicBento component, for any grid of `.bento-card`s:

     spotlight      a soft glow that follows the pointer across the grid
     border glow    each card's edge lights up nearest the pointer
     stars          a few particles drift inside the card under the pointer
     click effect   a ripple from where the card was clicked

   Tilt and magnetism are left out, as in the settings this was built to.
   Nothing here runs for people who have asked for reduced motion, and none
   of it is needed to read or edit a card.

       MagicBento.attach(gridElement)   // safe to call again after a repaint
   ========================================================================== */

(function () {
  "use strict";

  const OPTIONS = {
    glowColor: "132, 0, 255",
    spotlightRadius: 400,
    particleCount: 12,
  };

  const still = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function spawnStars(card) {
    const box = card.getBoundingClientRect();
    for (let i = 0; i < OPTIONS.particleCount; i++) {
      const star = document.createElement("span");
      star.className = "bento-star";
      star.style.left = Math.random() * box.width + "px";
      star.style.top = Math.random() * box.height + "px";
      star.style.setProperty("--dx", (Math.random() - 0.5) * 60 + "px");
      star.style.setProperty("--dy", (Math.random() - 0.5) * 60 + "px");
      star.style.animationDelay = (i * 0.07).toFixed(2) + "s";
      card.appendChild(star);
    }
  }

  function clearStars(card) {
    card.querySelectorAll(".bento-star").forEach(s => s.remove());
  }

  function ripple(card, e) {
    const box = card.getBoundingClientRect();
    const x = e.clientX - box.left;
    const y = e.clientY - box.top;
    // far enough to reach the furthest corner
    const r = Math.max(Math.hypot(x, y), Math.hypot(box.width - x, y),
                       Math.hypot(x, box.height - y), Math.hypot(box.width - x, box.height - y));
    const wave = document.createElement("span");
    wave.className = "bento-ripple";
    wave.style.left = x - r + "px";
    wave.style.top = y - r + "px";
    wave.style.width = wave.style.height = r * 2 + "px";
    card.appendChild(wave);
    wave.addEventListener("animationend", () => wave.remove());
  }

  function attach(grid) {
    if (!grid) return;
    grid.style.setProperty("--glow-rgb", OPTIONS.glowColor);
    grid.classList.add("bento-magic");
    if (still) return;

    grid.querySelectorAll(".bento-card").forEach(card => {
      if (card.dataset.magic) return;
      card.dataset.magic = "1";
      card.addEventListener("pointerenter", () => spawnStars(card));
      card.addEventListener("pointerleave", () => {
        clearStars(card);
        card.style.setProperty("--glow", "0");
      });
      card.addEventListener("click", e => ripple(card, e));
    });

    if (grid.dataset.magic) return;
    grid.dataset.magic = "1";

    const spot = document.createElement("div");
    spot.className = "bento-spotlight";
    spot.style.width = spot.style.height = OPTIONS.spotlightRadius * 2 + "px";
    document.body.appendChild(spot);

    let frame = 0;
    grid.addEventListener("pointermove", e => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        spot.style.transform = `translate(${e.clientX - OPTIONS.spotlightRadius}px, ` +
                               `${e.clientY - OPTIONS.spotlightRadius}px)`;
        spot.style.opacity = "1";
        grid.querySelectorAll(".bento-card").forEach(card => {
          const b = card.getBoundingClientRect();
          const x = e.clientX - b.left;
          const y = e.clientY - b.top;
          // distance from the card's edge, not its centre: a big card lights
          // up as readily as a small one
          const dx = Math.max(b.left - e.clientX, 0, e.clientX - b.right);
          const dy = Math.max(b.top - e.clientY, 0, e.clientY - b.bottom);
          const d = Math.hypot(dx, dy);
          const glow = Math.max(0, 1 - d / (OPTIONS.spotlightRadius * 0.5));
          card.style.setProperty("--gx", (x / b.width) * 100 + "%");
          card.style.setProperty("--gy", (y / b.height) * 100 + "%");
          card.style.setProperty("--glow", glow.toFixed(3));
        });
      });
    });
    grid.addEventListener("pointerleave", () => {
      spot.style.opacity = "0";
      grid.querySelectorAll(".bento-card").forEach(c => c.style.setProperty("--glow", "0"));
    });
  }

  window.MagicBento = { attach: attach, options: OPTIONS };
})();

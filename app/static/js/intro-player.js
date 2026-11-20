/* The BoS intro film: plays at once — with sound if the browser lets it,
   else muted, with "Turn sound on" — a thin progress line under it, and a
   click on the picture pauses or plays it. */
(function () {
  document.querySelectorAll(".intro-player").forEach(function (box) {
    var v = box.querySelector(".intro-video");
    var sound = box.querySelector(".intro-sound");
    var bar = box.querySelector(".intro-bar i");
    if (!v) return;
    box.start = function () {
      v.currentTime = 0;
      v.muted = false;
      var p = v.play();
      if (p && p.catch) p.catch(function () {
        // no sound before a click: play muted and offer the sound
        v.muted = true;
        if (sound) sound.hidden = false;
        v.play().catch(function () {});
      });
    };
    if (sound) sound.addEventListener("click", function () {
      v.muted = false;
      sound.hidden = true;
      if (v.paused) v.play();
    });
    v.addEventListener("click", function () { if (v.paused) v.play(); else v.pause(); });
    v.addEventListener("timeupdate", function () {
      if (bar && v.duration) bar.style.width = (100 * v.currentTime / v.duration) + "%";
    });
    // the language row just above the player: the same moment, another voice
    var langs = box.previousElementSibling;
    if (langs && langs.classList.contains("intro-langs")) {
      langs.addEventListener("click", function (e) {
        var b = e.target.closest(".intro-lang");
        if (!b || b.classList.contains("is-on")) return;
        langs.querySelectorAll(".intro-lang").forEach(function (o) {
          o.classList.toggle("is-on", o === b);
          o.setAttribute("aria-pressed", o === b ? "true" : "false");
        });
        var at = v.currentTime, playing = !v.paused && !v.ended;
        v.src = b.dataset.src;
        v.addEventListener("loadedmetadata", function seek() {
          v.removeEventListener("loadedmetadata", seek);
          // the films differ a little in length: keep the same share of the way
          v.currentTime = Math.min(at, Math.max(0, v.duration - 1));
          if (playing || v.currentTime === 0) v.play().catch(function () {});
        });
        v.load();
      });
      box.resetLang = function () {
        var first = langs.querySelector(".intro-lang");
        if (first && !first.classList.contains("is-on")) first.click();
      };
    }
    if (box.closest(".intro-stage")) box.start();          // the first-sign-in page plays at once
  });
})();

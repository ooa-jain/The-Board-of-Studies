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
    if (box.closest(".intro-stage")) box.start();          // the first-sign-in page plays at once
  });
})();

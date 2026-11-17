/* The sign-in page's scene: three stage panels take turns at the front, and
   the front panel's cards tick themselves off one by one. Moving the pointer
   tilts the scene; clicking a panel brings it forward. Still for anyone who
   asks their system for reduced motion. */
(function () {
  var scene = document.getElementById("login-scene");
  if (!scene) return;
  var panels = Array.prototype.slice.call(scene.querySelectorAll(".lp"));
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  // order[last] is at the front: Pre-BoS first, then BoS Documents, then Curriculum
  var order = panels.length === 3 ? [panels[1], panels[2], panels[0]] : panels.slice();
  var turn = null, ticker = null;

  // the caption's steps: the one at the front is lit, and a tap brings one forward
  var steps = Array.prototype.slice.call(document.querySelectorAll(".lsc-step"));

  function place() {
    order.forEach(function (p, i) { p.dataset.pos = String(i); });
    var front = panels.indexOf(order[order.length - 1]);
    steps.forEach(function (s) { s.classList.toggle("is-on", Number(s.dataset.step) === front); });
  }

  function tickNext() {
    var front = order[order.length - 1];
    var card = front.querySelector(".lp-card:not(.is-done)");
    if (!card) {                        // all ticked: start that panel over
      front.querySelectorAll(".lp-card").forEach(function (c) { c.classList.remove("is-done"); });
      return;
    }
    card.classList.add("is-done");
  }

  // the stage after the front one comes forward (Pre-BoS → BoS Documents → Curriculum → …)
  function next() { order.push(order.shift()); place(); }

  function bring(p) {
    var i = order.indexOf(p);
    if (i < 0) return;
    if (i !== order.length - 1) { order.splice(i, 1); order.push(p); place(); }
    else tickNext();
  }

  function start() {
    clearInterval(turn); clearInterval(ticker);
    if (reduced) return;
    ticker = setInterval(tickNext, 900);
    turn = setInterval(next, 3600);
  }

  place();
  // something ticked from the start, so the scene never opens blank
  scene.querySelectorAll(".lp").forEach(function (p) {
    var first = p.querySelector(".lp-card"); if (first) first.classList.add("is-done");
  });
  start();

  document.addEventListener("pointermove", function (e) {
    if (reduced) return;
    var x = e.clientX / window.innerWidth - 0.5, y = e.clientY / window.innerHeight - 0.5;
    scene.style.setProperty("--tx", (x * 16).toFixed(2) + "deg");
    scene.style.setProperty("--ty", (-y * 10).toFixed(2) + "deg");
  });
  panels.forEach(function (p) {
    p.addEventListener("click", function () { bring(p); start(); });
  });
  steps.forEach(function (s) {
    s.addEventListener("click", function () { var p = panels[Number(s.dataset.step)]; if (p) { bring(p); start(); } });
  });
  // a hidden tab does not need to keep turning
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { clearInterval(turn); clearInterval(ticker); } else start();
  });
})();

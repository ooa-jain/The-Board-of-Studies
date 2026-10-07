/* The sign-in page's scene: three stage panels take turns at the front, and
   the front panel's cards tick themselves off one by one. Moving the pointer
   tilts the scene; clicking a panel brings it forward. Still for anyone who
   asks their system for reduced motion. */
(function () {
  var scene = document.getElementById("login-scene");
  if (!scene) return;
  var panels = Array.prototype.slice.call(scene.querySelectorAll(".lp"));
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var order = panels.slice();          // order[last] is at the front
  var turn = null, ticker = null;

  function place() { order.forEach(function (p, i) { p.dataset.pos = String(i); }); }

  function tickNext() {
    var front = order[order.length - 1];
    var card = front.querySelector(".lp-card:not(.is-done)");
    if (!card) {                        // all ticked: start that panel over
      front.querySelectorAll(".lp-card").forEach(function (c) { c.classList.remove("is-done"); });
      return;
    }
    card.classList.add("is-done");
  }

  function next() { order.unshift(order.pop()); place(); }

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
  // a hidden tab does not need to keep turning
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { clearInterval(turn); clearInterval(ticker); } else start();
  });
})();

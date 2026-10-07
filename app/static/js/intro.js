/* A department's welcome scene (templates/_intro.html).
   The three stage panels take turns at the front; the hand taps the front
   panel's next card and ticks it; the pointer tilts the scene; a click on a
   panel brings it forward. The button, Enter, Escape or a click outside the
   scene goes in. It lifts by itself after a while if nobody touches it. */
(function () {
  var intro = document.getElementById("intro");
  if (!intro) return;
  var scene = document.getElementById("intro-scene");
  var hand = document.getElementById("intro-hand");
  var panels = Array.prototype.slice.call(intro.querySelectorAll(".ip"));
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var order = panels.slice();          // order[2] is at the front
  var timer = null, auto = null, touched = false, gone = false;

  document.documentElement.classList.add("intro-open");
  setTimeout(function () { intro.classList.add("is-on"); }, 20);

  function place() {
    order.forEach(function (p, i) { p.dataset.pos = String(i); });
  }

  function tap() {
    var front = order[order.length - 1];
    var cards = front.querySelectorAll(".ip-card:not(.is-done)");
    var card = cards[0];
    if (!card) {                         // all ticked: start that panel over
      front.querySelectorAll(".ip-card").forEach(function (c) { c.classList.remove("is-done"); });
      card = front.querySelector(".ip-card");
    }
    // the fingertip goes to the card
    var r = card.getBoundingClientRect(), s = hand.parentNode.getBoundingClientRect();
    hand.style.left = (r.left - s.left + r.width * 0.62) + "px";
    hand.style.top = (r.top - s.top + r.height * 0.45) + "px";
    hand.classList.remove("is-tap");
    void hand.offsetWidth;
    hand.classList.add("is-tap");
    setTimeout(function () { card.classList.add("is-done"); }, 420);
  }

  function next() {
    order.unshift(order.pop());         // the front panel goes to the back
    place();
    setTimeout(tap, 650);
  }

  function bring(p) {
    var i = order.indexOf(p);
    if (i < 0 || i === order.length - 1) { tap(); return; }
    order.splice(i, 1);
    order.push(p);
    place();
    setTimeout(tap, 500);
  }

  function leave() {
    if (gone) return;
    gone = true;
    clearInterval(timer);
    clearTimeout(auto);
    intro.classList.add("is-leaving");
    document.documentElement.classList.remove("intro-open");
    setTimeout(function () { intro.remove(); }, 650);
  }

  function hold() {                     // somebody is playing with it: no hurry
    if (touched) return;
    touched = true;
    clearTimeout(auto);
  }

  place();
  if (!reduced) {
    setTimeout(tap, 900);
    timer = setInterval(next, 2600);
  }
  auto = setTimeout(leave, reduced ? 4000 : 9000);

  intro.addEventListener("pointermove", function (e) {
    if (reduced) return;
    var x = e.clientX / window.innerWidth - 0.5, y = e.clientY / window.innerHeight - 0.5;
    scene.style.setProperty("--tx", (x * 16).toFixed(2) + "deg");
    scene.style.setProperty("--ty", (-y * 10).toFixed(2) + "deg");
  });
  panels.forEach(function (p) {
    p.addEventListener("click", function (e) {
      e.stopPropagation();
      hold();
      clearInterval(timer);
      bring(p);
      if (!reduced) timer = setInterval(next, 3200);
    });
  });
  intro.addEventListener("pointerdown", hold);
  document.getElementById("intro-go").addEventListener("click", leave);
  document.addEventListener("keydown", function (e) {
    if (gone) return;
    if (e.key === "Escape" || e.key === "Enter") { e.preventDefault(); leave(); }
  });
  document.getElementById("intro-go").focus({ preventScroll: true });
})();

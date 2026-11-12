/* The Office's home as a live dashboard.

   - Times marked <time data-local> are shown in the reader's own clock.
   - Every minute, while the tab is in front, the page counts again: it is
     fetched afresh and its numbers swapped in, with a "Live · as of" time.
     It waits while someone is typing in it or has a source list open.
   - "Sources" shows, under every number and chart, how it is counted, which
     records it reads, as of when, and the departments behind it. The choice
     is remembered on this browser. */
(function () {
  "use strict";
  function localTimes(root) {
    (root || document).querySelectorAll("time[data-local]").forEach(function (el) {
      var d = new Date(el.getAttribute("datetime"));
      if (isNaN(d)) return;
      el.textContent = d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric",
                                                     hour: "2-digit", minute: "2-digit" });
    });
  }
  localTimes();

  var box = document.getElementById("ad-live");
  if (!box) return;
  var KEY = "bos.sources";
  function stored() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function setSources(on) {
    box.classList.toggle("show-src", on);
    box.querySelectorAll("[data-src-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.classList.toggle("is-on", on);
    });
    try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* not kept: fine */ }
  }
  setSources(stored());

  var busy = false;
  function refresh(force) {
    if (busy || (!force && document.hidden)) return;
    var a = document.activeElement;
    if (!force && ((a && box.contains(a) && /INPUT|TEXTAREA|SELECT/.test(a.tagName)) ||
                   box.querySelector("details[open]"))) return;
    busy = true;
    box.classList.add("is-counting");
    fetch(location.href, { credentials: "same-origin", headers: { "X-Requested-With": "live" } })
      .then(function (r) {
        if (!r.ok || r.redirected) throw new Error("signed out or moved");
        return r.text();
      })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var fresh = doc.getElementById("ad-live");
        if (!fresh) return;
        fresh.classList.toggle("show-src", box.classList.contains("show-src"));
        box.replaceWith(fresh);
        box = fresh;
        localTimes(box);
        setSources(stored());
      })
      .catch(function () { /* keep what is on screen; try again next minute */ })
      .then(function () { busy = false; box.classList.remove("is-counting"); });
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-src-toggle]")) { setSources(!box.classList.contains("show-src")); }
    if (e.target.closest("[data-live-now]")) { refresh(true); }
  });
  var every = (parseInt(box.getAttribute("data-live"), 10) || 60) * 1000;
  setInterval(function () { refresh(false); }, every);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) refresh(false); });
})();

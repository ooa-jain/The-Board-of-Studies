/* ==========================================================================
   Page chrome: the menu, flash messages, print buttons, and the CSRF token
   every state-changing fetch has to carry.

   Loaded on every page, including the ones that hide the masthead, so each
   piece checks for what it needs before wiring anything up.
   ========================================================================== */

(function () {
  "use strict";

  /* ---------- CSRF ----------
     The server rejects an unsafe request without the session's token. Rather
     than thread it through every call site, wrap fetch once: same-origin,
     state-changing requests get the header added if they do not already have
     one. */
  const meta = document.querySelector('meta[name="csrf-token"]');
  const TOKEN = meta ? meta.getAttribute("content") : "";
  const SAFE = /^(GET|HEAD|OPTIONS|TRACE)$/i;

  if (TOKEN && window.fetch) {
    const original = window.fetch;
    window.fetch = function (input, init) {
      init = init || {};
      const method = init.method || (typeof input === "object" && input.method) || "GET";
      if (SAFE.test(method)) return original.call(this, input, init);

      const url = typeof input === "string" ? input : (input && input.url) || "";
      const sameOrigin = !/^https?:\/\//i.test(url) ||
        url.indexOf(window.location.origin) === 0;
      if (!sameOrigin) return original.call(this, input, init);

      const headers = new Headers(init.headers || (typeof input === "object" && input.headers) || {});
      if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", TOKEN);
      init.headers = headers;
      return original.call(this, input, init);
    };
  }

  /* ---------- the menu ---------- */
  const btn = document.getElementById("nav-toggle");
  const nav = document.getElementById("topnav");
  if (btn && nav) {
    const setOpen = function (open) {
      nav.dataset.open = open ? "true" : "false";
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    };
    setOpen(false);
    btn.addEventListener("click", function () {
      setOpen(nav.dataset.open !== "true");
    });
    // Escape closes it from anywhere on the page, not only from inside the
    // menu, and returns the caret to the button.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.dataset.open === "true") { setOpen(false); btn.focus(); }
    });
    // A click outside, or a jump back to the wide layout, closes it too.
    document.addEventListener("click", function (e) {
      if (nav.dataset.open === "true" && !nav.contains(e.target) && !btn.contains(e.target)) {
        setOpen(false);
      }
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 900) setOpen(false);
    });
  }

  /* ---------- flash messages ----------
     Dismissible, and the run-of-the-mill confirmations fade after a while.
     Errors and warnings stay until they are read and dismissed. */
  document.querySelectorAll(".alert[data-dismissible]").forEach(function (alert) {
    const close = document.createElement("button");
    close.type = "button";
    close.className = "alert-close";
    close.setAttribute("aria-label", "Dismiss this message");
    close.innerHTML = "&times;";
    close.addEventListener("click", function () {
      alert.classList.add("is-going");
      window.setTimeout(function () { alert.remove(); }, 200);
    });
    alert.appendChild(close);

    if (alert.classList.contains("alert-success") || alert.classList.contains("alert-info")) {
      window.setTimeout(function () {
        if (!alert.isConnected || alert.matches(":hover")) return;
        alert.classList.add("is-going");
        window.setTimeout(function () { alert.remove(); }, 400);
      }, 9000);
    }
  });

  /* ---------- print buttons, so no page needs an inline onclick ---------- */
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-print]")) { e.preventDefault(); window.print(); }
  });

  /* ---------- destructive actions confirm once ----------
     `data-confirm` on a form or a button, rather than an inline onsubmit. */
  document.addEventListener("submit", function (e) {
    const form = e.target;
    const message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) e.preventDefault();
  });

  /* ---------- filter forms submit on change ----------
     A select that only works when you also press a button is a select that
     gets left alone. */
  document.querySelectorAll("[data-autosubmit] select").forEach(function (select) {
    select.addEventListener("change", function () {
      const form = select.closest("form");
      if (form) form.submit();
    });
  });
})();

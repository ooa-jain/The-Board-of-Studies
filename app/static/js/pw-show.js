/* An eye on every password box: press it to see what was typed, press it
   again to hide it. A box that already has its own Show button (the
   sign-in form) is left as it is. */
(function () {
  "use strict";
  const EYE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.7 8.4 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

  function wire(input) {
    if (input.dataset.pwShow) return;
    if (input.id && document.querySelector('[aria-controls="' + input.id + '"]')) return;
    input.dataset.pwShow = "1";
    const wrap = document.createElement("span");
    wrap.className = "pw-eye-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-eye";
    btn.setAttribute("aria-pressed", "false");
    btn.setAttribute("aria-label", "Show password");
    btn.title = "Show password";
    if (input.id) btn.setAttribute("aria-controls", input.id);
    btn.innerHTML = EYE;
    btn.addEventListener("click", function () {
      const shown = input.type === "text";
      input.type = shown ? "password" : "text";
      btn.innerHTML = shown ? EYE : EYE_OFF;
      const words = shown ? "Show password" : "Hide password";
      btn.setAttribute("aria-label", words);
      btn.title = words;
      btn.setAttribute("aria-pressed", shown ? "false" : "true");
      input.focus();
    });
    wrap.appendChild(btn);
  }

  function all() {
    document.querySelectorAll('input[type="password"]').forEach(wire);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", all);
  else all();
  // a form that hides its passwords again before sending, so a browser does
  // not offer to remember a password as plain text
  document.addEventListener("submit", function (e) {
    e.target.querySelectorAll("input[data-pw-show]").forEach(function (i) { i.type = "password"; });
  }, true);
})();

/* ==========================================================================
   Copy-to-clipboard buttons.

   Any element with data-copy gets wired up. The async Clipboard API only
   exists in a secure context, so on a plain-HTTP deployment it is simply
   undefined — the old inline handlers threw and the button did nothing at
   all. Fall back to a hidden textarea, and say so plainly when neither
   route works, rather than claiming a copy that never happened.
   ========================================================================== */

(function () {
  "use strict";

  function legacyCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:0;left:-9999px;opacity:0";
    document.body.appendChild(ta);
    const selection = document.getSelection();
    const previous = selection.rangeCount ? selection.getRangeAt(0) : null;
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    if (previous) { selection.removeAllRanges(); selection.addRange(previous); }
    return ok;
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(() => true, () => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  }

  /** A single polite live region, so a copy is announced and not just coloured. */
  let live;
  function announce(message) {
    if (!live) {
      live = document.createElement("div");
      live.className = "sr-only";
      live.setAttribute("role", "status");
      live.setAttribute("aria-live", "polite");
      document.body.appendChild(live);
    }
    live.textContent = message;
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    e.preventDefault();

    const text = btn.dataset.copy;
    const what = btn.dataset.copyLabel || "Copied";
    const idle = btn.dataset.copyIdle || btn.textContent.trim();
    btn.dataset.copyIdle = idle;

    clearTimeout(btn._copyTimer);
    copy(text).then(function (ok) {
      btn.classList.toggle("done", ok);
      btn.classList.toggle("failed", !ok);
      btn.textContent = ok ? what : "Press Ctrl+C";
      announce(ok ? what : "Copying is blocked in this browser — select the text and press Ctrl+C.");
      if (!ok) {
        // Leave the value selected so the keyboard shortcut has something to take.
        const value = btn.closest(".cred-row, td, .flex");
        const node = value && value.querySelector(".v, .mono");
        if (node) {
          const range = document.createRange();
          range.selectNodeContents(node);
          const sel = document.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
      btn._copyTimer = setTimeout(function () {
        btn.textContent = idle;
        btn.classList.remove("done", "failed");
      }, 2400);
    });
  });
})();

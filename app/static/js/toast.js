/* Alert cards (after Uiverse.io, xerith_8140): a stack in the top-right
   corner, one card per message — success, info, warning or error — on a
   faint grid, with an icon, a close button and a bar that runs down the
   time it stays. Pointing at a card holds it; clicking it can take you to
   the field it is about.

   window.Toast.show(kind, text, { title, timeout, onClick })
   window.Toast.success / info / warning / error (text, opts) */
(function (global) {
  "use strict";

  const ICONS = {
    success: '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    info: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v6M12 7.5v.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
    warning: '<path d="M12 3.5L2.8 19.5h18.4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 10v4.5M12 17v.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
    error: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 9l6 6M15 9l-6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  };
  const CLOSE = '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>';
  const recent = new Map();     // the same message twice in a row shows once

  let box = null;
  function container() {
    if (box && document.body.contains(box)) return box;
    box = document.createElement("ul");
    box.className = "notification-container";
    box.setAttribute("aria-live", "polite");
    box.setAttribute("aria-label", "Messages");
    document.body.appendChild(box);
    return box;
  }

  function show(kind, text, opts) {
    const o = opts || {};
    kind = ICONS[kind] ? kind : "info";
    const key = kind + "|" + (o.title || "") + "|" + text;
    const now = Date.now();
    if (recent.has(key) && now - recent.get(key) < 4000) return null;
    recent.set(key, now);

    const timeout = o.timeout ?? (kind === "error" ? 9000 : kind === "warning" ? 7000 : 5000);
    const li = document.createElement("li");
    li.className = "notification-item " + kind;
    li.setAttribute("role", kind === "error" ? "alert" : "status");

    const content = document.createElement("div");
    content.className = "notification-content";
    const icon = document.createElement("div");
    icon.className = "notification-icon";
    icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICONS[kind] + "</svg>";
    content.appendChild(icon);
    const words = document.createElement("div");
    words.className = "notification-text";
    if (o.title) {
      const t = document.createElement("strong");
      t.textContent = o.title;
      words.appendChild(t);
    }
    const p = document.createElement("span");
    p.textContent = text;
    words.appendChild(p);
    content.appendChild(words);
    li.appendChild(content);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "notification-close";
    close.setAttribute("aria-label", "Close this message");
    close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + CLOSE + "</svg>";
    li.appendChild(close);

    const bar = document.createElement("div");
    bar.className = "notification-progress-bar";
    li.appendChild(bar);

    let timer = null, left = timeout, started = 0;
    const gone = () => {
      clearTimeout(timer);
      li.classList.add("is-leaving");
      setTimeout(() => li.remove(), 260);
    };
    const run = () => {
      if (!timeout) return;
      started = Date.now();
      bar.style.animationDuration = timeout + "ms";
      bar.style.animationPlayState = "running";
      timer = setTimeout(gone, left);
    };
    // pointing at a card holds it there
    li.addEventListener("mouseenter", () => {
      if (!timeout) return;
      clearTimeout(timer);
      left -= Date.now() - started;
      bar.style.animationPlayState = "paused";
    });
    li.addEventListener("mouseleave", () => { if (timeout && left > 0) { started = Date.now(); timer = setTimeout(gone, left); bar.style.animationPlayState = "running"; } });
    close.addEventListener("click", e => { e.stopPropagation(); gone(); });
    if (typeof o.onClick === "function") {
      li.classList.add("is-link");
      li.addEventListener("click", () => { o.onClick(); });
    }

    container().appendChild(li);
    // no more than five at once: the oldest go first
    const all = container().querySelectorAll(".notification-item:not(.is-leaving)");
    for (let i = 0; i < all.length - 5; i++) all[i].remove();
    if (timeout) run(); else bar.remove();
    return { close: gone };
  }

  global.Toast = {
    show,
    success: (t, o) => show("success", t, o),
    info: (t, o) => show("info", t, o),
    warning: (t, o) => show("warning", t, o),
    error: (t, o) => show("error", t, o),
  };
})(window);

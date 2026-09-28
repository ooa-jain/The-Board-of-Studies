/* AI summary box — shared by the department's upload cards and the admin's
   document list. `load(host, url, refresh)` POSTs to a summary endpoint and
   draws the answer (or the reason there is none) inside `host`. */
(function () {
  "use strict";

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function head(title, by) {
    const h = el("div", "fs-head");
    h.appendChild(el("span", "fs-spark", "✦"));
    h.appendChild(el("strong", null, title));
    if (by) h.appendChild(el("span", "fs-by", by));
    return h;
  }

  function load(host, url, refresh) {
    let box = host.querySelector(".file-summary");
    if (!box) { box = el("div", "file-summary"); host.appendChild(box); }
    host.classList.add("has-summary");
    box.setAttribute("aria-live", "polite");
    box.className = "file-summary is-loading";
    box.innerHTML = "";
    box.appendChild(head("AI summary", "Reading the PDF…"));
    ["w-90", "w-70", "w-90", "w-50"].forEach(w => box.appendChild(el("span", "sk sk-line " + w)));

    fetch(url + (refresh ? "?refresh=1" : ""), { method: "POST", credentials: "same-origin" })
      .then(r => r.json())
      .then(j => {
        box.className = "file-summary" + (j.ok ? "" : " is-bad");
        box.innerHTML = "";
        const h = head(j.ok ? "AI summary" : "No summary",
                       j.ok ? "by Grok · check it against the document" : "");
        if (j.ok) {
          const again = el("button", "fs-again", "Redo");
          again.type = "button";
          again.title = "Ask for a fresh summary";
          again.addEventListener("click", () => load(host, url, true));
          h.appendChild(again);
        }
        box.appendChild(h);
        box.appendChild(el("div", "fs-text", j.ok ? j.summary : j.error));
      })
      .catch(() => {
        box.className = "file-summary is-bad";
        box.innerHTML = "";
        box.appendChild(head("No summary"));
        box.appendChild(el("div", "fs-text", "Could not get a summary — check your connection and try again."));
      });
  }

  window.PortalSummary = { load };
})();

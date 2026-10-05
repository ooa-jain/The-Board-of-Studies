/* The Office's review of a stage: the same pop-up the department saw before
   submitting, with how much was filled, when it was started and submitted,
   how long it took, and Send back. */
(function () {
  "use strict";
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const WORDS = { submitted: "Submitted", returned: "Sent back", draft: "In progress",
                  open: "Not started", locked: "Locked" };

  function open(url) {
    fetch(url, { credentials: "same-origin" }).then(r => r.json()).then(j => {
      const title = (j.programme_name ? j.programme_name + " · " : "") + j.stage.title;
      const st = Review.stats(j.stage, j.data);
      const top = el("div", "rv-stats");
      const ring = el("div", "rv-ring");
      ring.style.setProperty("--p", st.percent);
      ring.appendChild(el("strong", null, st.percent + "%"));
      top.appendChild(ring);
      const words = el("div", "rv-stats-words");
      words.appendChild(el("strong", null, `${st.filled} of ${st.total} filled · ${WORDS[j.status] || j.status}`));
      words.appendChild(el("span", null, st.missing.length
        ? "Empty: " + st.missing.slice(0, 5).join(", ") + (st.missing.length > 5 ? "…" : "")
        : "Everything asked for is filled in."));
      if (j.summary && (j.summary.errors || j.summary.warnings))
        words.appendChild(el("span", "rv-warn", `${j.summary.errors || 0} error(s), ${j.summary.warnings || 0} warning(s) at the last check`));
      if (j.returned_note) words.appendChild(el("span", "rv-warn", "Sent back: " + j.returned_note));
      top.appendChild(words);
      const facts = el("div", "rv-stats-facts");
      const fact = (k, v) => { if (!v) return; const s = el("span"); s.appendChild(document.createTextNode(k + " ")); s.appendChild(el("b", null, v)); facts.appendChild(s); };
      fact("Started", j.timing.started);
      fact("Submitted", j.timing.submitted);
      fact("Time taken", j.timing.took);
      if (!j.timing.submitted) fact("Last saved", j.timing.updated);
      top.appendChild(facts);

      const body = Review.build(j.stage, j.data, {});
      const foot = el("div", "rv-admin-acts");
      if (j.status === "submitted") {
        const f = el("form");
        f.method = "post";
        f.action = j.return_url;
        f.className = "rv-admin-acts";
        const ta = el("textarea");
        ta.name = "note";
        ta.required = true;
        ta.rows = 2;
        ta.placeholder = "Send back: what must the department correct?";
        f.appendChild(ta);
        if (j.programme) { const h = el("input"); h.type = "hidden"; h.name = "programme"; h.value = j.programme; f.appendChild(h); }
        const b = el("button", "btn btn-danger", "Send back");
        b.type = "submit";
        f.appendChild(b);
        foot.appendChild(f);
      }
      const row = el("div", "rv-actions");
      const copy = el("button", "btn btn-ghost", "Download a copy");
      copy.type = "button";
      copy.addEventListener("click", () => Review.print(title, j.dept_name +
        (j.timing.submitted ? " · submitted " + j.timing.submitted : ""), body));
      row.appendChild(copy);
      foot.appendChild(row);
      Review.modal({ title, sub: j.dept_name, top, body, foot });
    }).catch(() => { if (window.Toast) window.Toast.error("Could not load this stage. Try again."); });
  }

  document.addEventListener("click", e => {
    const b = e.target.closest("[data-review]");
    if (!b) return;
    e.preventDefault();
    open(b.getAttribute("data-review"));
  });
})();

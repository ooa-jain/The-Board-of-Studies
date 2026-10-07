/* Review & submit all: every stage and every programme part in one review —
   each opens to show what was entered — then one confirmation, and every
   one not yet submitted goes, in order. If one cannot go, the review says
   which and why, with a link to it.

   window.SubmitAll.open({ record, submit, beforeOpen }) */
(function () {
  "use strict";
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const WORDS = { submitted: "Submitted", draft: "Filled, not submitted", open: "Not started",
                  returned: "Sent back", locked: "Locked" };

  function itemBlock(item, openIt) {
    const d = el("details", "sa-item is-" + item.status);
    d.open = !!openIt;
    const s = el("summary", "sa-head");
    const st = Review.stats(item.stage, item.data);
    s.appendChild(el("span", "sa-dot", item.status === "submitted" ? "✓" : item.status === "returned" ? "!" : "•"));
    const t = el("span", "sa-title", item.title);
    s.appendChild(t);
    s.appendChild(el("span", "sa-fill", st.total ? `${st.percent}% filled` : ""));
    s.appendChild(el("span", "sa-status", WORDS[item.status] || item.status));
    d.appendChild(s);
    const body = el("div", "sa-body");
    const go = el("a", "sa-go", "Open this stage →");
    go.href = item.url;
    body.appendChild(go);
    body.appendChild(Review.build(item.stage, item.data, {}));
    d.appendChild(body);
    return { el: d, stats: st };
  }

  function open(opts) {
    const start = opts.beforeOpen ? opts.beforeOpen() : Promise.resolve();
    Promise.resolve(start).then(() => fetch(opts.record, { credentials: "same-origin" }))
      .then(r => r.json()).then(j => draw(opts, j))
      .catch(() => { if (window.Toast) window.Toast.error("Could not load the record. Try again."); });
  }

  function draw(opts, j) {
    const items = j.items || [];
    const body = el("div", "rv");
    let filled = 0, total = 0, firstOpen = false;
    const pending = items.filter(i => i.status !== "submitted");
    items.forEach(it => {
      const openIt = !firstOpen && it.status !== "submitted";
      if (openIt) firstOpen = true;
      const b = itemBlock(it, false);
      filled += b.stats.filled; total += b.stats.total;
      body.appendChild(b.el);
    });
    const pct = total ? Math.round(filled * 100 / total) : 100;

    const top = el("div", "rv-stats");
    const ring = el("div", "rv-ring");
    ring.style.setProperty("--p", pct);
    ring.appendChild(el("strong", null, pct + "%"));
    top.appendChild(ring);
    const words = el("div", "rv-stats-words");
    const nDone = items.length - pending.length;
    words.appendChild(el("strong", null, `${nDone} of ${items.length} submitted · ${filled} of ${total} filled`));
    words.appendChild(el("span", null, pending.length
      ? `${pending.length} to submit: ${pending.slice(0, 3).map(i => i.title).join(", ")}${pending.length > 3 ? "…" : ""}. Open any one to see what is in it.`
      : "Everything is submitted. Open any one to see what was sent."));
    top.appendChild(words);

    const foot = el("div");
    const err = el("div", "sa-error");
    err.hidden = true;
    foot.appendChild(err);
    let terms = null, go = null;
    if (pending.length) {
      terms = el("label", "rv-terms");
      const tick = el("input");
      tick.type = "checkbox";
      terms.appendChild(tick);
      terms.appendChild(el("span", null,
        "I have checked every stage above. I understand that once submitted, the Board of Studies record " +
        "goes to the Office of Academics and is locked — only the Office can send a part back for correction."));
      foot.appendChild(terms);
      tick.addEventListener("change", () => { go.disabled = !tick.checked; });
    }
    const row = el("div", "rv-actions");
    const copy = el("button", "btn btn-ghost", "Download a copy");
    copy.type = "button";
    row.appendChild(copy);
    row.appendChild(el("span", "spacer"));
    if (pending.length) {
      go = el("button", "btn btn-gold", `Submit all ${pending.length} now`);
      go.type = "button";
      go.disabled = true;
      row.appendChild(go);
    }
    foot.appendChild(row);

    const ctl = Review.modal({ title: opts.title || "Review & submit all stages", sub: j.dept_name, top, body, foot });
    const printAll = () => {
      const all = el("div");
      items.forEach(it => {
        all.appendChild(el("h2", null, it.title));
        all.appendChild(Review.build(it.stage, it.data, {}));
      });
      Review.print("Board of Studies record", j.dept_name, all);
    };
    copy.addEventListener("click", printAll);
    if (!go) return;

    go.addEventListener("click", () => {
      go.disabled = true;
      go.innerHTML = '<span class="loader-one is-light" aria-hidden="true"><i></i><i></i><i></i></span>Submitting…';
      err.hidden = true;
      fetch(opts.submit, { method: "POST", credentials: "same-origin" }).then(r => r.json()).then(res => {
        if (res.ok) {
          ctl.panel.querySelector(".rv-head h3").textContent = "Submitted";
          const done = el("div", "rv-done");
          done.appendChild(el("span", "rv-done-tick", "✓"));
          const w = el("div");
          w.appendChild(el("strong", null, "Your Board of Studies record is with the Office of Academics."));
          w.appendChild(el("span", null, res.done.length
            ? `${res.done.length} stage${res.done.length === 1 ? "" : "s"} and programme parts submitted just now — every one is ticked below.`
            : "Everything was already submitted."));
          done.appendChild(w);
          top.replaceWith(done);
          ctl.panel.querySelectorAll(".sa-item:not(.is-submitted)").forEach(d => {
            d.className = "sa-item is-submitted";
            d.querySelector(".sa-dot").textContent = "✓";
            d.querySelector(".sa-status").textContent = "Submitted";
          });
          if (terms) terms.remove();
          go.remove();
          const on = el("a", "btn btn-gold", "Done");
          on.href = res.redirect || "/department/";
          row.appendChild(on);
          return;
        }
        // stopped at one: say which, why, and take them there
        go.disabled = false;
        go.textContent = "Try again";
        err.hidden = false;
        err.textContent = "";
        const f = res.failed || {};
        err.appendChild(el("strong", null, (res.done && res.done.length ? `Submitted ${res.done.length}; stopped at ` : "Could not submit ") + (f.title || "a stage") + "."));
        const ul = el("ul");
        (f.issues || []).forEach(i => ul.appendChild(el("li", null, i.message)));
        err.appendChild(ul);
        if (f.url) { const a = el("a", "btn btn-sm", "Go to it and fix it →"); a.href = f.url; err.appendChild(a); }
        if (window.Toast) window.Toast.error((f.title || "A stage") + " needs fixing before everything can be submitted.", { title: "Not all submitted" });
      }).catch(() => { go.disabled = false; go.textContent = "Try again"; });
    });
  }

  window.SubmitAll = { open };
})();

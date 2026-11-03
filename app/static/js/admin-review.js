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

  const post = (url, body) => fetch(url, {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  }).then(r => r.json());

  /* Train: the words this file carries that its upload box's keywords do not
     have yet. The Office ticks the right ones and adds them; the file is
     checked again with the new list. */
  function train(v, chip, j) {
    const next = chip.nextElementSibling;
    if (next && next.classList.contains("kw-train")) { next.remove(); return; }
    const box = el("div", "kw-train");
    box.appendChild(el("p", "small muted", "Reading " + v.name + "…"));
    chip.after(box);
    post(j.train_url, { dept_code: j.dept_code, stored: v.stored }).then(r => {
      box.textContent = "";
      if (!r.ok) { box.appendChild(el("p", "small rv-warn", r.error || "This file could not be read.")); return; }
      box.appendChild(el("strong", null, `Train “${r.label}” from ${v.name}`));
      const now = el("p", "small kw-train-now");
      now.appendChild(el("span", "muted", "Keywords now: "));
      r.current.forEach(w => {
        const t = el("span", "kw-tag" + (r.found.includes(w) ? " is-hit" : ""), w.split("/")[0].trim());
        t.title = w;
        now.appendChild(t);
        now.appendChild(document.createTextNode(" "));
      });
      box.appendChild(now);
      if (r.unread) {
        box.appendChild(el("p", "small", "This file has no text to read (a scan or an image) — there is nothing to learn from it."));
        return;
      }
      if (!r.suggestions.length) {
        box.appendChild(el("p", "small", "Nothing new: the words this file uses often are in the list already."));
        return;
      }
      box.appendChild(el("p", "small", "Words this file uses often that the list does not have. Tick the right ones and add them:"));
      const list = el("div", "kw-train-list");
      const ticks = r.suggestions.map(sg => {
        const lab = el("label", "kw-train-opt");
        const cb = el("input");
        cb.type = "checkbox";
        cb.value = sg.word;
        lab.appendChild(cb);
        lab.appendChild(el("span", null, sg.word));
        lab.appendChild(el("small", "muted", ` ×${sg.count}`));
        list.appendChild(lab);
        return cb;
      });
      box.appendChild(list);
      const acts = el("div", "kw-train-acts");
      const add = el("button", "btn btn-sm", "Add to keywords");
      add.type = "button";
      add.disabled = true;
      const paint = () => {
        const n = ticks.filter(c => c.checked).length;
        add.disabled = !n;
        add.textContent = n ? `Add ${n} to keywords` : "Add to keywords";
      };
      ticks.forEach(c => c.addEventListener("change", paint));
      const cancel = el("button", "btn btn-ghost btn-sm", "Cancel");
      cancel.type = "button";
      cancel.addEventListener("click", () => box.remove());
      add.addEventListener("click", () => {
        const words = ticks.filter(c => c.checked).map(c => c.value);
        add.disabled = true;
        post(j.train_add_url, { field: r.field, words, dept_code: j.dept_code, stored: v.stored }).then(a => {
          if (!a.ok) { if (window.Toast) window.Toast.error(a.error || "Could not add them."); add.disabled = false; return; }
          box.textContent = "";
          box.classList.add("is-done");
          const said = a.added.length ? `Added to “${r.label}”: ${a.added.join(", ")}.` : "They were in the list already.";
          box.appendChild(el("strong", null, said));
          if (a.match) box.appendChild(el("p", "small", "This file, checked again: " +
            ({ match: "keywords match", weak: "few keywords match", miss: "no keywords match", unread: "not readable" }[a.match.status] || a.match.status) + "."));
          box.appendChild(el("p", "small muted", "The next uploads to this box are checked with the new list. See or change it under Settings › Keywords."));
          if (window.Toast) window.Toast.success(said, { title: "Keywords trained" });
        }).catch(() => { add.disabled = false; if (window.Toast) window.Toast.error("Could not reach the server. Try again."); });
      });
      acts.appendChild(add);
      acts.appendChild(cancel);
      box.appendChild(acts);
    }).catch(() => { box.textContent = ""; box.appendChild(el("p", "small rv-warn", "Could not reach the server. Try again.")); });
  }

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

      const body = Review.build(j.stage, j.data, j.train_url ? { trainFile: (v, chip) => train(v, chip, j) } : {});
      const foot = el("div", "rv-admin-acts");
      // the links are left out for someone whose access does not reach them
      if (j.status === "submitted" && j.return_url) {
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
      // comments: what the Office asked to change, and a box to ask for more
      (j.comments || []).forEach(c => {
        const box = el("div", "office-comment" + (c.status === "open" ? "" : " is-done"));
        box.appendChild(el("div", "oc-head", null));
        box.firstChild.appendChild(el("strong", null, (c.status === "open" ? "Open comment" : c.status === "done" ? "Done by the department" : "Closed") + " · " + c.at));
        box.appendChild(el("p", "oc-text", c.text));
        if (c.reply) box.appendChild(el("p", "small muted", "Reply: " + c.reply));
        foot.appendChild(box);
      });
      const cf = el("form", "rv-admin-acts");
      cf.method = "post";
      cf.action = j.comment_url;
      [["dept", j.dept_code], ["stage", j.stage.key], ["programme", j.programme || ""]].forEach(([n, v]) => {
        const h = el("input"); h.type = "hidden"; h.name = n; h.value = v; cf.appendChild(h);
      });
      const ta2 = el("textarea");
      ta2.name = "text"; ta2.required = true; ta2.rows = 2;
      ta2.placeholder = "Comment: what should the department change?";
      cf.appendChild(ta2);
      const lab = el("label", "check small");
      const cb = el("input"); cb.type = "checkbox"; cb.name = "reopen"; cb.checked = j.status === "submitted";
      lab.appendChild(cb);
      lab.appendChild(el("span", null, " open it again for them"));
      if (j.return_url) cf.appendChild(lab);
      const cbtn = el("button", "btn", "Send comment");
      cbtn.type = "submit";
      cf.appendChild(cbtn);
      if (j.comment_url) foot.appendChild(cf);

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

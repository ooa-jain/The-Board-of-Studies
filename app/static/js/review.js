/* The review of a stage: everything entered, section by section, in plain
   reading form — the same view for the department before it submits and
   for the Office when it checks. Files are links that open them; a
   department can also remove one, or jump back to a section to change it.

   window.Review.build(stage, data, opts) → element
     opts.viewFile(val)          open a file (else its url opens in a tab)
     opts.removeFile(path)       offer Remove beside each file
     opts.edit(sectionKey)       offer “Change” beside each section
   window.Review.stats(stage, data) → { filled, total, percent, missing[] }
   window.Review.modal({ title, sub, body, foot }) → { el, close }
   window.Review.print(title, sub, body)  a copy to print or save as PDF */
(function () {
  "use strict";

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const isFile = v => v && typeof v === "object" && !Array.isArray(v) && v.name && (v.url || v.stored);
  const isFiles = v => Array.isArray(v) && v.length && v.every(isFile);
  const empty = v => v === null || v === undefined || (typeof v === "string" && !v.trim()) ||
                     (Array.isArray(v) && !v.length) ||
                     (typeof v === "object" && !Array.isArray(v) && !isFile(v) && !Object.keys(v).length);
  // sections worked out from others: shown on the form, not entered
  const DERIVED = ["credit_distribution", "credit_matrix", "revision_summary"];

  function shown(def) {
    return def && !def.hidden && def.type !== "hidden";
  }
  function enterable(def) {
    return shown(def) && def.type !== "readonly" && !def.readonly && !def.fixed_value;
  }

  function text(v, def) {
    if (v === true) return "Yes";
    if (v === false) return "No";
    if (Array.isArray(v)) return v.map(x => typeof x === "object" ? (x.name || x.label || JSON.stringify(x)) : x).join(", ");
    if (typeof v === "object") return Object.values(v).filter(x => x !== "" && x != null).join(" · ");
    if (def && def.type === "date" && /^\d{4}-\d\d-\d\d$/.test(v)) {
      const [y, m, d] = v.split("-");
      return `${d}/${m}/${y}`;
    }
    return String(v);
  }

  function fileChip(v, path, opts) {
    const chip = el("span", "rv-file");
    const kind = /\.pdf$/i.test(v.name) ? "PDF" : (v.name.split(".").pop() || "").toUpperCase();
    chip.appendChild(el("span", "rv-file-ext", kind));
    const a = el("a", "rv-file-name", v.name);
    a.href = v.url ? v.url + (/\.(pdf|png|jpe?g|webp|gif)$/i.test(v.name) ? "?inline=1" : "") : "#";
    a.target = "_blank";
    a.rel = "noopener";
    if (opts.viewFile) a.addEventListener("click", e => { e.preventDefault(); opts.viewFile(v); });
    chip.appendChild(a);
    const tp = v.match && v.match.template;
    if (tp && ((tp.blank || []).length || (tp.half || []).length || tp.placeholders)) {
      const mk = el("span", "rv-kw is-miss", "! blank: " + ((tp.blank || []).concat(tp.half || []).join(", ") || "“Words only” left"));
      mk.title = "Fill these in the form and upload it again";
      chip.appendChild(mk);
    } else if (tp) chip.appendChild(el("span", "rv-kw is-match", "✓ form filled"));
    if (v.match && v.match.status && v.match.status !== "unread") {
      const ok = v.match.status === "match";
      const mk = el("span", "rv-kw is-" + v.match.status, ok ? "✓ keywords" : v.match.status === "weak" ? "! few keywords" : "! no keywords");
      mk.title = ok ? "Keywords match" : "Check this is the right file";
      chip.appendChild(mk);
    }
    if (opts.removeFile) {
      const rm = el("button", "rv-file-rm", "Remove");
      rm.type = "button";
      rm.addEventListener("click", () => opts.removeFile(path));
      chip.appendChild(rm);
    }
    return chip;
  }

  function value(v, def, path, opts) {
    if (isFile(v)) return fileChip(v, path, opts);
    if (isFiles(v)) {
      const box = el("span", "rv-files");
      v.forEach((f, i) => box.appendChild(fileChip(f, path.concat(i), opts)));
      return box;
    }
    if (empty(v)) return el("span", "rv-empty" + (def && def.required ? " is-req" : ""), def && def.required ? "Not filled — required" : "—");
    const s = el("span", "rv-val", text(v, def));
    if (String(text(v, def)).length > 160) s.classList.add("is-long");
    return s;
  }

  function fieldsBlock(section, data, opts) {
    const dl = el("dl", "rv-dl");
    (section.fields || []).forEach(f => {
      if (!shown(f)) return;
      const v = (data || {})[f.name];
      if ((f.type === "readonly" || f.readonly) && empty(v)) return;   // worked out elsewhere
      dl.appendChild(el("dt", null, f.label || f.name));
      const dd = el("dd");
      if (f.type === "fixed") dd.appendChild(el("span", "rv-std", "As set by the university"));
      else if (empty(v) && f.prefill_text) {
        const std = el("span", "rv-std", f.prefill_text);
        std.title = "Left empty, so the standard wording is used";
        dd.appendChild(std);
        dd.appendChild(el("span", "rv-std-tag", "standard wording"));
      } else dd.appendChild(value(v, f, [section.key, f.name], opts));
      dl.appendChild(dd);
    });
    return dl;
  }

  function tableBlock(section, rows, opts) {
    rows = Array.isArray(rows) ? rows.filter(r => r && Object.values(r).some(x => !empty(x))) : [];
    if (!rows.length) return el("p", "rv-empty", "No rows entered.");
    const cols = (section.columns || []).filter(shown);
    // long text columns (modules, outcomes, books) read better as a list under each row
    const longCols = cols.filter(c => ["textarea", "module_compare"].includes(c.type) || c.rows > 2);
    const shortCols = cols.filter(c => !longCols.includes(c)).slice(0, 9);
    const wrap = el("div", "rv-table-wrap");
    const t = el("table", "rv-table");
    const hr = el("tr");
    hr.appendChild(el("th", null, "#"));
    shortCols.forEach(c => hr.appendChild(el("th", null, c.label || c.name)));
    const thead = el("thead"); thead.appendChild(hr); t.appendChild(thead);
    const tb = el("tbody");
    rows.forEach((r, i) => {
      const tr = el("tr");
      tr.appendChild(el("td", "rv-rown", String(i + 1)));
      shortCols.forEach(c => {
        const td = el("td");
        td.appendChild(value(r[c.name], null, [section.key, i, c.name], opts));
        tr.appendChild(td);
      });
      tb.appendChild(tr);
      const longs = longCols.filter(c => !empty(r[c.name]));
      if (longs.length) {
        const lr = el("tr", "rv-long");
        const td = el("td");
        td.colSpan = shortCols.length + 1;
        longs.forEach(c => {
          const p = el("div", "rv-long-item");
          p.appendChild(el("strong", null, (c.label || c.name) + ": "));
          const v = r[c.name];
          p.appendChild(el("span", null, typeof v === "object" ? text(v) : String(v)));
          td.appendChild(p);
        });
        lr.appendChild(td);
        tb.appendChild(lr);
      }
    });
    t.appendChild(tb);
    wrap.appendChild(t);
    const n = el("p", "rv-count", `${rows.length} row${rows.length === 1 ? "" : "s"}`);
    const box = el("div");
    box.appendChild(n);
    box.appendChild(wrap);
    return box;
  }

  function programmeBlock(rows) {
    rows = Array.isArray(rows) ? rows : [];
    if (!rows.length) return el("p", "rv-empty is-req", "No programmes listed.");
    const ul = el("ul", "rv-progs");
    rows.forEach(p => {
      const li = el("li", p.decision === "remove" ? "is-removed" : "");
      li.appendChild(el("span", "rv-prog-deg", p.degree || ""));
      li.appendChild(el("strong", null, p.programme_name || p.programme_code || "—"));
      li.appendChild(el("span", "rv-prog-code", p.programme_code || ""));
      li.appendChild(el("span", "rv-prog-dec", p.decision === "remove"
        ? "Removed" + (p.removal_reason ? " — " + p.removal_reason : "")
        : p.source === "new" ? "New" : "Kept"));
      ul.appendChild(li);
    });
    return ul;
  }

  function stats(stage, data) {
    data = data || {};
    let filled = 0, total = 0;
    const missing = [];
    (stage.sections || []).forEach(sec => {
      if (sec.hidden || sec.frozen || DERIVED.includes(sec.type)) return;
      const d = data[sec.key];
      if (sec.type === "table" || sec.type === "programme_list") {
        if (sec.min_rows === 0) return;          // optional: nothing missing if empty
        total += 1;
        const rows = Array.isArray(d) ? d.filter(r => r && Object.values(r).some(x => !empty(x))) : [];
        if (rows.length) filled += 1; else missing.push(sec.title || sec.key);
        return;
      }
      (sec.fields || []).forEach(f => {
        if (!enterable(f) || f.type === "fixed" || f.type === "file" && !f.required && f.help && /only if/i.test(f.help)) return;
        total += 1;
        const v = (d || {})[f.name];
        if (!empty(v)) filled += 1;
        else if (f.required || f.prefill_text) {
          if (!f.prefill_text) missing.push(f.label || f.name);
          else filled += 1;          // left empty means the standard wording
        }
      });
    });
    return { filled, total, percent: total ? Math.round(filled * 100 / total) : 100, missing };
  }

  function build(stage, data, opts) {
    opts = opts || {};
    data = data || {};
    const box = el("div", "rv");
    (stage.sections || []).forEach(sec => {
      if (sec.hidden || DERIVED.includes(sec.type)) return;
      const part = el("section", "rv-sec");
      const head = el("div", "rv-sec-head");
      head.appendChild(el("h4", null, sec.title || ""));
      if (sec.frozen) head.appendChild(el("span", "rv-lock", "from the Office record"));
      if (opts.edit && !sec.frozen) {
        const b = el("button", "rv-edit", "Change");
        b.type = "button";
        b.addEventListener("click", () => opts.edit(sec.key));
        head.appendChild(b);
      }
      part.appendChild(head);
      const d = data[sec.key];
      if (sec.type === "programme_list") part.appendChild(programmeBlock(d));
      else if (sec.type === "table") part.appendChild(tableBlock(sec, d, opts));
      else part.appendChild(fieldsBlock(sec, d, opts));
      box.appendChild(part);
    });
    return box;
  }

  function modal(o) {
    const back = el("div", "rv-modal");
    back.setAttribute("role", "dialog");
    back.setAttribute("aria-modal", "true");
    back.setAttribute("aria-label", o.title);
    const panel = el("div", "rv-panel");
    const head = el("div", "rv-head");
    const hl = el("div");
    hl.appendChild(el("h3", null, o.title));
    if (o.sub) hl.appendChild(el("p", "rv-sub", o.sub));
    head.appendChild(hl);
    const x = el("button", "rv-x", "×");
    x.type = "button";
    x.setAttribute("aria-label", "Close");
    head.appendChild(x);
    panel.appendChild(head);
    if (o.top) panel.appendChild(o.top);
    const body = el("div", "rv-body");
    if (o.body) body.appendChild(o.body);
    panel.appendChild(body);
    if (o.foot) { const f = el("div", "rv-foot"); f.appendChild(o.foot); panel.appendChild(f); }
    back.appendChild(panel);
    const close = () => { back.remove(); document.body.classList.remove("rv-open"); document.removeEventListener("keydown", esc); if (o.onClose) o.onClose(); };
    const esc = e => { if (e.key === "Escape") close(); };
    x.addEventListener("click", close);
    back.addEventListener("click", e => { if (e.target === back) close(); });
    document.addEventListener("keydown", esc);
    document.body.appendChild(back);
    document.body.classList.add("rv-open");
    x.focus();
    return { el: back, panel, body, close };
  }

  function print(title, sub, body) {
    const w = window.open("", "_blank");
    if (!w) { window.print(); return; }
    const css = `body{font:14px/1.5 Roboto,Segoe UI,Arial,sans-serif;color:#1d3c6e;margin:32px}
      h1{font-size:20px;margin:0 0 2px;color:#0e3d7c} .sub{color:#5f6672;margin:0 0 18px}
      .rv-sec{border:1px solid #dde3ea;border-radius:10px;padding:12px 14px;margin:0 0 12px;page-break-inside:avoid}
      .rv-sec-head h4{margin:0 0 8px;font-size:15px;color:#0e3d7c} .rv-edit,.rv-file-rm{display:none}
      .rv-lock{font-size:11px;color:#5f6672} dl{display:grid;grid-template-columns:240px 1fr;gap:4px 14px;margin:0}
      dt{color:#5f6672} dd{margin:0} table{border-collapse:collapse;width:100%;font-size:12px}
      th,td{border:1px solid #dde3ea;padding:4px 6px;text-align:left;vertical-align:top} th{background:#eef3fa}
      .rv-file{display:inline-flex;gap:6px;margin:0 8px 4px 0} .rv-file-ext{font-size:10px;font-weight:700}
      .rv-kw{font-size:11px;color:#5f6672} .rv-empty{color:#9aa0a8} .rv-empty.is-req{color:#b23a2a}
      .rv-count{font-size:12px;color:#5f6672;margin:0 0 4px} ul{margin:0;padding-left:18px} .is-removed{text-decoration:line-through;color:#9aa0a8}
      .rv-long-item{font-size:12px;margin:2px 0} .foot{margin-top:24px;font-size:12px;color:#5f6672}`;
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${title.replace(/</g, "&lt;")}</title><style>${css}</style></head><body>
      <h1></h1><p class="sub"></p><div id="b"></div>
      <p class="foot">BoS Academic Portal · JAIN (Deemed-to-be University) · Office of Academics · printed ${new Date().toLocaleString()}</p></body></html>`);
    w.document.close();
    w.document.querySelector("h1").textContent = title;
    w.document.querySelector(".sub").textContent = sub || "";
    w.document.getElementById("b").appendChild(w.document.importNode(body.cloneNode(true), true));
    w.focus();
    setTimeout(() => w.print(), 300);
  }

  window.Review = { build, stats, modal, print };
})();

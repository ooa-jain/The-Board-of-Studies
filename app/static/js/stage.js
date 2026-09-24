/* ==========================================================================
   Stage form renderer + live validator.

   Builds the whole form from the stage definition emitted by app/schema.py,
   keeps a single `state` object in memory, autosaves it, and mirrors the
   server's validation rules closely enough to catch mistakes at the keystroke.
   The server re-validates everything on submit — this is convenience, not
   the gate.
   ========================================================================== */

(function () {
  "use strict";

  const STAGE = JSON.parse(document.getElementById("stage-def").textContent);
  const CREDIT = JSON.parse(document.getElementById("credit-def").textContent || "{}");
  const CTX = window.STAGE_CTX;
  let state = JSON.parse(document.getElementById("stage-data").textContent || "{}");

  const root = document.getElementById("sections");
  const issuesBox = document.getElementById("issues");
  const countsBox = document.getElementById("issue-counts");
  const saveNote = document.getElementById("save-note");

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  // ---------------------------------------------------------------- helpers

  function get(sectionKey) {
    return state[sectionKey];
  }

  function setVal(sectionKey, field, value) {
    state[sectionKey] = state[sectionKey] || {};
    state[sectionKey][field] = value;
    touch();
  }

  function rows(sectionKey) {
    if (!Array.isArray(state[sectionKey])) state[sectionKey] = [];
    return state[sectionKey];
  }

  function words(s) {
    return String(s || "").trim().split(/\s+/).filter(Boolean).length;
  }

  function lines(s) {
    return String(s || "").split("\n").map(x => x.trim()).filter(Boolean);
  }

  // ------------------------------------------------- keystroke-level typing

  // Integer fields accept digits only; name-like fields reject digits; etc.
  function constrain(input, def) {
    const t = def.type;
    input.addEventListener("keypress", (e) => {
      if (e.ctrlKey || e.metaKey || e.key.length > 1) return;
      if (t === "integer" && !/[0-9]/.test(e.key)) { e.preventDefault(); flash(input); }
      if (t === "number" && !/[0-9.\-]/.test(e.key)) { e.preventDefault(); flash(input); }
      if (t === "phone" && !/[0-9+ ]/.test(e.key)) { e.preventDefault(); flash(input); }
    });
    input.addEventListener("paste", (e) => {
      if (t !== "integer" && t !== "number") return;
      const text = (e.clipboardData || window.clipboardData).getData("text");
      if (!/^-?[0-9.]+$/.test(text.trim())) { e.preventDefault(); flash(input); }
    });
  }

  function flash(input) {
    input.style.borderColor = "var(--err)";
    clearTimeout(input._flashTimer);
    input._flashTimer = setTimeout(() => { input.style.borderColor = ""; }, 380);
  }

  // Mirror of validation.validate_field, for immediate feedback only.
  function checkField(def, value) {
    const label = def.label || def.name;
    if (def.type === "readonly") return null;

    const blank = value === null || value === undefined || value === "" ||
                  (Array.isArray(value) && !value.length);
    if (blank) return null; // "required" is reported on check/submit, not while typing

    if (def.type === "integer" || def.type === "number") {
      const n = Number(value);
      if (Number.isNaN(n)) return `${label} must be a number.`;
      if (def.type === "integer" && !Number.isInteger(n)) return `${label} must be a whole number.`;
      if (def.min !== undefined && def.min !== null && n < def.min)
        return `${label} cannot be less than ${def.min}. You typed ${value}.`;
      if (def.max !== undefined && def.max !== null && n > def.max)
        return `${label} cannot be more than ${def.max}. You typed ${value}.`;
      return null;
    }
    if (def.type === "email") {
      if (!/^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/.test(String(value).trim()))
        return `${label} is not a valid email address.`;
      return null;
    }
    if (def.pattern) {
      let re;
      try { re = new RegExp(def.pattern); } catch (_) { re = null; }
      if (re && !re.test(String(value)))
        return `${label} is not in the expected format.${def.help ? " " + def.help : ""}`;
    }
    if (def.min_words && words(value) < def.min_words)
      return `${label} needs at least ${def.min_words} words. You have ${words(value)}.`;
    if (def.min_items && lines(value).length < def.min_items)
      return `${label} needs at least ${def.min_items} entries, one per line. You have ${lines(value).length}.`;
    return null;
  }

  let errSeq = 0;

  function attachLiveCheck(input, def, wrap) {
    const show = () => {
      const msg = checkField(def, readInput(input, def));
      wrap.querySelectorAll(":scope > .field-error").forEach(n => n.remove());
      input.classList.toggle("is-bad", !!msg);
      if (msg) {
        if (!input.id) input.id = `fld-${++errSeq}`;
        const errId = `${input.id}-error`;
        const node = el("span", "field-error", msg);
        node.id = errId;
        wrap.appendChild(node);
        input.setAttribute("aria-invalid", "true");
        describe(input, errId);
      } else {
        input.removeAttribute("aria-invalid");
        undescribe(input, `${input.id}-error`);
      }
    };
    input.addEventListener("blur", show);
    input.addEventListener("input", () => {
      if (input.classList.contains("is-bad")) show();
      touch();
    });
    input.addEventListener("change", show);
  }

  /** aria-describedby is a token list — add and remove without clobbering it. */
  function describe(input, id) {
    const ids = (input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (!ids.includes(id)) ids.push(id);
    input.setAttribute("aria-describedby", ids.join(" "));
  }

  function undescribe(input, id) {
    const ids = (input.getAttribute("aria-describedby") || "")
      .split(/\s+/).filter(Boolean).filter(x => x !== id);
    if (ids.length) input.setAttribute("aria-describedby", ids.join(" "));
    else input.removeAttribute("aria-describedby");
  }

  function readInput(input, def) {
    if (def.type === "checkbox") return input.checked;
    return input.value;
  }

  // ------------------------------------------------------------- widgets

  function makeInput(def, value, onChange) {
    let input;
    if (def.type === "textarea") {
      input = el("textarea");
      input.rows = def.rows || 3;
      input.value = value ?? "";
    } else if (def.type === "select") {
      input = el("select");
      input.appendChild(new Option(def.required ? "Choose…" : "—", ""));
      (def.options || []).forEach(o => input.appendChild(new Option(o, o)));
      input.value = value ?? "";
    } else if (def.type === "checkbox") {
      input = el("input");
      input.type = "checkbox";
      input.checked = !!value;
    } else if (def.type === "file") {
      input = el("input");
      input.type = "file";
      if (def.accept) input.accept = def.accept;
      if (def.multiple) input.multiple = true;
    } else if (def.type === "readonly") {
      input = el("input");
      input.type = "text";
      input.readOnly = true;
      input.value = value ?? "";
    } else {
      input = el("input");
      input.type = { integer: "text", number: "text", email: "email",
                     date: "date", phone: "tel" }[def.type] || "text";
      if (def.type === "integer" || def.type === "number") input.inputMode = "numeric";
      input.value = value ?? "";
    }

    if (def.placeholder) input.placeholder = def.placeholder;
    if (def.required) input.setAttribute("aria-required", "true");
    if (CTX.readonly) { input.disabled = true; }
    constrain(input, def);

    if (def.type === "file") {
      input.addEventListener("change", () => uploadFile(input, def, onChange));
    } else {
      input.addEventListener("input", () => onChange(readInput(input, def)));
      input.addEventListener("change", () => onChange(readInput(input, def)));
    }
    return input;
  }

  /* ---------------------------------------------------------------- preview
     A file that has just been uploaded should be visible without leaving the
     form: the wrong scan is otherwise found weeks later by somebody else.

     A PDF previews for real — browsers render one natively, so a scaled-down
     frame of the first page is the actual document. So does an image. A Word
     or Excel file cannot be rendered in a browser without shipping a
     converter, so it gets a page-shaped card carrying its type, its name and
     its size, and opens in one click. */

  const IMAGE = /\.(png|jpe?g|webp|gif)$/i;

  function fileKind(name) {
    const ext = (String(name).match(/\.([a-z0-9]+)$/i) || [, ""])[1].toLowerCase();
    if (ext === "pdf") return { ext, kind: "pdf", label: "PDF" };
    if (IMAGE.test("." + ext)) return { ext, kind: "image", label: ext.toUpperCase() };
    if (ext === "doc" || ext === "docx") return { ext, kind: "doc", label: "WORD" };
    if (ext === "xls" || ext === "xlsx" || ext === "csv")
      return { ext, kind: "sheet", label: ext === "csv" ? "CSV" : "EXCEL" };
    return { ext, kind: "other", label: (ext || "file").toUpperCase() };
  }

  function sizeLabel(bytes) {
    if (!bytes && bytes !== 0) return "";
    return bytes >= 1048576
      ? (bytes / 1048576).toFixed(1) + " MB"
      : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function filePreview(host, val) {
    const old = host.querySelector(".file-preview");
    if (old) old.remove();
    if (!val || !val.name) return;

    const info = fileKind(val.name);
    const card = el("div", "file-preview kind-" + info.kind);

    const thumb = el("div", "file-thumb");

    // the card that stands in when the real thing cannot be shown: a page
    // with its corner turned, carrying the file's type
    function drawnPage() {
      const d = el("span", "file-drawn");
      d.appendChild(el("span", "file-ext", info.label));
      return d;
    }

    if (val.thumb || (val.url && info.kind === "image")) {
      /* A picture of the first page, drawn by the server. Whether a browser
         will render a PDF inside the page is up to the browser; an image is
         not. If it never arrives — no renderer on the server, an encrypted
         file — the card takes its place. */
      const img = document.createElement("img");
      img.src = val.thumb || (val.url + "?inline=1");
      img.alt = info.kind === "pdf"
        ? "First page of " + val.name : "Preview of " + val.name;
      img.loading = "lazy";
      img.addEventListener("error", function () {
        img.remove();
        thumb.classList.add("is-drawn");
        thumb.appendChild(drawnPage());
      });
      thumb.appendChild(img);
    } else {
      thumb.classList.add("is-drawn");
      thumb.appendChild(drawnPage());
    }
    card.appendChild(thumb);

    const meta = el("div", "file-meta");
    meta.appendChild(el("strong", "file-name", val.name));
    const facts = el("span", "file-facts");
    facts.textContent = [info.label, sizeLabel(val.size)].filter(Boolean).join(" · ");
    meta.appendChild(facts);

    if (val.url) {
      const open = el("a", "file-open", info.kind === "pdf" || info.kind === "image"
        ? "Open full size" : "Open");
      open.href = val.url;
      open.target = "_blank";
      open.rel = "noopener";
      meta.appendChild(open);
      if (info.kind === "doc" || info.kind === "sheet") {
        meta.appendChild(el("span", "file-note",
          "Word and Excel files cannot be shown in a browser — open it to check it."));
      }
    }
    card.appendChild(meta);
    host.appendChild(card);
  }

  function uploadFile(input, def, onChange) {
    const file = input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("stage", CTX.key);
    fd.append("field", def.name);
    const note = input.parentElement.querySelector(".upload-note") ||
                 input.parentElement.appendChild(el("span", "help upload-note"));
    note.className = "help upload-note";
    note.setAttribute("role", "status");
    note.textContent = "Uploading…";
    fetch(CTX.urls.upload, { method: "POST", body: fd })
      .then(r => r.json())
      .then(j => {
        if (j.ok) {
          // thumb comes along too, or the preview has no picture to show
          const val = { name: j.name, stored: j.stored, size: j.size,
                        url: j.url, thumb: j.thumb || null };
          note.textContent = `Uploaded: ${j.name} (${sizeLabel(j.size)})`;
          note.className = "help upload-note is-ok";
          filePreview(input.parentElement, val);
          onChange(val);
        } else {
          note.textContent = j.error || "Upload failed.";
          note.className = "help upload-note is-bad-text";
        }
      })
      .catch(() => {
        note.textContent = "Upload failed — check your connection and choose the file again.";
        note.className = "help upload-note is-bad-text";
      });
  }

  function fieldBlock(def, value, onChange) {
    const wrap = el("div", "field" + (def.type === "textarea" || def.wide ? " wide" : ""));
    wrap.dataset.field = def.name;

    if (def.type === "checkbox") {
      const lab = el("label", "check");
      const input = makeInput(def, value, onChange);
      input.id = `f-${def.name}`;
      lab.appendChild(input);
      lab.appendChild(el("span", null, def.label + (def.required ? " *" : "")));
      wrap.appendChild(lab);
      if (def.help) {
        const help = el("span", "help", def.help);
        help.id = `f-${def.name}-help`;
        wrap.appendChild(help);
        describe(input, help.id);
      }
      return wrap;
    }

    const lab = el("label", null, def.label);
    lab.setAttribute("for", `f-${def.name}`);
    if (def.required) {
      const star = el("span", "req");
      star.setAttribute("aria-hidden", "true");
      star.textContent = "*";
      lab.appendChild(star);
      lab.appendChild(el("span", "sr-only", " (required)"));
    }
    wrap.appendChild(lab);

    const input = makeInput(def, value, onChange);
    input.id = `f-${def.name}`;
    wrap.appendChild(input);

    if (value && def.type === "file" && typeof value === "object") {
      const n = el("span", "help upload-note", `Uploaded: ${value.name}`);
      n.classList.add("is-ok");
      wrap.appendChild(n);
      filePreview(wrap, value);
    }
    if (def.help) {
      const help = el("span", "help", def.help);
      help.id = `f-${def.name}-help`;
      wrap.appendChild(help);
      describe(input, help.id);
    }
    attachLiveCheck(input, def, wrap);
    return wrap;
  }

  // ------------------------------------------------------ hints and sums
  /* A small card that opens beside a field on hover or focus, saying what
     the field should hold and offering to fill it. One element serves the
     whole page. */

  const hintPop = el("div", "hint-pop");
  hintPop.hidden = true;
  hintPop.setAttribute("role", "tooltip");
  document.body.appendChild(hintPop);
  let hintTimer = null;

  function showHint(anchor, build) {
    clearTimeout(hintTimer);
    hintPop.textContent = "";
    build(hintPop);
    if (!hintPop.childNodes.length) { hintPop.hidden = true; return; }
    hintPop.hidden = false;
    const r = anchor.getBoundingClientRect();
    const w = hintPop.offsetWidth;
    const left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    hintPop.style.left = left + window.scrollX + "px";
    hintPop.style.top = r.bottom + window.scrollY + 6 + "px";
  }
  function hideHint() {
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => { hintPop.hidden = true; }, 200);
  }
  hintPop.addEventListener("mouseenter", () => clearTimeout(hintTimer));
  hintPop.addEventListener("mouseleave", hideHint);
  // the "Use" button must not steal focus and close the card before it is clicked
  hintPop.addEventListener("mousedown", e => e.preventDefault());

  function hintOn(holder, build) {
    holder.addEventListener("mouseenter", () => showHint(holder, build));
    holder.addEventListener("mouseleave", hideHint);
    holder.addEventListener("focusin", () => showHint(holder, build));
    holder.addEventListener("focusout", hideHint);
  }

  function hintCard(pop, title, lines, suggestion, current, apply) {
    pop.appendChild(el("strong", "hint-title", title));
    lines.filter(Boolean).forEach(t => pop.appendChild(el("span", "hint-line", t)));
    if (suggestion === null || suggestion === undefined || CTX.readonly) return;
    if (String(current ?? "") === String(suggestion)) {
      pop.appendChild(el("span", "hint-ok", "✓ Matches"));
      return;
    }
    const b = el("button", "hint-use", `Use ${suggestion}`);
    b.type = "button";
    b.addEventListener("click", () => { apply(); hintPop.hidden = true; });
    pop.appendChild(b);
  }

  const num = v => (v === null || v === undefined || String(v).trim() === "" ||
                    Number.isNaN(Number(v))) ? null : Number(v);
  const fmt = n => String(Math.round(n * 100) / 100);

  // Fields a table can work out for itself, from the columns it has.
  function derivedRules(section) {
    const has = n => (section.columns || []).some(c => c.name === n);
    const C = CTX.calc || {};
    const w = C.weights || {};
    const out = [];
    // "UG - 3 Year" → 3 years → 6 semesters
    const yearsOf = r => {
      const m = /(\d+)\s*Year/i.exec(String(r.degree_level || ""));
      return m ? Number(m[1]) : null;
    };
    if (has("degree_level") && has("duration_years")) {
      out.push({
        field: "duration_years", title: "Duration from the degree",
        calc: yearsOf,
        explain: r => [`“${r.degree_level}” runs for ${yearsOf(r)} year${yearsOf(r) === 1 ? "" : "s"}.`],
        empty: "Choose the degree / duration and this fills itself.",
      });
    }
    if (has("duration_years") && has("semesters")) {
      out.push({
        field: "semesters", title: "Semesters from the duration",
        calc: r => num(r.duration_years) === null ? null : num(r.duration_years) * 2,
        explain: r => [`${r.duration_years} year${num(r.duration_years) === 1 ? "" : "s"} × 2 semesters a year`],
        empty: "Enter the duration and the semesters fill themselves.",
      });
    }
    if (has("credits") && ["l", "t", "p", "e"].every(has)) {
      out.push({
        field: "credits", title: "Credits from contact hours",
        calc: r => {
          const [l, t, p, e] = ["l", "t", "p", "e"].map(k => num(r[k]));
          if ([l, t, p, e].some(x => x === null)) return null;
          return l * w.lecture + t * w.tutorial + p * w.practical + e * w.experiential;
        },
        explain: r => [
          `L ${r.l ?? "–"} × ${w.lecture} + T ${r.t ?? "–"} × ${w.tutorial} + ` +
          `P ${r.p ?? "–"} × ${w.practical} + E ${r.e ?? "–"} × ${w.experiential}`,
          `A course may carry at most ${C.max_per_course} credits.`,
        ],
        empty: "Fill L, T, P and E and the credits fill themselves.",
      });
    }
    if (has("total_marks") && has("credits")) {
      out.push({
        field: "total_marks", title: "Total marks from credits",
        calc: r => num(r.credits) === null ? null : num(r.credits) * C.marks_per_credit,
        explain: r => [`${r.credits ?? "–"} credits × ${C.marks_per_credit} marks per credit`],
        empty: "Enter the credits and the total fills itself.",
      });
    }
    if (has("ese") && has("cia") && has("total_marks")) {
      out.push({
        field: "ese", title: "End-semester marks",
        calc: r => {
          const t = num(r.total_marks), c = num(r.cia);
          return t === null || c === null || c > t ? null : t - c;
        },
        explain: r => [`Total ${r.total_marks ?? "–"} − CIA ${r.cia ?? "–"}`],
        empty: "Enter the CIA marks and the rest of the total fills in here.",
      });
    }
    return out;
  }

  function markManual(row, field, cells) {
    row._auto = (row._auto || []).filter(f => f !== field);
    row._manual = Array.from(new Set([...(row._manual || []), field]));
    if (cells[field]) cells[field].classList.remove("is-auto");
  }

  // Fill every derived field that is blank or was filled by us before.
  // A value the department typed itself is never overwritten.
  function derive(rules, row, cells) {
    if (CTX.readonly) return false;
    let changed = false;
    rules.forEach(rule => {
      const v = rule.calc(row);
      if (v === null) return;
      const blank = num(row[rule.field]) === null;
      const ours = (row._auto || []).includes(rule.field);
      const theirs = (row._manual || []).includes(rule.field);
      if (!(ours || (blank && !theirs))) return;
      const val = fmt(v);
      if (String(row[rule.field] ?? "") === val && ours) return;
      row[rule.field] = Number(val);
      row._auto = Array.from(new Set([...(row._auto || []), rule.field]));
      if (cells[rule.field]) {
        cells[rule.field].value = val;
        cells[rule.field].classList.add("is-auto");
      }
      changed = true;
    });
    return changed;
  }

  function derivedHint(pop, rule, row, cells, rules, after) {
    const v = rule.calc(row);
    const auto = (row._auto || []).includes(rule.field);
    hintCard(pop, rule.title,
      v === null ? [rule.empty] : [...rule.explain(row), `Suggested: ${fmt(v)}` +
                                   (auto ? " — filled in for you" : "")],
      v === null ? null : fmt(v), row[rule.field],
      () => {
        row._manual = (row._manual || []).filter(f => f !== rule.field);
        row._auto = (row._auto || []).filter(f => f !== rule.field);
        row[rule.field] = "";
        derive(rules, row, cells);
        touch();
        if (after) after();
      });
  }

  // Running totals under any table with credit columns.
  function renderTotals(section, data, box) {
    const creditCols = (section.columns || []).filter(c => /credits$/.test(c.name));
    box.textContent = "";
    if (!creditCols.length || !data.length) return;
    const sum = name => data.reduce((a, r) => a + (num(r[name]) || 0), 0);

    if (section.key === "semester_structure") {
      const bySem = {};
      data.forEach(r => {
        const sem = num(r.semester);
        if (sem === null) return;
        bySem[sem] = (bySem[sem] || 0) + (num(r.credits) || 0);
      });
      const total = sum("credits");
      const need = (CTX.calc || {}).required_total;
      const head = el("div", "tot-main");
      head.appendChild(el("span", "tot-label", "Total credits"));
      head.appendChild(el("span", "tot-num", fmt(total)));
      if (need) {
        const gap = need - total;
        head.appendChild(el("span", gap > 0 ? "tot-short" : "tot-met",
          gap > 0 ? `${fmt(gap)} short of ${need}` : gap < 0 ? `${fmt(-gap)} over ${need}` :
                    `meets the ${need} required`));
      }
      box.appendChild(head);
      const chips = el("div", "tot-chips");
      Object.keys(bySem).sort((a, b) => a - b).forEach(k => {
        chips.appendChild(el("span", "tot-chip", `Sem ${k} · ${fmt(bySem[k])}`));
      });
      box.appendChild(chips);
      return;
    }

    const head = el("div", "tot-main");
    creditCols.forEach(c => {
      head.appendChild(el("span", "tot-label", c.label.replace(/^Total /, "")));
      head.appendChild(el("span", "tot-num", fmt(sum(c.name))));
    });
    if (creditCols.length === 2) {
      const d = sum(creditCols[1].name) - sum(creditCols[0].name);
      head.appendChild(el("span", d === 0 ? "tot-met" : "tot-short",
                          d === 0 ? "no change" : `${d > 0 ? "+" : ""}${fmt(d)} credits`));
    }
    box.appendChild(head);
  }

  // ---------------------------------------------------------- repeating table

  function renderTable(section, host) {
    // Programme Information takes its rows from Department Information:
    // no adding or removing here, and code and name are not retyped.
    const synced = !!(section.synced_from && CTX.synced);
    const fixed = !!section.fixed_rows || synced;
    const LOCKED_COLS = ["programme_code", "programme_name"];
    const RULES = derivedRules(section);
    const DERIVED = Object.fromEntries(RULES.map(r => [r.field, r]));
    if (synced) {
      const note = el("div", "sync-note");
      note.appendChild(el("span", null,
        "These programmes come from Department Information. To add or remove one, "));
      const a = el("a", null, "change the list there");
      a.href = CTX.urls.dept_info;
      note.appendChild(a);
      note.appendChild(el("span", null, "."));
      host.appendChild(note);
    }
    const wrap = el("div", "rt-wrap");
    const table = el("table", "rt");
    const thead = el("thead");
    const htr = el("tr");
    htr.appendChild(el("th", null, "#"));
    section.columns.forEach(c => {
      const th = el("th", null, c.label + (c.required ? " *" : ""));
      if (c.width) th.style.width = c.width;
      if (c.help) th.title = c.help;
      htr.appendChild(th);
    });
    if (!fixed && !CTX.readonly) {
      const actions = el("th");
      actions.appendChild(el("span", "sr-only", "Remove row"));
      htr.appendChild(actions);
    }
    thead.appendChild(htr);
    table.appendChild(thead);

    const tbody = el("tbody");
    table.appendChild(tbody);
    wrap.appendChild(table);
    host.appendChild(wrap);

    const foot = el("div", "rt-foot");
    const count = el("span", "rt-count");
    // Row-count problems belong next to the table, not in a modal dialog.
    const rowNote = el("span", "rt-note");
    rowNote.setAttribute("role", "status");
    if (!fixed && !CTX.readonly) {
      const add = el("button", "btn btn-ghost btn-sm", "+ Add row");
      add.type = "button";
      add.addEventListener("click", () => { rows(section.key).push({}); draw(); touch(); });
      foot.appendChild(add);
    }
    foot.appendChild(count);
    foot.appendChild(rowNote);
    host.appendChild(foot);
    const totalsBox = el("div", "rt-totals");
    totalsBox.setAttribute("aria-live", "polite");
    host.appendChild(totalsBox);
    function showTotals() {
      renderTotals(section, rows(section.key), totalsBox);
      window.dispatchEvent(new CustomEvent("stage:rows", { detail: section.key }));
    }

    // seed fixed rows
    if (section.fixed_rows) {
      const data = rows(section.key);
      section.fixed_rows.forEach((label, i) => {
        data[i] = data[i] || {};
        const firstCol = section.columns[0].name;
        data[i][firstCol] = label;
      });
      data.length = section.fixed_rows.length;
    } else {
      const data = rows(section.key);
      while (data.length < (section.min_rows || 0)) data.push({});
    }

    function draw() {
      tbody.innerHTML = "";
      const data = rows(section.key);
      data.forEach((row, i) => {
        const tr = el("tr");
        tr.dataset.row = i;
        const cells = {};
        tr.appendChild(el("td", "rt-idx", String(i + 1)));

        section.columns.forEach(c => {
          const td = el("td");
          if (c.auto_index) {
            row[c.name] = i + 1;
            td.className = "rt-idx";
            td.textContent = String(i + 1);
            tr.appendChild(td);
            return;
          }
          const holder = el("div");
          holder.dataset.field = c.name;
          const input = makeInput(c, row[c.name], (v) => {
            row[c.name] = v;
            if (DERIVED[c.name]) markManual(row, c.name, cells);
            derive(RULES, row, cells);
            touch();
            showTotals();
          });
          cells[c.name] = input;
          if (DERIVED[c.name]) {
            if ((row._auto || []).includes(c.name)) input.classList.add("is-auto");
            hintOn(holder, pop => derivedHint(pop, DERIVED[c.name], row, cells, RULES, showTotals));
          }
          if (c.width) input.style.minWidth = c.width;
          if (c.type === "readonly" || (synced && LOCKED_COLS.includes(c.name))) {
            input.readOnly = true;
          }
          holder.appendChild(input);
          attachLiveCheck(input, c, holder);
          td.appendChild(holder);
          tr.appendChild(td);
        });

        if (!fixed && !CTX.readonly) {
          const td = el("td", "rt-del");
          const b = el("button", null, "×");
          b.type = "button";
          b.title = "Remove this row";
          b.setAttribute("aria-label", `Remove row ${i + 1}`);
          b.addEventListener("click", () => {
            if (data.length <= (section.min_rows || 0)) {
              rowNote.textContent =
                `This table has to keep at least ${section.min_rows} row` +
                `${section.min_rows === 1 ? "" : "s"}.`;
              return;
            }
            data.splice(i, 1);
            rowNote.textContent = "";
            draw();
            touch();
            // The row under the caret is gone — put focus somewhere sensible.
            const rowsLeft = tbody.querySelectorAll("tr").length;
            const nextRow = tbody.querySelectorAll("tr")[Math.min(i, rowsLeft - 1)];
            const target = nextRow && nextRow.querySelector("input, select, textarea");
            if (target) target.focus();
            else { const add = foot.querySelector("button"); if (add) add.focus(); }
          });
          td.appendChild(b);
          tr.appendChild(td);
        }
        tbody.appendChild(tr);
        if (!CTX.readonly && derive(RULES, row, cells)) touch();
      });
      showTotals();
      const min = section.min_rows || 0;
      count.textContent = `${data.length} row${data.length === 1 ? "" : "s"}` +
                          (min ? ` · minimum ${min}` : "");
      count.style.color = data.length < min ? "var(--err)" : "";
    }
    draw();
  }

  // ------------------------------------------------------------ credit matrix

  function renderCreditMatrix(section, host) {
    if (!CREDIT || !CREDIT.rows) {
      host.appendChild(el("p", "small muted",
        "This programme is not a three-year or four-year UG programme, so UGC Table 2 " +
        "does not apply. Enter the credits your regulations require."));
    }
    state[section.key] = state[section.key] || {};
    const data = state[section.key];

    const table = el("table", "credits");
    const thead = el("thead");
    // Built as nodes, not markup: track_label comes from the editable credit
    // rules, so it must never be parsed as HTML.
    const headRow = el("tr");
    [["S. No.", "44px", false],
     ["Broad Category of Course", null, false],
     [`UGC minimum (${CREDIT.track_label || "—"})`, "150px", true],
     ["Your credits", "130px", true]].forEach(([label, width, num]) => {
      const th = el("th", num ? "num" : null, label);
      th.scope = "col";
      if (width) th.style.width = width;
      headRow.appendChild(th);
    });
    const tickHead = el("th", "num");
    tickHead.scope = "col";
    tickHead.style.width = "70px";
    tickHead.appendChild(el("span", "sr-only", "Meets the minimum"));
    headRow.appendChild(tickHead);
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = el("tbody");
    table.appendChild(tbody);

    const totalRow = el("tr", "total");
    const inputs = {};
    const fromEls = {};

    // Which values the form filled from Section C, and which were typed.
    // Kept beside the sections, not in them, so they are never validated.
    function marks(kind) {
      state.__auto = state.__auto || {};
      const k = `${section.key}.${kind}`;
      return (state.__auto[k] = state.__auto[k] || []);
    }
    function mark(key, kind) {
      const other = kind === "auto" ? "manual" : "auto";
      const rest = marks(other).filter(x => x !== key);
      state.__auto[`${section.key}.${other}`] = rest;
      if (!marks(kind).includes(key)) marks(kind).push(key);
      if (inputs[key]) inputs[key].classList.toggle("is-auto", kind === "auto");
    }
    function courseSums() {
      const map = (CTX.calc || {}).nep_to_key || {};
      const out = {};
      (Array.isArray(state.semester_structure) ? state.semester_structure : []).forEach(r => {
        const key = map[r.nep_category];
        const c = num(r.credits);
        if (key && c !== null) out[key] = (out[key] || 0) + c;
      });
      return out;
    }
    // Section B follows the courses in Section C until the department types
    // its own figure into a category.
    function followCourses() {
      if (CTX.readonly) return;
      const sums = courseSums();
      let changed = false;
      Object.keys(inputs).forEach(key => {
        const s = sums[key];
        fromEls[key].textContent = s !== undefined ? `courses: ${fmt(s)}` : "";
        if (s === undefined) return;
        const ours = marks("auto").includes(key);
        const theirs = marks("manual").includes(key);
        const blank = num(data[key]) === null;
        if (!(ours || (blank && !theirs)) || num(data[key]) === s) return;
        data[key] = s;
        inputs[key].value = fmt(s);
        mark(key, "auto");
        changed = true;
      });
      if (changed) { tally(); touch(); }
    }
    window.addEventListener("stage:rows", e => {
      if (e.detail === "semester_structure") followCourses();
    });

    (CREDIT.rows || []).forEach(r => {
      const tr = el("tr", r.applicable ? "" : "na");
      tr.dataset.field = r.key;
      tr.appendChild(el("td", "num", String(r.sl)));
      tr.appendChild(el("td", null, r.label));

      const range = r.max ? `${pad(r.min)} – ${pad(r.max)}` : (r.applicable ? pad(r.min) : "—");
      const minTd = el("td", "num minmax", range);
      tr.appendChild(minTd);

      const td = el("td", "num");
      if (r.applicable) {
        const input = el("input");
        input.type = "text";
        input.inputMode = "numeric";
        input.value = data[r.key] ?? "";
        input.addEventListener("keypress", e => {
          if (e.key.length === 1 && !/[0-9]/.test(e.key)) { e.preventDefault(); flash(input); }
        });
        input.addEventListener("input", () => {
          data[r.key] = input.value === "" ? null : Number(input.value);
          mark(r.key, "manual");
          tally();
          touch();
        });
        if (CTX.readonly) input.disabled = true;
        if ((state.__auto || {})[`${section.key}.auto`]?.includes(r.key)) {
          input.classList.add("is-auto");
        }
        inputs[r.key] = input;
        td.appendChild(input);
        const from = el("span", "cm-from");
        fromEls[r.key] = from;
        td.appendChild(from);
        hintOn(td, pop => {
          const sums = courseSums();
          const range = r.max ? `${r.min} to ${r.max}` : `at least ${r.min}`;
          hintCard(pop, r.label,
            [`UGC Table 2: ${range} credits.`,
             sums[r.key] !== undefined
               ? `Your courses in Section C add up to ${fmt(sums[r.key])}.`
               : "No course in Section C is in this category yet."],
            sums[r.key] !== undefined ? fmt(sums[r.key]) : null, data[r.key],
            () => {
              data[r.key] = sums[r.key];
              input.value = fmt(sums[r.key]);
              mark(r.key, "auto");
              tally();
              touch();
            });
        });
      } else {
        td.appendChild(el("span", "muted", "Not applicable"));
      }
      tr.appendChild(td);
      tr.appendChild(el("td", "num tick"));
      tbody.appendChild(tr);
    });

    if (CREDIT.needs_in_lieu) {
      const note = inLieuRow("8a", "In lieu of research — courses",
                             `(${CREDIT.in_lieu.courses} required)`, CREDIT.in_lieu.courses);
      const ci = el("input");
      ci.type = "text"; ci.inputMode = "numeric";
      ci.value = data.in_lieu_courses ?? "";
      ci.addEventListener("input", () => { data.in_lieu_courses = Number(ci.value) || null; tally(); touch(); });
      if (CTX.readonly) ci.disabled = true;
      note.children[3].appendChild(ci);
      tbody.appendChild(note);

      const note2 = inLieuRow("8b", "In lieu of research — credits", null, CREDIT.in_lieu.credits);
      const cr = el("input");
      cr.type = "text"; cr.inputMode = "numeric";
      cr.value = data.in_lieu_credits ?? "";
      cr.addEventListener("input", () => { data.in_lieu_credits = Number(cr.value) || null; tally(); touch(); });
      if (CTX.readonly) cr.disabled = true;
      note2.children[3].appendChild(cr);
      tbody.appendChild(note2);
    }

    totalRow.appendChild(el("td"));
    totalRow.appendChild(el("td", null, "Total"));
    totalRow.appendChild(el("td", "num minmax", String(CREDIT.total ?? "—")));
    const totalCell = el("td", "num", "0");
    totalCell.id = "credit-total";
    totalRow.appendChild(totalCell);
    totalRow.appendChild(el("td", "num tick"));
    tbody.appendChild(totalRow);

    // Five columns will not fit a phone, so the table gets the same scrolling
    // box as the repeating tables — and a keyboard user can reach the scroll.
    const wrap = el("div", "rt-wrap");
    wrap.tabIndex = 0;
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", "UGC Table 2 credit matrix");
    wrap.appendChild(table);
    host.appendChild(wrap);

    if (CREDIT.needs_in_lieu) {
      const p = el("p", "small muted");
      p.style.marginTop = "10px";
      p.textContent = CREDIT.in_lieu.note;
      host.appendChild(p);
    }

    function pad(n) { return String(n).padStart(2, "0"); }

    function inLieuRow(sl, label, hint, minimum) {
      const tr = el("tr");
      tr.appendChild(el("td", "num", sl));
      const labelCell = el("td", null, label);
      if (hint) {
        labelCell.appendChild(document.createTextNode(" "));
        labelCell.appendChild(el("span", "muted small", hint));
      }
      tr.appendChild(labelCell);
      tr.appendChild(el("td", "num minmax", String(minimum)));
      tr.appendChild(el("td", "num"));
      tr.appendChild(el("td", "num tick"));
      return tr;
    }

    function tally() {
      let sum = 0;
      (CREDIT.rows || []).forEach(r => {
        const v = Number(data[r.key]);
        if (!Number.isNaN(v)) sum += v || 0;
        const tr = tbody.querySelector(`tr[data-field="${r.key}"]`);
        if (!tr) return;
        const tick = tr.querySelector(".tick");
        if (!r.applicable || data[r.key] === null || data[r.key] === undefined || data[r.key] === "") {
          tick.textContent = "";
          return;
        }
        const ok = v >= r.min && (r.max === null || r.max === undefined || v <= r.max);
        tick.textContent = ok ? "✓" : "✗";
        tick.className = "num tick " + (ok ? "ok-tick" : "bad-tick");
      });
      if (data.in_lieu_credits) sum += Number(data.in_lieu_credits) || 0;
      data.total = sum;
      const cell = document.getElementById("credit-total");
      if (cell) {
        cell.textContent = String(sum);
        cell.className = "num " + (CREDIT.total && sum < CREDIT.total ? "bad-tick" : "ok-tick");
      }
      const side = document.getElementById("credit-tally");
      if (side && CREDIT.total) {
        const short = CREDIT.total - sum;
        side.textContent = "";
        const head = el("span", short > 0 ? "tally-short" : "tally-met",
                        short > 0
                          ? `${short} credit${short === 1 ? "" : "s"} short`
                          : "Total requirement met");
        side.appendChild(head);
        side.appendChild(el("div", "muted",
          short > 0 ? `${sum} entered of ${CREDIT.total} required`
                    : `${sum} credits entered`));
      }
    }
    tally();
    // the course table may already have rendered above this one
    followCourses();
  }

  // --------------------------------------------------------------- cards
  /* A section the department mostly confirms rather than types: each value
     is a card, and a pencil opens the ordinary fields to change them. */

  const PENCIL = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
    '<path d="M4 20h4L19 9l-4-4L4 16v4z" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linejoin="round"/><path d="M13.5 6.5l4 4" ' +
    'stroke="currentColor" stroke-width="1.8"/></svg>';

  function renderCards(section, block) {
    state[section.key] = state[section.key] || {};
    const vals = () => state[section.key];

    const grid = el("div", "bento");
    const form = el("div", "bento-form");
    form.hidden = true;
    const fieldsGrid = el("div", "fields-grid");
    section.fields.forEach(f => {
      fieldsGrid.appendChild(fieldBlock(f, vals()[f.name], v => setVal(section.key, f.name, v)));
    });
    form.appendChild(fieldsGrid);
    const done = el("button", "btn btn-ghost btn-sm", "Done");
    done.type = "button";
    form.appendChild(done);

    // one box holding every value, with a single pencil for the lot
    function paint() {
      grid.textContent = "";
      const card = el("div", "bento-card bento-single");
      const list = el("dl", "bento-items");
      section.fields.forEach((f, i) => {
        const v = vals()[f.name];
        const empty = v === undefined || v === null || String(v).trim() === "";
        const item = el("div", "bento-item" + (i === 0 ? " is-wide" : "") +
                               (empty && f.required ? " is-missing" : ""));
        item.appendChild(el("dt", "bento-label", f.label));
        item.appendChild(el("dd", "bento-value" + (empty ? " is-empty" : ""),
                            empty ? (f.required ? "Not given yet" : "—") : String(v)));
        list.appendChild(item);
      });
      card.appendChild(list);
      if (!CTX.readonly) {
        const pen = el("button", "bento-edit");
        pen.type = "button";
        pen.innerHTML = PENCIL;
        pen.title = `Edit ${section.title.toLowerCase()}`;
        pen.setAttribute("aria-label", `Edit ${section.title}`);
        pen.addEventListener("click", () => openForm());
        card.appendChild(pen);
      }
      grid.appendChild(card);
      if (window.MagicBento) window.MagicBento.attach(grid);
    }

    function openForm(fieldName) {
      grid.hidden = true;
      form.hidden = false;
      const target = fieldName && form.querySelector(`[data-field="${fieldName}"] input, ` +
        `[data-field="${fieldName}"] select, [data-field="${fieldName}"] textarea`);
      (target || form.querySelector("input:not([readonly]), select"))?.focus();
    }
    form.openForm = openForm;

    done.addEventListener("click", () => {
      form.hidden = true;
      grid.hidden = false;
      paint();
      grid.querySelector(".bento-edit")?.focus();
    });

    block.appendChild(grid);
    block.appendChild(form);
    paint();
  }

  // ------------------------------------------------------- programme list
  /* The department's programmes from the Office of Academics workbook, in a
     UG tab and a PG tab. The minus takes a programme off — after asking why —
     and the plus puts it back or adds one the workbook does not have. A
     removed programme stays in the list, struck through with its reason, so
     the Office can see what was dropped and a slip is one click to undo. */

  const ICON = {
    plus: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
    minus: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
  };

  function iconButton(cls, icon, label) {
    const b = el("button", cls);
    b.type = "button";
    b.innerHTML = ICON[icon];
    b.title = label;
    b.setAttribute("aria-label", label);
    return b;
  }

  // Asks why a programme is being removed. Resolves with {reason, note}, or
  // null if the department thinks better of it.
  function askRemovalReason(row, reasons) {
    return new Promise(resolve => {
      const dlg = el("dialog", "reason-dlg");
      const form = el("form");
      form.method = "dialog";
      form.appendChild(el("h3", null, `Remove ${row.programme_code}?`));
      form.appendChild(el("p", "reason-prog", row.programme_name || ""));
      const fs = el("fieldset");
      fs.appendChild(el("legend", null, "Why is this programme being removed?"));
      reasons.forEach((r, i) => {
        const lab = el("label", "reason-opt");
        const radio = el("input");
        radio.type = "radio";
        radio.name = "reason";
        radio.value = r;
        if (r === row.removal_reason || (!row.removal_reason && i === 0)) radio.checked = true;
        lab.appendChild(radio);
        lab.appendChild(el("span", null, r));
        fs.appendChild(lab);
      });
      form.appendChild(fs);
      const noteLab = el("label", "reason-note-lab", "Anything the Office of Academics should know");
      const note = el("textarea");
      note.rows = 3;
      note.value = row.removal_note || "";
      note.placeholder = "For example: merged into BCHFBA from 2026-27";
      noteLab.appendChild(note);
      form.appendChild(noteLab);
      const warn = el("p", "reason-warn");
      warn.setAttribute("role", "alert");
      form.appendChild(warn);

      const actions = el("div", "reason-actions");
      const cancel = el("button", "btn btn-ghost btn-sm", "Keep it");
      cancel.type = "button";
      const ok = el("button", "btn btn-sm reason-ok", "Remove programme");
      ok.type = "submit";
      actions.appendChild(cancel);
      actions.appendChild(ok);
      form.appendChild(actions);
      dlg.appendChild(form);
      document.body.appendChild(dlg);

      let result = null;
      cancel.addEventListener("click", () => dlg.close());
      form.addEventListener("submit", e => {
        const reason = (form.querySelector("input[name=reason]:checked") || {}).value;
        if (reason === "Other" && !note.value.trim()) {
          e.preventDefault();
          warn.textContent = "Say what the reason is when you choose “Other”.";
          note.focus();
          return;
        }
        result = { reason: reason, note: note.value.trim() };
      });
      dlg.addEventListener("close", () => { dlg.remove(); resolve(result); });
      dlg.showModal();
      (form.querySelector("input[name=reason]:checked") || note).focus();
    });
  }

  function renderProgrammeList(section, host) {
    const data = rows(section.key);
    const tabs = section.tabs || [{ key: "all", label: "Programmes", degrees: null }];
    const tabOf = row => (tabs.find(t => t.degrees && t.degrees.includes(row.degree)) ||
                          tabs[0]).key;
    let active = tabs[0].key;

    const wrap = el("div", "pl-wrap");
    host.appendChild(wrap);

    const tablist = el("div", "pl-tabs");
    tablist.setAttribute("role", "tablist");
    const tabButtons = {};
    tabs.forEach(t => {
      const b = el("button", "pl-tab");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.addEventListener("click", () => { active = t.key; draw(); });
      tabButtons[t.key] = b;
      tablist.appendChild(b);
    });
    wrap.appendChild(tablist);

    const bar = el("div", "pl-bar");
    const tally = el("span", "pl-tally");
    tally.setAttribute("role", "status");
    const search = el("input", "pl-search");
    search.type = "search";
    search.placeholder = "Find a programme";
    search.setAttribute("aria-label", "Find a programme by name or code");
    bar.appendChild(tally);
    bar.appendChild(search);
    let add = null;
    if (!CTX.readonly) {
      add = el("button", "btn btn-gold btn-sm pl-add");
      add.type = "button";
      add.addEventListener("click", () => {
        const tab = tabs.find(t => t.key === active);
        data.push({ source: "new", decision: "keep", programme_code: "",
                    programme_name: "", degree: (tab.degrees || [""])[0], category: "" });
        draw();
        touch();
        list.lastElementChild?.querySelector("input")?.focus();
      });
      bar.appendChild(add);
    }
    wrap.appendChild(bar);

    const list = el("ul", "pl");
    list.setAttribute("role", "tabpanel");
    wrap.appendChild(list);

    // an issue on a row in the other tab brings that tab forward
    wrap.showRow = i => { if (data[i]) { active = tabOf(data[i]); draw(); } };

    function input(row, name, def) {
      const holder = el("div", "pl-in pl-in-" + name);
      holder.dataset.field = name;
      const i = makeInput(def, row[name], v => { row[name] = v; touch(); if (name === "degree") draw(); });
      i.setAttribute("aria-label", def.label);
      holder.appendChild(i);
      attachLiveCheck(i, def, holder);
      return holder;
    }

    function draw() {
      const tab = tabs.find(t => t.key === active);
      tabs.forEach(t => {
        const n = data.filter(r => tabOf(r) === t.key && r.decision !== "remove").length;
        const b = tabButtons[t.key];
        b.textContent = "";
        b.appendChild(el("span", null, t.label));
        b.appendChild(el("span", "pl-tab-n", String(n)));
        b.setAttribute("aria-selected", t.key === active ? "true" : "false");
      });
      if (add) {
        add.innerHTML = ICON.plus;
        add.appendChild(el("span", null, `Add ${tab.key === "all" ? "a" : tab.key} programme`));
      }

      list.textContent = "";
      const mine = data.map((r, i) => [r, i]).filter(([r]) => tabOf(r) === active);
      if (!mine.length) {
        list.appendChild(el("li", "pl-empty",
          `No ${tab.key === "all" ? "" : tab.key + " "}programmes on record. ` +
          "Use the plus button to add each one you run this year."));
      }
      mine.forEach(([row, i]) => {
        const removed = row.decision === "remove";
        const li = el("li", "pl-row" + (removed ? " is-removed" : "") +
                            (row.source === "new" ? " is-new" : ""));
        li.dataset.row = i;

        if (row.source === "new") {
          const grid = el("div", "pl-new");
          grid.appendChild(input(row, "programme_code",
            { name: "programme_code", label: "Programme code", type: "text", required: true,
              placeholder: "Code" }));
          grid.appendChild(input(row, "programme_name",
            { name: "programme_name", label: "Programme name", type: "text", required: true,
              placeholder: "Full programme name" }));
          grid.appendChild(input(row, "degree",
            { name: "degree", label: "Degree", type: "select", required: true,
              options: section.degrees || [] }));
          grid.appendChild(input(row, "category",
            { name: "category", label: "Type", type: "select",
              options: section.categories || [] }));
          li.appendChild(grid);
          li.appendChild(el("span", "pl-tag", "New"));
          if (!CTX.readonly) {
            const del = iconButton("pl-icon pl-minus", "minus", "Take this new programme off");
            del.addEventListener("click", () => { data.splice(i, 1); draw(); touch(); });
            li.appendChild(del);
          }
        } else {
          const body = el("div", "pl-body");
          const top = el("div", "pl-top");
          top.appendChild(el("span", "pl-code", row.programme_code || ""));
          top.appendChild(el("span", "pl-name", row.programme_name || ""));
          body.appendChild(top);
          const meta = [row.degree, row.year_introduced && `since ${row.year_introduced}`,
                        row.category, row.minors].filter(Boolean).join(" · ");
          if (meta) body.appendChild(el("span", "pl-meta", meta));
          if (removed) {
            const why = el("span", "pl-why");
            why.dataset.field = "removal_reason";
            why.textContent = "Removed — " + (row.removal_reason || "no reason given") +
                              (row.removal_note ? `: ${row.removal_note}` : "");
            body.appendChild(why);
          }
          li.appendChild(body);

          if (!CTX.readonly) {
            if (removed) {
              const back = iconButton("pl-icon pl-plus", "plus", `Keep ${row.programme_code} after all`);
              back.addEventListener("click", () => {
                row.decision = "keep";
                delete row.removal_reason;
                delete row.removal_note;
                draw();
                touch();
              });
              li.appendChild(back);
            } else {
              const rm = iconButton("pl-icon pl-minus", "minus", `Remove ${row.programme_code}`);
              rm.addEventListener("click", async () => {
                const answer = await askRemovalReason(row, section.removal_reasons || ["Other"]);
                if (!answer) { rm.focus(); return; }
                row.decision = "remove";
                row.removal_reason = answer.reason;
                row.removal_note = answer.note;
                draw();
                touch();
              });
              li.appendChild(rm);
            }
          }
        }
        list.appendChild(li);
      });

      const kept = data.filter(r => tabOf(r) === active && r.decision !== "remove" && r.source !== "new").length;
      const gone = data.filter(r => tabOf(r) === active && r.decision === "remove").length;
      const added = data.filter(r => tabOf(r) === active && r.source === "new").length;
      tally.textContent = `${kept} kept · ${gone} removed · ${added} new`;
      filter();
    }

    function filter() {
      const q = search.value.trim().toLowerCase();
      list.querySelectorAll(".pl-row").forEach(li => {
        const row = data[+li.dataset.row] || {};
        const hay = `${row.programme_code} ${row.programme_name}`.toLowerCase();
        li.hidden = !!q && row.source !== "new" && !hay.includes(q);
      });
    }
    search.addEventListener("input", filter);

    draw();
  }

  // ------------------------------------------------------------------ render

  function render() {
    root.textContent = "";
    if (!STAGE.sections || !STAGE.sections.length) {
      const note = el("div", "alert alert-warning");
      note.appendChild(el("div", null,
        "This stage has no fields to fill in. Tell the Office of Academics if that looks wrong."));
      root.appendChild(note);
      return;
    }
    STAGE.sections.forEach(section => {
      const block = el("div", "section-block");
      block.id = `sec-${section.key}`;
      const h = el("h3", null, section.title);
      block.appendChild(h);
      if (section.help) block.appendChild(el("div", "section-help", section.help));

      if (section.type === "table") {
        renderTable(section, block);
      } else if (section.type === "credit_matrix") {
        renderCreditMatrix(section, block);
      } else if (section.type === "programme_list") {
        renderProgrammeList(section, block);
      } else if (section.display === "cards") {
        renderCards(section, block);
      } else {
        const grid = el("div", "fields-grid");
        state[section.key] = state[section.key] || {};
        section.fields.forEach(f => {
          const b = fieldBlock(f, state[section.key][f.name],
                               v => setVal(section.key, f.name, v));
          grid.appendChild(b);
        });
        block.appendChild(grid);
      }
      root.appendChild(block);
    });
  }

  // ------------------------------------------------------- save / check / submit

  let saveTimer = null;
  let dirty = false;

  function touch() {
    dirty = true;
    saveNote.textContent = "Unsaved changes";
    saveNote.className = "save-note";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1400);
  }

  function save() {
    if (CTX.readonly || !dirty) return;
    saveNote.textContent = "Saving…";
    saveNote.className = "save-note saving";
    fetch(CTX.urls.save, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      if (j.ok) {
        dirty = false;
        saveNote.textContent = "Saved " + new Date().toLocaleTimeString();
        saveNote.className = "save-note saved";
      } else {
        saveNote.textContent = j.error || "Could not save";
        saveNote.className = "save-note";
      }
    }).catch(() => {
      saveNote.textContent = "Could not reach the server — your work is still in this tab";
    });
  }

  function paintIssues(issues, summary) {
    issuesBox.textContent = "";
    document.querySelectorAll(".is-bad").forEach(n => {
      n.classList.remove("is-bad");
      n.removeAttribute("aria-invalid");
    });

    if (!issues.length) {
      issuesBox.appendChild(el("p", "small issue-clear",
        "Everything checks out. You can submit this stage."));
      countsBox.textContent = "";
      countsBox.appendChild(pill("pill-ok", "Clear"));
      return;
    }

    countsBox.textContent = "";
    if (summary.errors) countsBox.appendChild(pill("pill-err", `${summary.errors} to fix`));
    if (summary.warnings) countsBox.appendChild(pill("pill-warn", `${summary.warnings} to check`));

    issues.forEach(iss => {
      // A button, not a clickable div: this is the fastest route to a bad
      // field and it has to be reachable from the keyboard.
      const d = el("button", "issue " + iss.level);
      d.type = "button";
      d.appendChild(el("span", null, iss.message));
      const sec = STAGE.sections.find(s => s.key === iss.section);
      const where = [sec ? sec.title : null,
                     iss.row !== null && iss.row !== undefined ? `row ${iss.row + 1}` : null]
                    .filter(Boolean).join(" · ");
      if (where) d.appendChild(el("span", "where", where));
      d.setAttribute("aria-label",
        `${iss.level === "error" ? "Error" : "Check"}: ${iss.message}${where ? " — " + where : ""}. Go to the field.`);
      d.addEventListener("click", () => focusIssue(iss));
      issuesBox.appendChild(d);

      const target = locate(iss);
      if (target && iss.level === "error") {
        const input = target.querySelector("input, select, textarea");
        if (input) {
          input.classList.add("is-bad");
          input.setAttribute("aria-invalid", "true");
        }
      }
    });
  }

  function pill(cls, text) {
    return el("span", "pill " + cls, text);
  }

  function locate(iss) {
    const block = document.getElementById(`sec-${iss.section}`);
    if (!block) return null;
    if (iss.row !== null && iss.row !== undefined) {
      const tr = block.querySelector(`[data-row="${iss.row}"]`);
      if (!tr) return block;
      return iss.field ? (tr.querySelector(`[data-field="${iss.field}"]`) || tr) : tr;
    }
    if (iss.field) {
      return block.querySelector(`[data-field="${iss.field}"]`) || block;
    }
    return block;
  }

  function focusIssue(iss) {
    const target = locate(iss);
    if (!target) return;
    // a field behind the cards has to be brought out before it can be fixed
    const behind = target.closest ? target.closest(".bento-form") : null;
    if (behind && behind.hidden && behind.openForm) behind.openForm(iss.field);
    // a programme in the tab that is not showing
    const plWrap = document.querySelector(`#sec-${iss.section} .pl-wrap`);
    if (plWrap && iss.row !== null && iss.row !== undefined &&
        !plWrap.querySelector(`[data-row="${iss.row}"]`)) {
      plWrap.showRow(iss.row);
      if (plWrap.querySelector(`[data-row="${iss.row}"]`)) return focusIssue(iss);
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    const input = target.querySelector("input, select, textarea");
    if (input) { input.focus(); input.classList.add("is-bad"); }
  }

  function check(cb) {
    const btn = document.getElementById("btn-check");
    if (btn) { btn.disabled = true; btn.textContent = "Checking…"; }
    const done = () => {
      if (btn) { btn.disabled = false; btn.textContent = "Check now"; }
    };
    fetch(CTX.urls.validate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      done();
      if (j.ok) paintIssues(j.issues, j.summary);
      else showPanelMessage(j.error || "The checks could not be run. Try again in a moment.");
      if (cb) cb(j);
    }).catch(() => {
      // Silence here used to look exactly like "no problems found".
      done();
      showPanelMessage("Could not reach the server to run the checks. Your answers are still in this tab.");
      if (cb) cb({ ok: false });
    });
  }

  /** A message in the Checks panel, for when we have no issue list to show. */
  function showPanelMessage(text) {
    issuesBox.textContent = "";
    issuesBox.appendChild(el("p", "small issue-note", text));
    countsBox.textContent = "";
  }

  function submit() {
    const btn = document.getElementById("btn-submit");
    btn.disabled = true;
    btn.textContent = "Checking…";
    save();
    fetch(CTX.urls.submit, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      if (j.ok) {
        // The dashboard flashes the confirmation, so keep the button busy
        // through the navigation rather than flicking it back to "Submit".
        btn.textContent = "Submitted";
        dirty = false;
        window.location = j.redirect || CTX.urls.dashboard;
        return;
      }
      paintIssues(j.issues || [], j.summary || { errors: 0, warnings: 0 });
      btn.disabled = false;
      btn.textContent = "Submit this stage";
      saveNote.textContent = "Not submitted — there are answers still to fix";
      saveNote.className = "save-note save-note-bad";
      const first = (j.issues || []).find(i => i.level === "error");
      if (first) focusIssue(first);
      else issuesBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }).catch(() => {
      btn.disabled = false;
      btn.textContent = "Submit this stage";
      saveNote.textContent = "Could not reach the server — nothing was submitted. Try again in a moment.";
      saveNote.className = "save-note save-note-bad";
    });
  }

  // ------------------------------------------------------------------- boot

  render();

  if (!CTX.readonly) {
    document.getElementById("btn-check").addEventListener("click", () => check());
    document.getElementById("btn-submit").addEventListener("click", submit);
    window.addEventListener("beforeunload", (e) => {
      if (dirty) { e.preventDefault(); e.returnValue = ""; }
    });
    setInterval(() => { if (dirty) save(); }, 25000);
  } else {
    check();
  }
})();

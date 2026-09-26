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
  // run after every change: counts that follow a table, and the like
  const refreshers = [];
  // course groups that carry no credits
  const NON_CREDIT = ["Mandatory Non-Credit Course", "Mandatory Non-Credit Audit Course"];
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

  // ---------------------------------------------- fixed text and module revision

  /** A block the university fixes, shown as the template shows it. */
  function fixedBlock(def) {
    const box = el("div", "fixed-block");
    (def.fixed_table || []).forEach(part => {
      const row = el("div", "fixed-part");
      row.appendChild(el("div", "fixed-head", part.head));
      const body = el("div", "fixed-body");
      const items = el("div", "fixed-items");
      (part.items || []).forEach(t => items.appendChild(el("span", "fixed-item", t)));
      body.appendChild(items);
      if (part.note) body.appendChild(el("div", "fixed-note", part.note));
      row.appendChild(body);
      box.appendChild(row);
    });
    return box;
  }

  const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                 "XI", "XII", "XIII", "XIV", "XV"];

  function wordsOf(t) {
    return String(t || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);
  }

  /** How much of a module changed, from the words the two versions share in
      order: 0 when identical, 100 when nothing carries over. */
  function percentChange(prev, next) {
    const a = wordsOf(prev), b = wordsOf(next);
    if (!b.length) return null;
    if (!a.length) return 100;
    const n = a.length, m = b.length;
    let row = new Array(m + 1).fill(0);
    for (let i = 1; i <= n; i++) {
      const cur = new Array(m + 1).fill(0);
      for (let j = 1; j <= m; j++) {
        cur[j] = a[i - 1] === b[j - 1] ? row[j - 1] + 1 : Math.max(row[j], cur[j - 1]);
      }
      row = cur;
    }
    const same = (2 * row[m]) / (n + m);
    return Math.round((1 - same) * 1000) / 10;
  }

  function averageChange(mods) {
    const v = (Array.isArray(mods) ? mods : [])
      .filter(m => m && String(m.revised || "").trim())
      .map(m => num(m.pct)).filter(x => x !== null);
    if (!v.length) return null;
    return Math.round(v.reduce((a, b) => a + b, 0) / v.length * 100) / 100;
  }

  /** Module by module: the previous syllabus beside the revised one, and the
      % change between them — worked out, unless the department types its own. */
  function moduleCompare(def, value, onChange) {
    const mods = (Array.isArray(value) ? value : []).map(m => Object.assign({}, m));
    if (!mods.length && !CTX.readonly) mods.push({});
    const box = el("div", "mc-box");
    const list = el("div", "mc-list");
    const foot = el("div", "mc-foot");
    const avg = el("span", "mc-avg");
    box.appendChild(list);
    box.appendChild(foot);

    const emit = () => {
      const a = averageChange(mods);
      avg.textContent = a === null ? "" : `Average change across modules: ${fmt(a)}%`;
      onChange(mods.map(m => Object.assign({}, m)));
    };

    function draw() {
      list.textContent = "";
      mods.forEach((m, i) => {
        const card = el("div", "mc-item");
        const head = el("div", "mc-head");
        head.appendChild(el("strong", null, `Module ${ROMAN[i] || i + 1}`));
        head.appendChild(el("span", "spacer"));
        const pctWrap = el("label", "mc-pct");
        pctWrap.appendChild(el("span", null, "% change"));
        const pct = el("input");
        pct.type = "text";
        pct.inputMode = "decimal";
        pct.value = m.pct ?? "";
        if (!m.pct_manual) pct.classList.add("is-auto");
        pct.title = "Worked out from the two versions — type to use your own figure";
        pct.addEventListener("input", () => {
          const v = pct.value.trim();
          m.pct = v === "" ? null : Number(v);
          m.pct_manual = v !== "";
          pct.classList.toggle("is-auto", !m.pct_manual);
          if (!m.pct_manual) recalc(m, pct);
          emit();
        });
        pctWrap.appendChild(pct);
        pctWrap.appendChild(el("span", null, "%"));
        head.appendChild(pctWrap);
        if (!CTX.readonly) {
          const rm = el("button", "btn btn-ghost btn-sm", "Remove");
          rm.type = "button";
          rm.setAttribute("aria-label", `Remove module ${i + 1}`);
          rm.addEventListener("click", () => { mods.splice(i, 1); draw(); emit(); });
          head.appendChild(rm);
        }
        card.appendChild(head);

        const cols = el("div", "mc-cols");
        [["previous", "Previous syllabus", "Leave empty for a new module"],
         ["revised", "Revised syllabus", "Module title (hours) — content"]].forEach(([k, label, ph]) => {
          const f = el("label", "mc-col");
          f.appendChild(el("span", "mc-col-label", label));
          const t = el("textarea");
          t.rows = 5;
          t.placeholder = ph;
          t.value = m[k] || "";
          if (CTX.readonly) t.disabled = true;
          t.addEventListener("input", () => {
            m[k] = t.value;
            if (!m.pct_manual) recalc(m, pct);
            emit();
          });
          f.appendChild(t);
          cols.appendChild(f);
        });
        card.appendChild(cols);
        if (CTX.readonly) pct.disabled = true;
        list.appendChild(card);
      });
    }

    function recalc(m, pct) {
      const v = percentChange(m.previous, m.revised);
      m.pct = v;
      pct.value = v === null ? "" : fmt(v);
    }

    if (!CTX.readonly) {
      const add = el("button", "btn btn-ghost btn-sm", "+ Add module");
      add.type = "button";
      add.addEventListener("click", () => { mods.push({}); draw(); emit(); });
      foot.appendChild(add);
    }
    foot.appendChild(avg);
    draw();
    const a = averageChange(mods);
    avg.textContent = a === null ? "" : `Average change across modules: ${fmt(a)}%`;
    return box;
  }

  /** One course's revision, laid out as the syllabus revision document lays
      it out: the previous and latest year, title and code side by side, then
      each module previous-beside-revised with its % change, and the average. */
  function revisionTable(def, row, commit) {
    if (!Array.isArray(row[def.name])) row[def.name] = [];
    const mods = row[def.name];
    if (!mods.length && !CTX.readonly) mods.push({});

    const wrap = el("div", "rt-wrap rv-wrap");
    const table = el("table", "rv-table");
    wrap.appendChild(table);

    const avgCell = el("td", "rv-pct rv-avg");
    function setAvg() {
      const a = averageChange(mods);
      row.avg_change = a === null ? "" : a;
      avgCell.textContent = a === null ? "—" : `${fmt(a)}%`;
    }
    const changed = () => { setAvg(); commit(); };

    function box(value, onInput, opts) {
      const o = opts || {};
      const t = el(o.multi ? "textarea" : "input");
      if (o.multi) t.rows = 5; else t.type = "text";
      t.value = value ?? "";
      if (o.placeholder) t.placeholder = o.placeholder;
      if (o.readonly) { t.readOnly = true; t.classList.add("is-auto"); t.tabIndex = -1; }
      if (CTX.readonly) t.disabled = true;
      if (!o.readonly) t.addEventListener("input", () => onInput(t.value));
      return t;
    }
    function cell(node, field) {
      const td = el("td");
      if (field) td.dataset.field = field;
      if (node) td.appendChild(node);
      return td;
    }

    const head = el("thead");
    const hr = el("tr");
    ["", "Year of previous revision in a subject / course",
     "Year of latest revision of a subject / course", "Percentage of change"]
      .forEach(x => hr.appendChild(el("th", null, x)));
    head.appendChild(hr);
    table.appendChild(head);
    const body = el("tbody");
    table.appendChild(body);

    function draw() {
      body.textContent = "";
      const line = (label, a, b) => {
        const tr = el("tr", "rv-meta");
        tr.appendChild(el("th", null, label));
        tr.appendChild(a);
        tr.appendChild(b);
        tr.appendChild(el("td", "rv-pct"));
        body.appendChild(tr);
      };
      line("Year",
        cell(box(row.year_previous, v => { row.year_previous = v; commit(); },
                 { placeholder: "e.g. 2020" }), "year_previous"),
        cell(box(row.year_latest, v => { row.year_latest = v; commit(); },
                 { placeholder: "e.g. 2026" }), "year_latest"));
      line("Subject / course title",
        cell(box(row.prev_title, v => { row.prev_title = v; commit(); },
                 { placeholder: "Previous title" }), "prev_title"),
        cell(box(row.course_title, null, { readonly: true })));
      line("Subject code",
        cell(box(row.prev_code, v => { row.prev_code = v; commit(); },
                 { placeholder: "Previous code" }), "prev_code"),
        cell(box(row.course_code, null, { readonly: true })));

      mods.forEach((m, i) => {
        const tr = el("tr", "rv-module");
        const th = el("th");
        th.appendChild(el("span", null, `Module ${ROMAN[i] || i + 1}`));
        if (!CTX.readonly) {
          const rm = el("button", "rv-remove", "Remove");
          rm.type = "button";
          rm.setAttribute("aria-label", `Remove module ${i + 1}`);
          rm.addEventListener("click", () => { mods.splice(i, 1); draw(); changed(); });
          th.appendChild(rm);
        }
        tr.appendChild(th);
        const pct = el("input");
        pct.type = "text";
        pct.inputMode = "decimal";
        pct.value = m.pct ?? "";
        pct.title = "Worked out from the two versions — type to use your own figure";
        if (!m.pct_manual) pct.classList.add("is-auto");
        if (CTX.readonly) pct.disabled = true;
        const recalc = () => {
          if (m.pct_manual) return;
          const v = percentChange(m.previous, m.revised);
          m.pct = v;
          pct.value = v === null ? "" : fmt(v);
        };
        tr.appendChild(cell(box(m.previous, v => { m.previous = v; recalc(); changed(); },
                                { multi: true, placeholder: "Leave empty for a new module" })));
        tr.appendChild(cell(box(m.revised, v => { m.revised = v; recalc(); changed(); },
                                { multi: true, placeholder: "Module title (hours) — content" })));
        pct.addEventListener("input", () => {
          const v = pct.value.trim();
          m.pct = v === "" ? null : Number(v);
          m.pct_manual = v !== "";
          pct.classList.toggle("is-auto", !m.pct_manual);
          recalc();
          changed();
        });
        const pc = el("td", "rv-pct");
        const pw = el("span", "rv-pct-in");
        pw.appendChild(pct);
        pw.appendChild(el("span", null, "%"));
        pc.appendChild(pw);
        tr.appendChild(pc);
        body.appendChild(tr);
      });

      if (!CTX.readonly) {
        const tr = el("tr", "rv-add");
        const td = el("td");
        td.colSpan = 4;
        const add = el("button", "btn btn-ghost btn-sm", "+ Add module");
        add.type = "button";
        add.addEventListener("click", () => { mods.push({}); draw(); changed(); });
        td.appendChild(add);
        tr.appendChild(td);
        body.appendChild(tr);
      }
      const tr = el("tr", "rv-total");
      tr.appendChild(el("td"));
      const lab = el("td", null, "Average percentage on revision considering all modules");
      lab.colSpan = 2;
      tr.appendChild(lab);
      tr.appendChild(avgCell);
      body.appendChild(tr);
      setAvg();
    }
    draw();
    return wrap;
  }

  /** Programme-wide: (A)-(D) and the course-wise change for every semester. */
  function renderRevisionSummary(section, host) {
    const box = el("div", "cd-box");
    host.appendChild(box);
    const T = section.threshold ?? 20;
    function paint() {
      box.textContent = "";
      const courses = rows(section.source || "courses").filter(r => r && r.course_code);
      if (!courses.length) {
        box.appendChild(el("p", "pl-empty", "Add courses above and this summary fills itself."));
        return;
      }
      const avgOf = r => num(r.avg_change) ?? averageChange(r.modules);
      const A = courses.length;
      const B = courses.filter(r => (avgOf(r) ?? 0) > T).length;
      const C = A ? Math.round(B / A * 10000) / 100 : 0;
      const known = courses.map(avgOf).filter(x => x !== null);
      const D = known.length ? Math.round(known.reduce((a, b) => a + b, 0) / known.length * 100) / 100 : null;
      const t = el("table", "cd-table");
      const tb = el("tbody");
      [["(A)", "Total number of courses", String(A)],
       ["(B)", `Number of courses with syllabus revision above ${T}%`, String(B)],
       ["(C)", "Percentage of courses revised — (B / A) × 100", fmt(C)],
       ["(D)", "Average percentage of syllabus revised, across all courses",
        D === null ? "—" : fmt(D) + "%"]].forEach(([k, label, v]) => {
        const tr = el("tr");
        tr.appendChild(el("td", null, k));
        tr.appendChild(el("td", null, label));
        tr.appendChild(el("td", "num cd-strong", v));
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      const w = el("div", "rt-wrap");
      w.appendChild(t);
      box.appendChild(w);

      box.appendChild(el("h4", "cd-head", "Percentage of change in syllabus — course-wise, by semester"));
      const t2 = el("table", "cd-table");
      const h = el("tr");
      ["SL", "Course code", "Course title", "Percentage of change in syllabus"].forEach(
        (x, n) => h.appendChild(el("th", n === 3 ? "num" : null, x)));
      const th = el("thead");
      th.appendChild(h);
      t2.appendChild(th);
      const b2 = el("tbody");
      const sems = Array.from(new Set(courses.map(r => num(r.semester)))).sort((a, b) =>
        (a ?? 99) - (b ?? 99));
      sems.forEach(sem => {
        const band = el("tr", "cd-band");
        const td = el("td", null, sem === null ? "Semester not given" : `Semester ${ROMAN[sem - 1] || sem}`);
        td.colSpan = 4;
        band.appendChild(td);
        b2.appendChild(band);
        courses.filter(r => num(r.semester) === sem).forEach((r, i) => {
          const tr = el("tr");
          tr.appendChild(el("td", null, String(i + 1)));
          tr.appendChild(el("td", null, r.course_code || ""));
          tr.appendChild(el("td", null, r.course_title || ""));
          const v = avgOf(r);
          tr.appendChild(el("td", "num", v === null ? "—" : fmt(v) + "%"));
          b2.appendChild(tr);
        });
      });
      t2.appendChild(b2);
      const w2 = el("div", "rt-wrap");
      w2.appendChild(t2);
      box.appendChild(w2);
    }
    refreshers.push(paint);
    paint();
  }

  function makeInput(def, value, onChange) {
    let input;
    if (def.type === "fixed") return fixedBlock(def);
    if (def.type === "module_compare") return moduleCompare(def, value, onChange);
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

  /** One preview, or a row of them for a box that takes several files. */
  function showFiles(host, val) {
    const oldList = host.querySelector(".file-previews");
    if (oldList) oldList.remove();
    if (!Array.isArray(val)) { filePreview(host, val); return; }
    const old = host.querySelector(".file-preview");
    if (old) old.remove();
    const list = el("div", "file-previews");
    val.forEach(v => { const slot = el("div"); filePreview(slot, v); list.appendChild(slot); });
    host.appendChild(list);
  }

  function fileNames(val) {
    return (Array.isArray(val) ? val : [val]).filter(v => v && v.name).map(v => v.name);
  }

  function uploadOne(file, def) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("stage", CTX.key);
    fd.append("field", def.name);
    return fetch(CTX.urls.upload, { method: "POST", body: fd })
      .then(r => r.json())
      .then(j => {
        if (!j.ok) throw new Error(j.error || `Upload of ${file.name} failed.`);
        // thumb comes along too, or the preview has no picture to show
        return { name: j.name, stored: j.stored, size: j.size,
                 url: j.url, thumb: j.thumb || null };
      });
  }

  function uploadFile(input, def, onChange) {
    const files = Array.from(input.files || []);
    if (!files.length) return;
    const note = input.parentElement.querySelector(".upload-note") ||
                 input.parentElement.appendChild(el("span", "help upload-note"));
    note.className = "help upload-note";
    note.setAttribute("role", "status");
    note.textContent = files.length > 1 ? `Uploading ${files.length} files…` : "Uploading…";
    // one after another, so a slow connection is not flooded
    files.reduce((chain, f) => chain.then(done => uploadOne(f, def).then(v => done.concat([v]))),
                 Promise.resolve([]))
      .then(done => {
        const val = def.multiple ? done : done[0];
        note.textContent = done.length > 1
          ? `Uploaded ${done.length} files`
          : `Uploaded: ${done[0].name} (${sizeLabel(done[0].size)})`;
        note.className = "help upload-note is-ok";
        showFiles(input.parentElement, val);
        onChange(val);
      })
      .catch(e => {
        note.textContent = (e && e.message) ||
          "Upload failed — check your connection and choose the file again.";
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

    if (value && def.type === "file" && typeof value === "object" && fileNames(value).length) {
      const n = el("span", "help upload-note", `Uploaded: ${fileNames(value).join(", ")}`);
      n.classList.add("is-ok");
      wrap.appendChild(n);
      showFiles(wrap, value);
    }
    wrap._input = input;
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
          if (NON_CREDIT.includes(r.nep_category)) return 0;
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
    if (has("avg_change") && has("modules")) {
      out.push({
        field: "avg_change", title: "Average percentage on revision",
        calc: r => averageChange(r.modules),
        explain: r => ["The average of the modules' % change."],
        empty: "Fill in the modules and the average works itself out.",
      });
    }
    if (has("total_marks") && has("cia") && has("ese")) {
      out.push({
        field: "total_marks", title: "Total marks",
        calc: r => num(r.cia) === null || num(r.ese) === null ? null : num(r.cia) + num(r.ese),
        explain: r => [`Continuous Assessment ${r.cia ?? "–"} + Term End ${r.ese ?? "–"}`],
        empty: "Enter both marks and the total fills itself.",
      });
    }
    if (has("total_credits") && has("degree_level")) {
      const totals = C.degree_totals || {};
      out.push({
        field: "total_credits", title: "Credits from UGC Table 2",
        calc: r => totals[r.degree_level] ?? null,
        explain: r => [`UGC Table 2 asks for at least ${totals[r.degree_level]} credits ` +
                       `for “${r.degree_level}”.`],
        empty: "Choose a UG degree and the UGC minimum fills in; enter a PG programme's own total.",
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
      data = data.filter(rowCounts);
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

  // ------------------------------------------------------------ row cards
  /* Programme Information, one programme at a time. Every programme sits
     in a strip of chips at the top — code, name and how complete it is —
     and the one clicked opens below in a framed card (navy for UG, orange
     for PG) with two tabs: its details, and its vision, mission and
     outcomes. Outcomes can be copied from another programme or handed to
     all of them at once. */

  function renderRowCards(section, host) {
    const synced = !!(section.synced_from && CTX.synced);
    const LOCKED_COLS = ["programme_code", "programme_name"];
    const RULES = derivedRules(section);
    const DERIVED = Object.fromEntries(RULES.map(r => [r.field, r]));
    const data = rows(section.key);
    const cols = section.columns.filter(c => !c.auto_index);
    // what a card is: a programme by default, or whatever the section says
    const CARD = Object.assign({ code: "programme_code", name: "programme_name",
                                 noun: "programme" }, section.card || {});
    const K = CARD.code, N = CARD.name, NOUN = CARD.noun;
    const TABS = section.tabs || [{ key: "details", label: "Details" }];
    const tabOf = c => c.tab || TABS[0].key;
    const OUT = cols.filter(c => tabOf(c) === "outcomes");
    const colourOf = r => /^PG/.test(r.degree_level || "") ? "orange" : "navy";
    const blank = v => v === undefined || v === null || String(v).trim() === "";
    const isBlankRow = r => cols.every(c => blank(r[c.name]) || c.type === "checkbox");
    const hasOutcomes = r => OUT.some(c => !blank(r[c.name]));
    let sel = 0;
    let tab = (section.tabs || [{ key: "details" }])[0].key;

    // Vision and mission used to be one block for the whole department. A
    // draft that still has it hands it to every programme that has none.
    if (state.vision && typeof state.vision === "object" && !CTX.readonly) {
      data.forEach(r => OUT.forEach(c => {
        if (blank(r[c.name]) && !blank(state.vision[c.name])) r[c.name] = state.vision[c.name];
      }));
    }

    const wrap = el("div", "rc-wrap");
    host.appendChild(wrap);

    if (synced) {
      const note = el("div", "sync-note");
      note.appendChild(el("span", null,
        "These programmes come from Department Information. To add or remove one, "));
      const a = el("a", null, "change the list there");
      a.href = CTX.urls.dept_info;
      note.appendChild(a);
      note.appendChild(el("span", null, "."));
      wrap.appendChild(note);
    }

    // --- the strip of every programme
    const strip = el("div", "rc-strip");
    const stripHead = el("div", "rc-strip-head");
    const stripCount = el("span", "rc-strip-count");
    stripHead.appendChild(stripCount);
    let fillBtn = null;
    if (!CTX.readonly && !synced && (CTX.fill || []).length) {
      fillBtn = el("button", "rc-fill");
      fillBtn.type = "button";
      fillBtn.addEventListener("click", fillAll);
      stripHead.appendChild(fillBtn);
    }
    strip.appendChild(stripHead);
    const chips = el("div", "rc-chips");
    chips.setAttribute("role", "tablist");
    chips.setAttribute("aria-label", "Programmes");
    strip.appendChild(chips);
    wrap.appendChild(strip);

    const note = el("p", "rc-note");
    note.setAttribute("role", "status");
    wrap.appendChild(note);

    const stage = el("div", "rc-stage");
    wrap.appendChild(stage);

    while (data.length < (section.min_rows || 0)) data.push({});

    wrap.showRow = (i, field) => {
      if (!data[i]) return;
      sel = i;
      const c = cols.find(x => x.name === field);
      if (c) tab = tabOf(c);
      draw();
    };

    function say(text) { note.textContent = text; }

    function missing() {
      const have = new Set(data.map(r => String(r[K] || "").trim().toUpperCase()));
      return (CTX.fill || []).filter(p => !have.has(String(p[K]).toUpperCase()));
    }

    function fillAll() {
      const add = missing();
      if (!add.length) return;
      for (let k = data.length - 1; k >= 0; k--) if (isBlankRow(data[k])) data.splice(k, 1);
      const first = data.length;
      add.forEach(p => data.push(Object.assign({}, p)));
      sel = first;
      tab = TABS[0].key;
      draw();
      touch();
      say(`Added ${add.length} ${NOUN}${add.length === 1 ? "" : "s"}. Click each one to fill it in.`);
    }

    // The part of a name that tells programmes apart: most share their first
    // words ("Bachelor of Technology (Computer Science and Engineering) with
    // specialisation in …"), so a chip shows what follows the last "in".
    function shortName(n) {
      let t = String(n || "").replace(/\s+/g, " ").trim();
      const spec = t.match(/speciali[sz]ation in\s+(.+)$/i);
      if (spec) return spec[1];
      // drop the degree ("Bachelor of Technology", "Master of Commerce (Honours …)")
      t = t.replace(/^(Bachelor|Master|Doctor|Post ?Graduate Diploma|PG Diploma|Diploma)\s+of\s+[A-Za-z ]+?(?=\s*\(|\s+in\s|$)/i, "")
           .replace(/\(Honours[^)]*\)/i, "")
           .replace(/^\s*in\s+/i, "")
           .replace(/[()<>]/g, " ").replace(/\s+/g, " ").trim();
      return t || String(n || "");
    }

    function removeAt(i) {
      const r = data[i];
      if (data.length <= (section.min_rows || 0)) {
        say(`Keep at least ${section.min_rows} ${NOUN}${section.min_rows === 1 ? "" : "s"}.`);
        return;
      }
      if (!isBlankRow(r) &&
          !window.confirm(`Remove ${r[K] || "this " + NOUN} and everything ` +
                          "filled in for it?")) return;
      data.splice(i, 1);
      if (sel > i || sel >= data.length) sel = Math.max(0, sel - 1);
      draw();
      touch();
      say(`${r[K] || "The " + NOUN} removed.`);
      chips.querySelector(".rc-chip.is-sel .rc-chip-open")?.focus();
    }

    function completeness(r) {
      const req = cols.filter(c => c.required);
      const done = req.filter(c => !blank(r[c.name])).length;
      return done === req.length ? "full" : done ? "part" : "none";
    }

    function drawStrip() {
      chips.textContent = "";
      data.forEach((r, i) => {
        const chip = el("span", `rc-chip is-${completeness(r)}` +
                                (colourOf(r) === "orange" ? " is-pg" : "") +
                                (i === sel ? " is-sel" : ""));
        const b = el("button", "rc-chip-open");
        b.type = "button";
        b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", i === sel ? "true" : "false");
        b.appendChild(el("span", "rc-chip-dot"));
        b.appendChild(el("span", "rc-chip-code", r[K] || `#${i + 1}`));
        b.appendChild(el("span", "rc-chip-name",
          (NOUN === "programme" ? shortName(r[N]) : r[N]) || `New ${NOUN}`));
        b.title = `${r[K] || "No code yet"} — ${r[N] || "no name yet"}`;
        b.addEventListener("click", () => { sel = i; draw(); });
        chip.appendChild(b);
        if (!synced && !CTX.readonly) {
          const x = el("button", "rc-chip-x", "×");
          x.type = "button";
          x.title = `Remove ${r[K] || "this " + NOUN}`;
          x.setAttribute("aria-label", `Remove ${r[K] || NOUN + " " + (i + 1)}`);
          x.addEventListener("click", () => removeAt(i));
          chip.appendChild(x);
        }
        chips.appendChild(chip);
      });
      if (!synced && !CTX.readonly) {
        const add = el("button", "rc-chip rc-chip-add");
        add.type = "button";
        add.innerHTML = ICON.plus;
        add.appendChild(el("span", null, `Add ${NOUN}`));
        add.addEventListener("click", () => {
          data.push({});
          sel = data.length - 1;
          tab = TABS[0].key;
          draw();
          touch();
          stage.querySelector("input:not([readonly]), select")?.focus();
        });
        chips.appendChild(add);
      }
      const full = data.filter(r => completeness(r) === "full").length;
      stripCount.textContent = `${data.length} ${NOUN}${data.length === 1 ? "" : "s"} · ` +
                               `${full} complete`;
      if (fillBtn) {
        const left = missing().length;
        fillBtn.disabled = !left;
        fillBtn.innerHTML = left ? ICON.plus : "";
        fillBtn.appendChild(el("span", null,
          left ? `Fill in all ${NOUN}s (${left})` : `All ${(CTX.fill || []).length} ${NOUN}s are in`));
      }
    }

    function field(row, c, cells, repaint) {
      const holder = el("div", "field" +
        (c.name === N || c.type === "textarea" || c.wide ? " wide" : ""));
      holder.dataset.field = c.name;
      if (c.type === "module_compare") {
        holder.appendChild(revisionTable(c, row, () => { repaint(c.name); touch(); }));
        if (c.help) holder.appendChild(el("span", "help", c.help));
        return holder;
      }
      const id = `rc-${section.key}-${c.name}`;
      if (c.type === "checkbox") {
        const lab = el("label", "check");
        const input = makeInput(c, row[c.name], v => { row[c.name] = v; touch(); });
        input.id = id;
        lab.appendChild(input);
        lab.appendChild(el("span", null, c.label));
        holder.appendChild(lab);
        return holder;
      }
      const lab = el("label", null, c.label);
      lab.setAttribute("for", id);
      if (c.required) {
        const star = el("span", "req", "*");
        star.setAttribute("aria-hidden", "true");
        lab.appendChild(star);
      }
      holder.appendChild(lab);
      const input = makeInput(c, row[c.name], v => {
        row[c.name] = v;
        if (DERIVED[c.name]) markManual(row, c.name, cells);
        derive(RULES, row, cells);
        repaint(c.name);
        touch();
      });
      input.id = id;
      if (c.type === "readonly" || (synced && LOCKED_COLS.includes(c.name))) input.readOnly = true;
      cells[c.name] = input;
      holder.appendChild(input);
      if (c.help) holder.appendChild(el("span", "help", c.help));
      if (DERIVED[c.name]) {
        if ((row._auto || []).includes(c.name)) input.classList.add("is-auto");
        hintOn(holder, pop => derivedHint(pop, DERIVED[c.name], row, cells, RULES,
                                          () => repaint(c.name)));
      }
      attachLiveCheck(input, c, holder);
      return holder;
    }

    // outcomes: take them from another programme, or give these to all
    function outcomeTools(row, i) {
      if (data.length < 2) return null;
      const box = el("div", "rc-copy");
      box.appendChild(el("span", "rc-copy-label", "Same as another programme?"));
      const pick = el("select", "rc-copy-pick");
      pick.setAttribute("aria-label", "Programme to copy from");
      // listed fresh each time, since any programme may have gained some
      const refill = () => {
        const keep = pick.value;
        pick.textContent = "";
        const others = data.map((r, k) => [r, k]).filter(([r, k]) => k !== i && hasOutcomes(r));
        if (!others.length) pick.appendChild(new Option("No other programme has any yet", ""));
        others.forEach(([r, k]) => pick.appendChild(
          new Option(`${r.programme_code || "#" + (k + 1)} — ${r.programme_name || ""}`, k)));
        if ([...pick.options].some(o => o.value === keep)) pick.value = keep;
      };
      refill();
      pick.addEventListener("focus", refill);
      pick.addEventListener("mousedown", refill);
      const go = el("button", "btn btn-ghost btn-sm", "Copy");
      go.type = "button";
      go.addEventListener("click", () => {
        refill();
        if (pick.value === "") { say("No other programme has a vision or mission to copy yet."); return; }
        const src = data[+pick.value];
        if (hasOutcomes(row) &&
            !window.confirm("Replace this programme's vision, mission and outcomes?")) return;
        OUT.forEach(c => { row[c.name] = src[c.name] ?? ""; });
        draw();
        touch();
        say(`Copied from ${src.programme_code || "the other programme"}. Change anything that differs.`);
      });
      const all = el("button", "btn btn-ghost btn-sm", "Use for all programmes");
      all.type = "button";
      all.title = "Copy these to every programme that has none of its own yet";
      all.addEventListener("click", () => {
        if (!hasOutcomes(row)) { say("Fill in this programme's vision and mission first."); return; }
        let given = 0, kept = 0;
        data.forEach((r, k) => {
          if (k === i) return;
          if (hasOutcomes(r)) { kept++; return; }
          OUT.forEach(c => { r[c.name] = row[c.name] ?? ""; });
          given++;
        });
        drawStrip();
        touch();
        say(`Copied to ${given} programme${given === 1 ? "" : "s"}` +
            (kept ? `; ${kept} already had their own and were left as they were.` : "."));
      });
      box.appendChild(pick);
      box.appendChild(go);
      box.appendChild(all);
      return box;
    }

    function drawCard() {
      stage.textContent = "";
      if (!data.length) {
        stage.appendChild(el("p", "pl-empty",
          fillBtn ? `No ${NOUN}s yet. Use “Fill in all ${NOUN}s” or “Add ${NOUN}” above.` : `No ${NOUN}s yet. Use “Add ${NOUN}” above.`));
        return;
      }
      sel = Math.min(sel, data.length - 1);
      const i = sel;
      const row = data[i];
      const card = el("div", `frame frame-${colourOf(row)} rc-card`);
      card.dataset.row = i;
      const tabLabel = el("span", "frame-tab");
      const title = el("div", "rc-title");
      const repaint = name => {
        const orange = colourOf(row) === "orange";
        card.classList.toggle("frame-orange", orange);
        card.classList.toggle("frame-navy", !orange);
        tabLabel.textContent = `${String(i + 1).padStart(2, "0")} · ` + (row[K] || `New ${NOUN}`);
        title.textContent = row[N] || `${NOUN[0].toUpperCase() + NOUN.slice(1)} name not given yet`;
        title.classList.toggle("is-empty", !row[N]);
        if (!name || [K, N, "degree_level"].includes(name) ||
            cols.some(c => c.name === name && c.required)) drawStrip();
      };
      card.appendChild(tabLabel);

      const head = el("div", "rc-head");
      head.appendChild(title);
      card.appendChild(head);

      const tabs = el("div", "rc-tabs");
      tabs.setAttribute("role", "tablist");
      TABS.forEach(t => {
        const b = el("button", "rc-tab", t.label);
        b.type = "button";
        b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", t.key === tab ? "true" : "false");
        b.addEventListener("click", () => { tab = t.key; drawCard(); });
        tabs.appendChild(b);
      });
      // one tab is no choice at all, so it is not shown
      if (TABS.length > 1) card.appendChild(tabs);

      if (tab === "outcomes" && OUT.length && !CTX.readonly) {
        const tools = outcomeTools(row, i);
        if (tools) card.appendChild(tools);
      }

      const grid = el("div", "fields-grid rc-grid" + (tab === "outcomes" ? " is-outcomes" : ""));
      const cells = {};
      // columns drawn inside the revision table are not drawn a second time
      cols.filter(c => tabOf(c) === tab && !c.in_table)
        .forEach(c => grid.appendChild(field(row, c, cells, repaint)));
      section.columns.forEach(c => { if (c.auto_index) row[c.name] = i + 1; });
      card.appendChild(grid);

      // prev / next, so a long list can be walked without scrolling up
      const nav = el("div", "rc-nav");
      if (i > 0) {
        const prev = el("button", "btn btn-ghost btn-sm", "← Previous");
        prev.type = "button";
        prev.addEventListener("click", () => { sel = i - 1; draw(); });
        nav.appendChild(prev);
      }
      const t = TABS.findIndex(x => x.key === tab);
      if (t < TABS.length - 1) {
        const on = el("button", "btn btn-sm", `${TABS[t + 1].label} →`);
        on.type = "button";
        on.addEventListener("click", () => { tab = TABS[t + 1].key; drawCard(); });
        nav.appendChild(on);
      } else if (i < data.length - 1) {
        const next = el("button", "btn btn-sm", `Next ${NOUN} →`);
        next.type = "button";
        next.addEventListener("click", () => { sel = i + 1; tab = TABS[0].key; draw(); });
        nav.appendChild(next);
      }
      card.appendChild(nav);

      stage.appendChild(card);
      repaint();
      if (!CTX.readonly && derive(RULES, row, cells)) touch();
    }

    function draw() {
      drawStrip();
      drawCard();
    }
    draw();
  }

  // --------------------------------------------------- credit distribution
  /* The template's two generated tables, worked out from the programme
     structure as it is typed: "Classification of Credits" (credits per
     semester in each group) and "Summary" (100% continuous-assessment
     credits against term-end credits, and marks). Semesters 7 and 8 of a
     4-year programme get an Honours block and an Honours with Research
     block, as in the template. */

  // Does a programme-structure row count for this programme's track?
  function rowCounts(r) {
    const t = r.track || "All semesters";
    const mine = (CTX.calc || {}).track;
    if (t === "Honours") return mine === "honours";
    if (t === "Honours with Research") return mine === "research";
    return true;
  }

  // the columns of the template's "Classification of Credits" table
  const DIST_GROUPS = [
    ["Major (Core)", "Major"],
    ["Minor Stream", "Minor"],
    ["Multidisciplinary", "Multi-Disciplinary / OE"],
    ["Ability Enhancement Courses (AEC)", "Ability Enhancement / AEC"],
    ["Skill Enhancement Courses (SEC)", "Skill Enhancement / SEC"],
    ["Value Added Courses (VAC)", "Common Value Added / VAC"],
    ["Summer Internship", "Summer Internship / INTERNSHIP"],
    ["Research Project / Dissertation", "Research Project / Dissertation / PROJECT"],
  ];
  const NC_COURSE = "Mandatory Non-Credit Course";
  const NC_AUDIT = "Mandatory Non-Credit Audit Course";

  function renderCreditDistribution(section, host) {
    const box = el("div", "cd-box");
    host.appendChild(box);
    // the template puts the classification before the programme structure and
    // the summary after it; one section can show either, or both
    const SHOW = section.show || "all";
    const wants = k => SHOW === "all" || SHOW === k;

    function paint() {
      box.textContent = "";
      const all = (Array.isArray(state.semester_structure) ? state.semester_structure : [])
        .filter(r => num(r.semester) !== null);
      if (!all.length) {
        box.appendChild(el("p", "pl-empty", SHOW === "classification"
          ? "Add courses to the programme structure below and this table fills itself."
          : "Add courses to the programme structure above and this table fills itself."));
        return;
      }
      const track = r => r.track || "All semesters";
      const special = new Set(all.filter(r => track(r) !== "All semesters").map(r => num(r.semester)));
      const sems = rows => Array.from(new Set(rows.map(r => num(r.semester)))).sort((a, b) => a - b);
      const base = all.filter(r => !special.has(num(r.semester)));
      const blocks = [{ title: null, rows: base }];
      [["Honours", "Honours"], ["Honours with Research", "Honours with Research"]].forEach(([t, label]) => {
        const rows = all.filter(r => special.has(num(r.semester)) &&
                                     (track(r) === t || track(r) === "All semesters"));
        if (rows.some(r => track(r) === t)) blocks.push({ title: label, rows: rows });
      });

      const sumBy = (rows, fn) => rows.reduce((a, r) => a + (fn(r) || 0), 0);
      const nc = rows => rows.filter(r => r.nep_category === NC_COURSE ||
        (num(r.credits) === 0 && r.nep_category !== NC_AUDIT)).length || "";
      const audit = rows => rows.filter(r => r.nep_category === NC_AUDIT).length || "";

      // --- classification of credits
      if (wants("classification")) {
      const t1 = el("table", "cd-table");
      const h = el("tr");
      ["Semester", ...DIST_GROUPS.map(g => g[1]), "Total Credits",
       "No. of Mandatory Non-Credit Course/s", "No. of Mandatory Non-Credit Audit Course"]
        .forEach(x => h.appendChild(el("th", x === "Semester" ? null : "num", x)));
      const thead = el("thead");
      thead.appendChild(h);
      t1.appendChild(thead);
      const b1 = el("tbody");
      blocks.forEach((blk, n) => {
        if (blk.title) {
          const tr = el("tr", "cd-band");
          const td = el("td", null, blk.title);
          td.colSpan = DIST_GROUPS.length + 4;
          tr.appendChild(td);
          b1.appendChild(tr);
        }
        sems(blk.rows).forEach(sem => {
          const rows = blk.rows.filter(r => num(r.semester) === sem);
          const tr = el("tr");
          tr.appendChild(el("td", null, String(sem)));
          DIST_GROUPS.forEach(([cat]) => tr.appendChild(el("td", "num",
            fmt(sumBy(rows.filter(r => r.nep_category === cat), r => num(r.credits))))));
          tr.appendChild(el("td", "num cd-strong", fmt(sumBy(rows, r => num(r.credits)))));
          tr.appendChild(el("td", "num", String(nc(rows))));
          tr.appendChild(el("td", "num", String(audit(rows))));
          b1.appendChild(tr);
        });
        // a track's total runs on from the common semesters, as in the template
        const counted = n === 0 ? blk.rows : base.concat(blk.rows);
        const tot = el("tr", "total");
        tot.appendChild(el("td", null, "Total"));
        DIST_GROUPS.forEach(([cat]) => tot.appendChild(el("td", "num",
          fmt(sumBy(counted.filter(r => r.nep_category === cat), r => num(r.credits))))));
        tot.appendChild(el("td", "num", fmt(sumBy(counted, r => num(r.credits)))));
        tot.appendChild(el("td", "num", String(nc(counted))));
        tot.appendChild(el("td", "num", String(audit(counted))));
        b1.appendChild(tot);
      });
      t1.appendChild(b1);
      const w1 = el("div", "rt-wrap");
      w1.appendChild(t1);
      box.appendChild(w1);
      }
      if (!wants("summary")) return;
      const running = base;

      // --- summary
      const t2 = el("table", "cd-table");
      const h2 = el("tr");
      ["Semester", "100% Continuous Assessment credits", "Term End (University) Examination credits",
       "Total credits", "Total marks"].forEach(x => h2.appendChild(el("th", x === "Semester" ? null : "num", x)));
      const th2 = el("thead");
      th2.appendChild(h2);
      t2.appendChild(th2);
      const b2 = el("tbody");
      const caOnly = r => num(r.ese) === 0 && num(r.cia) !== null;
      const line = (label, rows, cls) => {
        const tr = el("tr", cls || "");
        tr.appendChild(el("td", null, label));
        tr.appendChild(el("td", "num", fmt(sumBy(rows.filter(caOnly), r => num(r.credits)))));
        tr.appendChild(el("td", "num", fmt(sumBy(rows.filter(r => !caOnly(r)), r => num(r.credits)))));
        tr.appendChild(el("td", "num", fmt(sumBy(rows, r => num(r.credits)))));
        tr.appendChild(el("td", "num", fmt(sumBy(rows, r => num(r.total_marks)))));
        b2.appendChild(tr);
      };
      blocks.forEach((blk, n) => {
        if (blk.title) {
          const tr = el("tr", "cd-band");
          const td = el("td", null, blk.title);
          td.colSpan = 5;
          tr.appendChild(td);
          b2.appendChild(tr);
        }
        sems(blk.rows).forEach(sem => line(String(sem), blk.rows.filter(r => num(r.semester) === sem)));
        line("Total credits", n === 0 ? blk.rows : running.concat(blk.rows), "total");
      });
      t2.appendChild(b2);
      const w2 = el("div", "rt-wrap");
      w2.appendChild(t2);
      if (SHOW === "all") box.appendChild(el("h4", "cd-head", "Summary"));
      box.appendChild(w2);
      ugcCheck(all);
    }

    // --- UGC Table 2, from the same courses (only this programme's track)
    function ugcCheck(all) {
      const side = document.getElementById("credit-tally");
      if (!CREDIT || !CREDIT.rows || !CREDIT.rows.length) {
        box.appendChild(el("p", "small muted",
          "UGC Table 2 applies to 3-year and 4-year UG programmes only."));
        return;
      }
      const map = (CTX.calc || {}).nep_to_key || {};
      const by = {};
      all.filter(rowCounts).forEach(r => {
        const k = map[r.nep_category];
        if (k) by[k] = (by[k] || 0) + (num(r.credits) || 0);
      });
      const t3 = el("table", "cd-table");
      const h3 = el("tr");
      ["Category", `UGC minimum (${CREDIT.track_label})`, "Your credits", ""].forEach(
        (x, n) => h3.appendChild(el("th", n ? "num" : null, x)));
      const th3 = el("thead");
      th3.appendChild(h3);
      t3.appendChild(th3);
      const b3 = el("tbody");
      let total = 0;
      CREDIT.rows.forEach(r => {
        if (!r.applicable) return;
        const got = by[r.key] || 0;
        total += got;
        const ok = got >= r.min && (r.max === null || r.max === undefined || got <= r.max);
        const tr = el("tr");
        tr.appendChild(el("td", null, r.label));
        tr.appendChild(el("td", "num", r.max ? `${r.min} – ${r.max}` : String(r.min)));
        tr.appendChild(el("td", "num cd-strong", fmt(got)));
        tr.appendChild(el("td", "num " + (ok ? "ok-tick" : "bad-tick"), ok ? "✓" : "✗"));
        b3.appendChild(tr);
      });
      const need = CREDIT.total;
      const tr = el("tr", "total");
      tr.appendChild(el("td", null, "Total"));
      tr.appendChild(el("td", "num", String(need ?? "—")));
      tr.appendChild(el("td", "num", fmt(total)));
      tr.appendChild(el("td", "num " + (need && total < need ? "bad-tick" : "ok-tick"),
                        need && total < need ? "✗" : "✓"));
      b3.appendChild(tr);
      t3.appendChild(b3);
      const w3 = el("div", "rt-wrap");
      w3.appendChild(t3);
      box.appendChild(el("h4", "cd-head", "Check against UGC Table 2"));
      box.appendChild(w3);

      if (side && need) {
        const short = need - total;
        side.textContent = "";
        side.appendChild(el("span", short > 0 ? "tally-short" : "tally-met",
          short > 0 ? `${fmt(short)} credit${short === 1 ? "" : "s"} short` : "Total requirement met"));
        side.appendChild(el("div", "muted",
          short > 0 ? `${fmt(total)} entered of ${need} required` : `${fmt(total)} credits entered`));
      }
    }

    window.addEventListener("stage:rows", e => {
      if (e.detail === "semester_structure") paint();
    });
    paint();
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
        if (!rowCounts(r)) return;
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

    const wrap = el("div", "pl-wrap");
    host.appendChild(wrap);

    const bar = el("div", "pl-bar");
    const tally = el("span", "pl-tally");
    tally.setAttribute("role", "status");
    const search = el("input", "pl-search");
    search.type = "search";
    search.placeholder = "Find a programme";
    search.setAttribute("aria-label", "Find a programme by name or code");
    bar.appendChild(tally);
    bar.appendChild(search);
    wrap.appendChild(bar);

    // one panel per degree group, side by side
    const cols = el("div", "pl-cols");
    wrap.appendChild(cols);
    const panels = {};
    tabs.forEach((t, n) => {
      const panel = el("section", `pl-panel pl-panel-${n % 2 ? "b" : "a"}`);
      panel.setAttribute("aria-label", t.label);
      const head = el("div", "pl-panel-head");
      const title = el("h4", "pl-panel-title");
      head.appendChild(title);
      panel.appendChild(head);
      const list = el("ol", "pl");
      panel.appendChild(list);
      if (!CTX.readonly) {
        const add = el("button", "pl-panel-add");
        add.type = "button";
        add.innerHTML = ICON.plus;
        add.appendChild(el("span", null, `Add ${t.key === "all" ? "a" : t.key} programme`));
        add.addEventListener("click", () => {
          data.push({ source: "new", decision: "keep", programme_code: "",
                      programme_name: "", degree: (t.degrees || [""])[0] });
          draw();
          touch();
          list.lastElementChild?.querySelector("input")?.focus();
        });
        panel.appendChild(add);
      }
      cols.appendChild(panel);
      panels[t.key] = { tab: t, title: title, list: list };
    });

    // every row is on screen now; kept for focusIssue
    wrap.showRow = () => draw();

    function input(row, name, def) {
      const holder = el("div", "pl-in pl-in-" + name);
      holder.dataset.field = name;
      const i = makeInput(def, row[name], v => { row[name] = v; touch(); if (name === "degree") draw(); });
      i.setAttribute("aria-label", def.label);
      holder.appendChild(i);
      attachLiveCheck(i, def, holder);
      return holder;
    }

    function rowItem(row, i, n) {
      const removed = row.decision === "remove";
      const li = el("li", "pl-row" + (removed ? " is-removed" : "") +
                          (row.source === "new" ? " is-new" : ""));
      li.dataset.row = i;
      li.appendChild(el("span", "pl-num", String(n).padStart(2, "0")));

      if (row.source === "new") {
        const grid = el("div", "pl-new");
        grid.appendChild(input(row, "programme_code",
          { name: "programme_code", label: "Programme code", type: "text", required: true,
            placeholder: "Code" }));
        grid.appendChild(input(row, "degree",
          { name: "degree", label: "Degree", type: "select", required: true,
            options: section.degrees || [] }));
        grid.appendChild(input(row, "programme_name",
          { name: "programme_name", label: "Programme name", type: "text", required: true,
            placeholder: "Full programme name" }));
        const body = el("div", "pl-body");
        body.appendChild(el("span", "pl-tag", "New"));
        body.appendChild(grid);
        li.appendChild(body);
        if (!CTX.readonly) {
          const del = iconButton("pl-icon pl-minus", "minus", "Take this new programme off");
          del.addEventListener("click", () => { data.splice(i, 1); draw(); touch(); });
          li.appendChild(del);
        }
        return li;
      }

      const body = el("div", "pl-body");
      body.appendChild(el("span", "pl-name", row.programme_name || ""));
      const meta = el("span", "pl-meta");
      meta.appendChild(el("span", "pl-code", row.programme_code || ""));
      const rest = [row.degree, row.year_introduced && `since ${row.year_introduced}`,
                    row.minors].filter(Boolean).join(" · ");
      if (rest) meta.appendChild(document.createTextNode(" " + rest));
      body.appendChild(meta);
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
      return li;
    }

    function draw() {
      Object.values(panels).forEach(({ tab, title, list }) => {
        const mine = data.map((r, i) => [r, i]).filter(([r]) => tabOf(r) === tab.key);
        const live = mine.filter(([r]) => r.decision !== "remove").length;
        title.textContent = "";
        title.appendChild(el("span", null, tab.label));
        title.appendChild(el("span", "pl-panel-n", String(live)));
        list.textContent = "";
        if (!mine.length) {
          list.appendChild(el("li", "pl-empty",
            `No ${tab.key === "all" ? "" : tab.key + " "}programmes on record. ` +
            "Use the plus button below to add each one you run this year."));
        }
        mine.forEach(([row, i], n) => list.appendChild(rowItem(row, i, n + 1)));
      });

      const kept = data.filter(r => r.decision !== "remove" && r.source !== "new").length;
      const gone = data.filter(r => r.decision === "remove").length;
      const added = data.filter(r => r.source === "new").length;
      tally.textContent = `${kept} kept · ${gone} removed · ${added} new`;
      filter();
    }

    function filter() {
      const q = search.value.trim().toLowerCase();
      wrap.querySelectorAll(".pl-row").forEach(li => {
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
      (section.links || []).forEach(l => {
        const a = el("a", "section-link", `${l.label} →`);
        a.href = CTX.urls.stage.replace("__stage__", l.stage);
        block.appendChild(a);
      });

      if (section.type === "table" && section.display === "cards") {
        renderRowCards(section, block);
      } else if (section.type === "table") {
        renderTable(section, block);
      } else if (section.type === "credit_matrix") {
        renderCreditMatrix(section, block);
      } else if (section.type === "revision_summary") {
        renderRevisionSummary(section, block);
      } else if (section.type === "credit_distribution") {
        renderCreditDistribution(section, block);
      } else if (section.type === "programme_list") {
        renderProgrammeList(section, block);
      } else if (section.display === "cards") {
        renderCards(section, block);
      } else {
        const grid = el("div", "fields-grid");
        state[section.key] = state[section.key] || {};
        section.fields.forEach(f => {
          const b = fieldBlock(f, state[section.key][f.name], v => {
            setVal(section.key, f.name, v);
            // the credit check follows the degree: save, then reopen with it
            if (f.reload_on_change) { reloadAfterSave = true; clearTimeout(saveTimer); save(); }
          });
          if (f.count && b._input) {
            // "No. of courses with major revisions" and the like count themselves
            const c = f.count;
            refreshers.push(() => {
              const n = rows(c.section).filter(r => r && r[c.field] === c.value).length;
              state[section.key][f.name] = n;
              b._input.value = String(n);
            });
          }
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
  let reloadAfterSave = false;

  function refresh() {
    refreshers.forEach(fn => { try { fn(); } catch (_) { /* never block typing */ } });
  }

  function touch() {
    refresh();
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
        if (reloadAfterSave) { reloadAfterSave = false; window.location.reload(); }
      } else {
        saveNote.textContent = j.error || "Could not save";
        saveNote.className = "save-note";
      }
    }).catch(() => {
      saveNote.textContent = "Could not reach the server — your work is still in this tab";
    });
  }

  const checksCard = document.getElementById("checks-card");
  const checksClose = document.getElementById("checks-close");
  function showChecks() { if (checksCard) checksCard.hidden = false; }
  if (checksClose) checksClose.addEventListener("click", () => { checksCard.hidden = true; });

  function paintIssues(issues, summary) {
    showChecks();
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
    // a programme that is not the one on screen (or a row in the other panel)
    const plWrap = document.querySelector(`#sec-${iss.section} .pl-wrap, ` +
                                          `#sec-${iss.section} .rc-wrap`);
    if (plWrap && !iss._shown && iss.row !== null && iss.row !== undefined) {
      const want = `[data-row="${iss.row}"]` + (iss.field ? ` [data-field="${iss.field}"]` : "");
      if (!plWrap.querySelector(want)) {
        plWrap.showRow(iss.row, iss.field);
        return focusIssue(Object.assign({}, iss, { _shown: true }));
      }
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
    showChecks();
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
  refresh();

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

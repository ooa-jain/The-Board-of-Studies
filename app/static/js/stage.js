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
    // leaving a field with a wrong entry raises an alert as well as the
    // note under it
    const leave = () => {
      show();
      const msg = checkField(def, readInput(input, def));
      if (msg && window.Toast) {
        window.Toast.warning(msg, { title: def.label || "Check this entry",
                                    onClick: () => input.focus() });
      }
    };
    input.addEventListener("blur", leave);
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
        if (!m.pct_manual) {
          pct.classList.add("is-auto");
          if (m.pct === undefined || m.pct === null || m.pct === "") {
            const v0 = percentChange(m.previous, m.revised);
            if (v0 !== null) { m.pct = v0; pct.value = fmt(v0); }
          }
        }
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
  /* One module as the syllabus template sets it out: "Module No. N:" its
     title, its hours, and the content under them. */
  function moduleBlock(m, changed, i) {
    const wrapB = el("div", "mod-block");
    const top = el("div", "mod-top");
    top.appendChild(el("span", "mod-no", `Module No. ${i + 1}:`));
    const title = el("input", "mod-title");
    title.type = "text";
    title.placeholder = "Title of the module";
    title.value = m.title ?? "";
    const hrs = el("input", "mod-hours");
    hrs.type = "text";
    hrs.inputMode = "numeric";
    hrs.placeholder = "Hrs";
    hrs.value = m.hours ?? "";
    hrs.title = "Hours for this module";
    const content = el("textarea", "mod-content");
    content.rows = 5;
    content.placeholder = "Content of the module";
    content.value = m.revised ?? "";
    if (CTX.readonly) { title.disabled = hrs.disabled = content.disabled = true; }
    title.addEventListener("input", () => { m.title = title.value; changed(); });
    hrs.addEventListener("input", () => {
      hrs.value = hrs.value.replace(/[^0-9]/g, "");
      m.hours = hrs.value === "" ? "" : Number(hrs.value);
      changed();
      wrapB.dispatchEvent(new CustomEvent("mod:hours", { bubbles: true }));
    });
    content.addEventListener("input", () => { m.revised = content.value; changed(); });
    top.appendChild(title);
    const hw = el("span", "mod-hours-w");
    hw.appendChild(el("span", null, "Hours"));
    hw.appendChild(hrs);
    top.appendChild(hw);
    wrapB.appendChild(top);
    wrapB.appendChild(content);
    return wrapB;
  }

  // the modules' hours against the course's total teaching hours
  function hoursRow(mods, row, span) {
    const tr = el("tr", "mod-sum");
    const td = el("td");
    td.colSpan = span;
    const paint = () => {
      const sum = mods.reduce((a, m) => a + (num(m.hours) || 0), 0);
      const want = num(row.teaching_hours);
      td.textContent = "";
      td.appendChild(el("span", null, `Total hours of the modules: ${sum}`));
      if (want !== null) {
        const ok = sum === want;
        td.appendChild(el("span", "mod-sum-note" + (ok ? " is-ok" : " is-off"),
          ok ? ` — matches the ${want} teaching hours` : ` — the course has ${want} teaching hours`));
      }
    };
    paint();
    tr.addEventListener("mod:hours", paint);
    setTimeout(() => tr.closest("table")?.addEventListener("mod:hours", paint), 0);
    return tr;
  }

  /** An earlier batch's syllabus: the template's modules, no comparison. */
  function plainModules(def, row, commit) {
    if (!Array.isArray(row[def.name])) row[def.name] = [];
    const mods = row[def.name];
    if (!mods.length && !CTX.readonly) mods.push({});
    const wrap = el("div", "rt-wrap rv-wrap mod-wrap");
    const table = el("table", "rv-table mod-table");
    const head = el("thead");
    const hr = el("tr");
    const th = el("th", null, "Syllabus");
    th.colSpan = 2;
    hr.appendChild(th);
    head.appendChild(hr);
    table.appendChild(head);
    const body = el("tbody");
    table.appendChild(body);
    wrap.appendChild(table);
    function draw() {
      body.textContent = "";
      mods.forEach((m, i) => {
        const tr = el("tr", "rv-module");
        const td = el("td");
        td.colSpan = 2;
        td.appendChild(moduleBlock(m, commit, i));
        if (!CTX.readonly) {
          const rm = el("button", "rv-remove", "Remove");
          rm.type = "button";
          rm.setAttribute("aria-label", `Remove module ${i + 1}`);
          rm.addEventListener("click", () => { mods.splice(i, 1); draw(); commit(); });
          td.appendChild(rm);
        }
        tr.appendChild(td);
        body.appendChild(tr);
      });
      if (!CTX.readonly) {
        const tr = el("tr", "rv-add");
        const td = el("td");
        td.colSpan = 2;
        const add = el("button", "btn btn-ghost btn-sm", "+ Add module");
        add.type = "button";
        add.addEventListener("click", () => { mods.push({}); draw(); commit(); });
        td.appendChild(add);
        tr.appendChild(td);
        body.appendChild(tr);
      }
      body.appendChild(hoursRow(mods, row, 2));
    }
    draw();
    return wrap;
  }

  function revisionTable(def, row, commit) {
    if (def.compare === false) return plainModules(def, row, commit);
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
        if (!m.pct_manual) {
          pct.classList.add("is-auto");
          // filled in from the syllabi: work the % out straight away
          if (m.pct === undefined || m.pct === null || m.pct === "") {
            const v0 = percentChange(m.previous, m.revised);
            if (v0 !== null) { m.pct = v0; pct.value = fmt(v0); }
          }
        }
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
      body.appendChild(hoursRow(mods, row, 4));
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
    } else if (def.type === "select" || def.choices) {
      // a select, or a number picked from a short list (semester 1–8)
      input = el("select");
      input.appendChild(new Option(def.choices ? "—" : def.required ? "Choose…" : "—", ""));
      (def.options || def.choices || []).forEach(o => input.appendChild(new Option(String(o), String(o))));
      input.value = value == null ? "" : String(value);
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
      input.className = "sr-only";
      input.addEventListener("change", () => {
        uploadFile(input, Array.from(input.files || []), def, onChange);
        input.value = "";   // choosing the same file again still uploads it
      });
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

  function canView(info) { return info.kind === "pdf" || info.kind === "image"; }
  function inlineUrl(val) { return val.url + (val.url.includes("?") ? "&" : "?") + "inline=1"; }

  function filePreview(host, val, onRemove) {
    const old = host.querySelector(".file-preview");
    if (old) old.remove();
    if (!val || !val.name) return;

    const info = fileKind(val.name);
    const card = el("div", "file-preview kind-" + info.kind);

    const thumb = el(val.url && canView(info) ? "button" : "div", "file-thumb");
    if (thumb.tagName === "BUTTON") {
      thumb.type = "button";
      thumb.title = "View " + val.name;
      thumb.addEventListener("click", () => openViewer(val));
    }

    // the card that stands in when the real thing cannot be shown: a page
    // with its corner turned, carrying the file's type
    function drawnPage() {
      const d = el("span", "file-drawn");
      d.appendChild(el("span", "file-ext", info.label));
      return d;
    }

    if (val.thumb || (val.url && info.kind === "image")) {
      /* A picture of the first page, drawn by the server. If it never
         arrives — no renderer on the server, an encrypted file — the card
         takes its place. */
      const img = document.createElement("img");
      img.src = val.thumb || inlineUrl(val);
      img.alt = info.kind === "pdf"
        ? "First page of " + val.name : "Preview of " + val.name;
      img.loading = "lazy";
      img.addEventListener("load", () => thumb.classList.add("is-loaded"));
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

    const acts = el("div", "file-acts");
    if (val.url && canView(info)) {
      const view = el("button", "file-act is-view", "View");
      view.type = "button";
      view.addEventListener("click", () => openViewer(val));
      acts.appendChild(view);
    }
    if (val.url) {
      const open = el("a", "file-act", canView(info) ? "New tab" : "Open");
      open.href = canView(info) ? inlineUrl(val) : val.url;
      open.target = "_blank";
      open.rel = "noopener";
      acts.appendChild(open);
    }
    let sumBtn = null;
    if (val.url && info.kind === "pdf" && CTX.summaries) {
      sumBtn = el("button", "file-act is-ai", "✦ Summary");
      sumBtn.type = "button";
      sumBtn.title = "A short summary of this PDF";
      acts.appendChild(sumBtn);
    }
    if (onRemove && !CTX.readonly) {
      const rm = el("button", "file-act is-remove", "Remove");
      rm.type = "button";
      rm.setAttribute("aria-label", "Remove " + val.name);
      rm.addEventListener("click", onRemove);
      acts.appendChild(rm);
    }
    meta.appendChild(acts);
    const tl = templateLine(val);
    if (tl) meta.appendChild(tl);
    const kw = matchLine(val);
    if (kw) meta.appendChild(kw);
    if (val.url && (info.kind === "doc" || info.kind === "sheet")) {
      meta.appendChild(el("span", "file-note",
        "Word and Excel files cannot be shown in a browser — open it to check it."));
    }
    card.appendChild(meta);
    host.appendChild(card);
    if (sumBtn) {
      sumBtn.addEventListener("click", () => {
        const open = host.querySelector(".file-summary");
        if (open && !open.classList.contains("is-bad")) { open.remove(); host.classList.remove("has-summary"); return; }
        loadSummary(host, val, false);
      });
      // a PDF just uploaded is read straight away
      if (freshUploads.delete(val.url)) loadSummary(host, val, false);
    }
  }

  /* ------------------------------------------------------------- summaries
     The AI reads the PDF (pictures of its pages, for a scan) and says in a few
     lines what it is and whether it looks like the right document for the
     box. Made once per file on the server and kept. */
  const freshUploads = new Set();
  function loadSummary(host, val, refresh) {
    window.PortalSummary.load(host, val.url + "/summary", refresh);
  }

  /** One preview, or a row of them for a box that takes several files. */
  function showFiles(host, val, onRemove) {
    const oldList = host.querySelector(".file-previews");
    if (oldList) oldList.remove();
    const old = host.querySelector(":scope > .file-preview");
    if (old) old.remove();
    const list = el("div", "file-previews");
    const vals = (Array.isArray(val) ? val : [val]).filter(v => v && v.name);
    vals.forEach((v, i) => {
      const slot = el("div");
      filePreview(slot, v, onRemove ? () => onRemove(i) : null);
      list.appendChild(slot);
    });
    if (!vals.length) return;
    // under the box and its note, above the help line
    const anchor = host.querySelector(":scope > .upload-note") || host.querySelector(":scope > .upload-folder");
    if (anchor) anchor.after(list); else host.appendChild(list);
  }

  function fileNames(val) {
    return (Array.isArray(val) ? val : [val]).filter(v => v && v.name).map(v => v.name);
  }

  /* ---------------------------------------------------------------- viewer
     Every PDF and picture uploaded on the page, in one viewer: the whole
     document, all its pages, without leaving the form. Arrows step through
     the other uploads. */
  let viewer = null;
  function allViewable() {
    const out = [];
    document.querySelectorAll("#sections .field[data-field]").forEach(f => {
      (f._files ? f._files() : []).forEach(v => {
        if (v && v.url && canView(fileKind(v.name)) && !out.some(o => o.url === v.url)) out.push(v);
      });
    });
    return out;
  }
  function buildViewer() {
    const d = el("div", "file-viewer");
    d.hidden = true;
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-modal", "true");
    d.setAttribute("aria-label", "Document viewer");
    d.innerHTML =
      '<div class="fv-backdrop" data-close></div>' +
      '<div class="fv-panel">' +
      '  <div class="fv-head">' +
      '    <button type="button" class="fv-nav" data-step="-1" aria-label="Previous document">‹</button>' +
      '    <div class="fv-title"><strong></strong><span></span></div>' +
      '    <button type="button" class="fv-nav" data-step="1" aria-label="Next document">›</button>' +
      '    <a class="fv-btn" target="_blank" rel="noopener" data-newtab>New tab</a>' +
      '    <a class="fv-btn" data-download>Download</a>' +
      '    <button type="button" class="fv-close" data-close aria-label="Close viewer">×</button>' +
      '  </div>' +
      '  <div class="fv-body"><span class="sk fv-sk"></span></div>' +
      '</div>';
    document.body.appendChild(d);
    d.addEventListener("click", e => {
      if (e.target.closest("[data-close]")) closeViewer();
      const step = e.target.closest("[data-step]");
      if (step) stepViewer(+step.dataset.step);
    });
    document.addEventListener("keydown", e => {
      if (d.hidden) return;
      if (e.key === "Escape") closeViewer();
      if (e.key === "ArrowRight") stepViewer(1);
      if (e.key === "ArrowLeft") stepViewer(-1);
    });
    return d;
  }
  let viewList = [], viewAt = 0, viewFrom = null;
  function openViewer(val) {
    viewer = viewer || buildViewer();
    viewFrom = document.activeElement;
    viewList = allViewable();
    viewAt = viewList.findIndex(v => v.url === val.url);
    // a file outside the upload boxes (a table row's) opens first
    if (viewAt < 0) { viewList.unshift(val); viewAt = 0; }
    showInViewer();
    viewer.hidden = false;
    document.body.classList.add("fv-open");
    viewer.querySelector(".fv-close").focus();
  }
  function stepViewer(n) {
    if (viewList.length < 2) return;
    viewAt = (viewAt + n + viewList.length) % viewList.length;
    showInViewer();
  }
  function showInViewer() {
    const v = viewList[viewAt];
    const info = fileKind(v.name);
    viewer.querySelector(".fv-title strong").textContent = v.name;
    viewer.querySelector(".fv-title span").textContent =
      [info.label, sizeLabel(v.size), viewList.length > 1 ? `${viewAt + 1} of ${viewList.length}` : ""]
        .filter(Boolean).join(" · ");
    viewer.querySelectorAll(".fv-nav").forEach(b => { b.hidden = viewList.length < 2; });
    viewer.querySelector("[data-newtab]").href = inlineUrl(v);
    viewer.querySelector("[data-download]").href = v.url;
    const body = viewer.querySelector(".fv-body");
    body.innerHTML = '<span class="sk fv-sk"></span>';
    const doc = info.kind === "pdf" ? document.createElement("iframe") : document.createElement("img");
    doc.className = "fv-doc";
    if (info.kind === "pdf") {
      doc.title = v.name;
      doc.src = inlineUrl(v) + "#view=FitH";
    } else {
      doc.alt = v.name;
      doc.src = inlineUrl(v);
    }
    doc.addEventListener("load", () => { const sk = body.querySelector(".fv-sk"); if (sk) sk.remove(); });
    body.appendChild(doc);
  }
  function closeViewer() {
    if (!viewer) return;
    viewer.hidden = true;
    viewer.querySelector(".fv-body").innerHTML = "";
    document.body.classList.remove("fv-open");
    if (viewFrom && viewFrom.focus) viewFrom.focus();
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
        const v = { name: j.name, stored: j.stored, size: j.size,
                    url: j.url, thumb: j.thumb || null };
        if (j.match) v.match = j.match;
        matchToast(v);
        return v;
      });
  }

  /* --------------------------------------------------------- keyword match
     The server reads an upload and looks for the words a document for its box
     always carries; the answer shows as a line on the file and, when nothing
     matches, as a warning straight away. */
  const MATCH_WORDS = { match: "Keywords match", weak: "Few keywords match",
                        miss: "No expected keywords found", unread: "Keywords not checked" };
  /* A signed composition form: is every category filled in? */
  function templateLine(val) {
    const t = val && val.match && val.match.template;
    if (!t) return null;
    const bad = (t.blank || []).length || (t.half || []).length || t.placeholders;
    const line = el("div", "tpl-check " + (bad ? "is-bad" : "is-ok"));
    line.appendChild(el("span", "kw-icon", bad ? "!" : "✓"));
    line.appendChild(el("strong", null, bad ? `Blank in the ${t.template} — fill it`
                                            : `${t.template}: every category filled (${t.filled} of ${t.total})`));
    if (bad) {
      const ul = el("ul");
      if ((t.blank || []).length) ul.appendChild(el("li", null, "No name yet: " + t.blank.join(", ")));
      if ((t.half || []).length) ul.appendChild(el("li", null, "Designation missing: " + t.half.join(", ")));
      if (t.placeholders) ul.appendChild(el("li", null, `“Words only” still written in ${t.placeholders} place${t.placeholders === 1 ? "" : "s"}`));
      line.appendChild(ul);
      line.appendChild(el("span", "kw-sub", "Fill these in the form, sign it and upload it again — it cannot be submitted with blanks."));
    }
    return line;
  }

  function matchLine(val) {
    const m = val && val.match;
    if (!m || !m.status) return null;
    const line = el("div", "kw-match is-" + m.status);
    line.appendChild(el("span", "kw-icon", m.status === "match" ? "✓" : m.status === "unread" ? "–" : "!"));
    line.appendChild(el("strong", null, m.looks_like ? "Wrong document — this looks like " + m.looks_like
                                                     : (MATCH_WORDS[m.status] || "")));
    if (m.status === "unread") {
      line.appendChild(el("span", "kw-sub", "this file has no text to read (a scan, image or zip) — open it to check"));
    } else {
      const tags = el("span", "kw-tags");
      (m.expected || []).forEach(w => {
        const at = (m.found || []).indexOf(w), hit = at >= 0;
        const shown = hit && m.seen && m.seen[at] ? m.seen[at] : w.split("/")[0].trim();
        const t = el("span", "kw-tag" + (hit ? " is-hit" : ""), shown);
        t.title = (hit ? "Found in the file" : "Not found in the file") + (w.includes("/") ? " — any of: " + w : "");
        tags.appendChild(t);
      });
      line.appendChild(tags);
      if (m.looks_like) line.appendChild(el("span", "kw-sub", `This looks like ${m.looks_like}, not the “${m.label}” — check you chose the right box.`));
      else if (m.status === "miss") line.appendChild(el("span", "kw-sub", "make sure this is the right file for “" + m.label + "”"));
    }
    return line;
  }
  function matchToast(v) {
    const m = v.match;
    if (!m || !window.Toast) return;
    if (m.looks_like) {
      window.Toast.warning(`${v.name} looks like ${m.looks_like}, not the ${m.label}. Check you chose the right box.`,
                           { title: "Wrong document?", timeout: 12000 });
      return;
    }
    const t = m.template;
    if (t && ((t.blank || []).length || (t.half || []).length || t.placeholders)) {
      const what = (t.blank || []).length ? t.blank.join(", ") : (t.half || []).length ? "designation for " + t.half.join(", ") : "the “Words only” places";
      window.Toast.warning(`${v.name}: blank — fill ${what}.`, { title: "Blank in the form", timeout: 12000 });
      return;
    }
    if (t) { window.Toast.success(`${v.name}: every category in the ${t.template} is filled.`, { title: "Form complete" }); return; }
    if (m.status === "miss") {
      window.Toast.warning(`None of the words a “${m.label}” carries (${(m.expected || []).slice(0, 4).join(", ")}…) are in ${v.name}. Check it is the right file.`,
                           { title: "Keywords do not match" });
    } else if (m.status === "match") {
      window.Toast.success(`${v.name} carries ${(m.seen || m.found).slice(0, 4).join(", ")}.`, { title: "Keywords match" });
    }
  }

  // the types a box takes, from its accept list — a dropped file skips the
  // browser's own picker, so the check happens here
  function accepts(def, file) {
    if (!def.accept) return true;
    const name = file.name.toLowerCase();
    return def.accept.split(",").map(a => a.trim().toLowerCase()).some(a =>
      a.startsWith(".") ? name.endsWith(a) : a.endsWith("/*")
        ? (file.type || "").startsWith(a.slice(0, -1)) : file.type === a);
  }

  function uploadFile(input, files, def, onChange) {
    const wrap = input.closest(".field");
    if (!files.length) return;
    const note = wrap.querySelector(".upload-note") ||
                 wrap.querySelector(".upload-folder").insertAdjacentElement("afterend", el("span", "help upload-note"));
    note.className = "help upload-note";
    note.setAttribute("role", "status");
    const bad = files.filter(f => !accepts(def, f));
    files = files.filter(f => accepts(def, f));
    if (!def.multiple) files = files.slice(0, 1);
    if (!files.length) {
      note.textContent = `${bad.map(f => f.name).join(", ")} — this box takes ${def.accept} only.`;
      note.className = "help upload-note is-bad-text";
      return;
    }
    const zone = wrap.querySelector(".upload-folder");
    zone.classList.add("is-busy");
    note.textContent = files.length > 1 ? `Uploading ${files.length} files…` : `Uploading ${files[0].name}…`;
    // one after another, so a slow connection is not flooded
    files.reduce((chain, f) => chain.then(done => uploadOne(f, def).then(v => done.concat([v]))),
                 Promise.resolve([]))
      .then(done => {
        done.forEach(v => { if (CTX.summaries && fileKind(v.name).kind === "pdf") freshUploads.add(v.url); });
        const had = wrap._files ? wrap._files() : [];
        const val = def.multiple ? had.concat(done) : done[0];
        note.textContent = (done.length > 1
          ? `Uploaded ${done.length} files`
          : "✓ Uploaded") +
          (bad.length ? ` · skipped ${bad.map(f => f.name).join(", ")} (not ${def.accept})` : "");
        note.className = "help upload-note is-ok";
        wrap._set(val);
        onChange(val);
      })
      .catch(e => {
        note.textContent = (e && e.message) ||
          "Upload failed — check your connection and choose the file again.";
        note.className = "help upload-note is-bad-text";
      })
      .finally(() => zone.classList.remove("is-busy"));
  }

  /* The upload box: a folder that opens when a file is dragged over it or
     the pointer rests on it, and takes a click, a keypress or a drop. */
  function uploadBox(def, input, value, onChange) {
    const zone = el("div", "upload-folder");
    const folder = el("div", "folder");
    folder.setAttribute("aria-hidden", "true");
    const front = el("div", "front-side");
    front.appendChild(el("div", "tip"));
    front.appendChild(el("div", "cover"));
    folder.appendChild(front);
    folder.appendChild(el("div", "back-side cover"));
    zone.appendChild(folder);

    const lab = el("label", "custom-file-upload");
    lab.setAttribute("for", input.id);
    lab.appendChild(input);
    const txt = el("span", "cfu-text");
    txt.appendChild(el("strong", null, CTX.readonly ? "Uploads are locked"
      : def.multiple ? "Drag files here to upload" : "Drag a file here to upload"));
    if (def.accept) txt.appendChild(el("span", "cfu-types",
      def.accept.replace(/\./g, "").toUpperCase().split(",").join(" · ") + (def.multiple ? " · several at once" : "")));
    lab.appendChild(txt);
    if (!CTX.readonly) lab.appendChild(el("span", "cfu-btn", def.multiple ? "Choose files" : "Choose file"));
    zone.appendChild(lab);
    if (CTX.readonly) { zone.classList.add("is-locked"); return zone; }

    let depth = 0;
    zone.addEventListener("dragenter", e => { e.preventDefault(); depth++; zone.classList.add("is-over"); });
    zone.addEventListener("dragover", e => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; });
    zone.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; zone.classList.remove("is-over"); } });
    zone.addEventListener("drop", e => {
      e.preventDefault();
      depth = 0;
      zone.classList.remove("is-over");
      uploadFile(input, Array.from(e.dataTransfer.files || []), def, onChange);
    });
    return zone;
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
    if (def.type === "file") {
      let current = value && typeof value === "object" ? value : (def.multiple ? [] : null);
      const list = () => (Array.isArray(current) ? current : [current]).filter(v => v && v.name);
      wrap._files = list;
      wrap._set = v => {
        current = v;
        showFiles(wrap, current, i => {
          const next = def.multiple ? list().filter((_, j) => j !== i) : null;
          const note = wrap.querySelector(".upload-note");
          if (note) { note.textContent = "Removed — upload again if that was a mistake."; note.className = "help upload-note"; }
          wrap._set(next);
          onChange(def.multiple ? next : "");
        });
      };
      if (def.template) {
        const t = el("a", "tpl-link", "⤓ Download the template (Word)");
        t.href = CTX.urls.static + def.template;
        t.setAttribute("download", "");
        wrap.appendChild(t);
      }
      wrap.appendChild(uploadBox(def, input, value, onChange));
      // the file card under the box already names what is uploaded
      wrap._set(current);
    } else {
      wrap.appendChild(input);
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
    const fixedTotal = (section.columns || []).some(c => c.name === "total_marks" && c.fixed_value != null);
    if (has("total_marks") && has("cia") && has("ese") && !fixedTotal) {
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

  // a number box as wide as its value, never under two digits
  const FIELD_SIZING = window.CSS && CSS.supports && CSS.supports("field-sizing", "content");
  function fitNum(input) {
    if (FIELD_SIZING) return;
    input.style.width = `calc(${Math.max(2, String(input.value || "").length)}ch + 20px)`;
  }
  // derived values (credits, total) are written by code, not typed
  refreshers.push(() => document.querySelectorAll("input.num-cell").forEach(fitNum));

  /* A file for one row of a table: an Upload button, then the file's name
     (opening it, or the viewer for a PDF) and × to take it off. */
  function rowFile(def, row, changed) {
    const box = el("div", "row-file");
    const input = el("input");
    input.type = "file";
    if (def.accept) input.accept = def.accept;
    input.className = "sr-only";
    input.tabIndex = -1;
    function paint(note) {
      box.textContent = "";
      const v = row[def.name];
      if (v && v.name) {
        const info = fileKind(v.name);
        const a = el(canView(info) ? "button" : "a", "row-file-name", v.name);
        a.title = v.name;
        if (canView(info)) { a.type = "button"; a.addEventListener("click", () => openViewer(v)); }
        else { a.href = v.url; a.target = "_blank"; a.rel = "noopener"; }
        box.appendChild(el("span", "row-file-ext", info.label));
        box.appendChild(a);
        if (v.match && v.match.status && v.match.status !== "unread") {
          const ok = v.match.status === "match";
          const mk = el("span", "row-file-kw " + (ok ? "is-match" : "is-" + v.match.status), ok ? "✓" : "!");
          mk.title = ok ? "Keywords match: " + v.match.found.join(", ")
                        : v.match.status === "weak" ? "Few keywords match: " + v.match.found.join(", ")
                        : "No expected keywords found — check this is the right file";
          box.appendChild(mk);
        }
        if (!CTX.readonly) {
          const x = el("button", "row-file-x", "×");
          x.type = "button";
          x.title = "Remove this file";
          x.setAttribute("aria-label", `Remove ${v.name}`);
          x.addEventListener("click", () => { row[def.name] = ""; changed(); paint(); });
          box.appendChild(x);
        }
      } else if (!CTX.readonly) {
        const b = el("button", "row-file-up");
        b.type = "button";
        b.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M5 20h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        b.appendChild(el("span", null, note || "Upload"));
        b.title = def.help || "Upload a file";
        b.disabled = note === "Uploading…";
        b.addEventListener("click", () => input.click());
        box.appendChild(b);
      } else {
        box.appendChild(el("span", "muted", "—"));
      }
      box.appendChild(input);
    }
    input.addEventListener("change", () => {
      const f = input.files && input.files[0];
      input.value = "";
      if (!f) return;
      const ok = !def.accept || def.accept.split(",").some(a => f.name.toLowerCase().endsWith(a.trim()));
      if (!ok) { paint("PDF, Word or Excel"); return; }
      paint("Uploading…");
      uploadOne(f, def)
        .then(v => { row[def.name] = v; changed(); paint(); })
        .catch(() => paint("Failed — retry"));
    });
    paint();
    return box;
  }

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
      if (c.type === "integer") th.className = "num-col";
      else if (c.width) th.style.width = c.width;
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

    const FIXED = section.columns.filter(c => c.fixed_value != null);
    const PAIRS = section.columns.filter(c => c.complement);
    const OUT_OF = (FIXED.find(c => c.name === "total_marks") || {}).fixed_value ?? 100;
    // a value typed (or read from a file) in one of a pair sets the other
    function settle(row) {
      let changed = false;
      FIXED.forEach(c => { if (row[c.name] !== c.fixed_value) { row[c.name] = c.fixed_value; changed = true; } });
      const first = PAIRS[0];
      if (first) {
        const a = num(row[first.name]), b = num(row[first.complement]);
        if (a !== null && a >= 0 && a <= OUT_OF && b !== OUT_OF - a) { row[first.complement] = OUT_OF - a; changed = true; }
        else if (a === null && b !== null && b >= 0 && b <= OUT_OF) { row[first.name] = OUT_OF - b; changed = true; }
      }
      return changed;
    }

    function draw() {
      tbody.innerHTML = "";
      const data = rows(section.key);
      let settled = false;
      data.forEach((row, i) => {
        if (!CTX.readonly && settle(row)) settled = true;
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
          if (c.type === "file") {
            holder.appendChild(rowFile(c, row, () => { touch(); }));
            td.className = "rt-file";
            td.appendChild(holder);
            tr.appendChild(td);
            return;
          }
          const input = makeInput(c, row[c.name], (v) => {
            row[c.name] = v;
            if (c.complement) {
              if (cells[c.name]) cells[c.name].classList.remove("is-auto");   // typed, not worked out
              const n = num(v);
              if (n !== null && n >= 0 && n <= OUT_OF) {
                row[c.complement] = OUT_OF - n;
                if (cells[c.complement]) {
                  cells[c.complement].value = String(OUT_OF - n);
                  cells[c.complement].classList.add("is-auto");
                  fitNum(cells[c.complement]);
                }
              }
            }
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
          if (c.type === "integer" && !c.choices) {
            // two digits wide, growing with what is typed
            input.classList.add("num-cell");
            fitNum(input);
            input.addEventListener("input", () => fitNum(input));
          } else if (c.width) input.style.minWidth = c.width;
          if (c.fixed_value != null) {
            input.readOnly = true;
            input.classList.add("is-fixed");
            input.title = `Every course is out of ${c.fixed_value}`;
          }
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
      if (settled) touch();
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

  const LOCK = '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">' +
    '<rect x="5" y="11" width="14" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
    '<path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';

  /* The department's identity as a profile card (after Uiverse.io,
     Smit-Prajapati). It is the Office's record, so nothing is edited here.
     At rest a large monogram fills the card with the name on a strip at the
     foot; as the card scrolls into view the strip rises over it and the
     monogram shrinks into a round badge — scrolling drives it, no click. */
  function renderProfileCard(section, block) {
    const v = state[section.key] || {};
    const name = String(v.dept_name || CTX.dept_name || "Department").trim();
    const words = name.replace(/^Department of\s+/i, "").split(/\s+/).filter(w => /^[A-Z]/.test(w) && !/^(and|of|the)$/i.test(w));
    const mono = (words.slice(0, 2).map(w => w[0]).join("") || name[0] || "D").toUpperCase();
    const card = el("div", "pcard");
    card.setAttribute("aria-label", `${name} — department identity`);
    const pic = el("div", "pcard-pic");
    pic.setAttribute("aria-hidden", "true");
    pic.innerHTML =
      '<svg viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice">' +
      '<defs><pattern id="pcard-dots" width="18" height="18" patternUnits="userSpaceOnUse">' +
      '<circle cx="2" cy="2" r="1.6" fill="#c79c10" opacity=".35"/></pattern></defs>' +
      '<rect width="400" height="240" fill="#fbf1cf"/><rect width="400" height="240" fill="url(#pcard-dots)"/>' +
      '<circle cx="330" cy="40" r="70" fill="#f6dd8f" opacity=".7"/>' +
      '<circle cx="60" cy="210" r="56" fill="#f3c9a4" opacity=".55"/></svg>';
    pic.appendChild(el("span", "pcard-mono", mono));
    card.appendChild(pic);

    const lock = el("span", "pcard-lock");
    lock.innerHTML = LOCK;
    lock.title = "From the Office of Academics record";
    card.appendChild(lock);

    const bottom = el("div", "pcard-bottom");
    const content = el("div", "pcard-content");
    content.appendChild(el("span", "pcard-name", name));
    const facts = el("dl", "pcard-facts");
    section.fields.filter(f => f.name !== "dept_name").forEach(f => {
      const val = v[f.name];
      const d = el("div", "pcard-fact");
      d.appendChild(el("dt", null, f.label));
      d.appendChild(el("dd", null, val == null || String(val).trim() === "" ? "—" : String(val)));
      facts.appendChild(d);
    });
    content.appendChild(facts);
    bottom.appendChild(content);
    card.appendChild(bottom);
    block.appendChild(card);

    // open while the card is well in view, close as it leaves
    const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (still || !("IntersectionObserver" in window)) { card.classList.add("is-open"); return; }
    new IntersectionObserver(entries => entries.forEach(e => {
      card.classList.toggle("is-open", e.intersectionRatio >= 0.6);
    }), { threshold: [0, 0.6, 1] }).observe(card);
  }

  function renderCards(section, block) {
    if (section.frozen) return renderProfileCard(section, block);
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
      if (section.frozen) {
        // the Office's record: shown, never edited here
      } else if (!CTX.readonly) {
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

  // an icon and a word: "− Remove", "+ Keep", "+ Add"
  function labelButton(cls, icon, text, label) {
    const b = iconButton(cls + " pl-btn", icon, label || text);
    b.appendChild(el("span", null, text));
    return b;
  }

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
        const addNew = () => {
          data.push({ source: "new", decision: "keep", programme_code: "",
                      programme_name: "", degree: (t.degrees || [""])[0] });
          draw();
          touch();
          list.lastElementChild?.scrollIntoView({ block: "nearest", behavior: "smooth" });
          list.lastElementChild?.querySelector("input")?.focus();
        };
        const top = labelButton("pl-head-add", "plus", "Add", `Add a ${t.key === "all" ? "" : t.key + " "}programme`);
        top.addEventListener("click", addNew);
        panel.insertBefore(top, list);
        const add = el("button", "pl-panel-add");
        add.type = "button";
        add.innerHTML = ICON.plus;
        add.appendChild(el("span", null, `Add ${t.key === "all" ? "a" : t.key} programme`));
        add.addEventListener("click", addNew);
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
          const del = labelButton("pl-minus", "minus", "Remove", "Take this new programme off");
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
          const back = labelButton("pl-plus", "plus", "Add back", `Keep ${row.programme_code} after all`);
          back.addEventListener("click", () => {
            row.decision = "keep";
            delete row.removal_reason;
            delete row.removal_note;
            draw();
            touch();
          });
          li.appendChild(back);
        } else {
          const rm = labelButton("pl-minus", "minus", "Remove", `Remove ${row.programme_code}`);
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
            "Use Add to put in each one you run this year."));
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

  // ------------------------------------------------------------- template sheets
  /* A syllabus, laid out as the syllabus template is: one bordered sheet
     per course, with nothing on it but the template's own headings —
     Name of the Program, Course Code, Name of the Course, credits and
     hours, Pedagogy, Course Outcomes, the modules with their hours, Skill
     Development Activities and Books for reference. */
  function renderSheets(section, host) {
    const data = rows(section.key);
    if (!data.length && !CTX.readonly) data.push({});
    const C = Object.fromEntries(section.columns.map(c => [c.name, c]));
    const blank = r => Object.keys(r).filter(k => !k.startsWith("_"))
      .every(k => r[k] === "" || r[k] == null || (Array.isArray(r[k]) && !r[k].some(m => m && (m.title || m.revised || m.hours))));

    const top = el("div", "sheet-bar");
    const note = el("span", "sheet-note");
    note.setAttribute("role", "status");
    host.appendChild(top);
    const list = el("div", "sheets");
    host.appendChild(list);

    if (!CTX.readonly && (CTX.fill || []).length) {
      const fb = el("button", "btn btn-ghost btn-sm", "Fill in all courses from the Curriculum");
      fb.type = "button";
      fb.addEventListener("click", () => {
        const have = new Set(data.map(r => String(r.course_code || "").trim().toUpperCase()));
        const add = CTX.fill.filter(p => !have.has(String(p.course_code).toUpperCase()));
        if (!add.length) { note.textContent = "Every course of the Curriculum is already here."; return; }
        for (let k = data.length - 1; k >= 0; k--) if (blank(data[k])) data.splice(k, 1);
        add.forEach(p => data.push(Object.assign({}, p)));
        draw(); touch();
        note.textContent = `Added ${add.length} course${add.length === 1 ? "" : "s"} — code, name, credits and hours are in.`;
      });
      top.appendChild(fb);
    }
    top.appendChild(note);

    function field(row, i, name, extra) {
      const c = Object.assign({}, C[name], extra || {});
      const holder = el("div", "sh-in");
      holder.dataset.field = name;
      holder.dataset.row = i;
      const input = makeInput(c, row[name], v => { row[name] = v; touch(); });
      input.setAttribute("aria-label", c.label);
      if (c.placeholder) input.placeholder = c.placeholder;
      holder.appendChild(input);
      attachLiveCheck(input, c, holder);
      return holder;
    }
    const cell = (tag, cls, kids, span) => {
      const t = el(tag, cls);
      if (span) t.colSpan = span;
      (kids || []).forEach(k => t.appendChild(typeof k === "string" ? el("span", null, k) : k));
      return t;
    };
    const label = (txt, node) => {
      const d = el("div", "sh-line");
      d.appendChild(el("strong", "sh-lab", txt));
      d.appendChild(node);
      return d;
    };

    function modulesRows(row, i, tbody) {
      if (!Array.isArray(row.modules)) row.modules = [];
      const mods = row.modules;
      if (!mods.length && !CTX.readonly) mods.push({});
      const head = el("tr", "sh-syl-head");
      head.appendChild(cell("th", "sh-left", ["Syllabus:"]));
      head.appendChild(cell("th", "sh-hours", ["Hours"]));
      tbody.appendChild(head);
      const sum = el("span");
      const paintSum = () => {
        const total = mods.reduce((a, m) => a + (num(m.hours) || 0), 0);
        const want = num(row.teaching_hours);
        sum.textContent = `Total ${total} hours` + (want === null ? "" :
          total === want ? ` — matches the ${want} teaching hours` : ` — the course has ${want} teaching hours`);
        sum.className = want === null ? "" : total === want ? "is-ok" : "is-off";
      };
      mods.forEach((m, k) => {
        const tr = el("tr", "sh-mod");
        const t = el("input", "sh-mod-title");
        t.type = "text"; t.value = m.title ?? ""; t.placeholder = "Title of the module";
        t.addEventListener("input", () => { m.title = t.value; touch(); });
        const lab = el("div", "sh-mod-line");
        lab.appendChild(el("strong", null, `Module No. ${k + 1}:`));
        lab.appendChild(t);
        if (!CTX.readonly && mods.length > 1) {
          const rm = el("button", "sh-x", "×");
          rm.type = "button"; rm.title = `Remove module ${k + 1}`;
          rm.addEventListener("click", () => { mods.splice(k, 1); draw(); touch(); });
          lab.appendChild(rm);
        }
        tr.appendChild(cell("td", "sh-left", [lab]));
        const h = el("input", "sh-mod-hours");
        h.type = "text"; h.inputMode = "numeric"; h.value = m.hours ?? ""; h.placeholder = "—";
        h.addEventListener("input", () => {
          h.value = h.value.replace(/[^0-9]/g, "");
          m.hours = h.value === "" ? "" : Number(h.value);
          paintSum(); touch();
        });
        tr.appendChild(cell("td", "sh-hours", [h]));
        tbody.appendChild(tr);
        const tr2 = el("tr", "sh-mod-body");
        const ta = el("textarea", "sh-mod-content");
        ta.rows = 4; ta.value = m.revised ?? ""; ta.placeholder = "Content of the module";
        ta.addEventListener("input", () => { m.revised = ta.value; touch(); });
        if (CTX.readonly) t.disabled = h.disabled = ta.disabled = true;
        tr2.appendChild(cell("td", null, [ta], 2));
        tbody.appendChild(tr2);
      });
      const foot = el("tr", "sh-mod-foot");
      const td = cell("td", null, [], 2);
      if (!CTX.readonly) {
        const add = el("button", "btn btn-ghost btn-sm", "+ Add module");
        add.type = "button";
        add.addEventListener("click", () => { mods.push({}); draw(); touch(); });
        td.appendChild(add);
      }
      td.appendChild(sum);
      foot.appendChild(td);
      tbody.appendChild(foot);
      paintSum();
    }

    function sheet(row, i) {
      const wrap = el("section", "sheet-wrap");
      wrap.dataset.row = i;
      const cap = el("div", "sheet-cap");
      cap.appendChild(el("span", null, `Course ${i + 1}${row.course_code ? " · " + row.course_code : ""}`));
      if (!CTX.readonly && data.length > 1) {
        const rm = el("button", "btn btn-ghost btn-sm", "Remove");
        rm.type = "button";
        rm.addEventListener("click", () => {
          if (!blank(row) && !window.confirm(`Remove ${row.course_code || "this course"} and its syllabus?`)) return;
          data.splice(i, 1); draw(); touch();
        });
        cap.appendChild(rm);
      }
      wrap.appendChild(cap);

      const t = el("table", "sheet");
      const tb = el("tbody");
      t.appendChild(tb);
      const r1 = el("tr");
      const head = el("td", "sh-head");
      head.colSpan = 3;
      const prog = el("div", "sh-line sh-center");
      prog.appendChild(el("strong", "sh-lab", "Name of the Program:"));
      prog.appendChild(el("span", "sh-prog", CTX.programme_name || ""));
      head.appendChild(prog);
      head.appendChild(label("Course Code:", field(row, i, "course_code")));
      head.appendChild(label("Name of the Course:", field(row, i, "course_title")));
      r1.appendChild(head);
      tb.appendChild(r1);

      const r2 = el("tr", "sh-grid-h");
      ["credits", "hours_per_week", "teaching_hours"].forEach(n => r2.appendChild(cell("th", null, [C[n].label])));
      tb.appendChild(r2);
      const r3 = el("tr", "sh-grid");
      ["credits", "hours_per_week", "teaching_hours"].forEach(n => r3.appendChild(cell("td", null, [field(row, i, n)])));
      tb.appendChild(r3);

      const block = (lab, name, after) => {
        const tr = el("tr");
        const td = cell("td", "sh-block", [], 3);
        td.appendChild(el("strong", "sh-lab", lab));
        td.appendChild(field(row, i, name));
        if (after) td.appendChild(el("strong", "sh-note", after));
        tr.appendChild(td);
        tb.appendChild(tr);
      };
      block("Pedagogy:", "pedagogy");
      block("Course Outcomes: On successful completion of the course, the students' will be able to", "outcomes");
      // the modules sit in a table of their own, so the sheet keeps its
      // three equal columns above
      const mr = el("tr");
      const mtd = cell("td", "sh-nest", [], 3);
      const mt = el("table", "sheet sh-syl");
      const mtb = el("tbody");
      mt.appendChild(mtb);
      modulesRows(row, i, mtb);
      mtd.appendChild(mt);
      mr.appendChild(mtd);
      tb.appendChild(mr);
      block("Skill Development Activities:", "skill_activities");
      block("Books for reference:", "books", "Note: Latest edition of books may be used.");
      wrap.appendChild(t);
      return wrap;
    }

    function draw() {
      list.textContent = "";
      data.forEach((row, i) => list.appendChild(sheet(row, i)));
      if (!CTX.readonly) {
        const add = el("button", "btn btn-ghost sheet-add", "+ Add another course");
        add.type = "button";
        add.addEventListener("click", () => {
          data.push({});
          draw(); touch();
          list.lastElementChild.previousElementSibling?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
        list.appendChild(add);
      }
    }
    host.showRow = () => draw();
    draw();
  }

  // -------------------------------------------------------- revision tables
  /* Course Revision as the syllabus revision document has it: one
     module-wise table per course — year, title and code before and after,
     each module's previous and revised text with its % change, and the
     average. "Fill in all courses" brings every course of the current batch
     syllabus with its modules, and the previous ones from the latest earlier
     batch, so the percentages work themselves out. */
  function renderRevisionCourses(section, host) {
    const data = rows(section.key);
    if (!data.length && !CTX.readonly) data.push({});
    const C = Object.fromEntries(section.columns.map(c => [c.name, c]));
    const blank = r => !String(r.course_code || "").trim() && !String(r.course_title || "").trim()
      && !(r.modules || []).some(m => m && (m.previous || m.revised));
    const top = el("div", "sheet-bar");
    const note = el("span", "sheet-note");
    note.setAttribute("role", "status");
    host.appendChild(top);
    const list = el("div", "rv-list");
    host.appendChild(list);
    if (!CTX.readonly && (CTX.fill || []).length) {
      const fb = el("button", "btn btn-ghost btn-sm", "Fill in all courses from the syllabi");
      fb.type = "button";
      fb.title = "Revised modules from the current batch syllabus, previous ones from the latest earlier batch";
      fb.addEventListener("click", () => {
        const have = new Set(data.map(r => String(r.course_code || "").trim().toUpperCase()));
        const add = CTX.fill.filter(p => !have.has(String(p.course_code).toUpperCase()));
        if (!add.length) { note.textContent = "Every course is already here."; return; }
        for (let k = data.length - 1; k >= 0; k--) if (blank(data[k])) data.splice(k, 1);
        add.forEach(p => data.push(JSON.parse(JSON.stringify(p))));
        draw(); touch();
        note.textContent = `Added ${add.length} course${add.length === 1 ? "" : "s"} — the % change is worked out from the two syllabi.`;
      });
      top.appendChild(fb);
    }
    top.appendChild(note);

    function input(row, name) {
      const c = C[name];
      const holder = el("label", "rv-in");
      holder.dataset.field = name;
      holder.appendChild(el("span", null, c.label));
      const i = makeInput(c, row[name], v => { row[name] = v; touch(); });
      holder.appendChild(i);
      attachLiveCheck(i, c, holder);
      return [holder, i];
    }

    function course(row, i) {
      const wrap = el("section", "rv-course");
      wrap.dataset.row = i;
      const head = el("div", "rv-course-head");
      head.appendChild(el("span", "rv-course-no", String(i + 1).padStart(2, "0")));
      const [hc, ic] = input(row, "course_code");
      const [ht, it] = input(row, "course_title");
      const [hs] = input(row, "semester");
      head.appendChild(hc); head.appendChild(ht); head.appendChild(hs);
      if (!CTX.readonly && data.length > 1) {
        const rm = el("button", "btn btn-ghost btn-sm", "Remove");
        rm.type = "button";
        rm.addEventListener("click", () => {
          if (!blank(row) && !window.confirm(`Remove ${row.course_code || "this course"} from the revision?`)) return;
          data.splice(i, 1); draw(); touch();
        });
        head.appendChild(rm);
      }
      wrap.appendChild(head);
      let table = revisionTable(C.modules, row, () => touch());
      wrap.appendChild(table);
      // the revised side of the table shows the course's code and title
      const redraw = () => {
        const t = revisionTable(C.modules, row, () => touch());
        table.replaceWith(t); table = t;
      };
      ic.addEventListener("change", redraw);
      it.addEventListener("change", redraw);
      return wrap;
    }

    function draw() {
      list.textContent = "";
      data.forEach((row, i) => list.appendChild(course(row, i)));
      if (!CTX.readonly) {
        const add = el("button", "btn btn-ghost sheet-add", "+ Add another course");
        add.type = "button";
        add.addEventListener("click", () => { data.push({}); draw(); touch(); });
        list.appendChild(add);
      }
      refresh();
    }
    host.showRow = () => draw();
    draw();
  }

  // ------------------------------------------------------------------ expand
  /* A wide table is easier to fill in on the whole screen. Expand lifts the
     section itself into a large pop-up — the same inputs, still saving as
     you type — and Close (or Esc) puts it back where it was. */
  const WIDE_SECTIONS = ["table", "credit_distribution", "credit_matrix", "revision_summary"];
  let expanded = null;

  function expandable(block, heading, title) {
    heading.classList.add("has-expand");
    const btn = el("button", "btn btn-ghost btn-sm sec-expand");
    btn.type = "button";
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    btn.appendChild(el("span", null, "Expand"));
    btn.setAttribute("aria-label", `Expand ${title}`);
    btn.addEventListener("click", () => (expanded ? collapse() : expand(block, title, btn)));
    heading.appendChild(btn);
  }

  function expand(block, title, btn) {
    const holder = el("div", "sec-holder");
    block.replaceWith(holder);
    const pop = el("div", "sec-pop");
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-modal", "true");
    pop.setAttribute("aria-label", title);
    const panel = el("div", "sec-pop-panel");
    const head = el("div", "sec-pop-head");
    head.appendChild(el("strong", null, title));
    head.appendChild(el("span", "sec-pop-hint", "Changes save as you type · Esc to close"));
    const close = el("button", "btn btn-gold btn-sm", "Close");
    close.type = "button";
    close.addEventListener("click", collapse);
    head.appendChild(close);
    const body = el("div", "sec-pop-body");
    body.appendChild(block);
    panel.appendChild(head);
    panel.appendChild(body);
    pop.appendChild(el("div", "sec-pop-backdrop"));
    pop.appendChild(panel);
    document.body.appendChild(pop);
    document.body.classList.add("fv-open");
    btn.querySelector("span").textContent = "Collapse";
    expanded = { block, holder, pop, btn };
    close.focus();
  }

  function collapse() {
    if (!expanded) return;
    const { block, holder, pop, btn } = expanded;
    holder.replaceWith(block);
    pop.remove();
    document.body.classList.remove("fv-open");
    btn.querySelector("span").textContent = "Expand";
    expanded = null;
    btn.focus();
  }

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && expanded && !document.querySelector(".file-viewer:not([hidden])")) collapse();
  });

  // ------------------------------------------------------------------ render

  /* One row per document, in order, each opened with a click to upload.
     Closed, a row still says where it stands: not uploaded, uploaded (how
     many), the keyword check, a form with blanks. The first required one
     still missing is opened for you. */
  function docStatus(f, v) {
    const vals = (Array.isArray(v) ? v : [v]).filter(x => x && x.name);
    if (!vals.length) return f.required ? ["is-todo", "Not uploaded"] : ["is-opt", "Optional"];
    const bad = vals.find(x => x.match && x.match.template &&
      ((x.match.template.blank || []).length || (x.match.template.half || []).length || x.match.template.placeholders));
    if (bad) return ["is-bad", "Blank in the form — fill it"];
    const wrong = vals.find(x => x.match && x.match.looks_like);
    if (wrong) return ["is-bad", "Looks like " + wrong.match.looks_like];
    const miss = vals.find(x => x.match && x.match.status === "miss");
    if (miss) return ["is-warn", "Keywords do not match"];
    const weak = vals.find(x => x.match && x.match.status === "weak");
    const n = vals.length > 1 ? ` (${vals.length} files)` : "";
    if (weak) return ["is-warn", "Uploaded" + n + " · few keywords"];
    return ["is-ok", "Uploaded" + n + " ✓"];
  }

  function accordion(section, grid, made) {
    grid.classList.add("acc");
    let opened = false;
    made.forEach(([f, b], i) => {
      const d = el("details", "acc-item");
      const sum = el("summary", "acc-head");
      sum.appendChild(el("span", "acc-n", String(i + 1)));
      const t = el("span", "acc-title", f.label);
      if (f.required) t.appendChild(el("span", "req", " *"));
      sum.appendChild(t);
      const chip = el("span", "acc-chip");
      sum.appendChild(chip);
      sum.appendChild(el("span", "acc-caret", "›"));
      d.appendChild(sum);
      const body = el("div", "acc-body");
      b.replaceWith(d);
      body.appendChild(b);
      d.appendChild(body);
      const paint = () => {
        const [cls, words] = docStatus(f, (state[section.key] || {})[f.name]);
        chip.className = "acc-chip " + cls;
        chip.textContent = words;
        d.classList.toggle("is-done", cls === "is-ok");
      };
      paint();
      refreshers.push(paint);
      if (!opened && !CTX.readonly && f.required && chip.classList.contains("is-todo")) { d.open = true; opened = true; }
    });
  }

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
      if (section.hidden) return;        // filled from elsewhere on the page
      const block = el("div", "section-block");
      block.id = `sec-${section.key}`;
      const h = el("h3", null, section.title);
      if (section.title) block.appendChild(h);
      if (WIDE_SECTIONS.includes(section.type) && !["cards", "sheet"].includes(section.display) && section.title) expandable(block, h, section.title);
      if (section.help) block.appendChild(el("div", "section-help", section.help));
      (section.links || []).forEach(l => {
        const a = el("a", "section-link", `${l.label} →`);
        a.href = CTX.urls.stage.replace("__stage__", l.stage);
        block.appendChild(a);
      });

      if (section.type === "table" && section.display === "sheet") {
        renderSheets(section, block);
      } else if (section.type === "table" && section.display === "revision") {
        renderRevisionCourses(section, block);
      } else if (section.type === "table" && section.display === "cards") {
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
        const made = [];
        state[section.key] = state[section.key] || {};
        section.fields.forEach(f => {
          if (f.hidden) return;              // kept in the record, not shown
          // standard wording is the placeholder: an empty box means "use it".
          // A draft that still holds the wording word for word shows it the
          // same way, so the department sees grey text it can type over.
          if (f.prefill_text && f.type !== "fixed") {
            // never "required" on the page: empty is a valid answer here
            f = Object.assign({}, f, { placeholder: f.prefill_text, required: false });
            if (!CTX.readonly && String(state[section.key][f.name] || "").trim() === f.prefill_text.trim()) {
              state[section.key][f.name] = "";
            }
          }
          if (f.derive_from) f = Object.assign({}, f, { required: false });
          const b = fieldBlock(f, state[section.key][f.name], v => {
            setVal(section.key, f.name, v);
            // the credit check follows the degree: save, then reopen with it
            if (f.reload_on_change) { reloadAfterSave = true; clearTimeout(saveTimer); save(); }
          });
          if (f.derive_from && b._input) {
            // filled from other fields on the page (item 9 from the programme
            // name and specialisation) until the department types its own
            const read = ref => { const [sec, name] = ref.split("."); return String(((state[sec] || {})[name]) || "").trim(); };
            const make = () => f.derive_from.map(read).filter(Boolean).join(" — ");
            const example = f.placeholder || "";
            // worked out from the programme, shown as the placeholder; a value
            // that is just the worked-out text is cleared back to placeholder
            const cur0 = String(state[section.key][f.name] || "").trim();
            if (!CTX.readonly && cur0 && cur0 === make()) { state[section.key][f.name] = ""; b._input.value = ""; }
            refreshers.push(() => {
              b._input.placeholder = make() || example;
            });
          }
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
          made.push([f, b]);
        });
        block.appendChild(grid);
        if (section.display === "accordion") accordion(section, grid, made);
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

  /** Placeholder issue lines while the checks run. */
  function checksLoading() {
    showChecks();
    issuesBox.textContent = "";
    const wrap = el("div");
    wrap.setAttribute("aria-busy", "true");
    ["w-90", "w-70", "w-90", "w-50"].forEach(w => {
      const row = el("div", "sk-row");
      row.style.margin = "10px 0";
      row.appendChild(el("span", "sk sk-dot"));
      row.lastChild.style.cssText = "width:10px;height:10px;border-radius:50%";
      const g = el("div", "sk-grow");
      g.appendChild(el("span", "sk sk-line " + w));
      row.appendChild(g);
      wrap.appendChild(row);
    });
    issuesBox.appendChild(wrap);
  }

  function check(cb) {
    const btn = document.getElementById("btn-check");
    if (btn) { btn.disabled = true; btn.textContent = "Checking…"; }
    checksLoading();
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

  /* Submitting is two steps. First the checks run; if anything must be
     fixed, it is listed as before. If all is well, the review opens:
     everything entered, files as links (open, or remove), a Change link per
     section, and a confirmation to tick — once submitted the stage is
     locked until the Office sends it back. After it goes through, the same
     review can be downloaded as a copy. */
  const SUBMIT_LABEL = (document.getElementById("btn-submit") || {}).textContent || "Submit";
  function submitLabel(btn, text) {
    btn.disabled = false;
    btn.textContent = text || SUBMIT_LABEL.trim();
  }

  function submit() {
    const btn = document.getElementById("btn-submit");
    btn.disabled = true;
    btn.innerHTML = '<span class="loader-one is-light" aria-hidden="true"><i></i><i></i><i></i></span>Checking…';
    save();
    fetch(CTX.urls.validate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      const errs = (j.issues || []).filter(i => i.level === "error");
      if (!j.ok || errs.length) { notSubmitted(btn, j); return; }
      paintIssues(j.issues || [], j.summary || { errors: 0, warnings: 0 });
      // only the step that completes the record is reviewed first
      if (CTX.final) { submitLabel(btn); openReview(j.issues || []); }
      else submitAndGo(btn);
    }).catch(() => unreachable(btn));
  }

  /* An intermediate stage: submitted as soon as the checks pass, then on
     to the next one. */
  function submitAndGo(btn) {
    btn.innerHTML = '<span class="loader-one is-light" aria-hidden="true"><i></i><i></i><i></i></span>Submitting…';
    fetch(CTX.urls.submit, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      if (!j.ok) { notSubmitted(btn, j); return; }
      dirty = false;
      btn.textContent = "Submitted ✓";
      window.location = j.redirect || CTX.urls.dashboard;
    }).catch(() => unreachable(btn));
  }

  function recordBlock() {
    const box = el("section", "rv-sec rv-record");
    const h = el("div", "rv-sec-head");
    h.appendChild(el("h4", null, "Your whole record"));
    box.appendChild(h);
    const ul = el("ul", "rv-record-list");
    (CTX.record || []).forEach(r => {
      const li = el("li", "is-" + r.status);
      li.appendChild(el("span", "rv-rec-dot", r.status === "submitted" ? "✓" : r.status === "now" ? "→" : "!"));
      li.appendChild(el("span", "rv-rec-title", r.title));
      li.appendChild(el("span", "rv-rec-at", r.status === "now" ? "this one — below" : r.status === "submitted" ? (r.at ? "submitted " + r.at : "submitted") : r.status));
      ul.appendChild(li);
    });
    box.appendChild(ul);
    return box;
  }

  function notSubmitted(btn, j) {
    paintIssues(j.issues || [], j.summary || { errors: 0, warnings: 0 });
    submitLabel(btn);
    saveNote.textContent = "Not submitted — there are answers still to fix";
    saveNote.className = "save-note save-note-bad";
    alertIssues(j.issues || [], j.summary || {}, j.error);
    const first = (j.issues || []).find(i => i.level === "error");
    if (first) focusIssue(first);
    else issuesBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function unreachable(btn) {
    submitLabel(btn);
    saveNote.textContent = "Could not reach the server — nothing was submitted. Try again in a moment.";
    saveNote.className = "save-note save-note-bad";
    if (window.Toast) window.Toast.error("Could not reach the server — nothing was submitted. Try again in a moment.",
                                         { title: "Not submitted" });
  }

  function reviewTitle() {
    return (CTX.programme_name ? CTX.programme_name + " · " : "") + (CTX.title || STAGE.title || "This stage");
  }

  function removeAt(path) {
    // path: [section, field] or [section, field, i] or [section, row, column] …
    let node = state;
    for (let i = 0; i < path.length - 1; i++) {
      if (node == null) return;
      node = node[path[i]];
    }
    const last = path[path.length - 1];
    if (Array.isArray(node) && typeof last === "number") node.splice(last, 1);
    else if (node) node[last] = "";
    render();
    refresh();
    dirty = true;
    save();
  }

  function statsBar(st, warnings) {
    const bar = el("div", "rv-stats");
    const ring = el("div", "rv-ring");
    ring.style.setProperty("--p", st.percent);
    ring.appendChild(el("strong", null, st.percent + "%"));
    bar.appendChild(ring);
    const words = el("div", "rv-stats-words");
    words.appendChild(el("strong", null, `${st.filled} of ${st.total} filled`));
    words.appendChild(el("span", null, st.missing.length
      ? "Empty: " + st.missing.slice(0, 4).join(", ") + (st.missing.length > 4 ? "…" : "")
      : "Everything asked for is filled in."));
    if (warnings) words.appendChild(el("span", "rv-warn", `${warnings} thing${warnings === 1 ? "" : "s"} to double-check — see the Checks panel.`));
    bar.appendChild(words);
    return bar;
  }

  function openReview(issues) {
    const warnings = (issues || []).filter(i => i.level !== "error").length;
    let ctl = null;
    const draw = () => { const wrap = el("div"); if (CTX.final && (CTX.record || []).length) wrap.appendChild(recordBlock());
      wrap.appendChild(Review.build(STAGE, state, {
      viewFile: v => openViewer(v),
      removeFile: path => {
        if (!window.confirm("Remove this file? You will need to upload it again to submit.")) return;
        removeAt(path);
        ctl.body.textContent = "";
        ctl.body.appendChild(draw());
        ctl.panel.querySelector(".rv-stats").replaceWith(statsBar(Review.stats(STAGE, state), warnings));
      },
      edit: key => {
        ctl.close();
        const sec = document.getElementById("sec-" + key);
        if (sec) { sec.scrollIntoView({ behavior: "smooth", block: "start" }); sec.classList.add("is-flash"); setTimeout(() => sec.classList.remove("is-flash"), 1600); }
      }
    })); return wrap; };

    const foot = el("div", "rv-foot-in");
    const terms = el("label", "rv-terms");
    const tick = el("input");
    tick.type = "checkbox";
    terms.appendChild(tick);
    terms.appendChild(el("span", null,
      "I have checked everything above. I understand that once submitted, the whole Board of Studies " +
      "record goes to the Office of Academics and is locked — only the Office can send a part back for correction."));
    foot.appendChild(terms);
    const row = el("div", "rv-actions");
    const copy = el("button", "btn btn-ghost", "Download a copy");
    copy.type = "button";
    const backBtn = el("button", "btn btn-ghost", "Back to editing");
    backBtn.type = "button";
    const go = el("button", "btn btn-gold", "Submit now");
    go.type = "button";
    go.disabled = true;
    row.appendChild(copy);
    row.appendChild(el("span", "spacer"));
    row.appendChild(backBtn);
    row.appendChild(go);
    foot.appendChild(row);
    tick.addEventListener("change", () => { go.disabled = !tick.checked; });

    ctl = Review.modal({
      title: "Final submission — review everything",
      sub: reviewTitle() + " — " + CTX.dept_name,
      top: statsBar(Review.stats(STAGE, state), warnings),
      body: draw(),
      foot
    });
    copy.addEventListener("click", () => Review.print(reviewTitle(), CTX.dept_name + " · copy before submitting", ctl.body.firstChild));
    backBtn.addEventListener("click", () => ctl.close());
    go.addEventListener("click", () => reallySubmit(ctl, go));
  }

  function reallySubmit(ctl, go) {
    const btn = document.getElementById("btn-submit");
    go.disabled = true;
    go.innerHTML = '<span class="loader-one is-light" aria-hidden="true"><i></i><i></i><i></i></span>Submitting…';
    save();
    fetch(CTX.urls.submit, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    }).then(r => r.json()).then(j => {
      if (j.ok) {
        dirty = false;
        btn.disabled = true;
        btn.textContent = "Submitted";
        const reviewed = ctl.body.firstChild;
        // the review becomes the receipt: the copy to keep, then onward
        ctl.panel.querySelector(".rv-head h3").textContent = "Submitted";
        ctl.panel.querySelector(".rv-sub").textContent = reviewTitle() + " — " + CTX.dept_name + " · " + new Date().toLocaleString();
        ctl.panel.querySelectorAll(".rv-edit, .rv-file-rm").forEach(b => b.remove());
        ctl.panel.querySelectorAll(".rv-record-list li.is-now").forEach(li => {
          li.className = "is-submitted";
          li.querySelector(".rv-rec-dot").textContent = "✓";
          li.querySelector(".rv-rec-at").textContent = "submitted now";
        });
        const done = el("div", "rv-done");
        done.appendChild(el("span", "rv-done-tick", "✓"));
        const w = el("div");
        w.appendChild(el("strong", null, "Submitted to the Office of Academics."));
        w.appendChild(el("span", null, j.next ? `Next: ${j.next.title}. Keep a copy of what you sent first.` : "Keep a copy of what you sent."));
        done.appendChild(w);
        ctl.panel.querySelector(".rv-stats").replaceWith(done);
        const foot = ctl.panel.querySelector(".rv-foot");
        foot.textContent = "";
        const row = el("div", "rv-actions");
        const copy = el("button", "btn btn-ghost", "Download a copy");
        copy.type = "button";
        copy.addEventListener("click", () => Review.print(reviewTitle(), CTX.dept_name + " · submitted " + new Date().toLocaleString(), reviewed));
        const on = el("a", "btn btn-gold", j.next ? "Continue to " + j.next.title : "Done");
        on.href = j.redirect || CTX.urls.dashboard;
        row.appendChild(copy);
        row.appendChild(el("span", "spacer"));
        row.appendChild(on);
        foot.appendChild(row);
        return;
      }
      ctl.close();
      notSubmitted(btn, j);
    }).catch(() => { ctl.close(); unreachable(btn); });
  }

  /* A submission that did not go through: one alert saying so, then one per
     problem (the first few), each taking you to its field when clicked. */
  function alertIssues(issues, summary, error) {
    if (!window.Toast) return;
    const errs = issues.filter(i => i.level === "error");
    const warns = issues.filter(i => i.level !== "error");
    if (!errs.length && error) { window.Toast.error(error, { title: "Not submitted" }); return; }
    window.Toast.error(
      `${errs.length} thing${errs.length === 1 ? "" : "s"} to fix` +
      (warns.length ? ` and ${warns.length} to check` : "") + " — the list is in the Checks panel.",
      { title: "Not submitted" });
    errs.slice(0, 3).forEach(i => window.Toast.error(i.message, { onClick: () => focusIssue(i), timeout: 11000 }));
    if (errs.length > 3) window.Toast.info(`…and ${errs.length - 3} more in the Checks panel.`);
  }

  // ------------------------------------------------------------------- boot

  render();
  refresh();

  if (!CTX.readonly) {
    document.getElementById("btn-submit").addEventListener("click", submit);
    const sampleBtn = document.getElementById("btn-sample");
    if (sampleBtn) sampleBtn.addEventListener("click", () => {
      sampleBtn.disabled = true;
      fetch(CTX.urls.sample, { method: "POST" }).then(r => r.json()).then(j => {
        sampleBtn.disabled = false;
        if (!j.ok) return;
        Object.keys(state).forEach(k => delete state[k]);
        Object.assign(state, j.data);
        render();
        refresh();
        dirty = true;
        save();
        if (window.Toast) window.Toast.success("Every box is filled with sample data. Press Submit to review it.", { title: "Filled" });
      }).catch(() => { sampleBtn.disabled = false; });
    });
    window.addEventListener("beforeunload", (e) => {
      if (dirty) { e.preventDefault(); e.returnValue = ""; }
    });
    setInterval(() => { if (dirty) save(); }, 25000);
  } else {
    check();
    const show = () => Review.build(STAGE, state, { viewFile: v => openViewer(v) });
    const rv = document.getElementById("btn-review");
    if (rv) rv.addEventListener("click", () => {
      Review.modal({ title: "What was submitted", sub: reviewTitle() + " — " + CTX.dept_name +
                     (CTX.submitted_at ? " · submitted " + CTX.submitted_at : ""),
                     top: statsBar(Review.stats(STAGE, state), 0), body: show() });
    });
    const cp = document.getElementById("btn-copy");
    if (cp) cp.addEventListener("click", () => Review.print(reviewTitle(),
      CTX.dept_name + (CTX.submitted_at ? " · submitted " + CTX.submitted_at : ""), show()));
  }
})();

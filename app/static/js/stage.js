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
          note.textContent = `Uploaded: ${j.name} (${Math.round(j.size / 1024)} KB)`;
          note.className = "help upload-note is-ok";
          onChange({ name: j.name, stored: j.stored, size: j.size, url: j.url });
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

  // ---------------------------------------------------------- repeating table

  function renderTable(section, host) {
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
    if (!section.fixed_rows && !CTX.readonly) {
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
    if (!section.fixed_rows && !CTX.readonly) {
      const add = el("button", "btn btn-ghost btn-sm", "+ Add row");
      add.type = "button";
      add.addEventListener("click", () => { rows(section.key).push({}); draw(); touch(); });
      foot.appendChild(add);
    }
    foot.appendChild(count);
    foot.appendChild(rowNote);
    host.appendChild(foot);

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
          const input = makeInput(c, row[c.name], (v) => { row[c.name] = v; touch(); });
          if (c.width) input.style.minWidth = c.width;
          if (c.type === "readonly") input.readOnly = true;
          holder.appendChild(input);
          attachLiveCheck(input, c, holder);
          td.appendChild(holder);
          tr.appendChild(td);
        });

        if (!section.fixed_rows && !CTX.readonly) {
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
      });
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
          tally();
          touch();
        });
        if (CTX.readonly) input.disabled = true;
        inputs[r.key] = input;
        td.appendChild(input);
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
      const tr = block.querySelector(`tr[data-row="${iss.row}"]`);
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

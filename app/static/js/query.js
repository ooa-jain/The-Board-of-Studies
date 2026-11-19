/* The department's menu: Query and Report a bug.

   Query: the sections of the Help walkthrough; a click opens the video at
   that section. Report a bug: what went wrong and where, with a screenshot,
   sent to the Office of Academic Affairs as a ticket (B-0001 …). */
(function () {
  var dlg = document.getElementById("query-dialog");
  var qBtn = document.getElementById("query-btn");
  var bBtn = document.getElementById("bug-btn");
  if (!dlg || !window.fetch) return;
  var body = dlg.querySelector(".qd-body");
  var title = dlg.querySelector(".qd-title");
  var back = dlg.querySelector(".qd-back");
  if (back) back.hidden = true;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function show() { if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", ""); }
  function close() { if (typeof dlg.close === "function") dlg.close(); else dlg.removeAttribute("open"); }
  function step(heading) { title.textContent = heading; body.textContent = ""; }

  // ---- Query: the Help video, section by section
  function sections() {
    step("Query — which section?");
    var note = el("p", "qd-note", "Loading the sections…");
    body.appendChild(note);
    fetch(qBtn.dataset.sectionsUrl, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        note.textContent = "Choose a section — the video opens where it shows how it is done.";
        var list = el("ol", "qd-sections");
        (d.sections || []).forEach(function (s) {
          var li = el("li");
          var a = el("a", "qd-section");
          a.href = s.url;
          a.appendChild(el("span", "qd-n", String(s.n)));
          var t = el("span", "qd-t");
          t.appendChild(el("strong", null, s.title));
          if (s.sub) t.appendChild(el("small", null, s.sub));
          a.appendChild(t);
          a.addEventListener("click", close);
          li.appendChild(a);
          list.appendChild(li);
        });
        if (!(d.sections || []).length) {
          var a = el("a", "btn btn-sm", "Open Help");
          a.href = d.help_url;
          body.appendChild(a);
        }
        body.appendChild(list);
      })
      .catch(function () { note.textContent = "Could not load the sections. Open Help from the menu."; });
  }

  // ---- Report a bug
  var PLACES = ["Home", "Department Information", "Pre-BoS", "BoS Documents", "Curriculum",
                "Syllabus", "Course Revision", "Earlier batches", "Review & submit", "Reports",
                "Version History", "Help", "Somewhere else"];
  function here() {
    var p = location.pathname;
    if (/prog_syllabus_b\d/.test(p)) return "Earlier batches";
    if (/prog_syllabus/.test(p)) return "Syllabus";
    if (/prog_revision/.test(p)) return "Course Revision";
    if (/prog_curriculum|\/curriculum/.test(p)) return "Curriculum";
    if (/dept_info/.test(p)) return "Department Information";
    if (/pre_bos/.test(p)) return "Pre-BoS";
    if (/bos_documents/.test(p)) return "BoS Documents";
    if (/reports|report/.test(p)) return "Reports";
    if (/versions/.test(p)) return "Version History";
    if (/help/.test(p)) return "Help";
    if (/review=1/.test(location.search)) return "Review & submit";
    return "Home";
  }
  function field(label, input, hint) {
    var f = el("label", "qd-field");
    f.appendChild(el("span", null, label));
    f.appendChild(input);
    if (hint) f.appendChild(el("small", null, hint));
    return f;
  }
  function bugForm() {
    step("Report a bug");
    var form = el("form", "qd-form");
    form.appendChild(el("p", "qd-note", "Tell the Office of Academic Affairs what went wrong. A screenshot is needed."));
    var name = el("input");
    name.type = "text"; name.maxLength = 150; name.required = true;
    name.placeholder = "e.g. Credits do not add up in Semester 3";
    form.appendChild(field("Bug name", name));

    var email = el("input");
    email.type = "email"; email.maxLength = 120; email.required = true;
    email.value = bBtn.dataset.email || "";
    if (email.value) { email.readOnly = true; email.className = "is-auto"; }
    form.appendChild(field("Your e-mail", email, email.value ? "From your sign-in — the reply comes here." : ""));

    var where = el("select");
    PLACES.forEach(function (p) { where.appendChild(new Option(p, p)); });
    where.value = here();
    form.appendChild(field("Where is the bug?", where));

    var what = el("textarea");
    what.rows = 4; what.maxLength = 3000; what.required = true;
    what.placeholder = "What did you do, and what went wrong?";
    form.appendChild(field("What is the issue?", what));

    var shot = el("input");
    shot.type = "file"; shot.accept = "image/png,image/jpeg,image/webp"; shot.required = true;
    form.appendChild(field("Screenshot", shot, "Required — a picture of the screen (PNG or JPG, up to 5 MB)."));

    var err = el("p", "qd-err");
    err.hidden = true;
    var send = el("button", "btn qd-send", "Submit");
    send.type = "submit";
    form.appendChild(err);
    form.appendChild(send);
    body.appendChild(form);
    name.focus();

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var problem = !name.value.trim() ? "Give the bug a name." :
        !email.value.trim() ? "Give your e-mail." :
        what.value.trim().length < 5 ? "Say what the issue is." :
        !shot.files.length ? "Add a screenshot — it is required." :
        shot.files[0].size > 5 * 1024 * 1024 ? "The screenshot is over 5 MB." : "";
      if (problem) { err.textContent = problem; err.hidden = false; return; }
      var fd = new FormData();
      fd.append("title", name.value);
      fd.append("email", email.value);
      fd.append("where", where.value);
      fd.append("text", what.value);
      fd.append("page", location.pathname + location.search);
      fd.append("screenshot", shot.files[0]);
      send.disabled = true; send.textContent = "Sending…"; err.hidden = true;
      fetch(bBtn.dataset.bugUrl, { method: "POST", credentials: "same-origin", body: fd })
        .then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (d) {
          if (!d.ok) throw new Error(d.error || "Could not send the report. Please try again.");
          step("Bug reported");
          var ok = el("div", "qd-done");
          ok.appendChild(el("strong", "qd-ticket", d.ticket));
          ok.appendChild(el("p", null, "Thank you — the Office of Academic Affairs has your report. Keep this number for reference."));
          var c = el("button", "btn btn-sm", "Close");
          c.type = "button";
          c.addEventListener("click", close);
          ok.appendChild(c);
          body.appendChild(ok);
        })
        .catch(function (x) { err.textContent = x.message; err.hidden = false; send.disabled = false; send.textContent = "Submit"; });
    });
  }

  if (qBtn) qBtn.addEventListener("click", function () { sections(); show(); });
  if (bBtn) bBtn.addEventListener("click", function () { bugForm(); show(); });
  dlg.querySelector(".qd-close").addEventListener("click", close);
  dlg.addEventListener("click", function (e) { if (e.target === dlg) close(); });
})();

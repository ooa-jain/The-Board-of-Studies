/* The Query button on the right of every department page.

   Technical: the sections of the Help walkthrough; a click opens the video
   at that section. Academics: a short form, raised as a ticket for the
   Office of Academic Affairs. */
(function () {
  var btn = document.getElementById("query-btn");
  var dlg = document.getElementById("query-dialog");
  if (!btn || !dlg || !window.fetch) return;
  var body = dlg.querySelector(".qd-body");
  var title = dlg.querySelector(".qd-title");
  var back = dlg.querySelector(".qd-back");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function show() {
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
  }
  function close() {
    if (typeof dlg.close === "function") dlg.close(); else dlg.removeAttribute("open");
  }

  function step(name, heading) {
    title.textContent = heading;
    back.hidden = name === "start";
    body.textContent = "";
  }

  function start() {
    step("start", "What is your query about?");
    var grid = el("div", "qd-choices");
    [["technical", "Technical", "How to use the portal — see the help video for any section"],
     ["academics", "Academics", "A question for the Office of Academic Affairs — raised as a ticket"]]
      .forEach(function (c) {
        var b = el("button", "qd-choice");
        b.type = "button";
        b.appendChild(el("strong", null, c[1]));
        b.appendChild(el("span", null, c[2]));
        b.addEventListener("click", c[0] === "technical" ? technical : academics);
        grid.appendChild(b);
      });
    body.appendChild(grid);
    grid.querySelector("button").focus();
  }

  function technical() {
    step("technical", "Technical — which section?");
    var note = el("p", "qd-note", "Loading the sections…");
    body.appendChild(note);
    fetch(btn.dataset.sectionsUrl, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        note.textContent = "Choose a section to watch how it is done.";
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
          // already on Help: jump without reloading
          a.addEventListener("click", function () { close(); });
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

  function academics() {
    step("academics", "Academics — ask the Office");
    var form = el("form", "qd-form");
    form.appendChild(el("p", "qd-note",
      "Your question goes to the Office of Academic Affairs as a ticket."));
    var l1 = el("label", null, "Subject");
    var subj = el("input");
    subj.type = "text"; subj.maxLength = 150; subj.placeholder = "e.g. Credits for the minor stream";
    l1.appendChild(subj);
    var l2 = el("label", null, "Your question");
    var text = el("textarea");
    text.rows = 5; text.maxLength = 3000; text.required = true;
    l2.appendChild(text);
    var err = el("p", "qd-err");
    err.hidden = true;
    var send = el("button", "btn qd-send", "Raise ticket");
    send.type = "submit";
    form.appendChild(l1); form.appendChild(l2); form.appendChild(err); form.appendChild(send);
    body.appendChild(form);
    subj.focus();
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (text.value.trim().length < 5) { err.textContent = "Please write your question."; err.hidden = false; text.focus(); return; }
      send.disabled = true; send.textContent = "Sending…";
      fetch(btn.dataset.raiseUrl, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
        body: JSON.stringify({ subject: subj.value, text: text.value, page: location.pathname })
      }).then(function (r) { return r.json().catch(function () { return {}; }); })
        .then(function (d) {
          if (!d.ok) throw new Error(d.error || "Could not raise the ticket. Please try again.");
          step("done", "Ticket raised");
          var ok = el("div", "qd-done");
          ok.appendChild(el("strong", "qd-ticket", d.ticket));
          ok.appendChild(el("p", null, "Your query is with the Office of Academic Affairs. Keep this ticket number for reference."));
          var c = el("button", "btn btn-sm", "Close");
          c.type = "button";
          c.addEventListener("click", close);
          ok.appendChild(c);
          body.appendChild(ok);
          back.hidden = true;
        })
        .catch(function (x) {
          err.textContent = x.message; err.hidden = false;
          send.disabled = false; send.textContent = "Raise ticket";
        });
    });
  }

  btn.addEventListener("click", function () { start(); show(); });
  back.addEventListener("click", start);
  dlg.querySelector(".qd-close").addEventListener("click", close);
  dlg.addEventListener("click", function (e) { if (e.target === dlg) close(); });
})();

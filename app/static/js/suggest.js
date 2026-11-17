/* Word suggestions for names and titles: type a short form ("CS", "comm",
   "AI") or the start of a word ("cyb") in a programme name, a course title,
   a specialisation… and a list drops down — Computer Science, Cyber
   Security, Commerce… — to pick from with a click, Enter or Tab. Titles the
   department has already used are offered too, whole. One listener for the
   page, so boxes added later (a new row, a new course) get it as well. */
(function () {
  "use strict";

  // short forms and what they stand for, most likely first
  var ABBR = {
    cs: ["Computer Science", "Cyber Security", "Computer Systems"],
    cse: ["Computer Science and Engineering"], ise: ["Information Science and Engineering"],
    ca: ["Computer Applications", "Chartered Accountancy"],
    it: ["Information Technology", "Income Tax"],
    ai: ["Artificial Intelligence"], ml: ["Machine Learning"], aiml: ["Artificial Intelligence and Machine Learning"],
    ds: ["Data Science", "Data Structures"], da: ["Data Analytics"], dsa: ["Data Structures and Algorithms"],
    daa: ["Design and Analysis of Algorithms"], dbms: ["Database Management Systems"], db: ["Database"],
    os: ["Operating Systems"], cn: ["Computer Networks"], se: ["Software Engineering"],
    oop: ["Object Oriented Programming"], oops: ["Object Oriented Programming"],
    iot: ["Internet of Things"], ar: ["Augmented Reality"], vr: ["Virtual Reality"], arvr: ["Augmented and Virtual Reality"],
    ui: ["User Interface"], ux: ["User Experience"], uiux: ["UI/UX Design"], hci: ["Human Computer Interaction"],
    nlp: ["Natural Language Processing"], dl: ["Deep Learning"], cv: ["Computer Vision"],
    genai: ["Generative AI", "Generative Artificial Intelligence"], gen: ["Generative", "General"],
    bda: ["Big Data Analytics"], cc: ["Cloud Computing"], fsd: ["Full Stack Development"],
    toc: ["Theory of Computation"], cd: ["Compiler Design"], coa: ["Computer Organization and Architecture"],
    de: ["Digital Electronics"], dm: ["Discrete Mathematics", "Digital Marketing"], dip: ["Digital Image Processing"],
    evs: ["Environmental Studies"], cyber: ["Cyber Security"], cloud: ["Cloud Computing"], blockchain: ["Blockchain Technology"],
    comm: ["Commerce", "Communication", "Communication Skills"], com: ["Commerce", "Communication"],
    mgmt: ["Management"], mgt: ["Management"], mgmnt: ["Management"],
    hr: ["Human Resources"], hrm: ["Human Resource Management"], hrd: ["Human Resource Development"],
    fin: ["Finance", "Financial"], fm: ["Financial Management"], sm: ["Strategic Management"],
    acc: ["Accounting", "Accountancy"], acct: ["Accounting"], accts: ["Accounts"],
    eco: ["Economics"], econ: ["Economics"], bus: ["Business"], biz: ["Business"],
    ba: ["Business Analytics", "Business Administration", "Bachelor of Arts"],
    mktg: ["Marketing"], mkt: ["Marketing"], ob: ["Organisational Behaviour"], ib: ["International Business"],
    scm: ["Supply Chain Management"], lscm: ["Logistics and Supply Chain Management"],
    qt: ["Quantitative Techniques"], rm: ["Research Methodology"], bs: ["Business Statistics"],
    gst: ["Goods and Services Tax"], acca: ["ACCA"], cma: ["Cost and Management Accounting"],
    eng: ["English", "Engineering"], lit: ["Literature"], psy: ["Psychology"], psych: ["Psychology"],
    soc: ["Sociology"], pol: ["Political Science"], polsci: ["Political Science"], hist: ["History"],
    math: ["Mathematics"], maths: ["Mathematics"], stats: ["Statistics"], stat: ["Statistics"],
    phy: ["Physics"], chem: ["Chemistry"], bio: ["Biology", "Biotechnology"], biotech: ["Biotechnology"],
    micro: ["Microbiology", "Microeconomics"], macro: ["Macroeconomics"], env: ["Environmental Science"],
    jmc: ["Journalism and Mass Communication"], mc: ["Mass Communication"], pr: ["Public Relations"],
    fd: ["Fashion Design"], id: ["Interior Design"], vfx: ["Visual Effects"],
    ece: ["Electronics and Communication Engineering"], eee: ["Electrical and Electronics Engineering"],
    mech: ["Mechanical Engineering"], civil: ["Civil Engineering"], aero: ["Aerospace Engineering"],
    bca: ["Bachelor of Computer Applications"], mca: ["Master of Computer Applications"],
    bba: ["Bachelor of Business Administration"], mba: ["Master of Business Administration"],
    bcom: ["Bachelor of Commerce"], mcom: ["Master of Commerce"], bsc: ["Bachelor of Science"], msc: ["Master of Science"],
    btech: ["Bachelor of Technology"], mtech: ["Master of Technology"], ma: ["Master of Arts"], phd: ["Doctor of Philosophy"],
    hons: ["Honours"], res: ["Research"], spl: ["Specialisation"], spec: ["Specialisation"],
    apps: ["Applications"], app: ["Applications", "Applied"], adv: ["Advanced"], intro: ["Introduction to"],
    fund: ["Fundamentals of"], prog: ["Programming"], dev: ["Development"], sec: ["Security"],
    net: ["Networks", "Networking"], ent: ["Entrepreneurship"], edu: ["Education"], proj: ["Project"],
    lab: ["Laboratory"], intern: ["Internship"], tech: ["Technology"], sys: ["Systems"], info: ["Information"],
    mgr: ["Managerial"], prof: ["Professional"], comp: ["Computer", "Computing"], sci: ["Science"]
  };

  // words and phrases that titles in a university are made of
  var WORDS = ("Accounting|Accountancy|Advanced|Agile|Algorithms|Analysis|Analytics|Animation|Applications|Applied|" +
    "Architecture|Artificial Intelligence|Auditing|Augmented Reality|Automation|Banking|Behaviour|Big Data|Biology|" +
    "Biotechnology|Blockchain|Business|Business Analytics|Business Communication|Business Law|Business Statistics|" +
    "Calculus|Capstone Project|Chemistry|Cloud Computing|Commerce|Communication|Communication Skills|Compiler Design|" +
    "Computer|Computer Applications|Computer Networks|Computer Science|Computer Vision|Computing|Corporate|" +
    "Corporate Accounting|Corporate Finance|Cost Accounting|Cryptography|Cyber Security|Cybersecurity|Data|" +
    "Data Analytics|Data Mining|Data Science|Data Structures|Data Visualisation|Database|Database Management Systems|" +
    "Deep Learning|Design|Design Thinking|Development|DevOps|Digital|Digital Marketing|Discrete Mathematics|Economics|" +
    "Education|Electronics|Elective|Engineering|English|Entrepreneurship|Environmental Studies|Ethics|Ethical Hacking|" +
    "Finance|Financial|Financial Accounting|Financial Management|Financial Markets|Forensics|Foundations|Full Stack Development|" +
    "Fundamentals|Generative AI|Governance|Graphics|Healthcare|Honours|Honours with Research|Human Resource Management|" +
    "Human Computer Interaction|Indian Knowledge System|Information|Information Security|Information Technology|" +
    "Infrastructure|Innovation|Insurance|Intelligence|International Business|Internet of Things|Internship|Introduction to|" +
    "Investment|Java Programming|Laboratory|Language|Law|Leadership|Learning|Linear Algebra|Logistics|Machine Learning|" +
    "Management|Managerial Economics|Marketing|Mathematics|Mathematical Foundation|Microprocessors|Mobile Application Development|" +
    "Modelling|Natural Language Processing|Network Security|Networks|Object Oriented Programming|Operating Systems|" +
    "Operations|Operations Research|Optimisation|Organisational Behaviour|Penetration Testing|Physics|Principles of|" +
    "Probability|Problem Solving|Professional|Programming|Project|Project Management|Psychology|Python Programming|" +
    "Quantitative Techniques|Research|Research Methodology|Research Project|Retail|Risk Management|Robotics|Security|" +
    "Seminar|Skill Enhancement|Social|Software|Software Engineering|Software Testing|Sociology|Statistics|" +
    "Strategic Management|Supply Chain Management|Systems|Taxation|Technology|Testing|Theory of Computation|" +
    "Universal Human Values|Value Added Course|Virtual Reality|Web Development|Web Technologies").split("|");

  var phrases = [];        // whole titles this department has already used
  function addPhrases(list) {
    var seen = {};
    phrases.forEach(function (p) { seen[p.toLowerCase()] = 1; });
    (list || []).forEach(function (p) {
      p = String(p || "").replace(/\s+/g, " ").trim();
      if (p.length > 3 && p.length < 200 && !seen[p.toLowerCase()]) { seen[p.toLowerCase()] = 1; phrases.push(p); }
    });
  }
  var loaded = false;      // the page's own titles, read on first use

  // which boxes get suggestions: names and titles, never codes, e-mails or dates
  var WANT = /title|programme_name|program_name|specialisation|specialization|course_name|elective|stream|subject|minor|bucket/i;
  var NEVER = /code|e-?mail|phone|url|date|year|marks|credit|hours|person|member|username|password/i;
  function eligible(el) {
    if (!el || el.tagName !== "INPUT" || (el.type && el.type !== "text" && el.type !== "search")) return false;
    if (el.readOnly || el.disabled) return false;
    if (el.dataset.suggest === "off") return false;
    if (el.dataset.suggest) return true;
    var host = el.closest("[data-field]");
    var key = (host && host.dataset.field) || el.name || el.id || "";
    return WANT.test(key) && !NEVER.test(key);
  }

  // ---- the list ----
  var pop = null, items = [], active = -1, target = null, quiet = false;
  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.className = "sg-pop";
    pop.setAttribute("role", "listbox");
    pop.hidden = true;
    document.body.appendChild(pop);
    // pointerdown, not click: keep the focus in the box
    pop.addEventListener("pointerdown", function (e) {
      var li = e.target.closest(".sg-item");
      if (!li) return;
      e.preventDefault();
      accept(Number(li.dataset.i));
    });
    return pop;
  }
  function close() { if (pop) pop.hidden = true; items = []; active = -1; }

  function tokenOf(el) {
    var upto = el.value.slice(0, el.selectionStart == null ? el.value.length : el.selectionStart);
    var m = upto.match(/([A-Za-z][A-Za-z&.]*)$/);
    return m ? { word: m[1], start: upto.length - m[1].length, end: upto.length } : null;
  }

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function candidates(el) {
    if (!loaded) { loaded = true; addPhrases(window.SUGGEST_PHRASES); }
    var out = [], seen = {};
    function push(label, mode, hint) {
      var k = label.toLowerCase();
      if (seen[k] || out.length >= 8) return;
      seen[k] = 1;
      out.push({ label: label, mode: mode, hint: hint });
    }
    var value = el.value.trim();
    var tok = tokenOf(el);
    var w = tok ? tok.word.replace(/\./g, "").toLowerCase() : "";
    // 1. a short form: CS -> Computer Science, Cyber Security
    if (w && ABBR[w]) ABBR[w].forEach(function (x) { if (x.toLowerCase() !== w) push(x, "word", "short form"); });
    // 2. a title already used, whole
    if (value.length >= 3) {
      var v = value.toLowerCase(), starts = [], has = [];
      phrases.forEach(function (p) {
        var l = p.toLowerCase();
        if (l === v) return;
        if (l.indexOf(v) === 0) starts.push(p); else if (l.indexOf(v) > 0) has.push(p);
      });
      starts.concat(has).slice(0, 4).forEach(function (p) { push(p, "all", "existing title"); });
    }
    // 3. the rest of a word: cyb -> Cyber Security
    if (w.length >= 2) {
      var hits = WORDS.filter(function (x) { var l = x.toLowerCase(); return l.indexOf(w) === 0 && l !== w; });
      hits.sort(function (a, b) { return a.length - b.length; });
      hits.forEach(function (x) { push(x, "word", ""); });
    }
    return out;
  }

  function render(el) {
    var list = candidates(el);
    if (!list.length) { close(); return; }
    ensurePop();
    items = list; active = -1;
    pop.textContent = "";
    var tok = tokenOf(el), w = tok ? tok.word.toLowerCase() : "", v = el.value.trim().toLowerCase();
    list.forEach(function (it, i) {
      var li = document.createElement("div");
      li.className = "sg-item";
      li.setAttribute("role", "option");
      li.dataset.i = i;
      var main = document.createElement("span");
      main.className = "sg-main";
      // the part already typed, plain; the rest, bold
      var needle = it.mode === "all" ? v : w, at = needle ? it.label.toLowerCase().indexOf(needle) : -1;
      if (at >= 0 && needle) {
        main.appendChild(document.createTextNode(it.label.slice(0, at)));
        var typed = document.createElement("span"); typed.className = "sg-typed";
        typed.textContent = it.label.slice(at, at + needle.length); main.appendChild(typed);
        var rest = document.createElement("b"); rest.textContent = it.label.slice(at + needle.length); main.appendChild(rest);
      } else {
        var b = document.createElement("b"); b.textContent = it.label; main.appendChild(b);
      }
      li.appendChild(main);
      if (it.hint) { var h = document.createElement("small"); h.textContent = it.hint; li.appendChild(h); }
      pop.appendChild(li);
    });
    place(el);
    pop.hidden = false;
  }

  function place(el) {
    var r = el.getBoundingClientRect();
    pop.style.minWidth = Math.max(220, r.width) + "px";
    pop.style.left = Math.max(8, Math.min(r.left, window.innerWidth - Math.max(220, r.width) - 8)) + "px";
    var below = window.innerHeight - r.bottom;
    if (below < 220 && r.top > below) { pop.style.top = ""; pop.style.bottom = (window.innerHeight - r.top + 4) + "px"; }
    else { pop.style.bottom = ""; pop.style.top = (r.bottom + 4) + "px"; }
  }

  function mark(i) {
    active = i;
    Array.prototype.forEach.call(pop.children, function (c, k) {
      c.classList.toggle("is-on", k === i);
      c.setAttribute("aria-selected", k === i ? "true" : "false");
    });
  }

  function accept(i) {
    var it = items[i], el = target;
    if (!it || !el) return;
    if (it.mode === "all") {
      el.value = it.label;
    } else {
      var tok = tokenOf(el);
      if (!tok) return;
      var before = el.value.slice(0, tok.start), after = el.value.slice(tok.end);
      // keep a capital where a title wants one
      var word = /^\s*$/.test(before) ? cap(it.label) : it.label;
      el.value = before + word + after;
      var caret = (before + word).length;
      try { el.setSelectionRange(caret, caret); } catch (e) { /* not a text box */ }
    }
    close();
    quiet = true;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    quiet = false;
  }

  document.addEventListener("input", function (e) {
    if (quiet || !eligible(e.target)) return;
    target = e.target;
    render(target);
  }, true);
  document.addEventListener("keydown", function (e) {
    if (!pop || pop.hidden || e.target !== target) return;
    if (e.key === "ArrowDown") { e.preventDefault(); mark((active + 1) % items.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); mark((active - 1 + items.length) % items.length); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); accept(active); }
    else if (e.key === "Tab" && items.length) { if (active < 0) active = 0; e.preventDefault(); accept(active); }
    else if (e.key === "Escape") { close(); }
  }, true);
  document.addEventListener("focusout", function (e) { if (e.target === target) setTimeout(close, 120); }, true);
  window.addEventListener("scroll", function () { if (pop && !pop.hidden && target) place(target); }, { passive: true, capture: true });
  window.addEventListener("resize", close);

  window.Suggest = { addPhrases: addPhrases, candidates: candidates, abbreviations: ABBR };
})();

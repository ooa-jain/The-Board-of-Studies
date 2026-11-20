/* The portal in the language picked in the profile menu.
   window.BOS_I18N (from /i18n/<code>.js) maps the English text of the page
   to its translation. Every piece of the portal's own text on the page is
   looked up as it appears, also what the forms draw later; a key with
   {name} in it fits text with anything in that place ("Semester {n}").
   Untouched: what people type (inputs, text areas), anything marked
   translate="no", and any text the map has not got, so names, codes and
   entered data stay as they are. */
(function () {
  var D = window.BOS_I18N || {};
  var pats = [];
  Object.keys(D).forEach(function (k) {
    if (k.indexOf("{") < 0) return;
    // {n} a number, {year} a year span, {code} one word, {name} anything
    var re = k.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\{(\w+)\}/g, function (_, n) {
      return { n: "(\\d+(?:\\.\\d+)?)", year: "(\\d{4}\\s?[–-]\\s?\\d{2,4})", code: "(\\S+)" }[n] || "(.+?)";
    });
    pats.push({ re: new RegExp("^" + re + "$"), to: D[k], fixed: k.replace(/\{\w+\}/g, "").length });
  });
  // the most particular first: "Submit {name} & go to {name} →" before "{name} →"
  pats.sort(function (a, b) { return b.fixed - a.fixed; });

  function look(core, depth) {
    if (Object.prototype.hasOwnProperty.call(D, core)) return D[core];
    if ((depth || 0) > 3) return null;
    for (var i = 0; i < pats.length; i++) {
      var m = pats[i].re.exec(core);
      if (m) {
        // the translation names the pieces by place, {1} {2} …, as word
        // order differs between languages ("3 of 8" is "8 में से 3")
        // each piece is looked up too ("Expand {name}": "Expand Summary")
        var got = m.slice(1).map(function (v) {
          if (v == null) return v;
          var t = look(v.trim(), (depth || 0) + 1);
          return t == null ? v : t;
        });
        var out = pats[i].to.replace(/\{(\d+)\}/g, function (all, k) { var v = got[+k - 1]; return v == null ? all : v; });
        return out;
      }
    }
    return null;
  }
  function tr(s) {
    if (!s || !/[A-Za-z]/.test(s)) return null;
    var core = s.replace(/\s+/g, " ").trim();
    var t = look(core);
    if (t == null) return null;
    var lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0];
    return (lead ? " " : "") + t + (trail ? " " : "");
  }
  window.bosT = function (s) { var t = tr(s); return t == null ? s : t.trim(); };

  var SKIP = "script,style,noscript,textarea,code,pre,[translate=no],[contenteditable=true]";
  var ATTRS = ["placeholder", "title", "aria-label"];
  function skip(el) { return !el || (el.closest && el.closest(SKIP)); }
  function doText(n) {
    if (skip(n.parentElement)) return;
    var t = tr(n.nodeValue);
    if (t != null && t !== n.nodeValue) n.nodeValue = t;
  }
  function doEl(el) {
    if (skip(el)) return;
    for (var i = 0; i < ATTRS.length; i++) {
      var v = el.getAttribute(ATTRS[i]);
      if (v) { var t = tr(v); if (t != null) el.setAttribute(ATTRS[i], t.trim()); }
    }
    if (el.tagName === "INPUT" && (el.type === "submit" || el.type === "button") && el.value) {
      var t2 = tr(el.value); if (t2 != null) el.value = t2.trim();
    }
  }
  function walk(root) {
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1 || skip(root)) return;
    doEl(root);
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doEl(n); }
  }
  // the browser's own boxes too
  ["alert", "confirm", "prompt"].forEach(function (f) {
    var orig = window[f];
    window[f] = function (msg) { var a = [].slice.call(arguments); a[0] = window.bosT(String(msg == null ? "" : msg)); return orig.apply(window, a); };
  });
  function start() {
    var t = tr(document.title); if (t != null) document.title = t.trim();
    walk(document.body);
    document.documentElement.classList.remove("i18n-wait");
    new MutationObserver(function (list) {
      list.forEach(function (m) {
        if (m.type === "characterData") doText(m.target);
        else if (m.type === "attributes") doEl(m.target);
        else m.addedNodes.forEach(walk);
      });
    }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  // never keep the page hidden for long, whatever happens
  setTimeout(function () { document.documentElement.classList.remove("i18n-wait"); }, 2500);
})();

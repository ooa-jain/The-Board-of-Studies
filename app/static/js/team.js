/* Settings › Team & access › Add a person / Edit access.

   A preset fills the section table; touching the table makes it Custom.
   Full admin hides the table and the departments (they see everything).
   The department list filters as you type; a whole school or campus marks
   the departments it already takes in. */
(function () {
  "use strict";
  const form = document.getElementById("tm-form");
  if (!form) return;
  const $$ = (sel, root) => Array.from((root || form).querySelectorAll(sel));
  const matrix = form.querySelector(".tm-matrix-wrap");
  const fullNote = form.querySelector(".tm-full-note");
  const scopeCard = form.querySelector(".tm-scope-card");
  const del = form.querySelector('input[name="delete"]');
  let filling = false;

  function mark(name) {
    $$('input[name="' + name + '"]').forEach((r) => {
      const box = r.closest(".tm-preset, .tm-opt");
      if (box) box.classList.toggle("is-on", r.checked);
    });
  }

  // ---- presets and the section table
  function applyPreset(radio) {
    const full = radio.value === "full";
    if (matrix) matrix.hidden = full;
    if (fullNote) fullNote.hidden = !full;
    if (scopeCard) scopeCard.hidden = full;
    if (radio.value === "custom" || full) return;
    let secs = {};
    try { secs = JSON.parse(radio.dataset.sections || "{}"); } catch (e) { secs = {}; }
    filling = true;
    $$('.tm-matrix input[type="radio"]').forEach((r) => {
      const key = r.name.replace(/^sec_/, "");
      r.checked = r.value === (secs[key] || "none");
    });
    if (del) del.checked = !!radio.dataset.delete;
    filling = false;
  }
  $$('input[name="preset"]').forEach((r) => r.addEventListener("change", () => {
    applyPreset(r);
    mark("preset");
  }));
  function toCustom() {
    if (filling) return;
    const custom = form.querySelector('input[name="preset"][value="custom"]');
    if (custom && !custom.checked) {
      custom.checked = true;
      mark("preset");
    }
  }
  $$('.tm-matrix input[type="radio"]').forEach((r) => r.addEventListener("change", toCustom));
  if (del) del.addEventListener("change", toCustom);

  // ---- password: made for them, or typed
  const typed = form.querySelector(".tm-pw-typed");
  const pw = document.getElementById("tm-password");
  $$('input[name="pw_mode"]').forEach((r) => r.addEventListener("change", () => {
    if (!typed) return;
    typed.hidden = r.value !== "type" || !r.checked;
    if (pw) pw.required = !typed.hidden;
    if (!typed.hidden && pw) pw.focus();
  }));
  const gen = document.getElementById("tm-gen");
  if (gen && pw) gen.addEventListener("click", () => {
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
    const sym = "!@#$%&*?";
    const n = new Uint32Array(12);
    crypto.getRandomValues(n);
    let out = "";
    for (let i = 0; i < 10; i++) out += abc[n[i] % abc.length];
    out += "23456789"[n[10] % 8] + sym[n[11] % sym.length];
    pw.value = out;
    // a suggested password is shown, so it can be read out or noted down
    const eye = pw.parentNode.querySelector(".pw-eye");
    if (pw.type === "password" && eye) eye.click();
    pw.select();
  });

  // ---- departments
  const scope = form.querySelector(".tm-scope");
  $$('input[name="scope"]').forEach((r) => r.addEventListener("change", () => {
    if (scope) scope.hidden = form.querySelector('input[name="scope"]:checked').value !== "selected";
    mark("scope");
  }));

  const rows = $$(".tm-dept");
  const count = document.getElementById("tm-count");
  function recount() {
    const schools = new Set($$('input[name="schools"]:checked').map((x) => x.value));
    const campuses = new Set($$('input[name="campuses"]:checked').map((x) => x.value));
    let n = 0;
    rows.forEach((row) => {
      const box = row.querySelector("input");
      const via = schools.has(row.dataset.school) || campuses.has(row.dataset.campus);
      row.classList.toggle("is-via", via);
      row.querySelector(".tm-via").hidden = !via;
      if (box.checked || via) n++;
    });
    if (count) count.textContent = n;
  }
  form.addEventListener("change", (e) => {
    if (e.target.matches('input[name="codes"], input[name="schools"], input[name="campuses"]')) recount();
  });

  const find = document.getElementById("tm-find");
  if (find) find.addEventListener("input", () => {
    const words = find.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    rows.forEach((row) => {
      row.hidden = !words.every((w) => row.dataset.find.includes(w));
    });
  });
  function setShown(on) {
    rows.forEach((row) => { if (!row.hidden) row.querySelector("input").checked = on; });
    recount();
  }
  const all = document.getElementById("tm-all");
  const none = document.getElementById("tm-none");
  if (all) all.addEventListener("click", () => setShown(true));
  if (none) none.addEventListener("click", () => setShown(false));

  recount();
})();

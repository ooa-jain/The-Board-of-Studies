/* Data Flow in 2D: the same flows as the 3D view, drawn as a tree.

   Department
     └ stage (in the order a department meets them)
         └ what is entered there and carried on
             └ every stage it is used again in, and how (copied, worked out,
               offered to fill in one click)

   flow3d.js loads the department and calls FlowTree.render(data) and
   FlowTree.pick(id); clicking a field here calls FlowTree.onPick(id), so the
   list, the table and the 3D view follow the same choice. */
(function () {
  "use strict";
  const box = document.getElementById("flow-tree");
  if (!box) return;
  const HOW = {
    copied: { word: "Copied", cls: "h-copied" },
    "worked out": { word: "Worked out", cls: "h-worked" },
    offered: { word: "Offered", cls: "h-offered" },
  };
  let data = null, active = null;

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  function render(d) {
    data = d;
    box.textContent = "";
    if (!d) return;
    const title = key => (d.nodes.find(n => n.key === key) || {}).title || key;
    const tree = el("ul", "ft-tree");
    const rootLi = el("li", "ft-root");
    const root = el("div", "ft-node ft-dept");
    root.appendChild(el("strong", null, d.department.name));
    root.appendChild(el("small", null, [d.department.campus, d.programme ? "Programme " + d.programme.code
                                        : (d.programmes.length ? d.programmes.length + " programmes" : "")]
                                       .filter(Boolean).join(" · ")));
    if (d.programme) root.title = d.programme.name;
    rootLi.appendChild(root);
    const stages = el("ul");
    d.nodes.forEach(n => {
      const li = el("li");
      const node = el("div", "ft-node ft-stage");
      node.dataset.stage = n.key;
      node.appendChild(el("span", "ft-group", n.group));
      node.appendChild(el("strong", null, n.title));
      li.appendChild(node);
      const out = d.flows.filter(f => f.from === n.key);
      const into = d.flows.filter(f => f.to.indexOf(n.key) >= 0 && f.from !== n.key);
      const kids = el("ul");
      out.forEach(f => {
        const how = HOW[f.how] || HOW.copied;
        const fli = el("li");
        const b = el("button", "ft-node ft-field " + how.cls);
        b.type = "button";
        b.dataset.id = f.id;
        const head = el("span", "ft-field-head");
        head.appendChild(el("i", "ft-dot"));
        head.appendChild(el("strong", null, f.field));
        head.appendChild(el("span", "ft-how", how.word));
        b.appendChild(head);
        b.appendChild(el("span", "ft-value", f.value));
        const to = el("span", "ft-to");
        to.appendChild(el("span", "ft-arrow", "→"));
        f.to.forEach(t => {
          const c = el("span", "ft-chip", title(t));
          c.dataset.stage = t;
          to.appendChild(c);
        });
        b.appendChild(to);
        b.title = f.detail || "";
        b.addEventListener("click", () => { pick(active === f.id ? null : f.id); if (api.onPick) api.onPick(active); });
        fli.appendChild(b);
        kids.appendChild(fli);
      });
      if (!out.length) {
        const leaf = el("li");
        const note = el("div", "ft-node ft-note");
        note.textContent = into.length
          ? "Gathers " + into.map(f => f.field.replace(/ \(.*\)$/, "")).join(", ")
          : "Used where it is entered";
        leaf.appendChild(note);
        kids.appendChild(leaf);
      }
      li.appendChild(kids);
      stages.appendChild(li);
    });
    rootLi.appendChild(stages);
    tree.appendChild(rootLi);
    box.appendChild(tree);
    pick(active);
  }

  function pick(id) {
    active = id || null;
    box.classList.toggle("has-pick", !!active);
    const f = data && active ? data.flows.find(x => x.id === active) : null;
    box.querySelectorAll(".ft-field").forEach(b => b.classList.toggle("is-on", b.dataset.id === active));
    box.querySelectorAll(".ft-stage").forEach(s => {
      const k = s.dataset.stage;
      s.classList.toggle("is-from", !!f && f.from === k);
      s.classList.toggle("is-to", !!f && f.to.indexOf(k) >= 0);
    });
    box.querySelectorAll(".ft-root, .ft-tree li").forEach(li => li.classList.remove("on-path"));
    if (f) {
      const b = box.querySelector('.ft-field[data-id="' + active + '"]');
      let li = b && b.closest("li");
      while (li && box.contains(li)) { li.classList.add("on-path"); li = li.parentElement.closest("li"); }
    }
  }

  const api = { render, pick, onPick: null };
  window.FlowTree = api;
})();

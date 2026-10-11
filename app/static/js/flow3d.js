/* ==========================================================================
   Data Flow — how one department's data moves from stage to stage, in two
   views of the same flows:

   2D tree (the default, js/flow-tree.js): department → stages → what each
   stage carries on → where it is used again.

   3D: every place data lives is a platform — Level 0, Stage 1, Stage 2, the
   three Stage 3 parts and the worked-out checks — and every piece of data the
   portal carries forward is an arc from where it is entered to each place it
   is used again, with light running along it. Built the first time it is
   opened, framed to fit the panel, and drawn in the light or dark colours.

   Colour says how it is carried: copied, worked out, or offered to fill in
   one click. Nothing is drawn until a department is chosen.
   ========================================================================== */
(function () {
  "use strict";
  const stage = document.getElementById("flow-stage");
  const host = document.getElementById("flow-canvas");
  const tip = document.getElementById("flow-tip");
  const empty = document.getElementById("flow-empty");
  const deptSel = document.getElementById("flow-dept");
  const progSel = document.getElementById("flow-prog");
  const info = document.getElementById("flow-info");
  const list = document.getElementById("flow-list");
  const count = document.getElementById("flow-n");
  const mapBody = document.getElementById("map-body");
  const mapFor = document.getElementById("map-for");
  const xlsx = document.getElementById("map-xlsx");
  if (!stage || !deptSel) return;
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isDark = () => document.documentElement.getAttribute("data-theme") === "dark";

  const HOW = {
    copied: { word: "Copied", light: 0x0f2440, dark: 0x7aa2f7 },
    "worked out": { word: "Worked out", light: 0x6b7280, dark: 0xa3acbb },
    offered: { word: "Offered", light: 0x2563eb, dark: 0x3b82f6 },
  };
  const howOf = f => HOW[f.how] || HOW.copied;
  const hex = n => "#" + n.toString(16).padStart(6, "0");
  const howCss = f => hex(isDark() ? howOf(f).dark : howOf(f).light);

  let data = null, active = null, showAll = false, three = null;
  const title = key => (data && data.nodes.find(n => n.key === key) || {}).title || key;

  // ------------------------------------------------------- one choice, everywhere
  function highlight(id) {
    active = id || null;
    Array.prototype.forEach.call(list.querySelectorAll("li[data-id]"), li =>
      li.classList.toggle("is-on", li.dataset.id === active));
    Array.prototype.forEach.call(mapBody.querySelectorAll("tr[data-id]"), tr =>
      tr.classList.toggle("is-on", tr.dataset.id === active));
    if (window.FlowTree) window.FlowTree.pick(active);
    if (three) three.highlight(active);
  }
  if (window.FlowTree) window.FlowTree.onPick = id => highlight(id);

  // ------------------------------------------------------------ panels
  function paintList() {
    list.textContent = "";
    data.flows.forEach(f => {
      const li = document.createElement("li");
      li.dataset.id = f.id;
      li.tabIndex = 0;
      const dot = document.createElement("i");
      dot.style.background = howCss(f);
      li.appendChild(dot);
      const body = document.createElement("div");
      const s = document.createElement("strong"); s.textContent = f.field;
      const path = document.createElement("span");
      path.textContent = `${title(f.from)} → ${f.to.map(title).join(", ")}`;
      const val = document.createElement("em"); val.textContent = f.value;
      body.appendChild(s); body.appendChild(path); body.appendChild(val);
      li.appendChild(body);
      const pick = () => highlight(active === f.id ? null : f.id);
      li.addEventListener("click", pick);
      li.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      list.appendChild(li);
    });
    count.textContent = `${data.flows.length} flows`;
  }

  function paintTable() {
    mapBody.textContent = "";
    data.flows.forEach(f => {
      const tr = document.createElement("tr");
      tr.dataset.id = f.id;
      [f.field, title(f.from), f.to.map(title).join(", "), howOf(f).word, f.value].forEach((v, i) => {
        const td = document.createElement("td");
        if (i === 3) {
          const p = document.createElement("span");
          p.className = "pill fk-pill fk-" + (f.how || "copied").replace(" ", "-");
          p.textContent = v;
          td.appendChild(p);
        } else if (i === 0) {
          const s = document.createElement("strong"); s.textContent = v; td.appendChild(s);
          const d = document.createElement("small"); d.className = "muted"; d.textContent = f.detail;
          td.appendChild(d);
        } else {
          td.textContent = v;
        }
        tr.appendChild(td);
      });
      tr.addEventListener("click", () => highlight(f.id));
      mapBody.appendChild(tr);
    });
    const d = data.department;
    mapFor.textContent = `— ${d.name}${data.programme ? " · " + data.programme.code : ""}`;
    xlsx.hidden = false;
    xlsx.removeAttribute("aria-disabled");
    xlsx.href = `${window.FLOW_XLSX}?dept=${encodeURIComponent(d.code)}`;
  }

  function load() {
    const dept = deptSel.value;
    if (!dept) {
      data = null;
      if (three) three.setFlows([]);
      if (window.FlowTree) window.FlowTree.render(null);
      empty.hidden = false;
      progSel.disabled = true;
      list.innerHTML = '<li class="muted small">Choose a department.</li>';
      mapBody.innerHTML = '<tr><td colspan="5" class="muted">Choose a department above.</td></tr>';
      mapFor.textContent = "";
      xlsx.hidden = true;
      count.textContent = "";
      return;
    }
    empty.hidden = true;
    // the list and the table keep their shape while this department loads
    list.innerHTML = Array.from({ length: 6 }, () =>
      '<li class="sk-row" aria-hidden="true"><span class="sk" style="width:10px;height:10px;border-radius:50%"></span>' +
      '<div class="sk-grow"><span class="sk sk-line w-70"></span><span class="sk sk-line w-50"></span></div></li>').join("");
    mapBody.innerHTML = Array.from({ length: 6 }, () =>
      "<tr aria-hidden='true'>" + ["w-90", "w-70", "w-70", "w-50", "w-70"].map(w =>
        `<td><span class="sk sk-line ${w}"></span></td>`).join("") + "</tr>").join("");
    const url = `${window.FLOW_URL}?dept=${encodeURIComponent(dept)}` +
                (progSel.value ? `&prog=${encodeURIComponent(progSel.value)}` : "");
    fetch(url, { credentials: "same-origin" }).then(r => r.json()).then(j => {
      const keepProg = progSel.value;
      data = j;
      // the programme list follows the department
      if (progSel.dataset.dept !== dept) {
        progSel.dataset.dept = dept;
        progSel.textContent = "";
        progSel.appendChild(new Option(j.programmes.length ? "All programmes" : "No programmes yet", ""));
        j.programmes.forEach(p => progSel.appendChild(new Option(`${p.code} — ${p.name} (${p.level})`, p.code)));
      }
      progSel.disabled = !j.programmes.length;
      progSel.value = j.programme ? j.programme.code : (keepProg && j.programmes.some(p => p.code === keepProg) ? keepProg : "");
      info.textContent = j.programme
        ? `Showing ${j.programme.code} — ${j.programme.name}.`
        : `${j.department.name} · ${j.department.campus}. Choose a programme for its own values.`;
      if (active && !j.flows.some(f => f.id === active)) active = null;
      if (window.FlowTree) window.FlowTree.render(j);
      if (three) three.setFlows(j.flows);
      paintList();
      paintTable();
      highlight(active);
    }).catch(() => { info.textContent = "The map could not load. Try again."; });
  }

  deptSel.addEventListener("change", () => { progSel.value = ""; active = null; load(); });
  progSel.addEventListener("change", load);

  // ------------------------------------------------------------- views
  const VIEW_KEY = "bos.flowview";
  function setView(v) {
    stage.dataset.view = v;
    stage.querySelectorAll("[data-view-btn]").forEach(b =>
      b.setAttribute("aria-pressed", b.dataset.viewBtn === v ? "true" : "false"));
    try { localStorage.setItem(VIEW_KEY, v); } catch (e) { /* this visit only */ }
    if (v === "3d") {
      if (!three) three = make3D();
      if (three) {
        three.start();
        if (data) three.setFlows(data.flows);
        three.highlight(active);
      }
    } else if (three) {
      three.stop();
    }
  }
  stage.querySelectorAll("[data-view-btn]").forEach(b => b.addEventListener("click", () => setView(b.dataset.viewBtn)));

  window.addEventListener("themechange", () => {
    if (data) { paintList(); highlight(active); }
    if (three) three.theme();
  });

  // ---------------------------------------------------------- the 3D view
  function make3D() {
    const fail = words => {
      const p = document.createElement("p");
      p.className = "flow-no3d";
      p.textContent = words;
      host.appendChild(p);
      return null;
    };
    if (!window.THREE || !THREE.OrbitControls) return fail("The 3D view could not load. The 2D tree shows the same flows.");
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch (e) {
      return fail("This browser cannot draw 3D (WebGL is off). The 2D tree shows the same flows.");
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    host.appendChild(renderer.domElement);

    // left to right, as a department meets them: Level 0, Stages 1 and 2,
    // Curriculum in the middle, Syllabus and Course Revision after it, checks last
    const PLACE = {
      dept_info:       { pos: [-16, 0, 0],  tone: "navy" },
      pre_bos:         { pos: [-8.5, 0, 7], tone: "blue" },
      bos_documents:   { pos: [-8, 0, -7],  tone: "navy" },
      prog_curriculum: { pos: [1, 0, 0],    tone: "blue" },
      prog_syllabus:   { pos: [10, 0, -7],  tone: "blue" },
      prog_revision:   { pos: [10, 0, 7],   tone: "blue" },
      checks:          { pos: [18, 0, 0],   tone: "green" },
    };
    const TONES = { light: { navy: 0x0f2440, blue: 0x2563eb, green: 0x1d6b3e },
                    dark: { navy: 0x3b5b99, blue: 0x2f6fe4, green: 0x2f8f57 } };
    const NODES = [
      { key: "dept_info", title: "Department Information", group: "Level 0" },
      { key: "pre_bos", title: "Pre-BoS", group: "Stage 1" },
      { key: "bos_documents", title: "BoS Documents", group: "Stage 2" },
      { key: "prog_curriculum", title: "Curriculum", group: "Stage 3" },
      { key: "prog_syllabus", title: "Syllabus", group: "Stage 3" },
      { key: "prog_revision", title: "Course Revision", group: "Stage 3" },
      { key: "checks", title: "Checks & summaries", group: "Worked out" },
    ];

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 400);
    const TARGET = new THREE.Vector3(1, 1, 0);
    const DIR = new THREE.Vector3(0, 27, 35).normalize();
    const HOME = DIR.clone().multiplyScalar(50).add(TARGET);
    camera.position.copy(HOME);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.copy(TARGET);
    controls.minDistance = 12;
    controls.maxDistance = 160;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.autoRotateSpeed = 0.4;
    let moved = false;
    controls.addEventListener("start", () => { moved = true; });

    const hemi = new THREE.HemisphereLight(0xffffff, 0xe4e7ec, 0.9);
    scene.add(hemi);
    const sun = new THREE.DirectionalLight(0xffffff, 0.7);
    sun.position.set(10, 30, 16);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -34, right: 34, top: 34, bottom: -34 });
    scene.add(sun);
    const ground = new THREE.Mesh(new THREE.CircleGeometry(80, 64), new THREE.MeshStandardMaterial({ roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);
    let grid = null;

    const mat = (color, extra) => new THREE.MeshStandardMaterial(Object.assign(
      { color, roughness: 0.5, metalness: 0.05 }, extra || {}));

    function label(text, o) {
      o = Object.assign({ size: 40, color: "#0f2440", bg: null, weight: 800, pad: 16, scale: 0.02 }, o || {});
      const c = document.createElement("canvas");
      const g = c.getContext("2d");
      const font = `${o.weight} ${o.size}px Roboto, Inter, "Segoe UI", sans-serif`;
      g.font = font;
      const w = Math.ceil(g.measureText(text).width) + o.pad * 2;
      const h = o.size + o.pad * 2;
      c.width = w; c.height = h;
      g.font = font;
      if (o.bg) {
        const r = Math.min(18, h / 2);
        g.fillStyle = o.bg;
        g.beginPath();
        g.moveTo(r, 0); g.lineTo(w - r, 0); g.quadraticCurveTo(w, 0, w, r);
        g.lineTo(w, h - r); g.quadraticCurveTo(w, h, w - r, h);
        g.lineTo(r, h); g.quadraticCurveTo(0, h, 0, h - r);
        g.lineTo(0, r); g.quadraticCurveTo(0, 0, r, 0); g.fill();
        if (o.border) { g.strokeStyle = o.border; g.lineWidth = 4; g.stroke(); }
      }
      g.fillStyle = o.color;
      g.textBaseline = "middle";
      g.fillText(text, o.pad, h / 2 + 2);
      const tex = new THREE.CanvasTexture(c);
      tex.anisotropy = 4;
      // names are drawn over the arcs, so a line never hides one
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
      s.renderOrder = 10;
      s.scale.set(w * o.scale, h * o.scale, 1);
      return s;
    }

    // ------------------------------------------------------------- places
    const places = {};
    let hoverables = [];
    let placeGroup = null;
    function buildPlaces() {
      if (placeGroup) { scene.remove(placeGroup); hoverables = hoverables.filter(o => o.userData.kind !== "place"); }
      placeGroup = new THREE.Group();
      const tones = TONES[isDark() ? "dark" : "light"];
      NODES.forEach(n => {
        const p = PLACE[n.key], colour = tones[p.tone];
        const v = new THREE.Vector3(...p.pos);
        const base = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.9, 0.8, 6), mat(colour, { roughness: 0.4 }));
        base.position.set(v.x, 0.4, v.z);
        base.castShadow = true; base.receiveShadow = true;
        placeGroup.add(base);
        const top = new THREE.Mesh(new THREE.CylinderGeometry(2.45, 2.45, 0.1, 6), mat(isDark() ? 0x243044 : 0xffffff));
        top.position.set(v.x, 0.86, v.z);
        placeGroup.add(top);
        const g = label(n.group.toUpperCase(), { size: 26, color: isDark() ? "#9aa4b5" : "#6b7280", scale: 0.018 });
        g.position.set(v.x, 4.2, v.z);
        placeGroup.add(g);
        const t = label(n.title, { size: 38, color: "#fff", bg: hex(colour), scale: 0.021 });
        t.position.set(v.x, 3.05, v.z);
        placeGroup.add(t);
        base.userData = { kind: "place", node: n };
        hoverables.push(base);
        places[n.key] = { top: new THREE.Vector3(v.x, 0.95, v.z), node: n };
      });
      scene.add(placeGroup);
    }

    // -------------------------------------------------------------- flows
    let flowGroup = null;
    let arcs = [];
    function clearFlows() {
      if (flowGroup) scene.remove(flowGroup);
      hoverables = hoverables.filter(o => o.userData.kind !== "flow");
      flowGroup = null;
      arcs = [];
    }
    let lastFlows = [];
    function setFlows(flows) {
      lastFlows = flows || [];
      clearFlows();
      flowGroup = new THREE.Group();
      const pairCount = {};
      lastFlows.forEach(f => f.to.forEach(t => { const k = f.from + ">" + t; pairCount[k] = (pairCount[k] || 0) + 1; }));
      const pairSeen = {};
      lastFlows.forEach((f, fi) => {
        const colour = isDark() ? howOf(f).dark : howOf(f).light;
        f.to.forEach(t => {
          const a = places[f.from].top, b = places[t].top;
          const key = f.from + ">" + t;
          const n = pairSeen[key] = (pairSeen[key] || 0) + 1;
          const spread = (n - (pairCount[key] + 1) / 2) * 1.6;
          let curve;
          if (f.from === t) {
            const lift = 4 + n * 1.2;
            curve = new THREE.CubicBezierCurve3(
              a.clone().add(new THREE.Vector3(-1.2, 0.2, 0)),
              a.clone().add(new THREE.Vector3(-3.2 - n, lift, 1.5 * n)),
              a.clone().add(new THREE.Vector3(3.2 + n, lift, 1.5 * n)),
              a.clone().add(new THREE.Vector3(1.2, 0.2, 0)));
          } else {
            const mid = a.clone().lerp(b, 0.5);
            const dist = a.distanceTo(b);
            const side = new THREE.Vector3(-(b.z - a.z), 0, b.x - a.x).normalize().multiplyScalar(spread);
            mid.add(side);
            mid.y = 3 + dist * 0.28 + Math.abs(spread) * 0.8;
            curve = new THREE.QuadraticBezierCurve3(a.clone(), mid, b.clone());
          }
          const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.11, 8, false),
            mat(colour, { emissive: colour, emissiveIntensity: 0.18, transparent: true, opacity: 0.9 }));
          tube.userData = { kind: "flow", flow: f, to: t };
          flowGroup.add(tube);
          hoverables.push(tube);
          const dots = [];
          const dg = new THREE.SphereGeometry(0.2, 12, 12);
          for (let k = 0; k < 4; k++) {
            const d = new THREE.Mesh(dg, new THREE.MeshBasicMaterial({ color: 0xffffff }));
            d.userData.t = (k / 4 + fi * 0.13) % 1;
            flowGroup.add(d);
            dots.push(d);
          }
          const chip = label(f.field, { size: 26, color: hex(colour), bg: isDark() ? "rgba(17,22,32,0.95)" : "rgba(255,255,255,0.95)",
                                        border: hex(colour), pad: 12, weight: 800, scale: 0.016 });
          chip.position.copy(curve.getPoint(0.5)).add(new THREE.Vector3(0, 0.7, 0));
          flowGroup.add(chip);
          arcs.push({ flow: f, mesh: tube, curve, dots, chip });
        });
      });
      scene.add(flowGroup);
      paintArcs();
    }
    function paintArcs() {
      arcs.forEach(a => {
        const on = showAll ? (!active || a.flow.id === active) : (!active || a.flow.id === active);
        const lit = !!active && a.flow.id === active;
        a.mesh.material.opacity = on ? 0.95 : 0.07;
        a.mesh.material.emissiveIntensity = lit ? 0.55 : 0.18;
        // with nothing chosen every flow shows, but only the chosen one names itself
        a.chip.visible = lit || (showAll && !active);
        a.dots.forEach(d => { d.visible = on; });
      });
    }

    function paintTheme() {
      const dark = isDark();
      const bg = dark ? 0x0f141c : 0xf4f5f7;
      scene.background = new THREE.Color(bg);
      scene.fog = new THREE.Fog(bg, 110, 240);
      ground.material.color.set(dark ? 0x141b26 : 0xeef1f6);
      hemi.color.set(dark ? 0xc9d6ee : 0xffffff);
      hemi.groundColor.set(dark ? 0x101722 : 0xe4e7ec);
      hemi.intensity = dark ? 0.75 : 0.9;
      if (grid) scene.remove(grid);
      grid = new THREE.GridHelper(100, 50, dark ? 0x2a3446 : 0xd0d5dd, dark ? 0x1c2433 : 0xe4e7ec);
      grid.position.y = 0.01;
      scene.add(grid);
      buildPlaces();
      setFlows(lastFlows);
    }

    // ---------------------------------------------------------- interaction
    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    function hit(ev) {
      const r = renderer.domElement.getBoundingClientRect();
      mouse.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
      mouse.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
      ray.setFromCamera(mouse, camera);
      const h = ray.intersectObjects(hoverables.filter(o => o.visible && (!o.material || o.material.opacity > 0.2)), false)[0];
      return h ? h.object : null;
    }
    renderer.domElement.addEventListener("pointermove", ev => {
      const o = hit(ev);
      renderer.domElement.style.cursor = o ? "pointer" : "grab";
      if (!o) { tip.hidden = true; return; }
      const u = o.userData;
      let head, line;
      if (u.kind === "flow") {
        head = u.flow.field;
        line = `${title(u.flow.from)} → ${title(u.to)} · ${u.flow.value}`;
      } else {
        head = `${u.node.group} · ${u.node.title}`;
        const outs = data ? data.flows.filter(f => f.from === u.node.key).length : 0;
        const ins = data ? data.flows.filter(f => f.to.includes(u.node.key)).length : 0;
        line = data ? `${outs} carried out, ${ins} carried in` : "Choose a department";
        if (data && u.node.key === "pre_bos") line = "DIAC and DPAC uploads — nothing carried forward";
      }
      tip.hidden = false;
      tip.textContent = "";
      const b = document.createElement("strong"); b.textContent = head;
      const s = document.createElement("span"); s.textContent = line;
      tip.appendChild(b); tip.appendChild(s);
      const r = stage.getBoundingClientRect();
      tip.style.left = Math.min(r.width - 260, ev.clientX - r.left + 14) + "px";
      tip.style.top = (ev.clientY - r.top + 14) + "px";
    });
    renderer.domElement.addEventListener("pointerleave", () => { tip.hidden = true; });
    let downAt = null;
    renderer.domElement.addEventListener("pointerdown", ev => { downAt = [ev.clientX, ev.clientY]; });
    renderer.domElement.addEventListener("pointerup", ev => {
      if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 5) return;
      const o = hit(ev);
      if (o && o.userData.kind === "flow") highlight(o.userData.flow.id);
    });

    let fly = null;
    document.getElementById("flow-reset").addEventListener("click", () => {
      moved = false;
      fly = { from: camera.position.clone(), to: HOME.clone(), tf: controls.target.clone(), tt: TARGET.clone(), t: 0 };
    });
    const allBtn = document.getElementById("flow-all");
    allBtn.addEventListener("click", () => {
      showAll = !showAll;
      allBtn.setAttribute("aria-pressed", String(showAll));
      allBtn.textContent = showAll ? "Hide the names" : "Name every flow";
      paintArcs();
    });
    const spinBtn = document.getElementById("flow-spin");
    spinBtn.addEventListener("click", () => {
      controls.autoRotate = !controls.autoRotate;
      spinBtn.setAttribute("aria-pressed", String(controls.autoRotate));
      spinBtn.textContent = controls.autoRotate ? "Stop rotating" : "Rotate";
    });

    // the whole map fits the panel, whatever its shape: wide on a desktop,
    // tall on a phone — nothing cut off at the edges
    function fit() {
      const w = host.clientWidth, h = host.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const vf = camera.fov * Math.PI / 180;
      const hf = 2 * Math.atan(Math.tan(vf / 2) * camera.aspect);
      const dist = Math.max(23.5 / Math.tan(hf / 2), 12 / Math.tan(vf / 2));
      HOME.copy(DIR).multiplyScalar(dist).add(TARGET);
      if (!moved && !fly) { camera.position.copy(HOME); controls.target.copy(TARGET); }
    }

    let running = false, lastW = 0, lastH = 0;
    const clock = new THREE.Clock();
    function tick() {
      if (!running) return;
      const dt = Math.min(clock.getDelta(), 0.05);
      if (host.clientWidth !== lastW || host.clientHeight !== lastH) {
        lastW = host.clientWidth; lastH = host.clientHeight; fit();
      }
      arcs.forEach(a => a.dots.forEach(d => {
        if (!REDUCED) d.userData.t = (d.userData.t + dt * 0.18) % 1;
        d.position.copy(a.curve.getPoint(d.userData.t));
      }));
      if (fly) {
        fly.t = Math.min(1, fly.t + dt * (REDUCED ? 10 : 1.2));
        const e = 1 - Math.pow(1 - fly.t, 3);
        camera.position.lerpVectors(fly.from, fly.to, e);
        controls.target.lerpVectors(fly.tf, fly.tt, e);
        if (fly.t >= 1) fly = null;
      }
      controls.update();
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    }

    paintTheme();
    return {
      setFlows,
      highlight() { paintArcs(); },
      theme: paintTheme,
      start() { if (running) return; running = true; lastW = lastH = 0; clock.getDelta(); requestAnimationFrame(tick); },
      stop() { running = false; tip.hidden = true; },
    };
  }

  // ------------------------------------------------------------ begin
  let start = "2d";
  try { start = localStorage.getItem(VIEW_KEY) === "3d" ? "3d" : "2d"; } catch (e) { /* 2D */ }
  setView(start);
  if (deptSel.value) load();
})();

/* ==========================================================================
   Flow 3D — how one department's data moves from stage to stage.

   Every place data lives is a platform: Level 0, Stage 1, Stage 2, the three
   Stage 3 parts (Curriculum, Syllabus, Course Revision) and the worked-out
   checks. For the department chosen in the side panel, every piece of data
   the portal carries forward is an arc from where it is entered to each place
   it is used again, with light running along it and its name at the top.
   Colour says how it is carried: navy copied, gold worked out, orange offered
   to fill in one click. Nothing is drawn until a department is chosen.
   ========================================================================== */
(function () {
  "use strict";
  if (!window.THREE) return;

  const host = document.getElementById("flow-canvas");
  const tip = document.getElementById("flow-tip");
  const loading = document.getElementById("flow-loading");
  const empty = document.getElementById("flow-empty");
  const deptSel = document.getElementById("flow-dept");
  const progSel = document.getElementById("flow-prog");
  const info = document.getElementById("flow-info");
  const list = document.getElementById("flow-list");
  const count = document.getElementById("flow-n");
  const mapBody = document.getElementById("map-body");
  const mapFor = document.getElementById("map-for");
  const xlsx = document.getElementById("map-xlsx");
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const HOW = {
    copied: { colour: 0x0f2440, css: "#0f2440", word: "Copied" },
    "worked out": { colour: 0xc79c10, css: "#c79c10", word: "Worked out" },
    offered: { colour: 0xe8620f, css: "#e8620f", word: "Offered" },
  };

  // where each place stands: a loose arc from Level 0 to the checks
  const PLACE = {
    dept_info:       { pos: [-16, 0, 2],  colour: 0x0f2440 },
    pre_bos:         { pos: [-9, 0, 6],   colour: 0xe8620f },
    bos_documents:   { pos: [-4, 0, -3],  colour: 0x0f2440 },
    prog_curriculum: { pos: [4, 0, 4],    colour: 0xe8620f },
    prog_syllabus:   { pos: [11, 0, -3],  colour: 0xe8620f },
    prog_revision:   { pos: [16, 0, 5],   colour: 0xe8620f },
    checks:          { pos: [6, 0, -10],  colour: 0x1d6b3e },
  };

  // ------------------------------------------------------------------ scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf7f3ec);
  scene.fog = new THREE.Fog(0xf7f3ec, 60, 120);

  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 250);
  const HOME = new THREE.Vector3(0, 27, 35);
  const HOME_TARGET = new THREE.Vector3(0, 1, 0);
  camera.position.copy(HOME);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  host.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.copy(HOME_TARGET);
  controls.minDistance = 10;
  controls.maxDistance = 90;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.autoRotate = false;
  controls.autoRotateSpeed = 0.4;

  scene.add(new THREE.HemisphereLight(0xffffff, 0xe9dfcf, 0.9));
  const sun = new THREE.DirectionalLight(0xffffff, 0.7);
  sun.position.set(10, 30, 16);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -32, right: 32, top: 32, bottom: -32 });
  scene.add(sun);

  const ground = new THREE.Mesh(new THREE.CircleGeometry(70, 64),
    new THREE.MeshStandardMaterial({ color: 0xf1ebe0, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(90, 45, 0xe2d8c8, 0xebe3d6);
  grid.position.y = 0.01;
  scene.add(grid);

  const mat = (color, extra) => new THREE.MeshStandardMaterial(Object.assign(
    { color, roughness: 0.5, metalness: 0.05 }, extra || {}));

  function label(text, o) {
    o = Object.assign({ size: 40, color: "#0f2440", bg: null, weight: 800, pad: 16, scale: 0.02 }, o || {});
    const c = document.createElement("canvas");
    const g = c.getContext("2d");
    const font = `${o.weight} ${o.size}px Inter, "Segoe UI", sans-serif`;
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
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    s.scale.set(w * o.scale, h * o.scale, 1);
    return s;
  }

  // ------------------------------------------------------------- places
  const places = {};
  const hoverables = [];
  function buildPlaces(nodes) {
    nodes.forEach(n => {
      const p = PLACE[n.key];
      const v = new THREE.Vector3(...p.pos);
      const base = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.9, 0.8, 6), mat(p.colour, { roughness: 0.4 }));
      base.position.set(v.x, 0.4, v.z);
      base.castShadow = true; base.receiveShadow = true;
      scene.add(base);
      const top = new THREE.Mesh(new THREE.CylinderGeometry(2.45, 2.45, 0.1, 6), mat(0xfdfbf7));
      top.position.set(v.x, 0.86, v.z);
      scene.add(top);
      const g = label(n.group.toUpperCase(), { size: 26, color: "#c79c10", scale: 0.02 });
      g.position.set(v.x, 4.4, v.z);
      scene.add(g);
      const t = label(n.title, { size: 38, color: "#fff", bg: "#" + p.colour.toString(16).padStart(6, "0"), scale: 0.022 });
      t.position.set(v.x, 3.1, v.z);
      scene.add(t);
      base.userData = { kind: "place", node: n };
      hoverables.push(base);
      places[n.key] = { base, top: new THREE.Vector3(v.x, 0.95, v.z), node: n, label: t };
    });
  }

  // -------------------------------------------------------------- flows
  let flowGroup = null;
  let arcs = [];         // {flow, mesh, curve, dots, chip}
  let active = null;     // id of the highlighted flow

  function clearFlows() {
    if (flowGroup) {
      flowGroup.traverse(o => { const k = hoverables.indexOf(o); if (k >= 0) hoverables.splice(k, 1); });
      scene.remove(flowGroup);
    }
    flowGroup = null;
    arcs = [];
  }

  function buildFlows(flows) {
    clearFlows();
    flowGroup = new THREE.Group();
    // count arcs per pair, so parallel flows between the same two places fan out
    const pairCount = {};
    flows.forEach(f => f.to.forEach(t => { const k = f.from + ">" + t; pairCount[k] = (pairCount[k] || 0) + 1; }));
    const pairSeen = {};
    flows.forEach((f, fi) => {
      const how = HOW[f.how] || HOW.copied;
      f.to.forEach(t => {
        const a = places[f.from].top, b = places[t].top;
        const key = f.from + ">" + t;
        const n = pairSeen[key] = (pairSeen[key] || 0) + 1;
        const spread = (n - (pairCount[key] + 1) / 2) * 1.6;
        let curve;
        if (f.from === t) {
          // a flow within one place: a loop standing over it
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
          mat(how.colour, { emissive: how.colour, emissiveIntensity: 0.18, transparent: true, opacity: 0.9 }));
        tube.userData = { kind: "flow", flow: f, to: t };
        flowGroup.add(tube);
        hoverables.push(tube);

        const dots = [];
        const dg = new THREE.SphereGeometry(0.2, 12, 12);
        for (let k = 0; k < 4; k++) {
          const d = new THREE.Mesh(dg, new THREE.MeshBasicMaterial({ color: 0xfff1b8 }));
          d.userData.t = (k / 4 + fi * 0.13) % 1;
          flowGroup.add(d);
          dots.push(d);
        }
        const chip = label(f.field, { size: 26, color: how.css, bg: "rgba(255,255,255,0.95)",
                                      border: how.css, pad: 12, weight: 800, scale: 0.017 });
        chip.position.copy(curve.getPoint(0.5)).add(new THREE.Vector3(0, 0.7, 0));
        flowGroup.add(chip);
        arcs.push({ flow: f, to: t, mesh: tube, curve, dots, chip });
      });
    });
    scene.add(flowGroup);
    highlight(active);
  }

  let showAll = false;
  function highlight(id) {
    active = id;
    arcs.forEach(a => {
      const on = showAll ? (!id || a.flow.id === id) : a.flow.id === id;
      a.mesh.material.opacity = on ? 0.95 : 0.07;
      a.mesh.material.emissiveIntensity = id && on ? 0.55 : 0.18;
      a.chip.visible = on;
      a.dots.forEach(d => { d.visible = on; });
    });
    Array.prototype.forEach.call(list.querySelectorAll("li[data-id]"), li =>
      li.classList.toggle("is-on", li.dataset.id === id));
  }

  // ------------------------------------------------------------ panels
  const title = key => (data && data.nodes.find(n => n.key === key) || {}).title || key;
  let data = null;

  function paintList() {
    list.textContent = "";
    data.flows.forEach(f => {
      const how = HOW[f.how] || HOW.copied;
      const li = document.createElement("li");
      li.dataset.id = f.id;
      li.tabIndex = 0;
      const dot = document.createElement("i");
      dot.style.background = how.css;
      li.appendChild(dot);
      const body = document.createElement("div");
      const s = document.createElement("strong"); s.textContent = f.field;
      const path = document.createElement("span");
      path.textContent = `${title(f.from)} → ${f.to.map(title).join(", ")}`;
      const val = document.createElement("em"); val.textContent = f.value;
      body.appendChild(s); body.appendChild(path); body.appendChild(val);
      li.appendChild(body);
      const pick = () => highlight(active === f.id && showAll ? null : f.id);
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
      const how = HOW[f.how] || HOW.copied;
      [f.field, title(f.from), f.to.map(title).join(", "), how.word, f.value].forEach((v, i) => {
        const td = document.createElement("td");
        if (i === 3) {
          const p = document.createElement("span");
          p.className = "pill";
          p.style.background = how.css + "22";
          p.style.color = how.css;
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
      clearFlows();
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
      if (!active || !j.flows.some(f => f.id === active)) active = j.flows[0] && j.flows[0].id;
      buildFlows(j.flows);
      paintList();
      highlight(active);
      paintTable();
    }).catch(() => { info.textContent = "The map could not load. Try again."; });
  }

  deptSel.addEventListener("change", () => { progSel.value = ""; active = null; load(); });
  progSel.addEventListener("change", load);

  // -------------------------------------------------------- interaction
  const ray = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  function pick(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    mouse.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(mouse, camera);
    const hit = ray.intersectObjects(hoverables.filter(o => o.visible && (!o.material || o.material.opacity > 0.2)), false)[0];
    return hit ? hit.object : null;
  }
  renderer.domElement.addEventListener("pointermove", ev => {
    const o = pick(ev);
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
    tip.innerHTML = "";
    const b = document.createElement("strong"); b.textContent = head;
    const s = document.createElement("span"); s.textContent = line;
    tip.appendChild(b); tip.appendChild(s);
    const r = host.getBoundingClientRect();
    tip.style.left = (ev.clientX - r.left + 14) + "px";
    tip.style.top = (ev.clientY - r.top + 14) + "px";
  });
  renderer.domElement.addEventListener("pointerleave", () => { tip.hidden = true; });
  let downAt = null;
  renderer.domElement.addEventListener("pointerdown", ev => { downAt = [ev.clientX, ev.clientY]; });
  renderer.domElement.addEventListener("pointerup", ev => {
    if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 5) return;
    const o = pick(ev);
    if (o && o.userData.kind === "flow") highlight(o.userData.flow.id);
  });

  let fly = null;
  document.getElementById("flow-reset").addEventListener("click", () => {
    highlight(null);
    fly = { from: camera.position.clone(), to: HOME.clone(), tf: controls.target.clone(), tt: HOME_TARGET.clone(), t: 0 };
  });
  const allBtn = document.getElementById("flow-all");
  allBtn.addEventListener("click", () => {
    showAll = !showAll;
    allBtn.setAttribute("aria-pressed", String(showAll));
    allBtn.textContent = showAll ? "One flow at a time" : "Show all flows";
    highlight(showAll ? null : (active || (data && data.flows[0] && data.flows[0].id)));
  });
  const spinBtn = document.getElementById("flow-spin");
  spinBtn.addEventListener("click", () => {
    controls.autoRotate = !controls.autoRotate;
    spinBtn.setAttribute("aria-pressed", String(controls.autoRotate));
    spinBtn.textContent = controls.autoRotate ? "Stop rotating" : "Rotate";
  });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  const clock = new THREE.Clock();
  let lastW = 0, lastH = 0;
  function tick() {
    const dt = Math.min(clock.getDelta(), 0.05);
    if (host.clientWidth !== lastW || host.clientHeight !== lastH) {
      lastW = host.clientWidth; lastH = host.clientHeight; resize();
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

  // the places are the same for every department, so they are drawn at once
  resize();
  buildPlaces([
    { key: "dept_info", title: "Department Information", group: "Level 0" },
    { key: "pre_bos", title: "Pre-BoS", group: "Stage 1" },
    { key: "bos_documents", title: "BoS Documents", group: "Stage 2" },
    { key: "prog_curriculum", title: "Curriculum", group: "Stage 3" },
    { key: "prog_syllabus", title: "Syllabus", group: "Stage 3" },
    { key: "prog_revision", title: "Course Revision", group: "Stage 3" },
    { key: "checks", title: "Checks & summaries", group: "Worked out" },
  ]);
  loading.remove();
  tick();
  if (deptSel.value) load();
})();

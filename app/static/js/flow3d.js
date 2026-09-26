/* ==========================================================================
   Flow 3D — the admin's view of how a submission moves.

   Four platforms stand in a row, one per stage, joined by a path that a light
   runs along in the order the stages open. Every department is a small sphere
   standing on the platform of the stage it has reached (a pedestal at the end
   holds the sealed ones). Choosing a department grows its Curriculum tree over
   the last platform: a UG branch and a PG branch, each programme a column of
   three blocks — Curriculum, Syllabus, Course Revision — coloured by status.
   ========================================================================== */
(function () {
  "use strict";
  if (!window.THREE) return;

  const host = document.getElementById("flow-canvas");
  const tip = document.getElementById("flow-tip");
  const loading = document.getElementById("flow-loading");
  const picker = document.getElementById("flow-dept");
  const info = document.getElementById("flow-info");
  const counts = document.getElementById("flow-counts");
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const C = {
    navy: 0x0f2440, gold: 0xc79c10, orange: 0xe8620f, ivory: 0xf5f1e8,
    ok: 0x1d6b3e, warn: 0xc79c10, err: 0xad3325, idle: 0x8a94a6, line: 0xd8cfc0,
  };
  const STATUS_COLOUR = { submitted: C.ok, draft: C.warn, returned: C.err, open: C.idle, locked: C.idle };
  const STATUS_WORD = { submitted: "Submitted", draft: "In progress", returned: "Returned",
                        open: "Not started", locked: "Locked" };

  // ------------------------------------------------------------------ scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf7f3ec);
  scene.fog = new THREE.Fog(0xf7f3ec, 55, 110);

  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);
  const HOME = new THREE.Vector3(3.5, 22, 34);
  const HOME_TARGET = new THREE.Vector3(3.5, 1.2, 0);
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
  controls.minDistance = 8;
  controls.maxDistance = 70;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.autoRotate = !REDUCED;
  controls.autoRotateSpeed = 0.45;

  scene.add(new THREE.HemisphereLight(0xffffff, 0xe9dfcf, 0.85));
  const sun = new THREE.DirectionalLight(0xffffff, 0.75);
  sun.position.set(12, 26, 14);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30 });
  scene.add(sun);

  const ground = new THREE.Mesh(new THREE.CircleGeometry(60, 64),
    new THREE.MeshStandardMaterial({ color: 0xf1ebe0, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(80, 40, 0xe2d8c8, 0xebe3d6);
  grid.position.y = 0.01;
  scene.add(grid);

  // ------------------------------------------------------------ helpers
  function label(text, opts) {
    const o = Object.assign({ size: 44, color: "#0f2440", bg: null, weight: 700, pad: 18 }, opts || {});
    const c = document.createElement("canvas");
    const g = c.getContext("2d");
    g.font = `${o.weight} ${o.size}px Inter, "Segoe UI", sans-serif`;
    const w = Math.ceil(g.measureText(text).width) + o.pad * 2;
    const h = o.size + o.pad * 2;
    c.width = w; c.height = h;
    g.font = `${o.weight} ${o.size}px Inter, "Segoe UI", sans-serif`;
    if (o.bg) {
      g.fillStyle = o.bg;
      const r = h / 2;
      g.beginPath();
      g.moveTo(r, 0); g.lineTo(w - r, 0); g.arc(w - r, r, r, -Math.PI / 2, Math.PI / 2);
      g.lineTo(r, h); g.arc(r, r, r, Math.PI / 2, -Math.PI / 2); g.fill();
    }
    g.fillStyle = o.color;
    g.textBaseline = "middle";
    g.fillText(text, o.pad, h / 2 + 2);
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthWrite: false, transparent: true }));
    const scale = (o.scale || 0.012);
    s.scale.set(w * scale, h * scale, 1);
    return s;
  }

  const mat = (color, extra) => new THREE.MeshStandardMaterial(Object.assign(
    { color, roughness: 0.55, metalness: 0.05 }, extra || {}));

  // ------------------------------------------------------------- the stages
  const STAGE_X = [-12, -4, 4, 12];
  const SEALED_X = 19.5;
  const platforms = [];
  const hoverables = [];
  let data = null;
  let flowDots = [];
  let curve = null;
  let tree = null;          // the selected department's programme tree
  let deptSpheres = [];
  let deptLabels = [];
  // department name tags: short codes, full names, or none
  const LABEL_MODES = ["codes", "names", "off"];
  let labelMode = "codes";
  const labelText = d => labelMode === "names"
    ? (d.name.length > 34 ? d.name.slice(0, 33) + "…" : d.name).replace(/^Department of /, "")
    : d.code;

  function buildStages(stages) {
    stages.forEach((s, i) => {
      const x = STAGE_X[i];
      const base = new THREE.Mesh(new THREE.CylinderGeometry(3.2, 3.5, 0.9, 6),
                                  mat(i % 2 ? C.orange : C.navy, { roughness: 0.4 }));
      base.position.set(x, 0.45, 0);
      base.castShadow = true; base.receiveShadow = true;
      scene.add(base);
      const top = new THREE.Mesh(new THREE.CylinderGeometry(3.0, 3.0, 0.12, 6), mat(0xfdfbf7));
      top.position.set(x, 0.96, 0);
      top.receiveShadow = true;
      scene.add(top);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(3.05, 0.05, 8, 6), mat(C.gold, { emissive: C.gold, emissiveIntensity: 0.25 }));
      ring.rotation.x = Math.PI / 2;
      ring.rotation.z = Math.PI / 6;
      ring.position.set(x, 1.03, 0);
      scene.add(ring);

      const n = label(s.group.split("·")[0].trim().toUpperCase(), { size: 30, color: "#c79c10", weight: 800 });
      n.position.set(x, 0.55, 3.9);
      scene.add(n);
      const t = label(s.title, { size: 44, color: "#ffffff", bg: i % 2 ? "#e8620f" : "#0f2440", pad: 22 });
      t.position.set(x, 4.9, 0);
      scene.add(t);

      base.userData = { kind: "stage", stage: s, index: i };
      hoverables.push(base);
      platforms.push({ x, stage: s });
    });

    // the sealed pedestal
    const ped = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.4, 1.4, 32), mat(C.ok, { roughness: 0.35 }));
    ped.position.set(SEALED_X, 0.7, 0);
    ped.castShadow = true;
    scene.add(ped);
    const pt = label("Sealed", { size: 40, color: "#ffffff", bg: "#1d6b3e", pad: 20 });
    pt.position.set(SEALED_X, 4.9, 0);
    scene.add(pt);
    ped.userData = { kind: "sealed" };
    hoverables.push(ped);

    // the path the stages open along
    const pts = STAGE_X.map(x => new THREE.Vector3(x, 1.1, 0));
    pts.unshift(new THREE.Vector3(-17, 0.3, 3));
    pts.push(new THREE.Vector3(SEALED_X, 1.5, 0));
    curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.2);
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 200, 0.12, 10, false),
      mat(C.gold, { emissive: C.gold, emissiveIntensity: 0.35, transparent: true, opacity: 0.8 }));
    scene.add(tube);
    const dotGeo = new THREE.SphereGeometry(0.22, 16, 16);
    for (let k = 0; k < 14; k++) {
      const d = new THREE.Mesh(dotGeo, new THREE.MeshBasicMaterial({ color: 0xfff1b8 }));
      d.userData.t = k / 14;
      scene.add(d);
      flowDots.push(d);
    }
  }

  // --------------------------------------------------------- departments
  function buildDepartments(depts) {
    deptSpheres.forEach(s => scene.remove(s));
    deptLabels.forEach(t => scene.remove(t));
    deptSpheres = [];
    deptLabels = [];
    const byStop = {};
    depts.forEach(d => { (byStop[d.reached] = byStop[d.reached] || []).push(d); });
    const geo = new THREE.SphereGeometry(0.34, 24, 24);
    Object.entries(byStop).forEach(([stop, list]) => {
      const i = Number(stop);
      const cx = i >= STAGE_X.length ? SEALED_X : STAGE_X[i];
      const top = i >= STAGE_X.length ? 1.4 : 1.02;
      const radius = i >= STAGE_X.length ? 1.6 : 2.4;
      list.forEach((d, k) => {
        // a sunflower spiral: many departments share a platform without overlap
        const per = 28;
        const layer = Math.floor(k / per);
        const j = k % per;
        const r = radius * Math.sqrt((j + 0.5) / per);
        const a = j * 2.39996;
        const st = i >= STAGE_X.length ? "submitted" : (d.statuses[data.stages[i].key] || "open");
        const s = new THREE.Mesh(geo, mat(STATUS_COLOUR[st] || C.idle, { roughness: 0.3, metalness: 0.1 }));
        s.position.set(cx + r * Math.cos(a), top + 0.36 + layer * 0.72, r * Math.sin(a));
        s.castShadow = true;
        s.userData = { kind: "dept", dept: d, status: st, home: s.position.clone() };
        scene.add(s);
        deptSpheres.push(s);
        hoverables.push(s);
        // the department's name tag, floating over its ball
        const tag = label(labelText(d), { size: 34, color: "#0f2440", bg: "rgba(255,255,255,0.94)",
                                          pad: 12, weight: 800, scale: 0.019 });
        // staggered heights, so neighbours' tags do not sit on top of each other
        tag.position.copy(s.position).add(new THREE.Vector3(0, 1.0 + (k % 3) * 0.6, 0));
        tag.userData.base = tag.position.clone();
        tag.visible = labelMode !== "off";
        scene.add(tag);
        deptLabels.push(tag);
      });
    });
  }

  // ------------------------------------------------ one department's tree
  function clearTree() {
    if (!tree) return;
    tree.traverse(o => { const k = hoverables.indexOf(o); if (k >= 0) hoverables.splice(k, 1); });
    scene.remove(tree);
    tree = null;
  }

  function buildTree(dept) {
    clearTree();
    if (!dept) return;
    tree = new THREE.Group();
    const baseX = STAGE_X[3];
    const Z = -2.2;           // behind the platform, clear of its label
    const trunkTop = 7.4;
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, trunkTop - 1, 12), mat(C.navy));
    trunk.position.set(baseX, 1 + (trunkTop - 1) / 2, Z);
    tree.add(trunk);
    const partKeys = data.parts.map(p => p.key);

    ["UG", "PG"].forEach((lv, side) => {
      const progs = dept.programmes.filter(p => p.level === lv);
      if (!progs.length) return;
      const colour = lv === "UG" ? C.navy : C.orange;
      const dir = side === 0 ? -1 : 1;
      // the branch leans out and back, and the programmes hang along it
      // the branch grows with the number of programmes it carries
      const reach = Math.min(12, 3.5 + progs.length * 0.62);
      const end = new THREE.Vector3(baseX + dir * reach, trunkTop + 2.2, Z - 1.2);
      const start = new THREE.Vector3(baseX, trunkTop, Z);
      const branchCurve = new THREE.QuadraticBezierCurve3(start,
        new THREE.Vector3(baseX + dir * reach * 0.3, trunkTop + 2.6, Z), end);
      tree.add(new THREE.Mesh(new THREE.TubeGeometry(branchCurve, 40, 0.12, 8, false), mat(colour)));
      const tag = label(`${lv} programmes · ${progs.length}`, { size: 34, color: "#fff",
        bg: lv === "UG" ? "#0f2440" : "#e8620f", pad: 16 });
      tag.position.copy(end).add(new THREE.Vector3(dir * 1.2, 1.1, 0));
      tree.add(tag);

      const cube = new THREE.BoxGeometry(0.42, 0.42, 0.42);
      progs.forEach((p, n) => {
        const t = progs.length === 1 ? 0.9 : 0.18 + 0.82 * (n / (progs.length - 1));
        const at = branchCurve.getPoint(t).clone();
        at.z += (n % 2 ? 0.55 : -0.55);   // alternate either side, so neighbours never touch
        const drop = 0.8 + (n % 2) * 0.45;
        const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, drop, 6),
                                    mat(C.line));
        stem.position.set(at.x, at.y - drop / 2, at.z);
        tree.add(stem);
        partKeys.forEach((k, m) => {
          const st = p.parts[k] || "open";
          const b = new THREE.Mesh(cube, mat(STATUS_COLOUR[st] || C.idle, { roughness: 0.35 }));
          b.position.set(at.x, at.y - drop - 0.3 - m * 0.5, at.z);
          b.castShadow = true;
          b.userData = { kind: "part", prog: p, part: data.parts[m], status: st, dept };
          tree.add(b);
          hoverables.push(b);
        });
      });
    });

    const name = label(dept.name, { size: 40, color: "#0f2440", bg: "#ffffff", pad: 20 });
    name.position.set(baseX, trunkTop + 4.8, Z - 1.2);
    tree.add(name);
    tree.scale.set(0.001, 0.001, 0.001);
    tree.userData.grow = 0;
    scene.add(tree);
  }

  // ------------------------------------------------------------ side panel
  function paintCounts(depts) {
    counts.textContent = "";
    const total = depts.length || 1;
    const stops = data.stages.map((s, i) => ({ title: s.title, n: depts.filter(d => d.reached === i).length }));
    stops.push({ title: "Sealed (all four submitted)", n: depts.filter(d => d.reached >= data.stages.length).length });
    stops.forEach(s => {
      const row = document.createElement("div");
      row.className = "flow-count";
      row.innerHTML = "<span></span><b></b><div class='bar'><i></i></div>";
      row.children[0].textContent = s.title;
      row.children[1].textContent = String(s.n);
      row.querySelector("i").style.width = Math.round(s.n * 100 / total) + "%";
      counts.appendChild(row);
    });
  }

  function describe(dept) {
    if (!dept) {
      info.textContent = "Choose a department, or click one in the view, to see its UG and PG " +
        "programmes and the state of each programme's Curriculum, Syllabus and Course Revision.";
      return;
    }
    const at = dept.reached >= data.stages.length ? "Sealed" : data.stages[dept.reached].title;
    const ug = dept.programmes.filter(p => p.level === "UG").length;
    const pg = dept.programmes.filter(p => p.level === "PG").length;
    info.innerHTML = "";
    const h = document.createElement("strong");
    h.textContent = dept.name;
    info.appendChild(h);
    const p = document.createElement("div");
    p.textContent = `${dept.campus} · at ${at} · ${ug} UG, ${pg} PG programme${ug + pg === 1 ? "" : "s"}`;
    info.appendChild(p);
    if (!dept.programmes.length) {
      const q = document.createElement("div");
      q.className = "mt-1";
      q.textContent = "Programmes appear once Department Information has been saved.";
      info.appendChild(q);
    }
  }

  function select(code) {
    const dept = (data.departments || []).find(d => d.code === code) || null;
    picker.value = dept ? dept.code : "";
    deptSpheres.forEach(s => {
      const me = dept && s.userData.dept.code === dept.code;
      s.scale.setScalar(me ? 1.7 : 1);
      s.material.emissive = new THREE.Color(me ? 0xffe28a : 0x000000);
      s.material.emissiveIntensity = me ? 0.6 : 0;
    });
    buildTree(dept);
    describe(dept);
    if (mapBody.children.length) paintMap();
    if (dept) {
      controls.autoRotate = false;
      spinBtn.setAttribute("aria-pressed", "false");
      spinBtn.textContent = "Resume rotation";
      flyTo(new THREE.Vector3(STAGE_X[3] - 1, 14, 31), new THREE.Vector3(STAGE_X[3] - 1, 6, -2));
    }
  }

  // ------------------------------------------------------- mapping table
  const WORD = { submitted: "Submitted", draft: "In progress", returned: "Returned",
                 open: "Not started", locked: "Locked" };
  const PILL = { submitted: "pill-ok", draft: "pill-warn", returned: "pill-err",
                 open: "pill-lock", locked: "pill-lock" };
  const mapQ = document.getElementById("map-q");
  const mapStage = document.getElementById("map-stage");
  const mapBody = document.getElementById("map-body");
  const mapHead = document.getElementById("map-head");
  const mapCount = document.getElementById("map-count");

  function currentStage(d) {
    return d.reached >= data.stages.length ? "Sealed" : data.stages[d.reached].title;
  }

  function paintMap() {
    const q = mapQ.value.trim().toLowerCase();
    const at = mapStage.value;
    const rows = data.departments.filter(d =>
      (!q || [d.name, d.code, d.campus, d.school].join(" ").toLowerCase().includes(q)) &&
      (at === "" || String(Math.min(d.reached, data.stages.length)) === at));
    mapBody.textContent = "";
    rows.forEach(d => {
      const tr = document.createElement("tr");
      tr.tabIndex = 0;
      tr.className = "flow-map-row" + (picker.value === d.code ? " is-picked" : "");
      const td = (text, cls) => { const c = document.createElement("td"); if (cls) c.className = cls;
                                  c.textContent = text; tr.appendChild(c); return c; };
      const name = td("");
      const b = document.createElement("strong"); b.textContent = d.name; name.appendChild(b);
      const sm = document.createElement("small"); sm.className = "muted";
      sm.textContent = ` ${d.code} · ${d.campus}`; name.appendChild(sm);
      const cur = td("");
      const cp = document.createElement("span");
      cp.className = "pill " + (d.reached >= data.stages.length ? "pill-ok" : "pill-gold");
      cp.textContent = currentStage(d); cur.appendChild(cp);
      data.stages.forEach(s => {
        const c = td("");
        const st = d.statuses[s.key];
        const pl = document.createElement("span");
        pl.className = "pill " + (PILL[st] || "pill-lock");
        pl.textContent = WORD[st] || st; c.appendChild(pl);
      });
      const ug = d.programmes.filter(p => p.level === "UG").length;
      const pg = d.programmes.filter(p => p.level === "PG").length;
      td(String(ug), "num");
      td(String(pg), "num");
      const cells = d.programmes.flatMap(p => data.parts.map(k => p.parts[k.key]));
      const done = cells.filter(c => c === "submitted").length;
      td(cells.length ? `${done} / ${cells.length}` : "—", "num");
      const open = () => {
        select(d.code);
        document.getElementById("flow-canvas").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
      };
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
      mapBody.appendChild(tr);
    });
    if (!rows.length) {
      const tr = document.createElement("tr");
      const c = document.createElement("td");
      c.colSpan = 4 + data.stages.length + 1;
      c.className = "muted";
      c.textContent = "No department matches.";
      tr.appendChild(c); mapBody.appendChild(tr);
    }
    mapCount.textContent = `${rows.length} of ${data.departments.length} departments`;
  }

  function buildMap() {
    const h = document.createElement("tr");
    ["Department", "Current stage", ...data.stages.map(s => s.title), "UG", "PG", "Curriculum parts"]
      .forEach((x, i, all) => { const th = document.createElement("th"); th.textContent = x;
        if (i >= all.length - 3) th.className = "num"; h.appendChild(th); });
    mapHead.appendChild(h);
    data.stages.forEach((s, i) => mapStage.appendChild(new Option(`At ${s.title}`, String(i))));
    mapStage.appendChild(new Option("Sealed", String(data.stages.length)));
    mapQ.addEventListener("input", paintMap);
    mapStage.addEventListener("change", paintMap);
    paintMap();
  }

  // ------------------------------------------------------------ camera
  let fly = null;
  function flyTo(pos, target) {
    fly = { from: camera.position.clone(), to: pos, tf: controls.target.clone(), tt: target, t: 0 };
  }

  // -------------------------------------------------------- interaction
  const ray = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let hovered = null;

  function pick(ev) {
    const r = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    mouse.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(mouse, camera);
    const hit = ray.intersectObjects(hoverables, false)[0];
    return hit ? hit.object : null;
  }

  function tipText(o) {
    const u = o.userData;
    if (u.kind === "dept") {
      const at = u.dept.reached >= data.stages.length ? "Sealed" : data.stages[u.dept.reached].title;
      return [u.dept.name, `${u.dept.campus} · at ${at} · ${STATUS_WORD[u.status] || u.status}`];
    }
    if (u.kind === "part") return [`${u.prog.code} — ${u.part.title}`, `${u.prog.name} · ${STATUS_WORD[u.status] || u.status}`];
    if (u.kind === "stage") {
      const n = data.departments.filter(d => d.reached === u.index).length;
      return [`${u.stage.group}`, `${n} department${n === 1 ? "" : "s"} working here`];
    }
    if (u.kind === "sealed") {
      const n = data.departments.filter(d => d.reached >= data.stages.length).length;
      return ["Sealed", `${n} department${n === 1 ? "" : "s"} with every stage submitted`];
    }
    return null;
  }

  renderer.domElement.addEventListener("pointermove", ev => {
    if (!data) return;
    const o = pick(ev);
    hovered = o;
    renderer.domElement.style.cursor = o && o.userData.kind === "dept" ? "pointer" : "grab";
    const t = o && tipText(o);
    if (!t) { tip.hidden = true; return; }
    tip.hidden = false;
    tip.innerHTML = "";
    const b = document.createElement("strong"); b.textContent = t[0];
    const s = document.createElement("span"); s.textContent = t[1];
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
    if (o && o.userData.kind === "dept") select(o.userData.dept.code);
    else if (o && o.userData.kind === "part") {
      const u = o.userData;
      describe(u.dept);
      const line = document.createElement("div");
      line.className = "mt-1 flow-picked";
      line.textContent = `${u.prog.code} ${u.prog.name} — ${u.part.title}: ${STATUS_WORD[u.status] || u.status}`;
      info.appendChild(line);
    }
  });

  picker.addEventListener("change", () => select(picker.value));
  document.getElementById("flow-reset").addEventListener("click", () => {
    select("");
    flyTo(HOME.clone(), HOME_TARGET.clone());
  });
  const labelBtn = document.getElementById("flow-labels");
  labelBtn.addEventListener("click", () => {
    labelMode = LABEL_MODES[(LABEL_MODES.indexOf(labelMode) + 1) % LABEL_MODES.length];
    labelBtn.textContent = "Labels: " + labelMode;
    buildDepartments(data.departments);
    select(picker.value);
  });
  const spinBtn = document.getElementById("flow-spin");
  if (REDUCED) { spinBtn.setAttribute("aria-pressed", "false"); spinBtn.textContent = "Resume rotation"; }
  spinBtn.addEventListener("click", () => {
    controls.autoRotate = !controls.autoRotate;
    spinBtn.setAttribute("aria-pressed", String(controls.autoRotate));
    spinBtn.textContent = controls.autoRotate ? "Pause rotation" : "Resume rotation";
  });

  // ------------------------------------------------------------ sizing
  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  // -------------------------------------------------------------- loop
  const clock = new THREE.Clock();
  function tick() {
    const dt = Math.min(clock.getDelta(), 0.05);
    const time = clock.elapsedTime;
    if (curve && !REDUCED) {
      flowDots.forEach(d => {
        d.userData.t = (d.userData.t + dt * 0.06) % 1;
        d.position.copy(curve.getPointAt(d.userData.t));
      });
    } else if (curve) {
      flowDots.forEach(d => d.position.copy(curve.getPointAt(d.userData.t)));
    }
    if (!REDUCED) {
      deptSpheres.forEach((s, k) => {
        s.position.y = s.userData.home.y + Math.sin(time * 1.6 + k) * 0.06;
        const t = deptLabels[k];
        if (t) t.position.y = t.userData.base.y + Math.sin(time * 1.6 + k) * 0.06;
      });
    }
    if (tree && tree.userData.grow < 1) {
      tree.userData.grow = Math.min(1, tree.userData.grow + dt * (REDUCED ? 10 : 1.8));
      const e = 1 - Math.pow(1 - tree.userData.grow, 3);
      tree.scale.set(e, e, e);
      tree.position.set(STAGE_X[3] * (1 - e), 0, 0);
    }
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

  // -------------------------------------------------------------- data
  resize();
  fetch(window.FLOW_URL, { credentials: "same-origin" })
    .then(r => r.json())
    .then(j => {
      data = j;
      loading.remove();
      buildStages(j.stages);
      buildDepartments(j.departments);
      paintCounts(j.departments);
      j.departments.forEach(d => picker.appendChild(new Option(`${d.name} — ${d.campus}`, d.code)));
      buildMap();
      tick();
    })
    .catch(() => { loading.textContent = "The view could not load its data. Refresh to try again."; });
})();

/* Motion: the year so far as a short animated explainer, drawn on a canvas
   from window.MOTION_DATA (the same reading as the home page). Play, pause,
   seek, jump to a scene — and "Download video" records one play-through
   with the browser's own recorder (MP4 where it can, else WebM). Nothing
   is generated: every shape is a number from the portal's records, and
   every scene says where it came from. */
(function () {
  "use strict";
  const D = window.MOTION_DATA;
  const cv = document.getElementById("mo-canvas");
  if (!D || !cv) return;
  const ctx = cv.getContext("2d");
  const W = 1920, H = 1080, M = 120;
  const C = { navy: "#0e2a5c", blue: "#2563eb", green: "#16a34a", red: "#dc2626", amber: "#2563eb",
              grey: "#e4e7ec", ink: "#1f2937", muted: "#5b6474", line: "#eef0f3", soft: "#f5f7fb" };
  const FONT = '"Roboto", "Inter", "Segoe UI", system-ui, sans-serif';
  const asOf = (() => {
    try {
      return new Date(D.made).toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric",
                                                          hour: "2-digit", minute: "2-digit" });
    } catch (e) { return D.made; }
  })();

  // ---------------------------------------------------------------- helpers
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const at = (local, start, dur) => ease((local - start) / dur);
  function font(size, weight) { ctx.font = (weight || 400) + " " + size + "px " + FONT; }
  function text(s, x, y, size, color, weight, align, alpha) {
    font(size, weight);
    ctx.fillStyle = color;
    ctx.textAlign = align || "left";
    ctx.textBaseline = "alphabetic";
    ctx.globalAlpha = alpha === undefined ? 1 : alpha;
    ctx.fillText(s, x, y);
    ctx.globalAlpha = 1;
  }
  function spaced(s, x, y, size, color, weight, gap) {
    font(size, weight);
    ctx.fillStyle = color;
    ctx.textAlign = "left";
    let cx = x;
    for (const ch of s) { ctx.fillText(ch, cx, y); cx += ctx.measureText(ch).width + gap; }
  }
  function rrect(x, y, w, h, r, color) {
    if (w <= 0 || h <= 0) return;
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }
  function wrap(s, maxW, size, weight) {
    font(size, weight);
    const words = String(s).split(/\s+/), lines = [];
    let line = "";
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
    }
    if (line) lines.push(line);
    return lines;
  }
  const n0 = (x) => Math.round(x).toLocaleString();
  function heading(s, local, sub) {
    const a = at(local, 0, 600);
    text(s, M, 230 - 20 * (1 - a), 72, C.navy, 700, "left", a);
    if (sub) text(sub, M, 290 - 20 * (1 - a), 34, C.muted, 400, "left", a);
  }

  // ------------------------------------------------------------- the scenes
  const T = D.totals, n = T.departments || 0;
  const scenes = [
    { key: "title", label: "Title", dur: 4200, draw(l) {
      const a = at(l, 0, 700), b = at(l, 350, 800), c = at(l, 900, 800);
      ctx.globalAlpha = a;
      spaced("OFFICE OF ACADEMIC AFFAIRS", M, 380 - 20 * (1 - a), 30, C.blue, 700, 6);
      ctx.globalAlpha = 1;
      text("Board of Studies", M, 540 - 30 * (1 - b), 140, C.navy, 800, "left", b);
      text(D.year, M, 700 - 30 * (1 - c), 140, C.blue, 800, "left", c);
      rrect(M, 760, 520 * at(l, 1300, 900), 10, 5, C.navy);
      text("Where every department stands", M, 850, 46, C.muted, 400, "left", at(l, 1600, 700));
    } },
    { key: "overview", label: "Overview", dur: 6500, draw(l) {
      heading("At a glance", l, D.scope);
      const cx = 560, cy = 640, r = 250, p = at(l, 400, 1800);
      ctx.lineWidth = 46; ctx.lineCap = "round";
      ctx.strokeStyle = C.grey;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
      if (T.percent > 0) {
        ctx.strokeStyle = C.green;
        ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (T.percent / 100) * p); ctx.stroke();
      }
      text(n0(T.percent * p) + "%", cx, cy + 30, 120, C.navy, 800, "center");
      text("of all stages completed", cx, cy + 90, 32, C.muted, 400, "center");
      const rows = [
        [n0(T.stages_done * at(l, 900, 1500)) + " of " + n0(T.stages_total), "stages completed", C.navy],
        [n0(n * at(l, 1300, 1200)), "department" + (n === 1 ? "" : "s"), C.navy],
        [n0(T.complete * at(l, 1700, 1200)), "completed every stage", C.green],
        [n0(T.untouched * at(l, 2100, 1200)), "not started yet", T.untouched ? C.red : C.muted],
      ];
      rows.forEach((row, i) => {
        const a = at(l, 900 + i * 400, 700), y = 430 + i * 145;
        text(row[0], 1000 + 40 * (1 - a), y, 72, row[2], 800, "left", a);
        text(row[1], 1000 + 40 * (1 - a), y + 44, 30, C.muted, 400, "left", a);
      });
    } },
    { key: "stages", label: "Stage by stage", dur: 7000, draw(l) {
      heading("Stage by stage", l, "How many of the " + n + " department" + (n === 1 ? " has" : "s have") + " each stage");
      const legend = [["Completed", C.green], ["In progress", C.blue], ["Sent back", C.red], ["Not started", C.grey]];
      let lx = M;
      legend.forEach(([w, col]) => {
        ctx.globalAlpha = at(l, 300, 600);
        rrect(lx, 338, 24, 24, 6, col);
        text(w, lx + 36, 359, 28, C.muted, 500);
        font(28, 500); lx += 36 + ctx.measureText(w).width + 44;
        ctx.globalAlpha = 1;
      });
      const rows = D.stages, gap = Math.min(150, 560 / Math.max(1, rows.length));
      const x0 = 720, tw = 940;
      rows.forEach((s, i) => {
        const y = 440 + i * gap, a = at(l, 500 + i * 300, 600), g = at(l, 800 + i * 300, 1400);
        ctx.globalAlpha = a;
        rrect(M, y - 4, 52, 52, 12, C.soft);
        text(String(i + 1), M + 26, y + 34, 30, C.navy, 700, "center");
        const label = wrap(s.title, x0 - M - 110, 36, 600)[0];
        text(label, M + 76, y + 36, 36, C.ink, 600);
        rrect(x0, y, tw, 44, 22, C.grey);
        let sx = x0;
        [[s.done, C.green], [s.prog, C.blue], [s.back, C.red]].forEach(([v, col]) => {
          const w = n ? tw * v / n * g : 0;
          if (w > 0) { rrect(sx, y, w, 44, 22, col); sx += w; }
        });
        text(n0(s.done * g) + "/" + n, x0 + tw + 30, y + 36, 38, C.navy, 800);
        ctx.globalAlpha = 1;
      });
    } },
    { key: "programmes", label: "Programmes", dur: 5200, draw(l) {
      const P = D.programmes;
      heading("Programmes", l, "Completed: Curriculum, every batch's Syllabus and Course Revision submitted");
      if (!P.total) {
        text("No programmes mapped yet — they appear once departments save Department Information.", M, 560, 40,
             C.muted, 400, "left", at(l, 400, 700));
        return;
      }
      const g = at(l, 400, 1600);
      text(n0(P.complete * g), M, 560, 180, C.navy, 800);
      font(180, 800);
      const w0 = ctx.measureText(n0(P.complete * g)).width;
      text("/ " + P.total, M + w0 + 20, 560, 80, C.muted, 700);
      text("programmes completed", M, 620, 36, C.muted, 400);
      (P.levels || []).forEach((lv, i) => {
        const y = 760 + i * 120, a = at(l, 900 + i * 400, 700), gg = at(l, 1100 + i * 400, 1400);
        ctx.globalAlpha = a;
        text(lv.level, M, y + 34, 44, C.navy, 800);
        rrect(M + 140, y, 1100, 44, 22, C.grey);
        rrect(M + 140, y, 1100 * (lv.total ? lv.complete / lv.total : 0) * gg, 44, 22, C.green);
        text(n0(lv.complete * gg) + " of " + lv.total, M + 1280, y + 34, 38, C.navy, 700);
        ctx.globalAlpha = 1;
      });
    } },
    { key: "campus", label: "By campus", dur: 5600, draw(l) {
      heading("By campus", l, "Stages completed, as a share of each campus's stages");
      const rows = D.campus;
      if (!rows.length) { text("No departments yet.", M, 560, 40, C.muted, 400, "left", at(l, 400, 700)); return; }
      const gap = Math.min(130, 600 / rows.length);
      rows.forEach((c, i) => {
        const y = 400 + i * gap, a = at(l, 400 + i * 300, 600), g = at(l, 700 + i * 300, 1400);
        ctx.globalAlpha = a;
        text(wrap(c.name, 520, 38, 600)[0], M, y + 36, 38, C.ink, 600);
        rrect(700, y, 1000, 44, 22, C.grey);
        rrect(700, y, 1000 * c.percent / 100 * g, 44, 22, i === 0 && c.percent ? C.navy : C.blue);
        text(n0(c.percent * g) + "%", 1740, y + 36, 40, C.navy, 800);
        ctx.globalAlpha = 1;
      });
    } },
    { key: "activity", label: "Last 14 days", dur: 5200, draw(l) {
      const A = D.activity, all = A.reduce((s, d) => s + d.all, 0), sub = A.reduce((s, d) => s + d.submitted, 0);
      heading("The last 14 days", l, n0(all) + " update" + (all === 1 ? "" : "s") + " from departments · " +
              n0(sub) + " submission" + (sub === 1 ? "" : "s"));
      const peak = Math.max(1, ...A.map((d) => d.all)), x0 = M, w = (W - 2 * M) / A.length, base = 830, top = 420;
      ctx.strokeStyle = C.line; ctx.lineWidth = 2;
      (all ? [0, 0.5, 1] : [0]).forEach((f) => { ctx.beginPath(); ctx.moveTo(x0, base - (base - top) * f); ctx.lineTo(W - M, base - (base - top) * f); ctx.stroke(); });
      A.forEach((d, i) => {
        const g = at(l, 300 + i * 90, 900), h = (base - top) * d.all / peak * g, hs = (base - top) * d.submitted / peak * g;
        const bx = x0 + i * w + w * 0.18, bw = w * 0.64;
        if (h > 0) rrect(bx, base - h, bw, h, 10, C.blue);
        if (hs > 0) rrect(bx, base - hs, bw, hs, 10, C.green);
        text(d.day, bx + bw / 2, base + 42, 26, C.muted, 600, "center");
        text(d.date, bx + bw / 2, base + 74, 24, C.muted, 400, "center");
        if (d.all && d.all === peak) text(String(d.all), bx + bw / 2, base - h - 16, 30, C.navy, 800, "center", g);
      });
      if (!all) text("No saves, uploads or submissions in these 14 days.", W / 2, 640, 40, C.muted, 400, "center", at(l, 400, 700));
      ctx.globalAlpha = at(l, 600, 600);
      rrect(W - M - 520, 330, 24, 24, 6, C.blue); text("Updates", W - M - 484, 351, 26, C.muted, 500);
      rrect(W - M - 300, 330, 24, 24, 6, C.green); text("Submissions", W - M - 264, 351, 26, C.muted, 500);
      ctx.globalAlpha = 1;
    } },
    { key: "findings", label: "What it says", dur: 8500, draw(l) {
      heading("What the numbers say", l);
      let y = 380;
      (D.findings || []).slice(0, 4).forEach((f, i) => {
        const a = at(l, 500 + i * 1700, 800);
        const lines = wrap(f, W - 2 * M - 110, 40, 400).slice(0, 3);
        ctx.globalAlpha = a;
        ctx.fillStyle = C.navy;
        ctx.beginPath(); ctx.arc(M + 28, y - 12, 28, 0, Math.PI * 2); ctx.fill();
        text(String(i + 1), M + 28, y - 1, 30, "#fff", 700, "center", a);
        lines.forEach((ln, k) => text(ln, M + 90 + 30 * (1 - a), y + k * 54, 40, C.ink, 400, "left", a));
        ctx.globalAlpha = 1;
        y += lines.length * 54 + 56;
      });
    } },
    { key: "end", label: "End", dur: 3800, draw(l) {
      const a = at(l, 0, 700), b = at(l, 500, 700);
      text("Board of Studies " + D.year, W / 2, 470, 96, C.navy, 800, "center", a);
      rrect(W / 2 - 160 * a, 520, 320 * a, 8, 4, C.blue);
      text("Office of Academic Affairs · JAIN (Deemed-to-be University)", W / 2, 620, 40, C.muted, 400, "center", b);
      text("Every figure counted from the portal's records as of " + asOf, W / 2, 690, 32, C.muted, 400, "center", b);
    } },
  ];
  let total = 0;
  scenes.forEach((s) => { s.start = total; total += s.dur; });

  // ------------------------------------------------------------- one frame
  function frame(t) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);
    rrect(0, 0, W, 12, 0, C.navy);
    const i = Math.max(0, scenes.findIndex((s) => t < s.start + s.dur));
    const sc = scenes[i === -1 ? scenes.length - 1 : i], local = Math.min(t, total) - sc.start;
    // the frame around every scene: who, where it stands, where it came from
    spaced("BOS ACADEMIC PORTAL", M, 84, 24, C.navy, 700, 3);
    scenes.forEach((s, k) => rrect(W - M - (scenes.length - k) * 34, 66, 22, 8, 4, k <= i ? C.navy : C.grey));
    ctx.fillStyle = C.line; ctx.fillRect(M, H - 108, W - 2 * M, 2);
    text("Source: BoS Academic Portal records · as of " + asOf + " · " + D.scope, M, H - 58, 26, C.muted, 400);
    text(D.year, W - M, H - 58, 26, C.navy, 700, "right");
    // fade between scenes
    const fadeIn = clamp(local / 350), fadeOut = sc.key === "end" ? 1 : clamp((sc.dur - local) / 350);
    ctx.save();
    ctx.globalAlpha = 1;
    sc.draw(local);
    ctx.restore();
    const veil = 1 - Math.min(fadeIn, fadeOut);
    if (veil > 0) { ctx.fillStyle = "rgba(255,255,255," + veil + ")"; ctx.fillRect(0, 100, W, H - 220); }
    return i;
  }

  // -------------------------------------------------------------- controls
  const playBtn = document.getElementById("mo-play"), big = document.getElementById("mo-big");
  const seek = document.getElementById("mo-seek"), timeEl = document.getElementById("mo-time");
  const restart = document.getElementById("mo-restart"), chips = document.getElementById("mo-scenes");
  const recBtn = document.getElementById("mo-record"), recFlag = document.getElementById("mo-rec");
  const note = document.getElementById("mo-note");
  let t = 0, playing = false, last = 0, recording = null;
  const mmss = (ms) => { const s = Math.round(ms / 1000); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

  scenes.forEach((s) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "mo-chip"; b.textContent = s.label;
    b.addEventListener("click", () => { t = s.start + 1; render(); });
    chips.appendChild(b);
  });

  function render() {
    const i = frame(t);
    seek.value = String(Math.round(t / total * 1000));
    timeEl.textContent = mmss(t) + " / " + mmss(total);
    chips.querySelectorAll(".mo-chip").forEach((c, k) => c.classList.toggle("is-on", k === i));
    playBtn.classList.toggle("is-playing", playing);
    playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
    big.hidden = playing || !!recording || (t > 0 && t < total);
  }
  function tick(now) {
    if (!playing) return;
    t += Math.min(100, now - last);
    last = now;
    if (t >= total) {
      t = total; playing = false;
      if (recording) setTimeout(() => recording && recording.stop(), 400);
    }
    render();
    if (playing) requestAnimationFrame(tick);
  }
  function play() {
    if (t >= total) t = 0;
    playing = true; last = performance.now();
    render();
    requestAnimationFrame(tick);
  }
  function pause() { playing = false; render(); }
  playBtn.addEventListener("click", () => (playing ? pause() : play()));
  big.addEventListener("click", play);
  restart.addEventListener("click", () => { t = 0; if (!playing) render(); });
  seek.addEventListener("input", () => { t = Number(seek.value) / 1000 * total; render(); });

  // --------------------------------------------------------- download video
  function pickType() {
    const want = ["video/mp4;codecs=avc1.42E01E", "video/mp4;codecs=avc1", "video/mp4",
                  "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
    return want.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) || "";
  }
  recBtn.addEventListener("click", () => {
    if (recording) return;
    const type = pickType();
    if (!cv.captureStream || !window.MediaRecorder || !type) {
      note.textContent = "This browser cannot record the animation. Use a recent Chrome, Edge or Firefox to download it.";
      return;
    }
    const stream = cv.captureStream(30);
    const chunks = [];
    const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8000000 });
    recording = rec;
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      const ext = type.indexOf("mp4") >= 0 ? "mp4" : "webm";
      const blob = new Blob(chunks, { type: type.split(";")[0] });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "BoS-Motion-" + String(D.year).replace(/–/g, "-") + "." + ext;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 60000);
      recording = null;
      recFlag.hidden = true;
      [recBtn, playBtn, restart, seek].forEach((x) => (x.disabled = false));
      note.textContent = "Downloaded as " + ext.toUpperCase() + " (" + Math.round(blob.size / 1024) + " KB).";
      render();
    };
    [recBtn, playBtn, restart, seek].forEach((x) => (x.disabled = true));
    recFlag.hidden = false;
    t = 0;
    rec.start(500);
    play();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && recording) note.textContent = "Recording pauses while this tab is hidden — keep it in front until it finishes.";
  });

  // first frame once the fonts are in, so the text is drawn in them
  render();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (!playing) render(); });
  window.__motion = { total, scenes: scenes.map((s) => s.key), seek(ms) { t = ms; render(); } };
})();

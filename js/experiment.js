/*
 * SALT human study: experiment logic. Plain JavaScript, no library (rewritten 13 Oct. 2026; jsPsych is no longer used,
 * because the browser's back button has to move between rounds).
 *
 * One round = one SAE neuron: the 9 images that activate it most, the 9 that activate it least and, depending on the
 * condition, a name for it. The participant clicks (or taps, or picks with the arrow keys) which of two new images
 * matches it. One screen per round: no confidence rating and no feedback.
 *
 * Draw. Every session draws its own neurons with a seeded generator (the seed is saved): config.nTest test neurons, the
 * same number from each stratum cell of the manifest, plus all practice neurons (the first rounds) and all catch neurons
 * (one per block of test rounds). Conditions (config.conditions) are balanced within the session and within each cell.
 * Which candidate goes first (left, or top) is random.
 *
 * Codes. Images are named by opaque codes (<neuron>-<image>.jpg, stimuli_gen/encode_stimuli.py). The manifest does not
 * say which candidate is correct, so neither does the page: answers are scored offline with the private codebook
 * (stimuli_gen/decode_responses.py). With ?debug=1 the answer key (debug_key.json) is also loaded for the debug banner.
 *
 * Navigation. Every screen is an entry of the browser history: back and forward move between rounds (an earlier answer
 * can be changed; the first answer is kept in the data). The progress is also kept in localStorage, so a reload or a
 * closed tab resumes the session where it stopped (48 h, same stimulus version).
 *
 * Layout. Wide windows show the reference images in two rows of 9 and the candidates side by side (arrow keys left /
 * right); tall windows and phones show them in two columns of 9 with the candidates one above the other (keys up / down).
 *
 * Data. One row per round plus one session row, saved at the end as CSV through DataPipe (config.datapipeExperimentId).
 * config.responseEndpoint, if set, also receives every answer as it is given and the whole session at the end.
 */
"use strict";

const EXP_VERSION = "3.0.0";
const CFG = window.EXP_CONFIG || {};
const TX = window.EXP_TEXTS || {};
const CONDS = CFG.conditions || ["A", "B", "D"];
const APP = "salt-study";                       // marker of our browser-history entries
const STORE = "salt-study-session";             // localStorage key: one session per browser
const STORE_MAX_AGE_MS = 48 * 3600 * 1000;
const LOCK_MS = 250;                            // answers are ignored during the first 250 ms of a round
const NEXT_MS = 180;                            // the chosen image stays highlighted this long
const AHEAD = 6;                                // rounds preloaded ahead of the current one

// Session state. Screens: 0 = introduction, 1..R = rounds, R + 1 = questionnaire, R + 2 = end.
const S = {
  stimDir: "stimuli", manifest: null, key: null,
  sid: null, seed: null, started: null, plan: [], answers: [], events: [],
  consent: false, frontier: 0, screen: 0, finished: false, saved: null, questionnaire: null, endIso: null,
  nBack: 0, nResume: 0, nBlur: 0,
  histPos: 0, histTop: 0, pendingGo: null,
  layout: "row", ready: false, busy: false, saving: false, onset: 0, token: 0, roundBlur: 0, lastPointer: "mouse",
  onLayoutChange: null
};
const PERSISTED = ["sid", "seed", "started", "plan", "answers", "events", "consent", "frontier", "finished", "saved",
  "questionnaire", "endIso", "nBack", "nResume", "nBlur"];

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

// Read a text key such as "ui.startButton". Missing keys log a warning and fall back to a plain default.
function tx(path, fallback) {
  let v = TX;
  for (const k of path.split(".")) {
    if (v === null || v === undefined || typeof v !== "object" || !(k in v)) {
      console.warn("[experiment] missing text key: " + path);
      return fallback;
    }
    v = v[k];
  }
  return v === null || v === undefined ? fallback : v;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function cleanName(name) {
  return String(name).replace(/_/g, " ");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function val(x) {
  return x === undefined || x === null ? "" : x;
}

function app() {
  return document.getElementById("app");
}

function nRounds() {
  return S.plan.length;
}

function isRound(s) {
  return s >= 1 && s <= nRounds();
}

function showFatal(html) {
  app().innerHTML = '<div class="page fatal">' + html + "</div>";
}

// Seeded generator (mulberry32): the same seed gives the same draw.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(a, rng) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const t = a[i]; a[i] = a[j]; a[j] = t;
  }
  return a;
}

function randomUint32() {
  try {
    const u = new Uint32Array(1);
    window.crypto.getRandomValues(u);
    return u[0];
  } catch (e) {
    return Math.floor(Math.random() * 4294967296);
  }
}

function randomId(n) {
  const A = "23456789abcdefghjkmnpqrstuvwxyz";
  let s = "";
  for (let i = 0; i < n; i++) s += A[randomUint32() % A.length];
  return s;
}

function toast(html) {
  if (!html) return;
  const t = document.createElement("div");
  t.className = "toast";
  t.setAttribute("role", "status");
  t.innerHTML = html;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("is-out"), 4000);
  setTimeout(() => t.remove(), 4600);
}

/* ------------------------------------------------------------------ */
/* Stimuli                                                             */
/* ------------------------------------------------------------------ */

function stimFolder() {
  // ?stim=<folder> and ?proto=<x> are honoured in debug only.
  if (!CFG.debug) return "stimuli";
  if (CFG.stimOverride) return CFG.stimOverride;
  const s = new URLSearchParams(window.location.search).get("stim");
  if (s && /^[A-Za-z0-9_-]+$/.test(s)) return s;
  return "stimuli";
}

async function fetchJson(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
  return r.json();
}

// Image files keep their code across versions when the image is unchanged; the version in the URL makes sure a browser
// never shows an image cached from another stimulus version.
function imgUrl(code) {
  return S.stimDir + "/img/" + code + ".jpg?v=" + encodeURIComponent(S.manifest.version || "0");
}

function roundImages(r) {
  const N = S.manifest.neurons[r.neuron];
  return N.top.concat(N.bottom, [r.img1, r.img2]).map(imgUrl);
}

function validateStimuli(m) {
  const errs = [];
  if (!m || typeof m !== "object" || m.format !== 2) return ["manifest.json must be format 2 (stimuli_gen/encode_stimuli.py)"];
  const cells = Array.isArray(m.cells) ? m.cells : [];
  if (!cells.length) errs.push("manifest.cells is empty");
  else if (CFG.nTest % cells.length) errs.push("config.nTest (" + CFG.nTest + ") is not a multiple of the " + cells.length + " cells");
  else cells.forEach((c, i) => {
    if (!Array.isArray(c) || c.length < CFG.nTest / cells.length) errs.push("cell " + i + " holds fewer than " + CFG.nTest / cells.length + " neurons");
  });
  if (!Array.isArray(m.practice) || !Array.isArray(m.catch)) errs.push("manifest.practice and manifest.catch must be lists");
  const ids = cells.flat().concat(m.practice || [], m.catch || []);
  if (new Set(ids).size !== ids.length) errs.push("a neuron is listed twice");
  const named = CONDS.filter((c) => c !== "A");
  for (const id of ids) {
    const a = (m.neurons || {})[id];
    if (!a) { errs.push("unknown neuron " + id); continue; }
    if (!Array.isArray(a.top) || a.top.length !== 9) errs.push(id + ": top must hold 9 image codes");
    if (!Array.isArray(a.bottom) || a.bottom.length !== 9) errs.push(id + ": bottom must hold 9 image codes");
    if (!Array.isArray(a.pair) || a.pair.length !== 2) errs.push(id + ": pair must hold 2 image codes");
    for (const c of named) {
      if (!a.names || typeof a.names[c] !== "string" || !a.names[c].trim()) errs.push(id + ": empty name " + c);
    }
  }
  return errs;
}

/* ------------------------------------------------------------------ */
/* Draw of the session                                                 */
/* ------------------------------------------------------------------ */

function withPair(rounds, rng) {
  return rounds.map((r, i) => {
    const pair = S.manifest.neurons[r.neuron].pair;
    const flip = rng() < 0.5;
    return { round: i + 1, phase: r.type === "practice" ? "practice" : "test", type: r.type, neuron: r.neuron,
             cond: CFG.debugCond || r.cond, img1: pair[flip ? 1 : 0], img2: pair[flip ? 0 : 1] };
  });
}

function makePlan(seed) {
  const rng = mulberry32(seed);
  const M = S.manifest;
  const NC = CONDS.length;
  const order = shuffle(CONDS.slice(), rng);      // which conditions receive the rounds left over after an even split
  const per = CFG.nTest / M.cells.length;
  let extra = 0;
  const test = [];
  M.cells.forEach((cell) => {
    const ids = shuffle(cell.slice(), rng).slice(0, per);
    const conds = [];
    for (let k = 0; k < Math.floor(per / NC); k++) conds.push(...CONDS);
    for (let k = 0; k < per % NC; k++) conds.push(order[extra++ % NC]);
    shuffle(conds, rng);
    ids.forEach((id, i) => test.push({ neuron: id, type: "test", cond: conds[i] }));
  });
  // Test rounds in blocks, one catch round per block; the first test round is never a catch round.
  const catches = shuffle(M.catch.slice(), rng).map((id, k) => ({ neuron: id, type: "catch", cond: order[k % NC] }));
  const T = shuffle(test, rng);
  const nB = Math.max(1, catches.length);
  const blocks = [];
  for (let b = 0; b < nB; b++) {
    const blk = T.slice(Math.round((b * T.length) / nB), Math.round(((b + 1) * T.length) / nB));
    if (catches[b]) blk.push(catches[b]);
    blocks.push(shuffle(blk, rng));
  }
  if (blocks[0].some((r) => r.type !== "catch")) {
    while (blocks[0][0].type === "catch") shuffle(blocks[0], rng);
  }
  // Practice rounds first (not announced), conditions balanced.
  const P = shuffle(M.practice.slice(), rng);
  const pConds = shuffle(P.map((_, i) => order[i % NC]), rng);
  const practice = P.map((id, i) => ({ neuron: id, type: "practice", cond: pConds[i] }));
  return withPair(practice.concat(blocks.flat()), rng);
}

// Debug browser with &all=1: every neuron of the set, conditions cycled.
function makeAllPlan(seed) {
  const M = S.manifest;
  const kind = (id) => (M.practice.includes(id) ? "practice" : M.catch.includes(id) ? "catch" : "test");
  const ids = M.practice.concat(...M.cells, M.catch);
  return withPair(ids.map((id, i) => ({ neuron: id, type: kind(id), cond: CONDS[i % CONDS.length] })), mulberry32(seed));
}

/* ------------------------------------------------------------------ */
/* Saved progress (localStorage)                                       */
/* ------------------------------------------------------------------ */

function storageOn() {
  return !CFG.debug || CFG.resume;
}

function persist() {
  if (!storageOn() || !S.manifest || !S.sid) return;
  const x = { app: APP, exp: EXP_VERSION, v: S.manifest.version, stim: S.stimDir, t: Date.now() };
  for (const k of PERSISTED) x[k] = S[k];
  try {
    localStorage.setItem(STORE, JSON.stringify(x));
  } catch (e) {
    /* storage full or disabled: the session still runs, without resume */
  }
}

function restore() {
  if (!storageOn()) return null;
  try {
    const x = JSON.parse(localStorage.getItem(STORE) || "null");
    if (!x || x.app !== APP || x.exp !== EXP_VERSION || x.v !== S.manifest.version || x.stim !== S.stimDir) return null;
    if (!(Date.now() - x.t < STORE_MAX_AGE_MS)) return null;
    if (!Array.isArray(x.plan) || !x.plan.length || x.plan.some((r) => !S.manifest.neurons[r.neuron])) return null;
    return x;
  } catch (e) {
    return null;
  }
}

/* ------------------------------------------------------------------ */
/* Screens and browser history                                         */
/* ------------------------------------------------------------------ */

// Show screen s. mode "push": new history entry; "replace": rewrite the current one.
function go(s, mode) {
  try {
    if (mode === "push") history.pushState({ app: APP, s: s }, "");
    else if (mode === "replace") history.replaceState({ app: APP, s: s }, "");
  } catch (e) {
    /* sandboxed frame: navigation still works inside the page */
  }
  S.histTop = s;
  S.histPos = s;
  S.screen = s;
  render();
  persist();
}

// Forward move after an answer. When the participant came back with the back button, the later screens are still in
// the browser history: step forward through it (popstate shows the screen), so that the forward button keeps working.
function moveTo(target) {
  if (target > S.histPos && target <= S.histTop) {
    S.pendingGo = target;
    history.go(target - S.histPos);
    setTimeout(() => {
      if (S.pendingGo === target) { S.pendingGo = null; go(target, "push"); }   // no popstate came
    }, 1500);
  } else {
    go(target, "push");
  }
}

function onPopState(e) {
  const st = e.state;
  if (!st || st.app !== APP || typeof st.s !== "number") return;
  closeInfo();
  const expected = S.pendingGo !== null && st.s === S.pendingGo;
  S.pendingGo = null;
  S.histPos = st.s;
  if (S.saving) return;                                     // keep the saving screen
  if (S.finished) { S.screen = nRounds() + 2; render(); return; }   // once saved, the end page stays
  if (!expected && st.s < S.screen) S.nBack += 1;
  S.screen = Math.max(0, Math.min(st.s, S.frontier, nRounds() + 1));
  render();
  persist();
}

function render() {
  S.token += 1;
  S.ready = false;
  S.busy = false;
  S.roundBlur = 0;
  document.body.classList.toggle("on-round", isRound(S.screen) && !S.finished);
  updateProgress();
  try { window.scrollTo(0, 0); } catch (e) { /* not available (headless) */ }
  const R = nRounds();
  if (S.finished || S.screen > R + 1) return renderEnd();
  if (S.screen === 0) return renderIntro();
  if (S.screen <= R) return renderRound(S.screen - 1);
  return renderQuestionnaire();
}

function updateProgress() {
  const bar = document.getElementById("progress");
  if (!bar) return;
  const R = nRounds();
  bar.hidden = !(isRound(S.screen) && !S.finished);
  const done = S.answers.filter(Boolean).length;
  bar.firstElementChild.style.width = (R ? Math.round((100 * done) / R) : 0) + "%";
}

// The layout follows the window shape: portrait windows (phones, narrow windows) get the 9 x 2 column layout.
function updateLayout() {
  const col = window.innerWidth < window.innerHeight;
  document.body.classList.toggle("layout-col", col);
  document.body.classList.toggle("layout-row", !col);
  const L = col ? "col" : "row";
  if (L !== S.layout) {
    S.layout = L;
    if (S.onLayoutChange) S.onLayoutChange();
  }
}

/* ------------------------------------------------------------------ */
/* Introduction                                                        */
/* ------------------------------------------------------------------ */

function renderIntro() {
  app().innerHTML = '<form class="page intro" id="intro-form">' + tx("introHtml", "") +
    '<div class="page-actions"><button type="submit" class="btn btn-primary">' + esc(tx("ui.startButton", "Start")) + "</button></div></form>";
  const f = document.getElementById("intro-form");
  const box = f.querySelector("#agree");
  if (box && S.consent) box.checked = true;
  f.addEventListener("submit", (e) => {
    e.preventDefault();
    if (box && !box.checked) return;               // the required checkbox already blocks the form
    S.consent = true;
    if (!S.started) S.started = new Date().toISOString();
    if (S.frontier < 1) S.frontier = 1;
    moveTo(S.frontier);
  });
  preloadAhead(0);
}

/* ------------------------------------------------------------------ */
/* Rounds                                                              */
/* ------------------------------------------------------------------ */

// Small "i" button that opens a detailed explanation (texts.js `info`).
function infoBtn(key) {
  return '<button type="button" class="info-btn" data-info="' + key + '" aria-label="' + esc(tx("ui.infoButton", "More information")) + '">i</button>';
}

function roundHtml(r, o) {
  const N = S.manifest.neurons[r.neuron];
  const name = r.cond === "A" ? null : N.names[r.cond];
  const pic = (code, cls) => '<img class="' + cls + '" src="' + esc(imgUrl(code)) + '" alt="" draggable="false">';
  const block = (cls, codes, which, info) =>
    '<section class="ref-block ' + cls + '">' +
    '<div class="ref-label"><span class="lab-long">' + tx("referenceLabels." + which, "") + '</span><span class="lab-short">' +
    tx("referenceLabels." + which + "Short", "") + "</span>" + infoBtn(info) + "</div>" +
    '<div class="ref-grid">' + codes.map((c) => pic(c, "ref-img")).join("") + "</div></section>";
  const cand = (slot, code) =>
    '<button type="button" class="query-btn' + (o.chosenSlot === slot ? " is-chosen" : "") + '" data-slot="' + slot +
    '" data-label="' + esc(tx("ui.yourAnswer", "Your answer")) + '" aria-label="' + esc(tx(slot === 1 ? "ui.firstImage" : "ui.secondImage", "")) + '">' +
    pic(code, "query-img") + "</button>";
  return '<div class="trial">' + (o.badge || "") +
    (name
      ? '<div class="concept-name"><span class="concept-label">' + tx("nameLabel", "This concept:") + '</span> <strong class="concept-name-value">' +
        esc(cleanName(name)) + "</strong>" + infoBtn("name") + "</div>"
      : "") +
    '<div class="refs">' + block("ref-high", N.top, "high", "refsHigh") + block("ref-low", N.bottom, "low", "refsLow") + "</div>" +
    '<div class="choice"><div class="trial-prompt">' + tx("trialPrompt", "Which image matches this concept?") + infoBtn("question") + "</div>" +
    '<div class="query-pair">' + cand(1, r.img1) + cand(2, r.img2) + "</div>" +
    '<div class="key-hint" aria-hidden="true"><span class="hint-row">' + tx("ui.keyHintRow", "") + '</span><span class="hint-col">' +
    tx("ui.keyHintCol", "") + "</span></div>" +
    "</div>" + '<div class="trial-loading">' + tx("ui.loadingHtml", "") + "</div></div>";
}

// Resolves once every image has loaded (or failed), then decoded, or after maxMs.
function whenLoaded(imgs, maxMs) {
  const one = (im) => (im.complete ? Promise.resolve() : new Promise((res) => {
    im.addEventListener("load", res, { once: true });
    im.addEventListener("error", res, { once: true });
  }));
  const dec = (im) => (im.decode && im.naturalWidth ? im.decode().catch(() => {}) : null);
  return Promise.race([Promise.all(imgs.map(one)), sleep(maxMs || 20000)])
    .then(() => Promise.race([Promise.all(imgs.map(dec)), sleep(1500)]));
}

function renderRound(idx) {
  const r = S.plan[idx];
  const prev = S.answers[idx];
  const token = S.token;
  app().innerHTML = roundHtml(r, { badge: CFG.debug ? debugBadge(r, prev ? prev.slot : null) : "", chosenSlot: prev ? prev.slot : null });
  const trial = app().querySelector(".trial");
  trial.querySelectorAll(".query-btn").forEach((b) => {
    b.addEventListener("click", (e) => choose(+b.dataset.slot, e.detail === 0 ? "keyboard" : S.lastPointer));
  });
  const imgs = Array.from(trial.querySelectorAll("img"));
  const slow = setTimeout(() => { if (token === S.token) trial.classList.add("is-loading"); }, 400);
  whenLoaded(imgs).then(() => {
    if (token !== S.token) return;
    clearTimeout(slow);
    trial.classList.remove("is-loading");
    trial.classList.add("is-shown");                 // all images appear together
    const shown = performance.now();
    setTimeout(() => {
      if (token !== S.token) return;
      S.onset = shown;                               // response times start when the images are on screen
      S.ready = true;
      trial.classList.add("is-ready");
    }, LOCK_MS);
  });
  preloadAhead(idx + 1);
}

function choose(slot, input) {
  if (!S.ready || S.busy || !isRound(S.screen) || S.finished) return;
  S.busy = true;
  const token = S.token;
  const idx = S.screen - 1;
  const r = S.plan[idx];
  const rt = Math.round(performance.now() - S.onset);
  const img = slot === 1 ? r.img1 : r.img2;
  const iso = new Date().toISOString();
  let a = S.answers[idx];
  if (!a) {
    a = S.answers[idx] = { first_slot: slot, first_img: img, first_rt_ms: rt, first_iso: iso, n_answers: 0, n_changes: 0, n_blur: 0 };
  } else if (a.slot !== slot) {
    a.n_changes += 1;
  }
  const broken = Array.from(app().querySelectorAll(".trial img")).filter((im) => !im.naturalWidth).length;
  Object.assign(a, { slot: slot, img: img, rt_ms: rt, input: input, layout: S.layout, iso: iso, n_answers: a.n_answers + 1,
                     n_blur: a.n_blur + S.roundBlur, n_img_errors: broken, window_w: window.innerWidth, window_h: window.innerHeight });
  S.events.push([r.round, slot, rt, input, S.layout, iso]);
  const atFrontier = S.screen === S.frontier;
  if (atFrontier) S.frontier = S.screen + 1;
  const target = atFrontier ? S.screen + 1 : S.frontier;   // after a change on an earlier round, back to where the participant was
  persist();
  sendAnswer(idx);
  updateProgress();
  app().querySelectorAll(".query-btn").forEach((b) => {
    b.classList.remove("is-chosen");
    b.classList.toggle("is-picked", +b.dataset.slot === slot);
  });
  setTimeout(() => { if (token === S.token) moveTo(target); }, NEXT_MS);
}

function onKey(e) {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || isInfoOpen()) return;
  if (!isRound(S.screen) || S.finished) return;
  let slot = null;
  if (S.layout === "row") {
    if (e.key === "ArrowLeft") slot = 1;
    else if (e.key === "ArrowRight") slot = 2;
  } else {
    if (e.key === "ArrowUp") slot = 1;
    else if (e.key === "ArrowDown") slot = 2;
  }
  if (slot === null) return;
  e.preventDefault();
  if (!e.repeat) choose(slot, "key");
}

/* ------------------------------------------------------------------ */
/* Preloading: the current round and the next AHEAD rounds, 6 at a time */
/* ------------------------------------------------------------------ */

const PRE = new Map();       // url -> Image (kept so the browser keeps the file in its memory cache)
const QUEUE = [];
let preActive = 0;

function pump() {
  while (preActive < 6 && QUEUE.length) {
    const u = QUEUE.shift();
    const im = new Image();
    preActive += 1;
    const done = () => { preActive -= 1; pump(); };
    im.onload = done;
    im.onerror = done;
    im.src = u;
    PRE.set(u, im);
  }
}

function preloadAhead(idx) {
  for (let i = Math.max(0, idx); i < Math.min(nRounds(), idx + AHEAD + 1); i++) {
    for (const u of roundImages(S.plan[i])) {
      if (!PRE.has(u)) { PRE.set(u, null); QUEUE.push(u); }
    }
  }
  pump();
}

/* ------------------------------------------------------------------ */
/* Questionnaire, saving, end                                          */
/* ------------------------------------------------------------------ */

function questionHtml(q) {
  const id = "q_" + q.name;
  let field;
  if (q.type === "multi-choice") {
    field = '<div class="q-options" role="radiogroup">' + (q.options || []).map((o, i) =>
      '<label class="q-option"><input type="radio" name="' + esc(q.name) + '" id="' + id + "_" + i +
      '" value="' + esc(o) + '" required> <span>' + esc(o) + "</span></label>").join("") + "</div>";
  } else {
    field = '<textarea name="' + esc(q.name) + '" id="' + id + '" rows="3" required></textarea>';
  }
  return '<div class="q-item"><p class="q-prompt">' + q.prompt + "</p>" + field + "</div>";
}

function readForm(f, qs) {
  const out = {};
  for (const q of qs) {
    const el = f.elements[q.name];
    out[q.name] = el ? (el.value || "") : "";
  }
  return out;
}

function renderQuestionnaire() {
  const qs = tx("questionnaire", []);
  app().innerHTML = '<form class="page questionnaire" id="q-form">' + tx("questionnaireIntroHtml", "") + qs.map(questionHtml).join("") +
    '<div class="page-actions"><button type="submit" class="btn btn-primary">' + esc(tx("ui.submitButton", "Submit")) + "</button></div></form>";
  const f = document.getElementById("q-form");
  const d = S.questionnaire || {};
  for (const q of qs) {                            // answers typed before a back / forward move, or before a reload
    if (!(q.name in d) || !d[q.name]) continue;
    if (q.type === "multi-choice") {
      f.querySelectorAll('input[name="' + q.name + '"]').forEach((el) => { el.checked = el.value === d[q.name]; });
    } else if (f.elements[q.name]) {
      f.elements[q.name].value = d[q.name];
    }
  }
  f.addEventListener("input", () => { S.questionnaire = readForm(f, qs); persist(); });
  f.addEventListener("change", () => { S.questionnaire = readForm(f, qs); persist(); });
  f.addEventListener("submit", (e) => {
    e.preventDefault();
    S.questionnaire = readForm(f, qs);
    finish();
  });
}

async function finish() {
  S.saving = true;
  S.frontier = nRounds() + 2;
  S.endIso = new Date().toISOString();
  persist();
  document.body.classList.remove("on-round");
  app().innerHTML = '<div class="page">' + tx("ui.savingHtml", "<p>Saving...</p>") + "</div>";
  S.saved = await saveSession();
  S.saving = false;
  S.finished = true;
  go(nRounds() + 2, "replace");
}

function renderEnd() {
  const failed = S.saved === false;
  app().innerHTML = '<div class="page end">' +
    (failed ? '<div class="save-error">' + tx("ui.saveErrorHtml", "") + '<div class="page-actions"><button type="button" class="btn btn-primary" id="retry">' +
      esc(tx("ui.retryButton", "Try again")) + "</button></div></div>" : "") +
    tx("endHtml", "<p>Thank you.</p>") + (CFG.debug ? debugSummaryHtml() : "") + "</div>";
  const b = document.getElementById("retry");
  if (b) {
    b.addEventListener("click", async () => {
      b.disabled = true;
      S.saved = await saveSession();
      persist();
      render();
    });
  }
}

/* ------------------------------------------------------------------ */
/* Data                                                                */
/* ------------------------------------------------------------------ */

function sessionFields() {
  return { subject_id: S.sid, seed: S.seed, exp_version: EXP_VERSION, stimuli: S.stimDir, manifest_version: S.manifest.version,
           debug: !!CFG.debug, start_iso: S.started };
}

// One row per round. img_1 / img_2: the two candidates, first = left (layout "row") or top (layout "col");
// chosen_img: the final answer, first_img: the first one (they differ only if the participant came back and changed it).
function roundRow(idx) {
  const r = S.plan[idx];
  const a = S.answers[idx] || {};
  const name = r.cond === "A" ? "" : cleanName(S.manifest.neurons[r.neuron].names[r.cond] || "");
  return Object.assign({ row_type: "round" }, sessionFields(), {
    round: r.round, phase: r.phase, item_type: r.type, neuron: r.neuron, condition: r.cond, name_shown: name,
    img_1: r.img1, img_2: r.img2, chosen_slot: val(a.slot), chosen_img: val(a.img), rt_ms: val(a.rt_ms),
    first_slot: val(a.first_slot), first_img: val(a.first_img), first_rt_ms: val(a.first_rt_ms),
    n_answers: val(a.n_answers), n_changes: val(a.n_changes), input: val(a.input), layout: val(a.layout),
    n_blur: val(a.n_blur), n_img_errors: val(a.n_img_errors), window_w: val(a.window_w), window_h: val(a.window_h),
    first_iso: val(a.first_iso), answer_iso: val(a.iso)
  });
}

function sessionRow() {
  const q = S.questionnaire || {};
  const row = Object.assign({ row_type: "session" }, sessionFields(), {
    end_iso: S.endIso, n_rounds: nRounds(), n_answered: S.answers.filter(Boolean).length,
    n_back: S.nBack, n_resume: S.nResume, n_blur_total: S.nBlur,
    screen_w: window.screen ? window.screen.width : "", screen_h: window.screen ? window.screen.height : "",
    window_w: window.innerWidth, window_h: window.innerHeight, dpr: window.devicePixelRatio || 1,
    touch: (navigator.maxTouchPoints || 0) > 0, user_agent: navigator.userAgent, events: JSON.stringify(S.events)
  });
  for (const item of tx("questionnaire", [])) row["q_" + item.name] = val(q[item.name]);
  return row;
}

function toCsv(rows) {
  const cols = [];
  rows.forEach((r) => Object.keys(r).forEach((k) => { if (!cols.includes(k)) cols.push(k); }));
  const cell = (v) => {
    const s = String(val(v));
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  return [cols.join(",")].concat(rows.map((r) => cols.map((c) => cell(r[c])).join(","))).join("\n") + "\n";
}

function buildCsv() {
  return toCsv(S.plan.map((_, i) => roundRow(i)).concat([sessionRow()]));
}

async function pipeSave(id, filename, data) {
  try {
    const r = await fetch("https://pipe.jspsych.org/api/data/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "*/*" },
      body: JSON.stringify({ experimentID: id, filename: filename, data: data })
    });
    const j = await r.json();
    return !!j && typeof j === "object" && !j.error;
  } catch (e) {
    return false;
  }
}

// text/plain avoids a CORS preflight; the server parses the JSON body.
async function postText(url, body) {
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "text/plain;charset=UTF-8" }, body: body });
    return r.ok;
  } catch (e) {
    return false;
  }
}

function sendAnswer(idx) {
  if (!CFG.responseEndpoint || CFG.debug) return;
  const body = JSON.stringify({ kind: "answer", row: roundRow(idx) });
  try {
    if (navigator.sendBeacon && navigator.sendBeacon(CFG.responseEndpoint, new Blob([body], { type: "text/plain;charset=UTF-8" }))) return;
  } catch (e) {
    /* fall back to fetch */
  }
  postText(CFG.responseEndpoint, body);
}

function download(text, name) {
  try {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (e) {
    console.warn("[experiment] download failed", e);
  }
}

async function saveSession() {
  const csv = buildCsv();
  const stamp = String(S.started || new Date().toISOString()).replace(/[-:]/g, "").replace(/\..*$/, "");
  const filename = S.sid + "_" + stamp + ".csv";
  if (CFG.debug) {                                  // debug: nothing is sent, the file is downloaded
    download(csv, "debug_" + filename);
    return true;
  }
  let ok = false;
  if (CFG.responseEndpoint) {
    ok = await postText(CFG.responseEndpoint, JSON.stringify({ kind: "session", filename: filename, csv: csv }));
  }
  const id = CFG.datapipeExperimentId;
  if (id && !/^DATAPIPE_/.test(id)) {
    for (let k = 0; k < 3; k++) {
      if (await pipeSave(id, filename, csv)) { ok = true; break; }
      await sleep(2000);
    }
  }
  return ok;
}

/* ------------------------------------------------------------------ */
/* Debug (never shown to participants)                                 */
/* ------------------------------------------------------------------ */

const DEBUG_SOURCE = {
  A: { cls: "dbg-a", label: "AUCUN NOM — images seules (condition A)" },
  B: { cls: "dbg-b", label: "NOM SALT — le vrai nom SALT de cet atome (condition B)" },
  C: { cls: "dbg-c", label: "NOM SALT PERMUTÉ — nom SALT d'un AUTRE atome, donc faux (condition C)" },
  D: { cls: "dbg-d", label: "NOM CLIP-DISSECT — le nom CLIP-Dissect de cet atome (condition D)" }
};

function keyOf(r) {
  return S.key && S.key.neurons ? S.key.neurons[r.neuron] || null : null;
}

function posSlotOf(r) {
  const k = keyOf(r);
  if (!k) return null;
  return k.pos === r.img1 ? 1 : k.pos === r.img2 ? 2 : null;
}

function sideWord(slot) {
  return S.layout === "col" ? (slot === 1 ? "haut" : "bas") : (slot === 1 ? "gauche" : "droite");
}

function debugBadge(r, chosenSlot) {
  const src = DEBUG_SOURCE[r.cond] || { cls: "", label: "condition inconnue" };
  const k = keyOf(r);
  const pos = posSlotOf(r);
  let verdict = "";
  if (chosenSlot && pos) {
    const ok = chosenSlot === pos;
    const nm = S.manifest.neurons[r.neuron].names || {};
    verdict = '<div class="dbg-verdict ' + (ok ? "dbg-ok" : "dbg-ko") + '">' + (ok ? "✓ JUSTE" : "✗ FAUX") +
      " — choisie : " + sideWord(chosenSlot) + ", bonne : " + sideWord(pos) + "</div>" +
      '<div class="dbg-names">Nom SALT : <b>' + esc(cleanName(nm.B || "—")) + "</b> · Nom CLIP-Dissect : <b>" + esc(cleanName(nm.D || "—")) + "</b></div>";
  }
  return '<div class="debug-badge ' + src.cls + '">' +
    '<div class="dbg-source">' + esc(src.label) + "</div>" +
    (r.type === "catch" ? '<div class="dbg-catch">ESSAI PIÈGE (voulu) : la bonne image est une copie d\'une des 9 images du haut ' +
      "(contrôle d'attention).</div>" : "") +
    '<div class="dbg-meta">' + esc(S.stimDir) + " " + esc(S.manifest.version) + " · graine " + esc(S.seed) + " · round " + r.round + " · neurone " + esc(r.neuron) +
    (k ? " = " + esc(k.atom) + " (" + esc(k.dataset) + ", strate " + esc(k.stratum) + ")" : " · clé de debug absente") + " · " +
    (r.type === "practice" ? "premier round (échauffement)" : r.type === "catch" ? "essai piège" : "test") +
    (pos ? " · bonne image : " + sideWord(pos) : "") + "</div>" +
    (k && k.judge_desc ? '<div class="dbg-meta">juge MLLM (sans les noms) : ' + esc(k.judge_desc) + "</div>" : "") +
    verdict + "</div>";
}

function debugSummaryHtml() {
  if (!S.key) return '<div class="debug-badge">Debug : clé absente, pas de score.</div>';
  const by = {};
  S.plan.forEach((r, i) => {
    const a = S.answers[i];
    const pos = posSlotOf(r);
    if (!a || !pos) return;
    const g = r.type === "test" ? "test " + r.cond : r.type;
    (by[g] = by[g] || []).push(a.slot === pos ? 1 : 0);
  });
  return '<div class="debug-badge"><b>Debug</b> (le CSV a été téléchargé) — ' + Object.keys(by).sort().map((g) =>
    esc(g) + " : " + by[g].reduce((x, y) => x + y, 0) + "/" + by[g].length).join(" · ") + "</div>";
}

// ?debug=1 without full=1: the rounds of one session draw (or of every neuron with &all=1), one by one. The arrows (or the
// keyboard arrow keys) go to the previous / next round without answering; a click on a candidate shows the verdict and both
// names. Nothing is saved.
function debugBrowser() {
  const items = CFG.debugAll ? S.plan : S.plan.filter((r) => r.type !== "practice");
  const answers = {};
  let i = 0;
  const draw = () => {
    S.token += 1;
    const r = items[i];
    app().innerHTML =
      '<div class="dbg-nav">' +
      '<button class="dbg-arrow" id="dbg-prev" title="Previous (left arrow)"' + (i === 0 ? " disabled" : "") + ">&#9664;</button>" +
      '<span class="dbg-count">round ' + (i + 1) + " / " + items.length + "</span>" +
      '<span class="dbg-version">' + esc(S.stimDir) + " " + esc(S.manifest.version || "?") + " · graine " + esc(S.seed) + "</span>" +
      '<button class="dbg-arrow" id="dbg-next" title="Next (right arrow)"' + (i === items.length - 1 ? " disabled" : "") + ">&#9654;</button>" +
      '<button class="dbg-end" id="dbg-end">End</button>' +
      "</div>" + roundHtml(r, { badge: debugBadge(r, answers[i] || null), chosenSlot: answers[i] || null });
    const trial = app().querySelector(".trial");
    trial.classList.add("is-shown", "is-ready");
    document.getElementById("dbg-prev").onclick = () => { if (i > 0) { i -= 1; draw(); } };
    document.getElementById("dbg-next").onclick = () => { if (i < items.length - 1) { i += 1; draw(); } };
    document.getElementById("dbg-end").onclick = finishBrowse;
    trial.querySelectorAll(".query-btn").forEach((b) => { b.onclick = () => { answers[i] = +b.dataset.slot; draw(); }; });
    const idx = S.plan.indexOf(r);
    preloadAhead(idx);
    try { window.scrollTo(0, 0); } catch (e) { /* headless */ }
  };
  const onKeyBrowse = (e) => {
    if (isInfoOpen() || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === "ArrowLeft" && i > 0) { i -= 1; draw(); }
    if (e.key === "ArrowRight" && i < items.length - 1) { i += 1; draw(); }
  };
  const finishBrowse = () => {
    document.removeEventListener("keydown", onKeyBrowse);
    S.onLayoutChange = null;
    const done = Object.keys(answers);
    const ok = done.filter((k) => answers[k] === posSlotOf(items[+k])).length;
    app().innerHTML = '<div class="page"><p>Debug browser closed: ' + ok + " correct out of " + done.length + " answered rounds.</p>" +
      "<p>Reload the page to browse again, or add <code>&amp;full=1</code> to the URL for the participant flow.</p></div>";
  };
  document.addEventListener("keydown", onKeyBrowse);
  S.onLayoutChange = draw;                          // the banner says left / right or top / bottom
  draw();
}

/* ------------------------------------------------------------------ */
/* Info pop-ups                                                        */
/* ------------------------------------------------------------------ */
// One modal outside #app, so it survives every screen change. Any element with data-info="<key>" (the small "i" buttons,
// the "conditions" link of the introduction) opens texts.js info[<key>].
const INFO = { close: null };

function setupInfoModal() {
  const m = document.createElement("div");
  m.id = "info-modal";
  m.hidden = true;
  m.setAttribute("role", "dialog");
  m.setAttribute("aria-modal", "true");
  m.setAttribute("aria-labelledby", "info-body");
  m.innerHTML = '<div class="info-box"><div id="info-body"></div><button type="button" id="info-close" class="btn">' +
    esc(tx("ui.closeButton", "Close")) + "</button></div>";
  document.body.appendChild(m);
  let opener = null;
  INFO.close = () => {
    m.hidden = true;
    if (opener) { try { opener.focus({ preventScroll: true }); } catch (e) { /* gone */ } }
    opener = null;
  };
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-info]");
    if (t) {
      e.preventDefault();
      e.stopPropagation();
      opener = t;
      document.getElementById("info-body").innerHTML = tx("info." + t.getAttribute("data-info"), "<p>No information.</p>");
      m.hidden = false;
      document.getElementById("info-close").focus();
      return;
    }
    if (!m.hidden && (e.target === m || e.target.id === "info-close")) INFO.close();
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !m.hidden) INFO.close(); });
}

function isInfoOpen() {
  const m = document.getElementById("info-modal");
  return !!m && !m.hidden;
}

function closeInfo() {
  if (isInfoOpen() && INFO.close) INFO.close();
}

/* ------------------------------------------------------------------ */
/* Startup                                                             */
/* ------------------------------------------------------------------ */

async function main() {
  setupInfoModal();
  updateLayout();
  window.addEventListener("resize", updateLayout);
  window.addEventListener("orientationchange", updateLayout);
  if (CFG.debug) document.body.classList.add("debug");
  document.addEventListener("pointerdown", (e) => { S.lastPointer = e.pointerType || "mouse"; }, true);
  const rot = document.getElementById("rotate");
  if (rot) rot.innerHTML = tx("ui.rotateHtml", "");

  S.stimDir = stimFolder();
  try {
    S.manifest = await fetchJson(S.stimDir + "/manifest.json");
  } catch (e) {
    console.error(e);
    showFatal(CFG.debug ? "<pre>" + esc(String(e)) + "</pre>" : tx("ui.loadErrorHtml", "<p>The study could not be loaded.</p>"));
    return;
  }
  const errs = validateStimuli(S.manifest);
  if (errs.length) {
    console.error("[experiment] stimulus errors:", errs);
    showFatal(CFG.debug ? "<pre>" + esc(errs.join("\n")) + "</pre>" : tx("ui.loadErrorHtml", "<p>The study could not be loaded.</p>"));
    return;
  }
  if (CFG.debug) {
    try { S.key = await fetchJson(S.stimDir + "/debug_key.json"); } catch (e) { S.key = null; }
  }
  const seed = CFG.seed !== null && CFG.seed !== undefined ? CFG.seed : randomUint32();

  if (CFG.debugBrowse) {
    S.seed = seed;
    S.plan = CFG.debugAll ? makeAllPlan(seed) : makePlan(seed);
    debugBrowser();
    return;
  }

  window.addEventListener("popstate", onPopState);
  document.addEventListener("keydown", onKey);
  window.addEventListener("blur", () => { S.nBlur += 1; S.roundBlur += 1; });
  window.addEventListener("pagehide", persist);
  window.addEventListener("beforeunload", (e) => {
    if (CFG.debug || !S.consent || S.finished) return;
    persist();
    e.preventDefault();
    e.returnValue = "";
  });

  const saved = restore();
  if (saved) {
    for (const k of PERSISTED) S[k] = saved[k];
    if (!S.answers) S.answers = [];
    if (!S.events) S.events = [];
    if (!S.finished) {
      S.nResume += 1;
      if (S.consent) toast(tx("ui.resumedNote", ""));
    }
    go(S.finished ? nRounds() + 2 : Math.min(Math.max(0, S.frontier), nRounds() + 1), "replace");
  } else {
    S.sid = randomId(12);
    S.seed = seed;
    S.plan = makePlan(seed);
    go(0, "replace");
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}

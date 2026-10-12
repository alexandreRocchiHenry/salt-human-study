/*
 * SALT human study: experiment logic (jsPsych 8.3.0).
 *
 * One trial = one SAE atom. The participant sees 9 most activating and
 * 9 least activating reference images, then clicks which of two query
 * images activates the atom, then rates confidence (1-5).
 *
 * Within-subject design: every session mixes the active conditions of
 * config.js (A no name, B SALT name, C permuted SALT name, D CLIP-Dissect
 * name; C is set aside for now, so A, B, D). With n active conditions the
 * counterbalancing cell (0 .. 3n-1, from DataPipe) gives the atom list
 * (cell / n) and the rotation (cell % n): within a list the 40 atoms are
 * split into n fixed groups balanced by dataset and stratum, and group g
 * gets condition (g + rotation) % n, so over the n rotations every atom is
 * seen once in every active condition.
 *
 * Reads: window.EXP_CONFIG (config.js), window.EXP_TEXTS (texts.js),
 *        <stim>/manifest.json and the example atom (example.json).
 * The full timeline is built up front. Parameters that depend on the
 * condition are functions that read the global STATE.
 */
"use strict";

const EXP_VERSION = "2.0.0-within";
const CONDITION_LETTERS = (window.EXP_CONFIG && window.EXP_CONFIG.conditions) || ["A", "B", "C", "D"];   // active conditions

const CFG = window.EXP_CONFIG || {};
const TX = window.EXP_TEXTS || {};

// Shared run state. Filled once the condition is known (node 3).
const STATE = {
  stimDir: "stimuli",
  manifest: null,
  example: null,
  rotation: null,
  list: null,
  cond_index: null,
  items: { practice: [], test: [] },
  test_order: [],
  sides: [],
  cur: null,           // item of the trial being shown
  lastChoice: null,    // {side, correct, rt} of the last choice screen
  done: 0,             // finished practice + test trials (progress bar)
  questionnaire: null,
  save_failed: false,
  session_complete: false,
  filename: null,
  bgPreloadStarted: false
};

let jsPsych = null;

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

// Read a text key such as "ui.nextButton". Missing keys log a warning
// and fall back to a plain default (participant text lives in texts.js).
function tx(path, fallback) {
  let v = TX;
  for (const k of path.split(".")) {
    if (v === null || v === undefined || typeof v !== "object" || !(k in v)) {
      console.warn("[experiment] missing text key: " + path);
      return fallback;
    }
    v = v[k];
  }
  if (v === null || v === undefined) {
    console.warn("[experiment] empty text key: " + path);
    return fallback;
  }
  return v;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function cleanName(name) {
  return String(name).replace(/_/g, " ");
}

function repeat(x, n) {
  return Array.from({ length: n }, () => x);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function median(xs) {
  const v = xs.filter((x) => typeof x === "number" && isFinite(x)).sort((a, b) => a - b);
  if (v.length === 0) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function mean(xs) {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
}

function totalTrials() {
  return CFG.nPractice + CFG.nTest + CFG.nCatch;
}

function showFatal(html) {
  const el = document.getElementById("jspsych-target");
  if (el) el.innerHTML = '<div class="fatal">' + html + "</div>";
}

/* ------------------------------------------------------------------ */
/* Stimuli: loading and validation                                     */
/* ------------------------------------------------------------------ */

function stimFolder() {
  // ?stim=<folder> is honoured in debug only (e.g. stimuli_mock).
  if (!CFG.debug) return "stimuli";
  if (CFG.stimOverride) return CFG.stimOverride;   // ?proto=a|b (config.js)
  const s = new URLSearchParams(window.location.search).get("stim");
  if (s && /^[A-Za-z0-9_-]+$/.test(s)) return s;
  if (s) console.warn("[experiment] ignored invalid ?stim value: " + s);
  return "stimuli";
}

async function fetchJson(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
  return r.json();
}

async function fetchExample(dir) {
  const urls = dir === "stimuli"
    ? ["stimuli/example/example.json"]
    : [dir + "/example/example.json", dir + "/example.json", "stimuli/example/example.json"];
  let lastErr = null;
  for (const u of urls) {
    try { return await fetchJson(u); } catch (e) { lastErr = e; }
  }
  throw lastErr;
}

function checkAtom(id, a, errs) {
  if (!a || typeof a !== "object") { errs.push("atom " + id + " missing"); return; }
  if (a.dataset !== "coco" && a.dataset !== "imagenet") errs.push(id + ": bad dataset");
  if (!["R", "Delta", "practice", "catch"].includes(a.stratum)) errs.push(id + ": bad stratum");
  for (const k of ["refs_high", "refs_low"]) {
    if (!Array.isArray(a[k]) || a[k].length !== 9 || a[k].some((p) => typeof p !== "string" || !p)) {
      errs.push(id + ": " + k + " must hold 9 paths");
    }
  }
  for (const k of ["query_pos", "query_neg"]) {
    if (typeof a[k] !== "string" || !a[k]) errs.push(id + ": missing " + k);
  }
  if (!a.names || typeof a.names !== "object") {
    errs.push(id + ": missing names");
  } else {
    if (a.names.A !== null && a.names.A !== undefined) errs.push(id + ": names.A must be null");
    for (const c of ["B", "C", "D"]) {
      if (typeof a.names[c] !== "string" || !a.names[c].trim()) errs.push(id + ": empty names." + c);
    }
  }
  if (!a.meta || typeof a.meta !== "object") errs.push(id + ": missing meta");
}

function validateStimuli(m, ex) {
  const errs = [];
  if (!m || typeof m !== "object") return ["manifest is not an object"];
  if (typeof m.version !== "string") errs.push("manifest.version missing");
  const atoms = m.atoms || {};
  const nLists = Math.floor(CFG.nConditions / CONDITION_LETTERS.length);
  if (!Array.isArray(m.lists) || m.lists.length !== nLists) {
    errs.push("manifest.lists must hold " + nLists + " lists");
  } else {
    m.lists.forEach((L, j) => {
      if (!L || L.list !== j) errs.push("lists[" + j + "].list must be " + j);
      const ids = (L && L.test_atoms) || [];
      if (ids.length !== CFG.nTest) errs.push("list " + j + " has " + ids.length + " test atoms, expected " + CFG.nTest);
      if (new Set(ids).size !== ids.length) errs.push("list " + j + " has duplicate ids");
      ids.forEach((id) => { if (!(id in atoms)) errs.push("list " + j + ": unknown atom " + id); });
    });
  }
  if (!Array.isArray(m.practice) || m.practice.length !== CFG.nPractice) errs.push("manifest.practice must hold " + CFG.nPractice + " ids");
  if (!Array.isArray(m.catch) || m.catch.length !== CFG.nCatch) errs.push("manifest.catch must hold " + CFG.nCatch + " ids");
  const pool = new Set((m.lists || []).flatMap((L) => (L && L.test_atoms) || []));
  const prac = new Set(m.practice || []);
  const cat = new Set(m.catch || []);
  for (const id of prac) { if (pool.has(id) || cat.has(id)) errs.push("practice atom " + id + " overlaps pool or catch"); }
  for (const id of cat) { if (pool.has(id)) errs.push("catch atom " + id + " overlaps pool"); }
  for (const id of new Set([...pool, ...prac, ...cat])) {
    if (!(id in atoms)) { errs.push("unknown atom " + id); continue; }
    checkAtom(id, atoms[id], errs);
  }
  checkAtom("example", ex, errs);
  return errs;
}

function atomImages(a) {
  return [...a.refs_high, ...a.refs_low, a.query_pos, a.query_neg];
}

/* ------------------------------------------------------------------ */
/* Rendering (section 5.5 / 5.6 of SPEC.md)                            */
/* ------------------------------------------------------------------ */

function img(src, cls) {
  return '<img class="' + cls + '" src="' + esc(src) + '" alt="" draggable="false">';
}

function renderName(atom, cond) {
  if (cond === "A" || !atom.names) return "";
  const name = atom.names[cond];
  if (name === null || name === undefined || name === "") return "";
  return '<div class="concept-name">' + tx("nameLabel", "This concept:") +
    ' <strong class="concept-name-value">' + esc(cleanName(name)) + "</strong></div>";
}

function renderRefBlock(paths, cls, label) {
  return '<div class="ref-block ' + cls + '">' +
    '<div class="ref-label">' + label + "</div>" +
    '<div class="ref-row">' + paths.map((p) => img(p, "ref-img")).join("") + "</div>" +
    "</div>";
}

function renderReferences(atom, cond) {
  return renderName(atom, cond) +
    renderRefBlock(atom.refs_high, "ref-high", tx("referenceLabels.high", "Most activating images")) +
    renderRefBlock(atom.refs_low, "ref-low", tx("referenceLabels.low", "Least activating images"));
}

// Debug only (never shown to participants): a banner that says where the displayed
// name comes from and, on the confidence screen, whether the choice was right.
const DEBUG_SOURCE = {
  A: { cls: "dbg-a", label: "AUCUN NOM — images seules (condition A)" },
  B: { cls: "dbg-b", label: "NOM SALT — le vrai nom SALT de cet atome (condition B)" },
  C: { cls: "dbg-c", label: "NOM SALT PERMUTÉ — nom SALT d'un AUTRE atome, donc faux (condition C)" },
  D: { cls: "dbg-d", label: "NOM CLIP-DISSECT — le nom CLIP-Dissect de cet atome (condition D)" }
};
const SIDE_FR = { left: "gauche", right: "droite" };

function debugBadge(item, chosenSide) {
  if (!CFG.debug) return "";
  const src = DEBUG_SOURCE[item.condition] || { cls: "", label: "condition inconnue" };
  let verdict = "";
  if (chosenSide) {
    const ok = chosenSide === item.pos_side;
    const nm = item.atom.names || {};
    verdict = '<div class="dbg-verdict ' + (ok ? "dbg-ok" : "dbg-ko") + '">' +
      (ok ? "✓ JUSTE" : "✗ FAUX") + " — tu as choisi l'image de " + SIDE_FR[chosenSide] +
      ", la bonne était à " + SIDE_FR[item.pos_side] + "</div>" +
      '<div class="dbg-names">Nom SALT : <b>' + esc(cleanName(nm.B || "—")) + "</b> · Nom CLIP-Dissect : <b>" +
      esc(cleanName(nm.D || "—")) + "</b></div>";
  }
  return '<div class="debug-badge ' + src.cls + '">' +
    '<div class="dbg-source">' + esc(src.label) + "</div>" +
    '<div class="dbg-meta">' + (CFG.stimOverride ? "stimuli : " + esc(CFG.stimOverride) + " · " : "") + "atome " + esc(item.atom_id) + " · " +
    (item.item_type === "practice" ? "entraînement" : item.item_type === "catch" ? "essai piège" : "test, strate " + esc(item.atom.stratum)) +
    " · bonne image : " + SIDE_FR[item.pos_side] + "</div>" +
    verdict + "</div>";
}

function renderChoiceScreen(item) {
  return '<div class="trial">' + debugBadge(item) +
    renderReferences(item.atom, item.condition) +
    '<div class="trial-prompt">' + tx("trialPrompt", "Which image activates this concept?") + "</div>" +
    "</div>";
}

// Two static query images. opts.chosen: side the participant chose;
// opts.target: side to outline as correct; opts.targetCaption: caption.
function renderQueryPair(item, opts) {
  const o = opts || {};
  const cell = (side, src) => {
    const cls = ["query-static"];
    if (o.chosen === side) cls.push("is-chosen");
    if (o.target === side) cls.push("is-target");
    let cap = "&nbsp;";
    if (o.target === side && o.targetCaption) cap = o.targetCaption;
    else if (o.chosen === side) cap = tx("ui.yourChoice", "Your choice");
    return '<div class="' + cls.join(" ") + '" data-side="' + side + '">' + img(src, "query-img") +
      '<div class="query-caption">' + cap + "</div></div>";
  };
  return '<div class="query-pair">' + cell("left", item.left_img) + cell("right", item.right_img) + "</div>";
}

function renderConfidenceScreen(item, chosenSide) {
  return '<div class="trial trial-confidence">' + debugBadge(item, chosenSide) +
    renderName(item.atom, item.condition) +
    renderQueryPair(item, { chosen: chosenSide }) +
    '<div class="trial-prompt">' + tx("confidencePrompt", "How sure are you?") + "</div>" +
    "</div>";
}

function renderFeedbackScreen(item, chosenSide) {
  const ok = chosenSide === item.pos_side;
  const msg = ok ? tx("feedback.correct", "Correct.") : tx("feedback.incorrect", "Not quite.");
  return '<div class="trial trial-feedback">' +
    '<div class="feedback ' + (ok ? "feedback-correct" : "feedback-incorrect") + '">' + msg + "</div>" +
    renderQueryPair(item, { chosen: chosenSide, target: item.pos_side }) +
    "</div>";
}

// The example looks like a real trial. The positive query is always on the right.
function renderExample(exampleAtom, cond) {
  const item = {
    atom_id: exampleAtom.atom_id || "example",
    atom: exampleAtom,
    pos_side: "right",
    left_img: exampleAtom.query_neg,
    right_img: exampleAtom.query_pos
  };
  return '<div class="example-trial">' +
    '<div class="trial">' + renderReferences(exampleAtom, cond) +
    '<div class="trial-prompt">' + tx("trialPrompt", "Which image activates this concept?") + "</div></div>" +
    renderQueryPair(item, { target: "right", targetCaption: tx("ui.exampleTargetCaption", "This one") }) +
    "</div>";
}

/* ------------------------------------------------------------------ */
/* Condition and randomisation                                         */
/* ------------------------------------------------------------------ */

function validOverride(ov) {
  if (!ov) return null;
  const nLists = Math.floor(CFG.nConditions / CONDITION_LETTERS.length);
  if (Number.isInteger(ov.rotation) && ov.rotation >= 0 && ov.rotation < CONDITION_LETTERS.length &&
      Number.isInteger(ov.list) && ov.list >= 0 && ov.list < nLists) {
    return ov;
  }
  console.warn("[experiment] invalid condition override ignored:", ov);
  return null;
}

function randomIndex() {
  return Math.floor(Math.random() * CFG.nConditions);
}

async function chooseCondition() {
  if (CFG.debug) {
    const ov = validOverride(CFG.conditionOverride);
    if (ov) {
      return { cond_index: ov.list * CONDITION_LETTERS.length + ov.rotation, cond_source: "override" };
    }
    return { cond_index: randomIndex(), cond_source: "debug_random" };
  }
  let x;
  try {
    x = await Promise.race([
      jsPsychPipe.getCondition(CFG.datapipeExperimentId),
      sleep(10000).then(() => new Error("timeout"))
    ]);
  } catch (e) {
    x = e;
  }
  if (Number.isInteger(x) && x >= 0 && x < CFG.nConditions) {
    return { cond_index: x, cond_source: "datapipe" };
  }
  return { cond_index: randomIndex(), cond_source: "fallback", cond_error: String(x) };
}

function makeItem(id, phase, itemType, seq, posSide, condition) {
  const atom = STATE.manifest.atoms[id];
  const left = posSide === "left" ? atom.query_pos : atom.query_neg;
  const right = posSide === "left" ? atom.query_neg : atom.query_pos;
  const name = condition === "A" ? null : atom.names[condition];
  return {
    atom_id: id, atom: atom, phase: phase, item_type: itemType, seq: seq, condition: condition,
    pos_side: posSide, left_img: left, right_img: right,
    name_shown: name === undefined || name === null ? null : cleanName(name)
  };
}

// Fixed split of a list into 4 groups balanced by dataset and stratum. Cells are
// taken in manifest order; cell offsets (R: 0, 2; Delta: 1, 3) give every group
// 5 R + 5 Delta atoms and 4 to 6 atoms of each dataset. The split depends only on
// the manifest, so all participants of a list share it.
function atomGroups(list) {
  const M = STATE.manifest;
  const ids = M.lists[list].test_atoms;
  const cells = [["coco", "R", 0], ["coco", "Delta", 1], ["imagenet", "R", 2], ["imagenet", "Delta", 3]];
  const g = {};
  for (const [ds, st, off] of cells) {
    ids.filter((id) => M.atoms[id].dataset === ds && M.atoms[id].stratum === st)
      .forEach((id, i) => { g[id] = (i + off) % CONDITION_LETTERS.length; });
  }
  ids.forEach((id, i) => { if (!(id in g)) g[id] = i % CONDITION_LETTERS.length; });   // other cells, if any
  return g;
}

function buildState(rotation, list) {
  const R = jsPsych.randomization;
  const M = STATE.manifest;
  const NC = CONDITION_LETTERS.length;
  STATE.rotation = rotation;
  STATE.list = list;
  const condOfGroup = (grp) => CONDITION_LETTERS[(grp + rotation) % NC];

  // Practice: shuffled atoms, sides 5 left + 4 right (for 9), conditions cycled.
  const P = R.shuffle(M.practice);
  const nL = Math.ceil(P.length / 2);
  const pSides = R.shuffle(repeat("left", nL).concat(repeat("right", P.length - nL)));
  const pConds = R.shuffle(P.map((_, i) => condOfGroup(i % NC)));
  STATE.items.practice = P.map((id, i) => makeItem(id, "practice", "practice", i + 1, pSides[i], pConds[i]));

  // Test: 5 blocks of 8 test atoms, one catch atom appended per block.
  const T = R.shuffle(M.lists[list].test_atoms);
  const K = R.shuffle(M.catch);
  const nB = K.length;
  const blocks = [];
  for (let b = 0; b < nB; b++) {
    const lo = Math.round((b * T.length) / nB);
    const hi = Math.round(((b + 1) * T.length) / nB);
    blocks.push(R.shuffle(T.slice(lo, hi).concat([K[b]])));
  }
  const catchSet = new Set(K);
  const groups = atomGroups(list);
  const catchCond = {};
  K.forEach((id, k) => { catchCond[id] = condOfGroup(k % NC); });
  if (blocks.length && blocks[0].length > 1) {
    while (catchSet.has(blocks[0][0])) blocks[0] = R.shuffle(blocks[0]);
  }
  const order = blocks.flat();

  // Sides: 20 left + 20 right over the test atoms; random for catch.
  const hT = Math.ceil(T.length / 2);
  const tSides = R.shuffle(repeat("left", hT).concat(repeat("right", T.length - hT)));
  let t = 0;
  const sides = order.map((id) => (catchSet.has(id) ? (Math.random() < 0.5 ? "left" : "right") : tSides[t++]));
  STATE.items.test = order.map((id, i) => makeItem(id, "test", catchSet.has(id) ? "catch" : "test", i + 1, sides[i],
    catchSet.has(id) ? catchCond[id] : condOfGroup(groups[id])));
  STATE.test_order = order;
  STATE.sides = sides;
}

function practiceImages() {
  return [atomImages(STATE.example), ...STATE.items.practice.map((it) => atomImages(it.atom))].flat();
}

function testImages() {
  return STATE.items.test.map((it) => atomImages(it.atom)).flat();
}

/* ------------------------------------------------------------------ */
/* Data helpers                                                        */
/* ------------------------------------------------------------------ */

function itemFields(it) {
  const meta = it.atom.meta || {};
  return {
    phase: it.phase,
    item_type: it.item_type,
    seq: it.seq,
    atom_id: it.atom_id,
    dataset: it.atom.dataset,
    stratum: it.atom.stratum,
    condition: it.condition,
    category: meta.category === undefined ? null : meta.category,
    name_shown: it.name_shown,
    pos_side: it.pos_side,
    left_img: it.left_img,
    right_img: it.right_img
  };
}

// DataPipe answers with JSON; failures carry an "error" field. A network
// failure makes plugin-pipe return the Error object itself (and still
// report success), so both cases are checked here.
function saveOk(result) {
  if (!result || typeof result !== "object") return false;
  if (result instanceof Error || Object.prototype.toString.call(result) === "[object Error]") return false;
  return !result.error;
}

function saveFilename() {
  if (!STATE.filename) {
    const v = (k) => jsPsych.data.getURLVariable(k) || null;
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..*$/, "");
    STATE.filename = (v("PROLIFIC_PID") || "nopid") + "_" + (v("SESSION_ID") || STATE.subject_id) + "_" + stamp + ".csv";
  }
  return STATE.filename;
}

function buildSummary() {
  const conf = jsPsych.data.get().filter({ task: "confidence" }).values();
  const test = conf.filter((r) => r.phase === "test" && r.item_type === "test");
  const catchRows = conf.filter((r) => r.phase === "test" && r.item_type === "catch");
  const prac = conf.filter((r) => r.phase === "practice");
  const inter = jsPsych.data.getInteractionData();
  const s = {
    session_complete: true,
    n_test: test.length,
    n_catch: catchRows.length,
    catch_failed: catchRows.filter((r) => !r.correct).length,
    test_accuracy: mean(test.map((r) => (r.correct ? 1 : 0))),
    test_accuracy_A: mean(test.filter((r) => r.condition === "A").map((r) => (r.correct ? 1 : 0))),
    test_accuracy_B: mean(test.filter((r) => r.condition === "B").map((r) => (r.correct ? 1 : 0))),
    test_accuracy_C: mean(test.filter((r) => r.condition === "C").map((r) => (r.correct ? 1 : 0))),
    test_accuracy_D: mean(test.filter((r) => r.condition === "D").map((r) => (r.correct ? 1 : 0))),
    practice_accuracy: mean(prac.map((r) => (r.correct ? 1 : 0))),
    median_rt_test: median(test.map((r) => r.rt_choice)),
    median_rt_test_incl_catch: median(test.concat(catchRows).map((r) => r.rt_choice)),
    total_duration_ms: jsPsych.getTotalTime(),
    n_blur: inter.filter({ event: "blur" }).count(),
    n_fullscreen_exit: inter.filter({ event: "fullscreenexit" }).count(),
    interactions: inter.json(),
    test_order: JSON.stringify(STATE.test_order),
    sides: JSON.stringify(STATE.sides),
    screen_w: window.screen ? window.screen.width : null,
    screen_h: window.screen ? window.screen.height : null,
    window_w: window.innerWidth,
    window_h: window.innerHeight
  };
  const q = STATE.questionnaire || {};
  for (const item of activeQuestions()) {
    s["q_" + item.name] = item.name in q ? q[item.name] : null;
  }
  return s;
}

/* ------------------------------------------------------------------ */
/* Questionnaire                                                       */
/* ------------------------------------------------------------------ */

function activeQuestions() {
  const qs = tx("questionnaire", []);
  return qs;   // within-subject: every participant answers every question
}

function buildQuestionnaire() {
  return '<div class="questionnaire">' + activeQuestions().map((q) => {
    const id = "q_" + q.name;
    let field;
    if (q.type === "multi-choice") {
      field = '<div class="q-options" role="radiogroup">' + (q.options || []).map((o, i) =>
        '<label class="q-option"><input type="radio" name="' + esc(q.name) + '" id="' + id + "_" + i +
        '" value="' + esc(o) + '" required> <span>' + esc(o) + "</span></label>").join("") + "</div>";
    } else {
      if (q.type !== "text") console.warn("[experiment] unknown question type, using text:", q.type);
      field = '<textarea name="' + esc(q.name) + '" id="' + id + '" rows="3" required></textarea>';
    }
    return '<div class="q-item"><p class="q-prompt">' + q.prompt + "</p>" + field + "</div>";
  }).join("") + "</div>";
}

/* ------------------------------------------------------------------ */
/* Timeline                                                            */
/* ------------------------------------------------------------------ */

function trialBlock(phase) {
  const items = () => STATE.items[phase];
  const n = phase === "practice" ? CFG.nPractice : CFG.nTest + CFG.nCatch;
  const slots = Array.from({ length: n }, (_, i) => ({ slot: i }));

  const choice = {
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-trial"],
    stimulus: () => {
      STATE.cur = items()[jsPsych.evaluateTimelineVariable("slot")];
      return renderChoiceScreen(STATE.cur);
    },
    choices: ["left", "right"],
    button_layout: "flex",
    button_html: (c, i) => {
      const src = c === "left" ? STATE.cur.left_img : STATE.cur.right_img;
      return '<button class="query-btn" data-side="' + c + '">' + img(src, "query-img") + "</button>";
    },
    response_ends_trial: true,
    data: { task: "choice" },
    on_finish: (d) => {
      const it = STATE.cur;
      const side = d.response === 0 ? "left" : "right";
      const correct = side === it.pos_side;
      Object.assign(d, itemFields(it), { response_side: side, correct: correct });
      d.stimulus = null; // paths are recorded; drop the large HTML
      STATE.lastChoice = { side: side, correct: correct, rt: d.rt };
    }
  };

  const confidence = {
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-trial"],
    stimulus: () => renderConfidenceScreen(STATE.cur, STATE.lastChoice.side),
    choices: () => tx("confidenceLabels", ["1", "2", "3", "4", "5"]),
    button_layout: "flex",
    button_html: (c, i) =>
      '<button class="jspsych-btn conf-btn"><span class="conf-num">' + (i + 1) +
      '</span><span class="conf-label">' + c + "</span></button>",
    data: { task: "confidence" },
    on_finish: (d) => {
      const it = STATE.cur;
      const lc = STATE.lastChoice;
      Object.assign(d, itemFields(it), {
        response_side: lc.side,
        correct: lc.correct,
        rt_choice: lc.rt,
        confidence: d.response + 1,
        rt_conf: d.rt,
        // aliases asked for in the task brief
        correct_side: it.pos_side,
        chosen_side: lc.side,
        rt_ms: lc.rt
      });
      d.stimulus = null;
      STATE.done += 1;
      jsPsych.progressBar.progress = Math.min(1, STATE.done / totalTrials());
    }
  };

  const feedback = {
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-trial"],
    stimulus: () => renderFeedbackScreen(STATE.cur, STATE.lastChoice.side),
    choices: () => [tx("ui.continueButton", "Continue")],
    data: { task: "feedback" },
    on_finish: (d) => {
      d.seq = STATE.cur.seq;
      d.atom_id = STATE.cur.atom_id;
      d.stimulus = null;
    }
  };

  return {
    timeline: phase === "practice" ? [choice, confidence, feedback] : [choice, confidence],
    timeline_variables: slots
  };
}

function textScreen(task, htmlFn, buttonFn) {
  return {
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-text"],
    stimulus: htmlFn,
    choices: () => [buttonFn()],
    data: { task: task }
  };
}

function buildTimeline() {
  const tl = [];

  // 1. Browser check (desktop, window at least 1000x650).
  tl.push({
    type: jsPsychBrowserCheck,
    minimum_width: 1000,
    minimum_height: 650,
    skip_features: ["webaudio", "webcam", "microphone", "vsync_rate"],
    inclusion_function: (d) => !d.mobile,
    exclusion_message: () => tx("ui.browserExclusionHtml", "<p>Please use a desktop or laptop computer.</p>"),
    data: { task: "browser_check" }
  });

  // 2. Consent. Decline ends the study; nothing is saved.
  tl.push({
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-text"],
    stimulus: () => tx("consentHtml", "<p>Consent text missing.</p>"),
    choices: () => [tx("ui.consentAgree", "I agree"), tx("ui.consentDecline", "I do not agree")],
    data: { task: "consent" },
    on_finish: (d) => {
      d.consent = d.response === 0;
      if (!d.consent) jsPsych.abortExperiment(tx("ui.noConsentHtml", "<p>You did not consent. Please return the study.</p>"));
    }
  });

  // 3. Condition (asked only after consent).
  tl.push({
    type: jsPsychCallFunction,
    async: true,
    func: (done) => {
      chooseCondition().then((c) => {
        const rotation = c.cond_index % CONDITION_LETTERS.length;
        const list = Math.floor(c.cond_index / CONDITION_LETTERS.length);
        STATE.cond_index = c.cond_index;
        jsPsych.data.addProperties({ cond_index: c.cond_index, rotation: rotation, list: list, cond_source: c.cond_source, design: "within" });
        buildState(rotation, list);
        done({ cond_error: c.cond_error || null });
      });
    },
    data: { task: "condition" }
  });

  // 4. No fullscreen step (removed 8 Oct. 2026 at the author's request); the window
  //    size is still checked by the browser check, and blur events are logged.

  // 5. Preload example + practice images.
  tl.push({
    type: jsPsychPreload,
    images: () => practiceImages(),
    show_progress_bar: true,
    message: () => tx("ui.loadingHtml", "<p>Loading...</p>"),
    max_load_time: 120000,
    continue_after_error: false,
    error_message: () => tx("ui.loadErrorHtml", "<p>The images could not be loaded.</p>"),
    data: { task: "preload_practice" },
    on_finish: () => {
      // Background preload of test and catch images. Started here, after
      // preload 1, so it does not slow down the first screens and is not
      // cancelled by that preload trial.
      if (!STATE.bgPreloadStarted) {
        STATE.bgPreloadStarted = true;
        jsPsych.pluginAPI.preloadImages(testImages(), () => {});
      }
    }
  });

  // 6. Instructions with the illustrated example.
  tl.push({
    type: jsPsychInstructions,
    css_classes: ["screen-instr"],
    pages: () => {
      const pages = (TX.instructionPages && TX.instructionPages.mixed) || null;
      if (!pages) console.warn("[experiment] missing text key: instructionPages.mixed");
      const ex = renderExample(STATE.example, "B");   // the example shows a name (the SALT name of the example atom)
      return (pages || ["{{EXAMPLE_TRIAL}}"]).map((p) => '<div class="instr-page">' + p.split("{{EXAMPLE_TRIAL}}").join(ex) + "</div>");
    },
    show_clickable_nav: true,
    allow_backward: true,
    allow_keys: false,
    button_label_next: () => tx("ui.nextButton", "Next"),
    button_label_previous: () => tx("ui.previousButton", "Previous"),
    data: { task: "instructions" }
  });

  // 7-8. Practice with feedback.
  tl.push(textScreen("practice_intro", () => tx("practiceIntroHtml", "<p>Practice.</p>"), () => tx("ui.continueButton", "Continue")));
  tl.push(trialBlock("practice"));

  // 9. Preload test + catch images (usually already cached).
  tl.push({
    type: jsPsychPreload,
    images: () => testImages(),
    show_progress_bar: true,
    message: () => tx("ui.loadingHtml", "<p>Loading...</p>"),
    max_load_time: 120000,
    continue_after_error: false,
    error_message: () => tx("ui.loadErrorHtml", "<p>The images could not be loaded.</p>"),
    data: { task: "preload_test" }
  });

  // 10-11. Test (no feedback), catch trials mixed in.
  tl.push(textScreen("test_intro", () => tx("testIntroHtml", "<p>The task starts now.</p>"), () => tx("ui.continueButton", "Continue")));
  tl.push(trialBlock("test"));

  // 12. Questionnaire.
  tl.push({
    type: jsPsychSurveyHtmlForm,
    css_classes: ["screen-text"],
    html: () => buildQuestionnaire(),
    button_label: () => tx("ui.submitButton", "Submit"),
    data: { task: "questionnaire" },
    on_finish: (d) => { STATE.questionnaire = d.response; }
  });

  // 13. Summary row.
  tl.push({
    type: jsPsychCallFunction,
    func: () => null,
    data: { task: "summary" },
    on_finish: (d) => {
      Object.assign(d, buildSummary());
      STATE.session_complete = true;
    }
  });

  // 14. Save. Production: DataPipe with retries. Debug: local download only.
  tl.push({
    timeline: [
      {
        type: jsPsychPipe,
        action: "save",
        experiment_id: CFG.datapipeExperimentId,
        filename: () => saveFilename(),
        data_string: () => jsPsych.data.get().csv(),
        wait_message: () => tx("ui.savingHtml", "<p>Saving your data. Please do not close this page.</p>"),
        data: { task: "save" }
      },
      {
        type: jsPsychCallFunction,
        async: true,
        func: (done) => {
          (async () => {
            const last = jsPsych.data.get().filter({ task: "save" }).last(1).values()[0];
            let ok = !!last && last.success === true && saveOk(last.result);
            let retries = 0;
            while (!ok && retries < 2) {
              jsPsych.getDisplayElement().innerHTML = tx("ui.savingHtml", "<p>Saving your data...</p>");
              await sleep(2000);
              retries += 1;
              let r;
              try {
                r = await jsPsychPipe.saveData(CFG.datapipeExperimentId, saveFilename(), jsPsych.data.get().csv());
              } catch (e) {
                r = e;
              }
              ok = saveOk(r);
            }
            STATE.save_failed = !ok;
            done({ save_ok: ok, save_retries: retries, save_failed: !ok });
          })();
        },
        data: { task: "save_check" }
      }
    ],
    conditional_function: () => !CFG.debug
  });
  tl.push({
    timeline: [{
      type: jsPsychCallFunction,
      func: () => {
        jsPsych.data.get().localSave("csv", "debug_" + STATE.subject_id + ".csv");
        return null;
      },
      data: { task: "save_debug" }
    }],
    conditional_function: () => !!CFG.debug
  });

  // 15. End screen and Prolific redirect (no redirect in debug).
  tl.push({
    type: jsPsychHtmlButtonResponse,
    css_classes: ["screen-text"],
    stimulus: () => (STATE.save_failed ? tx("ui.saveErrorHtml", "<p>Your data could not be saved.</p>") : "") +
      tx("endHtml", "<p>Thank you.</p>"),
    choices: () => [tx("ui.endButton", "Return to Prolific")],
    trial_duration: () => (CFG.debug || STATE.save_failed ? null : 10000),
    data: { task: "end" },
    on_finish: () => {
      if (!CFG.debug) window.location.href = tx("prolificCompletionUrl", "https://app.prolific.com/");
    }
  });

  return tl;
}

/* ------------------------------------------------------------------ */
/* Startup                                                             */
/* ------------------------------------------------------------------ */

async function main() {
  jsPsych = initJsPsych({
    display_element: "jspsych-target",
    show_progress_bar: true,
    auto_update_progress_bar: false,
    message_progress_bar: tx("ui.progressLabel", "Progress"),
    on_finish: () => {
      // Debug: show the data on screen once the session is complete.
      if (CFG.debug && STATE.session_complete) jsPsych.data.displayData("csv");
    }
  });

  const url = (k) => jsPsych.data.getURLVariable(k) || null;
  const prolific_pid = url("PROLIFIC_PID");
  STATE.subject_id = jsPsych.randomization.randomID(12);

  STATE.stimDir = stimFolder();
  try {
    const [m, ex] = await Promise.all([fetchJson(STATE.stimDir + "/manifest.json"), fetchExample(STATE.stimDir)]);
    STATE.manifest = m;
    STATE.example = ex;
  } catch (e) {
    console.error(e);
    showFatal(CFG.debug ? "<pre>" + esc(String(e)) + "</pre>" : tx("ui.loadErrorHtml", "<p>The study could not be loaded.</p>"));
    return;
  }
  const errs = validateStimuli(STATE.manifest, STATE.example);
  if (errs.length) {
    console.error("[experiment] stimulus errors:", errs);
    showFatal(CFG.debug ? "<pre>" + esc(errs.join("\n")) + "</pre>" : tx("ui.loadErrorHtml", "<p>The study could not be loaded.</p>"));
    return;
  }

  jsPsych.data.addProperties({
    prolific_pid: prolific_pid,
    study_id: url("STUDY_ID"),
    session_id: url("SESSION_ID"),
    subject_id: STATE.subject_id,
    pid_missing: !prolific_pid,
    exp_version: EXP_VERSION,
    manifest_version: STATE.manifest.version,
    debug: !!CFG.debug,
    user_agent: navigator.userAgent,
    start_iso: new Date().toISOString()
  });

  jsPsych.run(buildTimeline());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}

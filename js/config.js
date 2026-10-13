(function () {
  const p = new URLSearchParams(window.location.search);
  const debug = p.get("debug") === "1";
  const int = (k) => (/^\d+$/.test(p.get(k) || "") ? parseInt(p.get(k), 10) : null);
  // Debug only: ?proto=a|b|c loads a prototype stimulus set (stimuli_a / stimuli_b / stimuli_c) instead of stimuli/.
  const proto = p.get("proto");
  window.EXP_CONFIG = {
    debug: debug,
    // Debug only. Default: a trial browser (no introduction, no warm-up rounds, prev / next arrows, answers checked with
    // the answer key). &full=1 runs the participant flow instead (nothing is sent: the data are downloaded as a CSV file).
    debugBrowse: debug && p.get("full") !== "1",
    debugAll: debug && p.get("all") === "1",                      // browser: every neuron of the set, not one session draw
    debugCond: debug && /^[ABCD]$/.test(p.get("cond") || "") ? p.get("cond") : null,   // force one condition everywhere
    seed: debug ? int("seed") : null,                             // reproduce a draw (the seed is in the debug banner and the data)
    resume: debug && p.get("resume") === "1",                     // participant flow: keep / resume the session after a reload
    stimOverride: debug && proto && /^[a-z0-9_-]+$/.test(proto) ? "stimuli_" + proto : null,
    datapipeExperimentId: "DATAPIPE_EXPERIMENT_ID",   // placeholder, set by the author (pipe.jspsych.org)
    // Dynamic version: URL of a server that receives every answer as it is given and the whole session at the end
    // (POST, JSON sent as text/plain). null = only DataPipe, at the end. If set, update info.conditions in texts.js.
    responseEndpoint: null,
    // Active conditions (8 Oct. 2026: C, the permuted SALT name, is set aside for now). Within each session they are
    // balanced over the nTest test neurons (40 = 14 + 13 + 13), which are drawn at random, the same number from each stratum cell.
    conditions: ["A", "B", "D"],
    nTest: 40
  };
})();

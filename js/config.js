(function () {
  const p = new URLSearchParams(window.location.search);
  const debug = p.get("debug") === "1";
  // Debug only: ?debug=1&rot=0..2&list=0..2 fixes the counterbalancing cell (rotation of the
  // condition-to-atom assignment, and atom list). Each session mixes the four conditions.
  let conditionOverride = null;
  if (debug && (p.get("rot") !== null || p.get("list") !== null)) {
    conditionOverride = { rotation: parseInt(p.get("rot") || "0", 10), list: parseInt(p.get("list") || "0", 10) };
  }
  window.EXP_CONFIG = {
    datapipeExperimentId: "DATAPIPE_EXPERIMENT_ID",   // placeholder, set by the author
    // Active conditions (8 Oct. 2026: C, the permuted SALT name, is set aside for now).
    // DataPipe cells = 3 lists x number of active conditions (one rotation per condition).
    conditions: ["A", "B", "D"],
    nConditions: 9, nTest: 40, nPractice: 9, nCatch: 5,
    debug: debug,
    conditionOverride: conditionOverride
  };
})();

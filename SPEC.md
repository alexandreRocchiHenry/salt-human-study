# SALT human study: technical spec (GitHub Pages + jsPsych + DataPipe + Prolific)

Status: spec v1, 2026-10-08. This document is given verbatim to three builders.
Work only under `/lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE/human_exp/`
(below: `HX/`). Do not publish anything, do not create accounts (OSF, DataPipe, Prolific, GitHub), do not `git push`.
All participant-facing text and all code comments are in English, plain and short.

---

## Part 1. What the example does (https://anirudhprabhakaran3.github.io/experiment/)

Fetched on 2026-10-08: `index.html` (14.7 kB), `app.js` (21.7 kB), `translations.js` (35.6 kB), `styles.css` (9.9 kB),
`assets/tutorial_data.json`, `assets/survey_data.json` (150 items), images in `assets/*.jpg` (hashed names).
The source is **not** in the public repo: `anirudhprabhakaran3/anirudhprabhakaran3.github.io` (branches `main`,
`gh-pages`) has no `experiment/` folder; the page is deployed from somewhere else (Last-Modified 2026-08-12).

| Aspect | Example |
|---|---|
| Framework | **None.** Vanilla JS, no jsPsych, no plugins, no build step. One `index.html` holds every screen as a hidden `<div>`; `app.js` is a hand-written state machine that toggles `style.display`. |
| Files | `index.html`, `app.js` (logic), `translations.js` (all UI strings in EN/FR as `uiTranslations`, plus two class-name maps `complexToSimpleEN`, `simpleEnToFr`), `styles.css`, `assets/tutorial_data.json` (1 tutorial item), `assets/survey_data.json` (150 items), `assets/*.jpg`. |
| Timeline | Demographics form first (age range, gender, education, country, AI/ML expertise slider 1-7; Continue enabled only when all are filled) -> 3-step tutorial with clickable step dots: (1) explanation of heatmaps, (2) interactive try of task part 1 with feedback, must answer correctly to unlock "Next", (3) interactive try of part 2 -> "Point of no return" warning box (Review tutorial / Begin) -> 20 items, each in two parts: part 1 = 4-AFC "what is this object?" from a masked image + heatmap, with a "Not sure" button; part 2 = pick up to 2 best heatmaps among 4 methods -> finish screen showing the participant's score. No consent screen, no end questionnaire. |
| Stimuli | `survey_data.json` = list of `{id, trueClass, options[4], original, masks{aa,bpt,gradcam,morpho}, heatmaps{...}}`; image paths relative to `assets/`. Loaded with `fetch()` on `window.onload`. 20 random items out of 150 (`?all=true` runs all 150). |
| Preload | Minimal: `new Image().src = ...` for the 4 heatmaps of the *current* item only. RT measured with `Date.now()`, so RT includes image decode time. |
| Conditions | Within-subject. A balanced pool of method labels (each method ×5 for 20 items) is shuffled and assigned to items, so each participant sees every method equally often in part 1. Option and heatmap positions are shuffled per item. |
| Data | One `fetch(POST, mode:'no-cors', text/plain)` per item to a Google Apps Script web app (URL hard-coded in `app.js`); payload `{userId: crypto.randomUUID(), demographics, response:{imageId, trueClass, step1MethodAssigned, step1UserGuess, step1Correct, step1TimeMs, step2BestHeatmap, step2TimeMs}}`. Incremental (no data loss on dropout), but no confirmation of success (`no-cors`). |
| Prolific | **Not handled**: no PROLIFIC_PID / STUDY_ID / SESSION_ID capture, no completion code, no redirect. |
| Styling | CSS variables on `:root`, Inter (Google Fonts), white card (max 900 px, radius 16 px, soft shadow), gradient title and primary buttons, progress text + bar in the header, help modal ("?"), EN/FR toggle, success/error colored feedback boxes, one `@media (max-width:768px)` breakpoint. |
| Missing | Consent, browser/device check, fullscreen, attention checks, Prolific integration, end questionnaire, robust preload, reliable saving. |

**Good practices we copy**
1. Stimuli described in one JSON manifest, separate from code; UI text in its own file separate from logic (`translations.js` -> our `texts.js`).
2. Interactive tutorial with feedback before the real task, and a clear "the real task starts now, no feedback from here" screen.
3. Position of options shuffled per trial; balanced assignment pools rather than independent coin flips.
4. Progress indicator.
5. URL flag for testing (`?all=true` -> our `?debug=1&cond=..&list=..`).
6. Clean, calm card layout with CSS variables.

**What we do differently**
- jsPsych 8 (pinned) instead of a hand-written state machine: reliable RT, preload, browser check, fullscreen, interaction (blur/fullscreen-exit) logging.
- DataPipe -> OSF instead of Google Apps Script; condition assignment by DataPipe.
- Consent first, questionnaire last (demographics last avoid priming), Prolific IDs + completion redirect.
- Catch trials; no score shown at the end; no "Not sure" option (forced choice + confidence instead).
- English only (no language toggle).

---

## Part 2. Our experiment (fixed plan, do not change)

- Goal: show that names given by **SALT** (a linear text head on a frozen vision-only TopK SAE) make SAE atoms interpretable to humans. Always display the method name as `SALT` in code/docs; participants never see method names.
- Task (Colin thesis ch. 3, 2AFC): one trial = one SAE atom. Reference images: a row of 9 **most activating** and a row of 9 **least activating** images. Two query images (left/right, side randomised): one activates the atom strongly, the other does not, both from the same category (semantic control). The participant clicks the query that activates the atom (belongs with the most-activating row), then rates confidence on a 5-point scale. No feedback on test trials.
- Four between-subject conditions: **A** references only (no name, no placeholder); **B** references + SALT name shown above the references as `This concept: <name>`; **C** references + permuted SALT name (fixed derangement within dataset); **D** references + CLIP-Dissect name. Label wording identical in B, C, D.
- Atom pool: 120 atoms (60 COCO, 60 ImageNet); stratum **R** = 30 random evaluable atoms per dataset; stratum **Delta** = 30 per dataset, disjoint from R, among evaluable atoms whose SALT and CLIP-Dissect names differ, largest |corr(SALT) - corr(CD)| on held-out images (sign recorded).
- Session (~12 min): consent; instructions with an illustrated example in the participant's condition; 9 practice trials with feedback (atoms outside the pool); 40 test trials (20 R + 20 Delta, random order) without feedback; 5 catch trials interleaved; questionnaire (strategy, "Did you use the displayed name?" for B/C/D, age range, AI familiarity); redirect to Prolific.
- Counterbalancing: 3 lists; list j = R-set j + Delta-set j (each set = 10 COCO + 10 ImageNet). DataPipe condition index i in 0..11 -> `condition = ['A','B','C','D'][i % 4]`, `list = Math.floor(i / 4)`.
- Exclusions at analysis time only (>= 2/5 catch failed; median test RT < 1.5 s; incomplete). The page records everything needed and never excludes anyone itself.

---

## Part 3. Roles and file layout

| Builder | Owns (writes only these) |
|---|---|
| **B1 Stimuli** | `HX/build/**`, `HX/site/stimuli/**` (manifest, images, example) |
| **B2 Texts, style, page shell, docs** | `HX/site/index.html`, `HX/site/css/style.css`, `HX/site/js/config.js`, `HX/site/js/texts.js`, `HX/site/.nojekyll`, `HX/README.md` |
| **B3 Experiment logic + checks** | `HX/site/js/experiment.js`, `HX/tools/**`, `HX/site/stimuli_mock/**` |

```
HX/
  SPEC.md                      this file
  README.md                    (B2) setup + deployment checklist for the author
  build/                       (B1) never deployed
    dump_codes.py              GPU job: names, per-atom corr, sparse codes, pre-code extremes
    run_dump.sh                sbatch wrapper (aarch64 GPU node)
    select_and_render.py       login-node python3: selection, lists, images, manifest
    codes_coco.npz, codes_imagenet.npz
    selection_report.json      counts, exclusion reasons, balance stats
    contact_sheet.html         visual QA of every atom (refs, queries, names), for the author only
    logs/
  tools/                       (B3) never deployed
    check_site.py              validates the contract (manifest, example, texts, config, files)
    make_mock_stimuli.py       builds site/stimuli_mock/ with labelled placeholder images
  site/                        = GitHub Pages root (deploy this folder's contents)
    index.html
    .nojekyll
    css/style.css
    js/config.js  js/texts.js  js/experiment.js
    stimuli/manifest.json
    stimuli/img/<atom_id>/{h0..h8,l0..l8,qpos,qneg}.jpg
    stimuli/example/example.json + {h0..h8,l0..l8,qpos,qneg}.jpg
    stimuli_mock/              dev only, delete before deployment
```

---

## Part 4. Stack (pinned, verified HTTP 200 on 2026-10-08)

All from unpkg, exact versions (globals in parentheses):

```html
<link rel="stylesheet" href="https://unpkg.com/jspsych@8.3.0/css/jspsych.css">
<link rel="stylesheet" href="css/style.css">   <!-- after jspsych.css so it overrides -->
<script src="https://unpkg.com/jspsych@8.3.0/dist/index.browser.min.js"></script>                          <!-- initJsPsych -->
<script src="https://unpkg.com/@jspsych/plugin-browser-check@2.1.0/dist/index.browser.min.js"></script>     <!-- jsPsychBrowserCheck -->
<script src="https://unpkg.com/@jspsych/plugin-html-button-response@2.1.0/dist/index.browser.min.js"></script> <!-- jsPsychHtmlButtonResponse -->
<script src="https://unpkg.com/@jspsych/plugin-call-function@2.1.0/dist/index.browser.min.js"></script>     <!-- jsPsychCallFunction -->
<script src="https://unpkg.com/@jspsych/plugin-fullscreen@2.1.0/dist/index.browser.min.js"></script>        <!-- jsPsychFullscreen -->
<script src="https://unpkg.com/@jspsych/plugin-preload@2.1.0/dist/index.browser.min.js"></script>           <!-- jsPsychPreload -->
<script src="https://unpkg.com/@jspsych/plugin-instructions@2.1.0/dist/index.browser.min.js"></script>      <!-- jsPsychInstructions -->
<script src="https://unpkg.com/@jspsych/plugin-survey-html-form@2.1.0/dist/index.browser.min.js"></script>  <!-- jsPsychSurveyHtmlForm -->
<script src="https://unpkg.com/@jspsych-contrib/plugin-pipe@0.6.0/dist/index.browser.min.js"></script>     <!-- jsPsychPipe -->
<script src="js/config.js"></script>
<script src="js/texts.js"></script>
<script src="js/experiment.js"></script>
```

`index.html` (B2): `<!doctype html>`, `lang="en"`, charset + viewport metas, `<title>` = `EXP_TEXTS.title` value written literally (e.g. "Image study"), body contains only `<div id="jspsych-target"></div>` and a `<noscript>` message. No Google Fonts (system font stack; one less external dependency). No analytics.

plugin-pipe 0.6.0 API (read from its source): trial `{type: jsPsychPipe, action: "save", experiment_id, filename, data_string: () => ..., wait_message}`; static `jsPsychPipe.getCondition(expID)` POSTs to `https://pipe.jspsych.org/api/condition/` and returns `result.condition` (an integer) **or, on a network error, returns the Error object instead of throwing**, so the caller must check `Number.isInteger(x) && x >= 0 && x < 12`. Saved trial data contains `result` (server JSON response; `success` field when OK). Uploads are gzip-compressed by default.

jsPsych 8 notes for B3: there is no `addNodeToEndOfTimeline`; build the full timeline up front and make condition-dependent parameters **functions** (dynamic parameters), reading a global `STATE` filled once the condition is known. `button_html` is a function `(choice, index) => html`. Use `jsPsych.evaluateTimelineVariable`, `jsPsych.data.addProperties`, `jsPsych.data.getURLVariable`, `jsPsych.data.getInteractionData()`, `jsPsych.randomization.shuffle/randomID`, `jsPsych.abortExperiment(html)`, `jsPsych.progressBar.progress`, `jsPsych.pluginAPI.preloadImages(list, cb)`.

---

## Part 5. Shared contracts (all builders follow these exactly)

### 5.1 `site/stimuli/manifest.json` (B1 writes, B3 reads)

```jsonc
{
  "version": "<string>",                         // e.g. "2026-10-08-v1"; copied into every data row
  "lists": [ {"list": 0, "test_atoms": ["<atom_id>", ... 40 ids]}, {"list": 1, ...}, {"list": 2, ...} ],
  "atoms": {
    "<atom_id>": {                               // "coco_5590", "imagenet_1234"; also practice and catch items
      "dataset": "coco" | "imagenet",
      "stratum": "R" | "Delta" | "practice" | "catch",
      "refs_high": ["stimuli/img/<atom_id>/h0.jpg", ... 9 paths],   // most activating, naming split, h0 = highest
      "refs_low":  ["stimuli/img/<atom_id>/l0.jpg", ... 9 paths],   // lowest pre-code, naming split, l0 = lowest
      "query_pos": "stimuli/img/<atom_id>/qpos.jpg",                 // held-out, strongly activating
      "query_neg": "stimuli/img/<atom_id>/qneg.jpg",                 // held-out, same category, atom inactive
      "names": {"A": null, "B": "<SALT name>", "C": "<permuted SALT name>", "D": "<CLIP-Dissect name>"},
      "meta": {"corr_salt": <float>, "corr_cd": <float>, "delta_sign": <-1|0|1>, "category": "<string>"}
    }
  },
  "practice": ["<atom_id>", ... 9],
  "catch": ["<atom_id>", ... 5]
}
```
Rules: paths are relative to `site/` (the page root); all images are square RGB JPEG 224x224. `atom_id = "<dataset>_<global SAE atom index>"` (the index used as key in `ov8m_*_sd0.json` names). Every id in `lists`, `practice`, `catch` exists in `atoms`; the 120 pool atoms, 9 practice atoms and 5 catch atoms are pairwise disjoint. `meta` **may** contain extra keys (B3 ignores unknown keys); B1 adds the extras listed in 6.6.

### 5.2 `site/stimuli/example/example.json` (B1 writes, B3 reads; extension of the contract)
One atom entry with the **same schema** as a manifest atom, plus `"atom_id"`, with paths `stimuli/example/h0.jpg` ... `stimuli/example/qneg.jpg`, `"stratum": "practice"`. The example atom is outside the pool, the practice set and the catch set.

### 5.3 `site/js/texts.js` (B2 writes, B3 reads)
```js
window.EXP_TEXTS = {
  title: "...",
  consentHtml: "...",
  instructionPages: { A: [html, ...], B: [...], C: [...], D: [...] },  // each list ends with the example page
  practiceIntroHtml: "...",
  testIntroHtml: "...",
  trialPrompt: "...",                         // shown above the two queries
  nameLabel: "This concept:",
  referenceLabels: { high: "...", low: "..." },
  confidencePrompt: "...",
  confidenceLabels: ["...", "...", "...", "...", "..."],   // 1 (lowest) to 5 (highest), left to right
  feedback: { correct: "...", incorrect: "..." },
  questionnaire: [ { name, prompt, type: "text" | "multi-choice", options?, conditions?: ["B","C","D"] } ],
  endHtml: "...",
  prolificCompletionUrl: "https://app.prolific.com/submissions/complete?cc=COMPLETION_CODE",
  // ---- required extension (both B2 and B3 rely on it) ----
  ui: {
    consentAgree: "I agree", consentDecline: "I do not agree",
    noConsentHtml: "...",              // shown after decline; asks to return the study on Prolific
    browserExclusionHtml: "...",       // desktop/laptop only message
    fullscreenHtml: "...", fullscreenButton: "Enter full screen",
    nextButton: "Next", previousButton: "Previous", continueButton: "Continue", submitButton: "Submit",
    exampleTargetCaption: "...",       // under the correct query in the example page
    yourChoice: "Your choice",         // caption under the chosen query on confidence/feedback screens
    progressLabel: "Progress",
    savingHtml: "...", saveErrorHtml: "...",
    loadingHtml: "...", loadErrorHtml: "...",
    endButton: "Return to Prolific"
  }
};
```
Token: the last instruction page of every condition contains the literal token `{{EXAMPLE_TRIAL}}`. B3 replaces it with the rendered example display (5.6). The page may also reference `stimuli/example/*.jpg` directly. B3 must not hard-code participant-facing English except as a fallback when a key is missing (and must log a console warning).

### 5.4 `site/js/config.js` (B2 writes, B3 reads)
```js
(function () {
  const p = new URLSearchParams(window.location.search);
  const debug = p.get("debug") === "1";
  let conditionOverride = null;
  if (debug && p.get("cond")) {
    conditionOverride = { condition: p.get("cond").toUpperCase(), list: parseInt(p.get("list") || "0", 10) };
  }
  window.EXP_CONFIG = {
    datapipeExperimentId: "DATAPIPE_EXPERIMENT_ID",   // placeholder, set by the author
    nConditions: 12, nTest: 40, nPractice: 9, nCatch: 5,
    debug: debug,
    conditionOverride: conditionOverride
  };
})();
```
B3 validates the override (`condition` in A-D, `list` in 0-2); invalid -> ignored with a console warning. In debug mode only, B3 also reads `?stim=<folder>` (default `stimuli`) to load `<folder>/manifest.json` (used with `stimuli_mock`).

### 5.5 DOM and CSS classes (B3 emits, B2 styles)
Choice screen (`jsPsychHtmlButtonResponse`, `stimulus`):
```html
<div class="trial">
  <div class="concept-name">This concept: <strong class="concept-name-value">dog</strong></div>  <!-- omitted entirely in A -->
  <div class="ref-block ref-high">
    <div class="ref-label">Most activating images</div>
    <div class="ref-row"><img class="ref-img" src="..." alt="" draggable="false"> x9</div>
  </div>
  <div class="ref-block ref-low"> same structure, label = referenceLabels.low </div>
  <div class="trial-prompt">{trialPrompt}</div>
</div>
```
Buttons: `choices: ["left","right"]`, `button_layout: "flex"`, `button_html: (c,i) => '<button class="query-btn" data-side="'+c+'"><img class="query-img" src="..." alt="" draggable="false"></button>'`.
Confidence screen (stimulus): `.trial.trial-confidence` = `.concept-name` (B/C/D only) + `<div class="query-pair">` with two `<div class="query-static [is-chosen]"><img class="query-img"><div class="query-caption">Your choice</div></div>` + `.trial-prompt` (confidencePrompt). Buttons: `<button class="jspsych-btn conf-btn"><span class="conf-num">k</span><span class="conf-label">label</span></button>`, k = 1..5 left to right. References are not repeated on this screen (keeps it within 650 px height).
Practice feedback screen: `.trial.trial-feedback` = `<div class="feedback feedback-correct|feedback-incorrect">` + `.query-pair` where the target has class `is-target` and the chosen one `is-chosen` + one Continue button.
Example (instructions): `<div class="example-trial">` containing a static `.trial` (references + name for B/C/D) and a `.query-pair` with `is-target` on the positive query and caption `ui.exampleTargetCaption`.
Debug badge (debug only): `<div class="debug-badge">atom_id · stratum · target=left</div>`.

CSS requirements (B2): light theme only, explicit `body` background, system font stack, tokens on `:root` (`--bg --card --text --muted --accent --ok --err --border`). `--ref-size: min(96px, calc((100vw - 140px) / 9))`, `--query-size: min(200px, 24vh)`. Reference rows: 9 images on one line, 4 px gap, thin border; the two rows separated clearly (label above each row, 16 px gap); the high and low rows are styled identically (no green/red that could act as a cue). `.concept-name` centered, 1.25rem, light box, name in bold. `.query-btn`: no default jsPsych button chrome, 3 px transparent border, hover border `--accent`, cursor pointer. `.is-chosen` outline `--accent`, `.is-target` outline `--ok` 4 px. `.feedback-correct` uses `--ok`, `.feedback-incorrect` `--err`. Whole choice screen must fit without scrolling in a 1000x650 window. Disable text selection on trial screens; `img {user-select:none; -webkit-user-drag:none}`.

### 5.6 Render functions (B3, inside experiment.js)
`renderReferences(atom, cond)`, `renderChoiceScreen(item)`, `renderConfidenceScreen(item, chosenSide)`, `renderFeedbackScreen(item, chosenSide)`, `renderExample(exampleAtom, cond)`. The example uses the same functions as real trials, so it looks exactly like a trial. The positive query side in the example is fixed to `right`.

---

## Part 6. B1: stimulus pipeline

### 6.1 Sources (verified on disk)
- Names and paper numbers: `ov_out/ov8m_coco_sd0.json` and `ov_out/ov8m_imagenet_sd0.json` (the files `paper_cvpr27/gen_tables.py` reads). `vocabs['20k']['names']['tete']` = **SALT names**, `vocabs['20k']['names']['clip_dissect']` = **CLIP-Dissect names** (keys = global atom index as string; 6130 coco / 6143 imagenet). Reference medians: `vocabs['20k']['res'][arm]['mediane']['UF_correlation']` (coco: tete 0.21897, clip_dissect 0.19092; imagenet: 0.23755, 0.22944).
- Producing job: `scratch_xm/wk_jobs/m_{coco,imagenet}_sd0.sh`, i.e. `CKPT=etfix_ckpt/note_{key}_train_lin_supp_s0.pt SCALER=<XM>/{key}_train/cache/ds/{key}_train/scaler.pkl PLAN=1 VOCAB=both OUTTAG=_sd0 python scratch_xm/ov_8m.py {key}` with the venv `/lustre/work/pdl16831/udl5a0991/sae_bench_env/.venv/bin/python3` and `HF_HUB_OFFLINE=1 HF_HOME=/lustre/work/pdl16831/udl5a0991/.cache/huggingface`.
- Data caches (`XM=/lustre/work/pdl16831/udl5a0991/concept_captions_out/crossmodal`): coco = `XM/coco_ws/cache/ds/coco` (COCO val2017, N=5000, EVAL 1000), imagenet = `XM/imnet50k_sbert/cache/ds/imagenet` (ImageNet val, N=50000, EVAL 10000). Files: `A_img.npy`, `image_ids.npy`, `id2path.json`, `img_to_cats.json`, `cat_names.json`, `caps_by_img.json`.
- **ID trap**: in coco, `id2path.json` is keyed by **row** (`"0"` -> `.../000000256518.jpg`) while `image_ids[row]` is the COCO id (256518) and `img_to_cats.json` / `caps_by_img.json` / `plan_base` are keyed by **COCO id**. In imagenet, ids == rows. Work with row indices internally; assert for every image used that `basename(id2path[str(row)])` contains `f"{image_ids[row]:012d}"` (coco) and that rows equal ids (imagenet).
- Category: coco = the 80 COCO categories (multi-label list per image); imagenet = the class name (one per image).

### 6.2 GPU job `build/dump_codes.py` (+ `build/run_dump.sh`)
GPU nodes are aarch64; the login node is x86 without torch. Run through sbatch: `sbatch -p defq --gres=gpu:1 -c 16 -t 01:00:00 -o HX/build/logs/%x_%j.out` with the venv above. Start from a **copy** of `scratch_xm/ov_8m.py` (do not edit the original), run with the sd0 environment but `VOCAB=20k`, and add a dump after the scoring loop. It reproduces exactly: Z = TopK(k=32)(ReLU(scaler(A) @ We.T + be)); split `perm = default_rng(0).permutation(N)`, EVAL = first 20 % (held-out), TRAIN = rest (naming split); Y_open from captions; `uf_scores` per arm grouped by word. Write `build/codes_{key}.npz` with:
- `live` (global atom indices), `ev`, `tr` (row indices), `words` (20k list);
- `salt_word`, `cd_word` (word index per live atom), `corr_salt`, `corr_cd` (per live atom, `UF_correlation` on EVAL, NaN when not scored);
- `nact_ev` (number of EVAL images with Z>0 per atom), `nact_tr`;
- sparse codes for all N images: `z_idx` [N,32] int32, `z_val` [N,32] float32 (post-TopK);
- `top_tr` [n_live,50] TRAIN rows with the highest Z (descending), `low_tr` [n_live,9] TRAIN rows with the **lowest pre-code** h = scaler(A) @ We.T + be (ascending), with their values `top_tr_val`, `low_tr_val`;
- `top_ev` [n_live,10] EVAL rows with the highest Z and their values.
**Validation (blocking)**: recomputed `salt_word`/`cd_word` must equal the sd0 names for 100 % of atoms, and the medians of `corr_salt`/`corr_cd` over scored atoms must equal the sd0 medians to 1e-6. On any mismatch, stop and report; never continue on approximate names. Pilot on coco first, read the log, then imagenet.

### 6.3 Evaluable atoms (`build/select_and_render.py`, login `python3` 3.9 with numpy 1.20 + Pillow 10)
An atom is evaluable iff all hold:
1. live; `nact_ev >= 16` (same threshold as the judge plans); at least 9 TRAIN images with Z>0;
2. both names exist and both corrs are finite;
3. neither name nor any name it could receive in C is on the blocklist (a short explicit list of slurs/sexual/violent words in `build/blocklist.txt`; report every hit);
4. a valid query pair exists (6.4);
5. all 20 source images open, are RGB-convertible, and are distinct files.
Record the count lost at each step per dataset in `selection_report.json`.

### 6.4 Query pair
- Positive: walk `top_ev` (rank 1..5 only) in order; the first candidate for which a negative exists is `query_pos`.
- Category: imagenet = class of the positive. coco = the positive's categories tried from rarest to most frequent on EVAL ('person' last); the first category with at least one negative is used. A coco image without categories cannot be a positive.
- Negative: EVAL rows with Z_atom = 0 (atom inactive) that share the category, excluding the positive; pick one with `default_rng(seed_atom)`, `seed_atom = 1000003*atom + 7` (dataset-specific offset: +1 for imagenet). Record its pre-code.
Queries come from EVAL, references from TRAIN, so they never overlap.

### 6.5 Selection (seed `rng = numpy.random.default_rng(20261008)`, recorded)
Per dataset, in this order:
1. **R**: 30 atoms drawn uniformly from evaluable atoms.
2. **Delta**: from evaluable atoms not in R with `salt name != cd name` (string compare), the 30 with the largest `|corr_salt - corr_cd|`; `delta_sign = sign(corr_salt - corr_cd)` (0 if equal) is stored for every atom.
3. **Practice**: 9 atoms (5 coco + 4 imagenet) not in R/Delta, the most clear-cut ones: largest `min(corr_salt, corr_cd)` with `z_pos` above the median of the pool's `z_pos`.
4. **Catch**: 5 atoms (3 coco + 2 imagenet) drawn uniformly from the remaining evaluable atoms. `query_pos` = **a copy of `refs_high[k]`** with `k = rng.integers(9)`; store `meta.catch_ref_index = k`. `query_neg` as in 6.4.
5. **Example**: 1 imagenet atom from the remaining evaluable atoms with high `corr_salt` and a visually obvious pair (check on the contact sheet); write it to `stimuli/example/`.
6. **Lists**: for each dataset, R atoms sorted by `corr_salt` and Delta atoms sorted by `|delta|`; walk each sorted list in consecutive blocks of 3 and assign a random permutation of lists {0,1,2} inside each block. Result: each list gets 10 R + 10 Delta per dataset; list `test_atoms` = its 40 ids. Report per-list mean corr_salt, corr_cd, |delta| and sign counts.
7. **C names**: within each (dataset, group) with group in {pool (R+Delta), practice, catch}, a random derangement sigma; `names.C(a) = SALT name of sigma(a)`, redrawn until for every a: `names.C(a) != names.B(a)` and `names.C(a) != names.D(a)`. Store `meta.c_source = sigma(a)`. The example's C name comes from another non-pool imagenet atom.

### 6.6 Images and extra meta
- Crop: mirror the preprocessing used to build `A_img.npy` for these caches (find it in the cache builder; `crossmodal/scripts/build_backbone_feature_cache.py` uses `Resize((224,224))`, other scripts use shorter-side resize + `CenterCrop`). Participants should see what the model saw; if the cache squashed the image, use shorter-side resize to 224 + center crop 224 instead (no distortion) and note it in the report. Bicubic, RGB, JPEG quality 85, `optimize=True`, EXIF stripped. Target <= 20 kB per file (total site < 60 MB).
- Names: shown verbatim as stored (lowercase); replace `_` with a space.
- Extra `meta` keys: `same_name` (bool), `c_source`, `z_pos`, `h_neg`, `pos_rank_ev`, `nact_ev`, `catch_ref_index` (catch only), `src` = `{"refs_high":[dataset ids], "refs_low":[...], "query_pos":id, "query_neg":id}` for traceability.

### 6.7 B1 outputs and checks
- `site/stimuli/manifest.json`, `site/stimuli/img/**`, `site/stimuli/example/**`, `build/selection_report.json`, `build/contact_sheet.html` (one block per atom: 9+9 refs, the two queries labelled pos/neg, names A-D, corrs, category; for the author to screen out disturbing or identifying images, especially people in ImageNet).
- Run `python3 HX/tools/check_site.py` (from B3) when available; otherwise check counts, disjointness, list composition, image sizes yourself.
- Deliver only what really ran: report job ids, the validation numbers of 6.2, and the counts of 6.3.

---

## Part 7. B3: experiment.js

### 7.1 Startup (before `jsPsych.run`)
1. `jsPsych = initJsPsych({ display_element: "jspsych-target", show_progress_bar: true, auto_update_progress_bar: false, message_progress_bar: EXP_TEXTS.ui.progressLabel, on_finish: ... })`.
2. Read URL: `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID` (`jsPsych.data.getURLVariable`). `subject_id = jsPsych.randomization.randomID(12)`. `pid_missing = !PROLIFIC_PID`.
3. `fetch(manifestUrl)` and `fetch("stimuli/example/example.json")`; on failure show `ui.loadErrorHtml` and stop. Validate the manifest (counts against `EXP_CONFIG`, 3 lists of 40, every id present); on failure in production show `ui.loadErrorHtml`; in debug, show the error.
4. `jsPsych.data.addProperties({prolific_pid, study_id, session_id, subject_id, pid_missing, exp_version: EXP_VERSION, manifest_version, debug, user_agent: navigator.userAgent, start_iso})`. `EXP_VERSION = "1.0.0"` constant at the top of the file.
5. Build the whole timeline (7.2) and `jsPsych.run(timeline)`.

### 7.2 Timeline
| # | Node | Plugin | Notes |
|---|---|---|---|
| 1 | Browser check | `jsPsychBrowserCheck` | `minimum_width: 1000, minimum_height: 650, window_resize_message` (default ok), `skip_features: ["webaudio","webcam","microphone","vsync_rate"]`, `inclusion_function: d => !d.mobile`, `exclusion_message: ui.browserExclusionHtml`. |
| 2 | Consent | `jsPsychHtmlButtonResponse` | `stimulus: consentHtml`, `choices: [ui.consentAgree, ui.consentDecline]`. Decline (index 1) -> `jsPsych.abortExperiment(ui.noConsentHtml)`; no data are saved for decliners. Record `consent: true`. |
| 3 | Condition | `jsPsychCallFunction` `async: true` | Debug + valid override -> use it (`cond_source:"override"`). Debug without override -> random (`"debug_random"`). Production -> `await jsPsychPipe.getCondition(id)` raced against a 10 s timeout; valid integer 0..11 -> `"datapipe"`, else `Math.floor(Math.random()*12)` and `"fallback"`. Then `condition = "ABCD"[i % 4]`, `list = Math.floor(i / 4)`, `addProperties({cond_index, condition, list, cond_source})`, build `STATE` (7.3), and start a **background** `jsPsych.pluginAPI.preloadImages(testAndCatchImages)`. The condition is requested only after consent, so decliners and ineligible browsers do not consume DataPipe slots. |
| 4 | Fullscreen | `jsPsychFullscreen` | `fullscreen_mode: true`, `message: ui.fullscreenHtml`, `button_label: ui.fullscreenButton`. Not forced afterwards; exits are logged by interaction data. |
| 5 | Preload 1 | `jsPsychPreload` | `images: () => example + practice images` (dynamic), `show_progress_bar: true`, `message: ui.loadingHtml`, `max_load_time: 120000`, `continue_after_error: false`, `error_message: ui.loadErrorHtml`. |
| 6 | Instructions | `jsPsychInstructions` | `pages: () => EXP_TEXTS.instructionPages[STATE.condition]` with `{{EXAMPLE_TRIAL}}` replaced by `renderExample(example, condition)`; `show_clickable_nav: true, allow_backward: true`, button labels from `ui`. |
| 7 | Practice intro | `jsPsychHtmlButtonResponse` | `practiceIntroHtml`, Continue. |
| 8 | Practice x9 | timeline with `timeline_variables` = slots 0..8 | choice -> confidence -> feedback (7.4). |
| 9 | Preload 2 | `jsPsychPreload` | test + catch images (usually instant, already cached by the background preload). |
| 10 | Test intro | `jsPsychHtmlButtonResponse` | `testIntroHtml` ("from now on no feedback"), Continue. This is the "point of no return" screen of the example. |
| 11 | Test x45 | timeline with slots 0..44 | choice -> confidence (no feedback); 40 test + 5 catch, same look. |
| 12 | Questionnaire | `jsPsychSurveyHtmlForm` | Built from `EXP_TEXTS.questionnaire`, keeping items with no `conditions` or whose `conditions` include the participant's condition. `text` -> `<textarea name=... required rows=3>`; `multi-choice` -> radio group, `required`. One page, `button_label: ui.submitButton`. Exit fullscreen before it (`jsPsychFullscreen` with `fullscreen_mode:false`, only if currently fullscreen). |
| 13 | Summary | `jsPsychCallFunction` | Writes one row `task:"summary"` (7.6). |
| 14 | Save | `jsPsychPipe` `action:"save"` | Production only. `experiment_id: EXP_CONFIG.datapipeExperimentId`, `filename: \`${prolific_pid or "nopid"}_${session_id or subject_id}.csv\``, `data_string: () => jsPsych.data.get().csv()`, `wait_message: ui.savingHtml`. Then a call-function checks `result.success`; on failure retry up to 2 times with `jsPsychPipe.saveData(...)` (2 s apart). If still failing, set `save_failed` and show `ui.saveErrorHtml` (the participant still gets the completion link). Debug: skip DataPipe and call `jsPsych.data.get().localSave("csv", "debug_<subject_id>.csv")`. |
| 15 | End | `jsPsychHtmlButtonResponse` | `endHtml` + button `ui.endButton`; on click (or after 10 s, `trial_duration: 10000`) `window.location.href = EXP_TEXTS.prolificCompletionUrl`. No redirect in debug. |

Progress bar: `jsPsych.progressBar.progress = done / 54` after each practice and test trial (practice + test + catch = 9 + 45).

### 7.3 Randomisation (`STATE`)
- Practice: `manifest.practice` shuffled; sides = shuffle(5 x "left" + 4 x "right").
- Test: `T = shuffle(manifest.lists[list].test_atoms)`; split into 5 blocks of 8; `K = shuffle(manifest.catch)`; append `K[b]` to block b; shuffle each block; reshuffle block 0 until its first item is not a catch; concatenate -> 45 items. Sides: shuffle(20 x "left" + 20 x "right") for the 40 test atoms; catch sides random.
- Each item: `{atom_id, atom, phase: "practice"|"test", item_type: "practice"|"test"|"catch", seq (1-based within phase), pos_side, left_img, right_img, name_shown: atom.names[condition]}`.
- Store `STATE.test_order` (array of atom ids) and `STATE.sides` and add them to the summary row.

### 7.4 Trial screens (all `jsPsychHtmlButtonResponse`)
- **Choice**: stimulus `renderChoiceScreen(item)`, `choices: ["left","right"]`, `response_ends_trial: true`, no time limit. RT from screen onset (images are preloaded).
- **Confidence**: stimulus `renderConfidenceScreen(item, chosen)`; 5 buttons (`confidenceLabels`), response index + 1 = confidence 1..5.
- **Feedback** (practice only): `renderFeedbackScreen(item, chosen)` with `feedback.correct` or `feedback.incorrect`; Continue button.
- Debug: add the `.debug-badge` to choice screens.
- No keyboard responses; mouse/touchpad only.

### 7.5 Data written per row (`on_finish`)
Choice row: `task:"choice"`, `phase`, `item_type`, `seq`, `atom_id`, `dataset`, `stratum`, `category`, `name_shown` (null in A), `pos_side`, `left_img`, `right_img`, `response_side`, `correct` (bool), `rt` (jsPsych, ms).
Confidence row (**the analysis row, one per trial**): same item fields + `task:"confidence"`, `response_side`, `correct`, `rt_choice`, `confidence` (1-5), `rt_conf`.
Feedback row: `task:"feedback"`, `seq`, `atom_id`.
Other rows: `task` = `browser_check` (plugin fields: width, height, browser, browser_version, mobile, os, fullscreen), `consent`, `condition`, `instructions` (plugin `view_history`), `questionnaire` (`response` object; also copied as `q_<name>` columns on the summary row), `save`.
Participant columns on every row (via `addProperties`): `prolific_pid, study_id, session_id, subject_id, pid_missing, exp_version, manifest_version, debug, user_agent, start_iso, cond_index, condition, list, cond_source`.

### 7.6 Summary row (`task:"summary"`)
`session_complete: true`, `n_test` (40), `n_catch` (5), `catch_failed` (count), `test_accuracy` (40 test items), `practice_accuracy`, `median_rt_test` (choice RT over the 40 test items, catch excluded), `median_rt_test_incl_catch`, `total_duration_ms`, `n_blur`, `n_fullscreen_exit`, `interactions` (`jsPsych.data.getInteractionData().json()`), `test_order`, `sides`, `q_<name>` for each questionnaire item, `screen_w/h`, `window_w/h`. These are conveniences; exclusions are recomputed at analysis time from the trial rows.

### 7.7 B3 tools
- `tools/make_mock_stimuli.py` (login python3 + Pillow): writes `site/stimuli_mock/manifest.json` + `example.json` + placeholder JPEGs (224x224 grey squares with large text "coco_12 h3", "qpos", ...) following 5.1 exactly, image paths prefixed `stimuli_mock/`. Run with `?debug=1&stim=stimuli_mock&cond=B&list=1`.
- `tools/check_site.py`: validates 5.1-5.4 (keys, counts 3x40/9/5, pairwise disjointness, per list 10 R + 10 Delta per dataset, every path exists, every image is JPEG 224x224 RGB, names.A null and B/C/D non-empty, C != B and C != D, meta keys present, the token `{{EXAMPLE_TRIAL}}` present in the last page of every condition, `nameLabel == "This concept:"`, questionnaire item `used_name` restricted to B/C/D), and **warns** when placeholders remain (`DATAPIPE_EXPERIMENT_ID`, `COMPLETION_CODE`, `[ETHICS_`). Exit code 1 on any error. Usage: `python3 HX/tools/check_site.py [--stim stimuli|stimuli_mock]`.
- JS check: no Node on the login node. If possible download a Node LTS tarball into the scratchpad (not into `HX/site`) and run `node --check` on the three JS files; otherwise state that the JS was not executed. A local preview is `cd HX/site && python3 -m http.server 8000` (author opens it in a browser).

---

## Part 8. B2: texts, style, shell, README

### 8.1 Text guidance (plain, short, neutral)
- Never mention SALT, CLIP-Dissect, COCO, ImageNet, "permuted" or the condition letters to participants. Call the atom a "concept" learned by "an AI model".
- **Consent** (`consentHtml`): purpose in one sentence; task and duration (~12 minutes); voluntary, can stop at any time by closing the page; anonymous data, stored on a private OSF project, used for research and publication; Prolific ID used only to pay and removed before data are shared; 18+; contact `[CONTACT_EMAIL]`, `[PI_NAME]`, `[INSTITUTION]`, ethics `[ETHICS_COMMITTEE]` ref `[ETHICS_REF]` (keep these bracketed placeholders).
- **Instructions**: 4 pages + example page. A: (1) an AI model has many small units; each responds to a visual concept; (2) we show 9 images that activate a unit most (top row) and 9 that activate it least (bottom row); (3) you then see two new images and click the one that activates the unit, i.e. that belongs with the top row; both new images may show the same kind of object, so look at what the top-row images really share; then say how confident you are; (4) 9 practice trials with feedback, then about 45 trials without feedback, about 10 seconds each, take a short look but do not overthink; (5) example page with `{{EXAMPLE_TRIAL}}` and one line explaining the outlined answer.
  B, C, D: **identical text to each other**: same pages as A plus one paragraph (page 2): "Above the images you will also see a short name for the concept, produced automatically by a computer program, shown as: This concept: ...". No claim about whether the name is accurate or helpful. A contains no word about names.
- `trialPrompt`: "Which image activates this concept? (Which one belongs with the top row?)" (or close). `referenceLabels`: `{high: "Most activating images", low: "Least activating images"}`.
- `confidencePrompt`: "How sure are you?"; `confidenceLabels`: `["Guessing", "Not very sure", "Somewhat sure", "Quite sure", "Very sure"]`.
- `feedback`: `{correct: "Correct.", incorrect: "Not quite. The outlined image is the one that activates the concept."}`.
- `practiceIntroHtml`, `testIntroHtml` (states that feedback stops and the task starts for real; cannot go back).
- `questionnaire` (in this order, names fixed, all required):
  1. `{name:"strategy", type:"text", prompt:"In a few words, how did you choose between the two images?"}`
  2. `{name:"used_name", type:"multi-choice", conditions:["B","C","D"], prompt:"Did you use the displayed name?", options:["Yes, on most trials","Yes, on some trials","Rarely","No, never"]}`
  3. `{name:"age_range", type:"multi-choice", prompt:"Your age range", options:["18-24","25-34","35-44","45-54","55-64","65 or older","Prefer not to say"]}`
  4. `{name:"ai_familiarity", type:"multi-choice", prompt:"How familiar are you with artificial intelligence (AI)?", options:["Not at all","I have heard of it","I use AI tools","I have studied machine learning","I work in AI or machine learning"]}`
- `endHtml`: thanks; short debrief: the study tests whether automatically generated names help people understand what an AI unit responds to; different participants saw different versions (no name, or names from different programs, some deliberately mismatched); button returns to Prolific.
- `ui.saveErrorHtml`: data could not be saved; please send a Prolific message with your Prolific ID; you will still be paid; the completion button works.

### 8.2 `HX/README.md` (author checklist, no account creation by builders)
1. Local test: `python3 tools/make_mock_stimuli.py`, `python3 tools/check_site.py --stim stimuli_mock`, `cd site && python3 -m http.server 8000`, open `http://localhost:8000/?debug=1&stim=stimuli_mock&cond=C&list=2`, then the real stimuli with `?debug=1&cond=A&list=0` etc. (all 12 combinations).
2. OSF: create a private project + component for data; DataPipe (pipe.jspsych.org): new experiment linked to the OSF component, **enable data collection**, **enable condition assignment with 12 conditions**, optionally set a session limit; copy the 12-character id into `js/config.js` (`DATAPIPE_EXPERIMENT_ID`).
3. Prolific: study URL `https://<user>.github.io/<repo>/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` ("I'll use URL parameters"); device = desktop only; completion code into `texts.js` (`COMPLETION_CODE`); duration ~12 min; recruit in multiples of 12. DataPipe hands out conditions in order, so participants who drop out after consent leave gaps: check the counts per `cond_index` and top up.
4. Ethics placeholders in `texts.js`.
5. Delete `site/stimuli_mock/`, run `tools/check_site.py` (no warnings), then push the contents of `site/` to a GitHub Pages repo (author only), keep `.nojekyll`.
6. Pilot with 2-3 people in each condition; download the OSF files; check one row per trial and the summary row.
7. Exclusion rules (applied at analysis): `catch_failed >= 2`; `median_rt_test < 1500`; no `summary` row / missing file (incomplete; cross-check with Prolific "returned/timed-out").

### 8.3 Style
As in 5.5. Calm, neutral, light. Card max-width 1100 px for trial screens, 760 px for text screens (`.jspsych-content` override). Readable 16-17 px base font.

---

## Part 9. Acceptance criteria

- **B1**: GPU validation of 6.2 passed and quoted; manifest validates with `check_site.py`; 120 + 9 + 5 + 1 atoms, 2,700 images (134 x 20 + 20 for the example), all 224x224 JPEG; selection report with counts and balance; contact sheet written; nothing outside `HX/build/`, `HX/site/stimuli/`.
- **B2**: `index.html` loads exactly the pinned URLs of Part 4 in that order; `texts.js` has every key of 5.3 including `ui`, the token on every last instruction page, identical B/C/D wording, no name text in A; `config.js` is exactly 5.4; CSS covers every class of 5.5; README complete; all placeholders left visible.
- **B3**: experiment.js implements Part 7 with only the plugins of Part 4; works with the mock stimuli for all 12 (condition, list) pairs; per-trial confidence rows carry all item fields; catch trials look exactly like test trials; condition request happens after consent; debug never calls DataPipe; `check_site.py` and `make_mock_stimuli.py` run on the login node.

---

## Part 10. Open points for the author (not for builders to decide)
1. **Image rights**: ImageNet images are research-only; publishing ~1,300 ImageNet thumbnails on a public GitHub Pages site may need a check (COCO images carry Flickr licenses). Screen people/faces on the contact sheet.
2. Ethics references, contact, completion code, DataPipe id: placeholders.
3. Sample size per cell and the analysis model (e.g. mixed logistic regression `correct ~ condition * stratum + (1|participant) + (1|atom)`) are not fixed here.
4. Condition C is a mild deception (mismatched names presented as automatic names); the end screen debriefs. Confirm with the ethics committee.
5. COCO EVAL has only 1,000 images; if fewer than 60 COCO atoms + practice/catch are evaluable under 6.3-6.4, B1 stops and reports instead of relaxing the rules.

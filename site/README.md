# Image study (SALT human evaluation)

This folder is the web page for an online behavioural study run on Prolific. It is a static
site (HTML, CSS, JavaScript, JPEG images) meant for GitHub Pages. There is no build step.

The study asks whether the names that **SALT** gives to the units ("atoms") of a sparse
autoencoder (SAE) help people understand what those units respond to. SALT is a linear text
head on a frozen vision-only TopK SAE.

Full design: `../SPEC.md`. Deployment steps: `../DEPLOY.md`. Pre-registration draft:
`../PREREGISTRATION_DRAFT.md`.

> This file is served publicly if you deploy the whole folder. It names the conditions.
> `stimuli/manifest.json` does too. See DEPLOY.md, step 1, if you want to remove it.

## The task

Two-alternative forced choice (Colin, PhD thesis, chapter 3, experiment II with a semantic
control). One trial = one SAE atom.

1. The participant sees 9 images that activate the atom most (top row) and 9 that activate it
   least (bottom row).
2. Below, two new held-out images of the same category, left and right in random order. One
   activates the atom strongly, the other does not.
3. The participant clicks the one that belongs with the top row, then rates confidence (1-5).

Participant-facing text never says "atom", "SAE" or "activation". It says "concept" and
"images that match the concept most / least".

## Conditions (within subjects: every session mixes the active ones)

**8 Oct. 2026: condition C (permuted SALT name) is set aside for now.** The active conditions are
listed in `js/config.js` (`conditions: ["A", "B", "D"]`), with `nConditions = 3 lists x 3
rotations = 9` DataPipe cells; each session has 13-14 test atoms per condition. To bring C back,
set `conditions` to the four letters and `nConditions` to 12. The text below describes the
four-condition version.

| Letter | Shown above the reference images |
|---|---|
| A | nothing (no name, no placeholder) |
| B | `This concept: <SALT name>` |
| C | `This concept: <SALT name of another atom>` (fixed derangement within dataset) |
| D | `This concept: <CLIP-Dissect name>` |

B, C and D use the same instructions word for word.

Every participant sees the four conditions, mixed in random order: 10 test atoms each
(5 R + 5 Delta), plus practice and catch trials cycled over the four. DataPipe assigns a
counterbalancing cell `i` in 0..11: `list = Math.floor(i / 4)`, `rotation = i % 4`. Within a
list the 40 atoms are split into 4 fixed groups balanced by dataset and stratum
(`atomGroups` in `js/experiment.js`); group `g` gets condition `"ABCD"[(g + rotation) % 4]`,
so over the 4 rotations every atom is seen once in every condition. The condition of each
trial is in the `condition` column of the data. Each list holds 40 test atoms
(10 R + 10 Delta per dataset, COCO and ImageNet).

## Session

Browser check (desktop, window at least 1000 x 650) → consent → condition assignment →
full screen → instructions with an example → 9 practice trials with feedback → 40 test
trials + 5 catch trials, no feedback → questionnaire → save to OSF via DataPipe → end page
and redirect to Prolific. About 12 minutes.

## Run locally

From the `human_exp/` folder (login node, Python 3, Pillow):

```bash
python3 tools/make_mock_stimuli.py                  # placeholder images in site/stimuli_mock/
python3 tools/check_site.py --stim stimuli_mock     # validates manifest, texts, config, files
cd site && python3 -m http.server 8000
```

Then open in a desktop browser (pages must be served over HTTP; opening `index.html` as a
file does not work because the page fetches JSON):

- `http://localhost:8000/?debug=1&stim=stimuli_mock&rot=1&list=1` (mock images)
- `http://localhost:8000/?debug=1&rot=0&list=0` (real images)

On the cluster, forward the port first, e.g. `ssh -L 8000:localhost:8000 <login node>`.

Debug mode never contacts DataPipe and never redirects to Prolific. At the end it downloads
the data as `debug_<subject_id>.csv`. Try all 12 (condition, list) pairs before launch.

## URL parameters

| Parameter | Used when | Meaning |
|---|---|---|
| `PROLIFIC_PID` | production | Prolific participant id, filled by Prolific (`{{%PROLIFIC_PID%}}`) |
| `STUDY_ID` | production | Prolific study id (`{{%STUDY_ID%}}`) |
| `SESSION_ID` | production | Prolific session id (`{{%SESSION_ID%}}`) |
| `debug=1` | testing | debug mode: no DataPipe, no redirect, local CSV download, debug badge on trials |
| `rot=0..2` (0..3 with C) | debug only | force the rotation of the condition-to-atom assignment |
| `list=0..2` | debug only | force the list (default 0 when `rot` is given) |
| `stim=<folder>` | debug only | stimuli folder (default `stimuli`; use `stimuli_mock` for placeholders) |

Without `debug=1`, `cond`, `list` and `stim` are ignored. A missing `PROLIFIC_PID` does not
block the session; it is recorded as `pid_missing = true`.

## File layout

```
site/                       GitHub Pages root (publish the contents of this folder)
  index.html                page shell: loads jsPsych 8.3.0 and plugins (pinned, unpkg), then js/ and css/
  .nojekyll                 tells GitHub Pages to serve files as they are
  README.md                 this file
  css/style.css             layout and look (light theme, system fonts)
  js/config.js              DataPipe id (placeholder), counts, debug flags from the URL
  js/texts.js               every word participants see (consent, instructions, labels, questionnaire, end page)
  js/experiment.js          timeline, randomisation, data recording, saving
  stimuli/manifest.json     atoms, lists, names per condition, image paths, metadata
  stimuli/img/<atom_id>/    h0..h8.jpg (top row), l0..l8.jpg (bottom row), qpos.jpg, qneg.jpg
  stimuli/example/          example.json + the same 20 images, for the example on the last instruction page
  stimuli_mock/             placeholder stimuli for testing; delete before deployment
```

Outside `site/` (never deployed): `build/` (stimulus selection and rendering),
`tools/` (checks and mock stimuli), `SPEC.md`, `DEPLOY.md`, `PREREGISTRATION_DRAFT.md`.

## Editing text

All participant text is in `js/texts.js`. Keep these rules:

- Never mention SALT, CLIP-Dissect, COCO, ImageNet, permutation or condition letters.
- B, C and D share the same instruction pages (`NAMED_PAGES`); A uses `PLAIN_PAGES`, with no
  mention of names.
- Keep `{{EXAMPLE_TRIAL}}` on the last instruction page of each condition.
- Keep `nameLabel` as `This concept:` and the questionnaire `name` fields unchanged.
- Run `tools/check_site.py` after every change.

## Data

One CSV per participant is saved to the OSF component linked to DataPipe, named
`<PROLIFIC_PID>_<SESSION_ID>.csv`. The analysis row is the `task == "confidence"` row (one
per trial: item fields, choice, correctness, choice RT, confidence, confidence RT). A
`task == "summary"` row closes a complete session. Exclusions are applied at analysis time
only (see `../PREREGISTRATION_DRAFT.md`).

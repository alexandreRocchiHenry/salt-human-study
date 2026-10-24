# Image study (SALT human evaluation)

Static web page (HTML, CSS, plain JavaScript, JPEG images) for an online study with volunteers. It is meant for GitHub
Pages; there is no build step and no library.

The study asks whether the names that **SALT** gives to the units ("atoms", "neurons") of a sparse autoencoder help
people understand what those units respond to. SALT is a linear text head on a frozen vision-only TopK SAE.

> This file names the methods and the conditions, and `stimuli*/debug_key.json` holds the correct answers. For the real
> study, deploy without them (see "Deploying" below).

## The task

One round = one neuron. Participant text says "concept", never "neuron", "atom", "SAE" or "activation".

1. The 9 images that activate the neuron most and the 9 that activate it least.
2. Depending on the condition, a name for it: `This concept: <name>`.
3. Two new images. One activates the neuron strongly (the correct one); the other one does not. The participant clicks
   or taps the one that matches, or presses an arrow key. The next round follows at once: there is no confidence
   rating and no feedback (13 Oct. 2026).

| Condition | Shown above the images |
|---|---|
| A | nothing |
| B | the SALT name of the neuron |
| C | the SALT name of another neuron (set aside since 8 Oct. 2026) |
| D | the CLIP-Dissect name of the neuron |

## Session

Introduction page (context; a required "I am 18 or older and I agree to the conditions" checkbox; the conditions in a
pop-up) → 9 first rounds (practice neurons, not announced, recorded with phase `practice`) → 40 test rounds with 5 catch
rounds mixed in → questionnaire → saving → thank-you page (no redirect). About 10 minutes. Small "i" buttons open
detailed explanations (`EXP_TEXTS.info`) on every screen.

**Draw (random among the neurons).** Every session draws its own neurons with a seeded generator; the seed is saved.
`config.nTest` = 40 test neurons, 10 from each of the 4 stratum cells of the manifest (COCO R, COCO Delta, ImageNet R,
ImageNet Delta, 30 neurons each), so each neuron is seen by a third of the participants. The conditions are balanced
within the session (14 / 13 / 13) and within each cell. The 9 practice and 5 catch neurons are the same for everyone, in a
random order (one catch round per block of 8 test rounds; never the first test round). Which candidate comes first is
random. Balance across participants holds on average; a server-side assignment could balance it exactly later.

**Navigation.** Each screen is an entry of the browser history: the browser's back button returns to the previous round
(its answer is outlined and can be changed), the forward button returns to where the participant was, and answering a
round that was already answered jumps back to the first unanswered one. The progress is kept in `localStorage`: a
reload or a closed tab resumes the session at the same round (for 48 hours, with the same stimulus version). After the
end, the page stays on the thank-you screen.

**Layout.** Round screens fill about 85-90 % of the window. Landscape windows show the reference images in two rows of
9 and the two candidates side by side (keys ← and →). Portrait windows (narrow desktop windows, tablets held upright,
phones) show them in two columns of 9, with the candidates one above the other (keys ↑ and ↓). Image sizes follow the
window. A phone held sideways is asked to turn upright. Phones and tablets are accepted; the keyboard tip is hidden on
touch screens.

## Image codes (13 Oct. 2026)

Images are named `<neuron>-<image>.jpg` (for example `2g7qgy-7nyvyd.jpg`): the first 6 characters are the same for the
20 images of a neuron, the last 6 identify the image. Both are keyed hashes: they reveal neither the atom, nor the
dataset, nor whether the image is a top, bottom, correct or wrong one. `manifest.json` lists the two candidates of a
neuron in code order, so it does not say which one is correct either, and neither does the page: the answers are
scored offline. The codes are produced by `../stimuli_gen/encode_stimuli.py`, which also writes the private codebook
(`../stimuli_gen/codebook/<set>_<version>.json` and `.csv`: every code → atom, dataset, stratum, role, rank, source image).
The same image in the same role of the same atom keeps its code from one version to the next.

## Data

One CSV per session, saved at the end through DataPipe (`datapipeExperimentId` in `js/config.js`, a placeholder for now)
as `<subject_id>_<start time>.csv`. One row per round (`row_type = round`) and one session row (`row_type = session`).

Round columns: `round`, `phase` (practice / test), `item_type` (practice / test / catch), `neuron`, `condition`,
`name_shown`, `img_1` and `img_2` (the candidates, first = left or top), `chosen_slot` and `chosen_img` (final answer),
`rt_ms` (from the moment the images are on screen), `first_slot`, `first_img`, `first_rt_ms` (first answer),
`n_answers`, `n_changes`, `input` (mouse, touch, pen, key, keyboard), `layout` (row / col), `n_blur`, `n_img_errors`,
window size, time stamps. Session row: questionnaire answers (`q_strategy`, `q_used_name`, `q_age_range`,
`q_ai_familiarity`), number of back moves and resumptions, screen size, pixel ratio, touch screen, user agent, and every
answer event as JSON. Every row also carries `subject_id`, `seed`, `exp_version`, `stimuli`, `manifest_version`.

Scoring: `python3 ../stimuli_gen/decode_responses.py <csv files or folder> -o decoded.csv` adds `atom`, `dataset`,
`stratum`, `pos_img`, `pos_slot`, `correct`, `first_correct` and checks every code.

`responseEndpoint` in `js/config.js` (null for now) prepares a dynamic version: if set to a URL, every answer is sent there
as it is given (`{"kind": "answer", "row": ...}`) and the whole session at the end (`{"kind": "session", "csv": ...}`),
by POST with a JSON body sent as `text/plain`. If you use it, update the "conditions" text (answers are no longer sent
only at the end).

## Debug mode

| Parameter | Meaning |
|---|---|
| `debug=1` | trial browser: the rounds of one session draw (practice excluded), ◀ ▶ buttons or ← → keys to move without answering; a click on a candidate shows the verdict and both names. The banner says where the name comes from, the atom, the correct image and the MLLM judge's description (`debug_key.json`) |
| `&full=1` | the participant flow instead, with the banner on every round; nothing is sent, the CSV is downloaded at the end and the scores are shown |
| `&all=1` | browser: every neuron of the set (practice and catch included) |
| `&proto=a\|b\|c` | prototype set `stimuli_a`, `stimuli_b`, `stimuli_c` (the default `stimuli` is prototype b) |
| `&proto=hard_a0` ... `hard_b2` | harder reference rows on 20 neurons, 5 per cell (`stimuli_gen/make_hard_grid.py`, 23 Oct. 2026): top row 0 = as now, 1 = 9 drawn among the top 25, 2 = 9 drawn among the top 50; bottom row A = nearest twins with no category cap and no judge, B = as now; `hard_a1` is the author's case C, `hard_b0` the control. The banner names the case. Small sets like these are accepted in debug only |
| `&seed=<n>` | reproduce a draw (the seed is in the banner and in the data) |
| `&cond=A\|B\|C\|D` | show one condition on every round |
| `&resume=1` | with `full=1`: keep the progress in `localStorage`, to test resuming after a reload |
| `&stim=<folder>` | another stimulus folder |

## Local test

```bash
cd human_exp/site && python3 -m http.server 8000
# then open http://localhost:8000/?debug=1  (browser)  or  http://localhost:8000/?debug=1&full=1  (participant flow)
```

## Files

```
index.html            page shell (no external script)
css/style.css         layout and look (light theme, system fonts)
js/config.js          DataPipe id, response endpoint, conditions, number of test rounds, debug flags from the URL
js/texts.js           every word participants see
js/experiment.js      draw, screens, browser history, saved progress, data, saving, debug browser
stimuli/              default set (prototype b): manifest.json, debug_key.json, img/<neuron>-<image>.jpg
stimuli_a|b|c/        prototype sets, same layout
```

## Caching

Image URLs carry the stimulus version (`?v=<manifest.version>`); scripts and the stylesheet carry `?v=<date>` in
`index.html`: change it whenever `js/` or `css/` changes. The manifest is fetched with `cache: "no-store"`.

## Deploying

Fill in `[PI_NAME]`, `[INSTITUTION]`, `[CONTACT_EMAIL]` in `js/texts.js` and the DataPipe id in `js/config.js`. For the
real study, leave out this README and the answer keys:

```bash
rsync -a --delete --exclude '.git' --exclude '.nojekyll' --exclude 'README.md' --exclude 'debug_key.json' \
  human_exp/site/ <pages repo>/
```

Debug mode then still works, without the banner's answer information.

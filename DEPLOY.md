# Deploying the SALT human study

Step-by-step guide for the author. Nothing here has been done yet: no repository, OSF
project, DataPipe experiment or Prolific study exists. Every value written `LIKE_THIS` or
`[LIKE_THIS]` is a placeholder you fill in.

Order: 0 local test → 1 GitHub Pages → 2 OSF + DataPipe → 3 Prolific → 4 pilot → 5 main
collection. Use the checklist at the end before each launch.

---

## 0. Test locally first

```bash
cd human_exp
python3 tools/make_mock_stimuli.py
python3 tools/check_site.py --stim stimuli_mock
python3 tools/check_site.py                       # real stimuli
cd site && python3 -m http.server 8000
```

Open `http://localhost:8000/?debug=1&rot=0&list=0` and go through all 12 combinations
(A-D × list 0-2), at least up to the first test trials. Run one full session to the end and
open the downloaded `debug_*.csv`: one `choice` and one `confidence` row per trial, and one
`summary` row.

Look at `build/contact_sheet.html` and remove any atom with disturbing or identifying images
(people's faces, especially in ImageNet). If you remove atoms, the stimuli builder must
regenerate the manifest so that lists stay balanced.

## 1. GitHub repository and GitHub Pages

1. On GitHub, create a **new repository**, e.g. `image-study`. Free GitHub Pages needs a
   **public** repository, so everything in it is public: the images, `stimuli/manifest.json`
   (which contains the names of each condition) and `README.md`. Do not put anything else in it
   (no build scripts, no notes, no data).
2. Prepare the folder to publish:
   - delete `site/stimuli_mock/`;
   - optional: delete `site/README.md` from the published copy (it describes the conditions);
   - keep `site/.nojekyll` (otherwise GitHub runs Jekyll and may hide files).
3. Copy the **contents** of `human_exp/site/` (not the folder itself) to the root of the
   repository, commit and push from your own machine.
4. In the repository: **Settings → Pages → Build and deployment → Source: Deploy from a branch**,
   branch `main`, folder `/ (root)`. Save.
5. After a minute or two the page is at `https://<github-user>.github.io/<repo>/`.
   Check `https://<github-user>.github.io/<repo>/?debug=1&rot=1&list=0` in a desktop browser.
6. Image rights: the repository publishes about 1,340 ImageNet and 1,340 COCO thumbnails.
   ImageNet images are for non-commercial research only; COCO images keep their Flickr
   licences. Check with your institution that this is acceptable before making the
   repository public.

Every later change (completion code, DataPipe id, text fixes) is a new commit to this
repository. Do not change stimuli or texts between the pilot and the main study except
under the rules in the pre-registration.

## 2. OSF project and DataPipe

1. On https://osf.io create a **private** project, e.g. "SALT image study", and inside it a
   **component** named `data`. The data component stays private.
2. On https://pipe.jspsych.org log in with your OSF account and create a **new experiment**:
   - OSF project: the `data` component above;
   - give DataPipe access to OSF when asked (OSF personal access token or OAuth, as the site
     explains).
3. In the experiment settings:
   - **Enable data collection**: on.
   - **Enable base64 data collection**: off (not used).
   - **Enable condition assignment**: on, **number of conditions: 12**.
   - Optional: a session limit a little above the number of participants you plan.
4. Copy the experiment ID (12 characters) into `site/js/config.js`:
   `datapipeExperimentId: "DATAPIPE_EXPERIMENT_ID"` → your ID. Commit and push.
5. Test without Prolific: open the GitHub page **without** `debug=1`
   (`https://<user>.github.io/<repo>/`), finish a session, and check that a file appears in
   the OSF component. Delete that test file afterwards and note that it used one condition
   slot.

How conditions work: DataPipe hands out indices 0, 1, ..., 11, 0, 1, ... in order. The page
maps index `i` to condition `"ABCD"[i % 4]` and list `floor(i / 4)`. It asks for an index only
after consent, so people who decline do not use a slot. People who drop out after consent do
leave gaps: check counts per `cond_index` during collection and top up (see section 5).

## 3. Prolific study

Create the study in Prolific (one study for the pilot, a separate one for the main data).

| Setting | Value |
|---|---|
| Study URL | `https://<github-user>.github.io/<repo>/?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}` |
| How to record Prolific IDs | "I'll use URL parameters" |
| Completion | "I'll redirect them using a URL". Copy the completion code into `site/js/texts.js`: `prolificCompletionUrl: "https://app.prolific.com/submissions/complete?cc=COMPLETION_CODE"` → replace `COMPLETION_CODE`. Commit and push. |
| Devices | Desktop only (untick mobile and tablet) |
| Estimated time | 12 minutes (adjust after the pilot to the median duration) |
| Payment | At or above Prolific's **recommended** hourly rate (check the current value on Prolific when you create the study), computed on the pilot's median duration |
| Approval rate | ≥ 95% |
| Repeat participation | Prolific already blocks repeats within one study. For the main study, add the screener **"Exclude participants from previous studies"** and select the pilot study (and any earlier version) |
| Language (suggested) | Fluent in English |
| Description | Neutral: "Look at sets of images and choose which new image belongs with a set (about 12 minutes, desktop only)." Do not mention names, AI explanations or methods. |

Before publishing, use Prolific's **Preview** to run one session and check that the
redirect at the end marks the submission as completed.

Approving submissions: approve everyone who reaches the end, including people who will be
excluded at analysis (failing catch trials is not by itself a reason to reject on Prolific;
follow Prolific's own attention-check policy if you want to reject).

## 4. Pilot

Goal: check that everything works, measure duration, and estimate accuracy and variance for
the power simulation. Pilot data are **not** used in the confirmatory analysis.

1. Every participant sees the active conditions (A, B, D for now; within-subject design). Cells are
   3 rotations × 3 lists = 9 DataPipe conditions (set 9 in DataPipe), so recruit **18** (2 per cell).
2. Download all CSVs from OSF. Check:
   - one file per participant, named `<PROLIFIC_PID>_<SESSION_ID>.csv`;
   - per file: 9 + 45 `confidence` rows, one `summary` row, `cond_source = "datapipe"`;
   - the four conditions and three lists are all present;
   - duration (median `total_duration_ms`), catch failures, median test RT;
   - the free-text strategy answers (do people understand the task?).
3. Apply the **ceiling rule** of the pre-registration: if accuracy on test trials in
   condition A is above 90%, the stimuli builder regenerates the positive queries with the
   harder rule and you re-check the site. Record the new `manifest.version`.
4. Run the power simulation on the pilot data (pre-registration, sample size section) and fix
   the final sample size. Update `PREREGISTRATION_DRAFT.md` and **register it on OSF before
   the main collection starts**.
5. Adjust payment and estimated time on Prolific to the pilot's median duration.

## 5. Main collection

1. Target: the number fixed by the power simulation on the pilot (within-subject design:
   every participant contributes to the four conditions), in multiples of 12.
2. Recruit in multiples of 12, plus the exclusion rate seen in the pilot, rounded up.
3. During collection, count usable sessions per `cond_index` (complete, not excluded). Top up
   by publishing more places in multiples of 12. DataPipe keeps cycling through 0..11, so
   cells stay close to balanced. All usable sessions are analysed, even if cells end up
   slightly unequal (this is the rule in the pre-registration).
4. Stop when every cell has reached its target. Do not look at accuracy by condition before
   collection is complete.

---

## Pre-launch checklist

Run through this before the pilot and again before the main study.

**Placeholders filled**
- [ ] `site/js/config.js`: `DATAPIPE_EXPERIMENT_ID` replaced by the real 12-character id.
- [ ] `site/js/texts.js`: `COMPLETION_CODE` replaced (and it matches the Prolific study).
- [ ] `site/js/texts.js`: `[PI_NAME]`, `[INSTITUTION]`, `[CONTACT_EMAIL]` (consent and end page),
      `[ETHICS_COMMITTEE]`, `[APPROVAL_NUMBER]` filled.
- [ ] `grep -rn "COMPLETION_CODE\|DATAPIPE_EXPERIMENT_ID\|\[[A-Z_]*\]" site/js` returns nothing.

**Ethics**
- [ ] Ethics approval obtained, including the mild deception in condition C (mismatched names
      presented as automatic names) and the debrief on the end page.
- [ ] Image publication (ImageNet / COCO) cleared.

**Site**
- [ ] `site/stimuli_mock/` deleted from the published copy.
- [ ] `python3 tools/check_site.py` passes with no errors and **no warnings**.
- [ ] `.nojekyll` is in the repository root.
- [ ] The live URL loads on Chrome, Firefox and Safari (desktop), with `?debug=1&rot=..&list=..`
      for all 12 pairs.
- [ ] A phone or a small window gets the exclusion message.
- [ ] Declining consent shows the "return the study" message and saves nothing.

**Data path**
- [ ] One production session (no `debug`) wrote a CSV to the OSF component.
- [ ] That CSV has `cond_source = "datapipe"`, all participant columns, 54 `confidence` rows,
      a `summary` row with `catch_failed`, `median_rt_test`, `test_order`, `sides` and the
      `q_*` answers.
- [ ] Test files deleted from OSF; test sessions noted (they used condition slots).

**Prolific**
- [ ] Study URL has the three `{{%...%}}` parameters and points to the live page (no `debug`).
- [ ] Desktop only, approval rate ≥ 95%, previous studies excluded (main study), payment at or
      above the recommended rate.
- [ ] Preview session completed and redirected correctly.

**Pre-registration**
- [ ] (Main study) Final sample size filled in and the pre-registration registered on OSF,
      with the `manifest.version` that will be used.

# Pre-registration draft: Do SALT names make SAE atoms interpretable to humans?

Format: OSF Preregistration template. Status: **draft**, to be completed after the pilot and
registered on OSF **before** the main data collection starts. Items marked `[TO FILL]` are
open.

> **Condition C (permuted SALT name) is set aside for now (8 Oct. 2026):** sessions mix A, B and D,
> 9 DataPipe cells (3 lists × 3 rotations). H2 (B > C) is suspended until C is reinstated.
>
> **Design change (8 Oct. 2026): the experiment is now within-subject.** Every participant sees
> the four conditions mixed in random order, 10 test atoms each (5 R + 5 Delta), with the
> condition-to-atom assignment rotated over 4 counterbalancing rotations × 3 lists (12 DataPipe
> cells), so that every atom is seen in every condition. The sections below that describe a
> between-subject design (study type, design, sample size, pilot size) must be rewritten
> accordingly: condition becomes a within-subject factor, the model gains a by-participant
> random slope of condition, and N is set by a power simulation for this design.

---

## 1. Study information

### 1.1 Title
Do automatically generated names help people predict what a sparse-autoencoder feature
responds to? A pre-registered test of SALT names.

### 1.2 Authors
[AUTHOR_LIST]

### 1.3 Description
Sparse autoencoders (SAEs) trained on the activations of a vision model decompose them into
many sparse units ("atoms"). Naming methods attach a short text label to each atom. **SALT**
is our naming method: a linear text head trained on a frozen, vision-only TopK SAE.
CLIP-Dissect is an established baseline.

We test whether SALT names help humans understand atoms, using the two-alternative
forced-choice task of Colin (PhD thesis, chapter 3, experiment II with semantic control).
On each trial, participants see 9 images that activate an atom most and 9 that activate it
least, then choose which of two new held-out images (same category, one strongly activating,
one not) activates the atom. Between subjects, we vary what is shown above the images: no
name (A), the SALT name (B), a SALT name of another atom (C, permuted), or the CLIP-Dissect
name (D).

### 1.4 Hypotheses

All hypotheses concern accuracy (probability of choosing the activating query) on test
trials.

- **H1 (names help).** On stratum R (random atoms), accuracy is higher with the SALT name (B)
  than with no name (A). One-sided.
- **H2 (the content of the name matters).** On stratum R, accuracy is higher with the correct
  SALT name (B) than with a permuted SALT name (C). One-sided. This rules out that any name,
  or the mere presence of text, explains H1.
- **H3 (SALT vs CLIP-Dissect where they disagree).** On stratum Delta (atoms where SALT and
  CLIP-Dissect names differ most in held-out quality), accuracy differs between the
  CLIP-Dissect name (D) and the SALT name (B). Two-sided.

Error control: H1 and H2 form one family, corrected with Holm at α = 0.05 (one-sided tests).
H3 is tested separately at α = 0.05 (two-sided).

---

## 2. Design plan

### 2.1 Study type
Experiment with four within-subject conditions (see the design change above).

### 2.2 Blinding
- Participants do not know that there are other conditions or what they are. The names of
  the methods are never shown. Condition C is described exactly like B and D ("a short name
  ... produced automatically by a computer program. It may or may not be accurate."). The end
  page debriefs participants, including the deliberately mismatched names.
- The page assigns conditions and records data automatically; there is no experimenter
  contact.
- The analysis script is written and tested on pilot and simulated data before the main
  data are downloaded.

### 2.3 Study design
- Within-subject factor **condition** (A, B, C, D), 10 test atoms per condition per participant.
- Within-subject factors **stratum** (R, Delta) and **dataset** (COCO, ImageNet), crossed by
  design: each participant sees 40 test atoms = 10 R + 10 Delta from each dataset.
- **Atom pool** (fixed before data collection, manifest version `[MANIFEST_VERSION]`):
  120 atoms, 60 COCO + 60 ImageNet.
  - Stratum R: 30 atoms per dataset drawn uniformly at random among evaluable atoms
    (seed 20261008).
  - Stratum Delta: 30 atoms per dataset, disjoint from R, among evaluable atoms whose SALT
    and CLIP-Dissect open-vocabulary names differ, with the largest
    |corr(SALT) − corr(CLIP-Dissect)| on held-out images, sign ignored. The sign is recorded
    for each atom.
  - "Evaluable" is defined in SPEC.md section 6.3 (enough activating images, both names
    available, no blocklisted word, a valid query pair, readable images).
- **Stimuli per atom.** Reference images come from the naming split (TRAIN): the 9 images with
  the highest activation and the 9 with the lowest pre-activation. Query images come from the
  held-out split (EVAL): the positive is among the 5 most activating held-out images; the
  negative is a held-out image of the same category on which the atom is inactive.
- **Lists.** The 60 R atoms are split into 3 sets of 20 (10 per dataset) and the 60 Delta atoms
  likewise, balanced on corr(SALT) (R) and |Δ| (Delta). List j = R-set j + Delta-set j.
- **Session** (~12 min): consent; instructions with an example in the participant's
  condition; 9 practice trials with feedback (atoms outside the pool); 40 test trials and 5
  catch trials (positive query = one of the top-row images) in random order, no feedback;
  confidence rating (1-5) after each choice; questionnaire (strategy, use of the displayed
  name in B/C/D, age range, AI familiarity).

### 2.4 Randomisation
- Condition and list: DataPipe assigns index i ∈ {0..11} in rotation; condition =
  ["A","B","C","D"][i mod 4], list = ⌊i / 4⌋. Every atom therefore gets the same expected
  number of responses per condition.
- Within a session: trial order is random (5 blocks of 8 test trials, one catch trial per
  block, block order shuffled; the first trial is never a catch trial). The side of the
  positive query is balanced (20 left, 20 right) and shuffled across test trials.
- The permutation used in C is a fixed derangement within each dataset, drawn once, such
  that the shown name never equals the atom's own SALT or CLIP-Dissect name.

---

## 3. Sampling plan

### 3.1 Existing data
Registration before data collection. Only the pilot (section 3.5) will have been collected.
Pilot data are not used in any confirmatory analysis.

### 3.2 Data collection procedures
Participants are recruited on Prolific: desktop or laptop only, age 18+, approval rate
≥ 95%, [LANGUAGE_SCREENER, e.g. fluent English], not having taken part in the pilot. Payment
is at or above Prolific's recommended hourly rate ([PAYMENT]). The study runs in the browser
(jsPsych 8, hosted on GitHub Pages); data are saved to a private OSF component through
DataPipe.

### 3.3 Sample size
Target: **60 participants per condition after exclusions** (240 in total, 20 per condition ×
list cell), to be confirmed by the power simulation below. Final number: **[N_PER_CONDITION]**
per condition.

### 3.4 Sample size rationale
Power simulation on the pilot data, done before registration:
- Fit the confirmatory model (section 5.1) to the pilot data to obtain the intercept, the
  stratum and dataset effects and the random-effect variances (participant, atom).
- Simulate data sets with the design of section 2.3 (40 test trials per participant, 120
  atoms, 3 lists), with a true gain of **5 percentage points** in accuracy for B over A and
  for B over C on stratum R (on the probability scale at the pilot's accuracy in A).
- Power = proportion of simulations in which both H1 and H2 are rejected under Holm
  (one-sided, α = 0.05). Use at least 1,000 simulations per candidate N.
- Choose the smallest N per condition, in steps of 3 (one more participant per condition ×
  list cell), that gives power ≥ 0.80. If this is below 60, keep
  60. If it exceeds the budget ([MAX_N_PER_CONDITION]), report the achievable power and keep
  the maximum.

Expected exclusions are taken from the pilot; we recruit enough to reach the target after
exclusions.

### 3.5 Pilot
About 10 participants per condition (48 in total, 4 per condition × list cell). Uses: check
the procedure, measure duration, estimate parameters for the power simulation, and apply the
ceiling rule below. Pilot participants are excluded from the main study and their data are
not analysed with it.

**Ceiling rule (decided before the pilot).** If test accuracy in condition A in the pilot is
above **90%**, the positive query is redrawn between the top 5% and the top 15% of held-out
images by activation for the atom, instead of the top 5%, and the manifest is regenerated
with a new version number before the main study. Nothing else changes.
[NOTE FOR THE AUTHOR: the current stimulus rule takes the positive among the 5 highest-ranked
held-out images (SPEC.md 6.4). State precisely what "top 5%" and "top 5-15%" refer to, e.g.
"ranks within the held-out images on which the atom is active", before registering.]

### 3.6 Stopping rule
Recruitment continues, in batches that are multiples of 12, until every condition × list
cell has at least [N_PER_CONDITION / 3] usable participants. All usable sessions collected
by then are analysed, even if cells end up slightly unequal. Accuracy by condition is not
looked at before data collection stops.

---

## 4. Variables

### 4.1 Manipulated variables
- **Condition** (between subjects): A = reference images only; B = SALT name of the atom;
  C = SALT name of another atom of the same dataset (fixed derangement); D = CLIP-Dissect
  name of the atom. In B, C and D the name is shown above the reference images as
  "This concept: <name>", with identical wording and layout.

### 4.2 Measured variables
- **correct** (primary): 1 if the participant chose the activating query, 0 otherwise, per test
  trial.
- **confidence**: 1-5 rating after each choice.
- **rt_choice**, **rt_conf**: response times (ms) from screen onset.
- Catch-trial responses; practice responses.
- Questionnaire: strategy (free text), use of the displayed name (B/C/D), age range, AI
  familiarity.
- Session information: browser, window size, focus losses, full-screen exits, duration.

### 4.3 Indices
None beyond the trial-level variables. Accuracy per participant is reported descriptively.

---

## 5. Analysis plan

### 5.1 Statistical model
Generalised linear mixed model (binomial, logit link), fitted with `lme4::glmer` in R on the
40 test trials per participant (catch and practice trials excluded):

```
correct ~ condition * stratum + dataset + (1 | participant) + (1 | atom)
```

- `condition`: factor A, B, C, D; `stratum`: R, Delta; `dataset`: COCO, ImageNet (sum-coded).
- Optimiser `bobyqa`. If the model does not converge, refit with other optimisers
  (`allFit`); if all fail, fit the same model with `glmmTMB`. The random-effects structure is
  not reduced.

### 5.2 Transformations
None. Contrasts are computed on the logit scale with `emmeans` (averaging over dataset) and
also reported on the probability scale.

### 5.3 Inference criteria
- **H1:** contrast B − A within stratum R. One-sided Wald z test (H1: B > A).
- **H2:** contrast B − C within stratum R. One-sided Wald z test (H2: B > C).
- H1 and H2: Holm correction over the two one-sided p-values, family-wise α = 0.05.
- **H3:** contrast D − B within stratum Delta. Two-sided Wald z test, α = 0.05.
- We report each contrast as an odds ratio and as a difference in accuracy, with 95%
  confidence intervals (one-sided intervals for H1-H2 in addition).
- Robustness check (reported, not used for the decision): the same contrasts with a
  parametric bootstrap (1,000 resamples) or likelihood-ratio tests.

### 5.4 Data exclusion
Applied at analysis time, in this order, to whole participants:
1. **Incomplete session:** no `summary` row, or fewer than 40 test trials recorded
   (cross-checked with Prolific "returned" and "timed out").
2. **Catch trials:** 2 or more of the 5 catch trials failed.
3. **Speed:** median choice RT on the 40 test trials (catch excluded) below 1.5 s.

Also removed: debug sessions (`debug = true`), sessions without a valid condition, and repeat
sessions by the same Prolific ID (we keep the first complete one). No trial-level exclusions.
We report the number excluded per rule and per condition.

### 5.5 Missing data
Only complete sessions are analysed, so there are no missing trials. A participant whose
data file could not be saved is treated as incomplete.

### 5.6 Exploratory analyses (not confirmatory)
- All other contrasts: B vs A and B vs C on stratum Delta; D vs A and D vs C; D vs B on
  stratum R; condition × dataset interactions.
- Confidence: same model with an ordinal outcome (cumulative link mixed model); calibration
  of confidence against accuracy per condition.
- Response times (log RT, linear mixed model).
- Item level: relation between per-atom accuracy gain (B − A) and corr(SALT); on stratum
  Delta, the D − B difference as a function of the sign of corr(SALT) − corr(CLIP-Dissect).
- Effect of the questionnaire answer "Did you use the displayed name?" and of AI familiarity.
- Practice accuracy and learning across the session.
- Coding of the free-text strategy answers.

---

## 6. Other

- **Materials:** the full page (`site/`), the stimulus manifest with per-atom metadata, the
  selection report and the specification (SPEC.md) will be attached to the registration.
- **Deception:** condition C shows names that do not belong to the atom, presented as
  automatic names. Participants are debriefed on the end page. Approved by [ETHICS_COMMITTEE],
  approval number [APPROVAL_NUMBER].
- **Data sharing:** Prolific IDs are removed before the data are made public.
- **Deviations** from this plan will be reported and justified in the paper.

# Lens A_feature_hardneg: hard negatives in DINOv2 feature space

Exploration of a stimulus-selection rule for the SALT 2AFC study (120 pool atoms of
`site/stimuli/manifest.json`). Nothing in `make_stimuli.py`, `site/` or the manifest was touched.
Files: `select.py` (rule + metrics + sheets), `metrics.json` (per atom and summary, sweep embedded),
`sweep.json`, `contact_sheet.html` (12 requested atoms, rule vs current manifest, relative links to the
real image files), `montage.png` (same 12 atoms, 224 px thumbnails, PIL).

## The rule (no name, no CLIP, no text embedding is used anywhere in the selection)

Inputs: the atom's and the other atoms' TopK codes (`codes_<key>.npz`), the standardized DINOv2
features (`A_img.npy` through `sc_mean/sc_scale`, then L2-normalised; "cos" below is the cosine in
this space), the dataset categories (wnid / COCO 80-label sets). The namesake rule of the current
generator (negatives silent on every atom sharing the SALT **or** the CLIP-Dissect name) is kept
because it is symmetric; it is the only place where names enter, and only as a group of atom indices.

| element | rule | thresholds |
|---|---|---|
| refs_high | naming-split images walked by decreasing z_a among the top 25, skipping a candidate whose cos to an already chosen reference exceeds `DUP_HIGH` (variety without leaving the concept) | `N_HIGH_POOL=25`, `DUP_HIGH=0.85` |
| refs_low | naming-split images **nearest to the refs_high centroid** among images on which the atom and all its namesakes are silent (z = 0) **and** whose pre-code h_a < `H_MAX` (the atom's own ReLU would kill it); near-duplicates skipped; at most `LOW_MAX_PER_CAT` per category so that the row spans the category boundary instead of 9 within-class look-alikes | `H_MAX=0`, `DUP=0.95`, `LOW_MAX_PER_CAT=3` |
| query_pos | among the top 10 held-out images by z_a with z_a >= `Z_REL_MIN` x max held-out z_a, keep those **inside the concept region**: cos to the refs_high centroid >= median cos of the refs_low images, and >= 3 of their 5 nearest references are high | `N_POS_TOP=10`, `Z_REL_MIN=0.5`, `POS_KNN_MIN=0.6` |
| query_neg | held-out images of the same category as the positive (same wnid / >= 1 shared COCO label), silent on the atom and its namesakes, h_a < `H_NEG_MAX`, restricted to the `N_NEG_NEAR` nearest to the positive | `H_NEG_MAX=0`, `N_NEG_NEAR=30` |
| pair choice | every admissible (pos, neg) pair gets the visual margin m1 (nearest-centroid score against the two reference rows); keep the pair with the **smallest** margin among those with m1 >= `FLOOR` and a strictly positive 5-NN margin | `FLOOR=0.02`, `KNN_FLOOR=0` |

Fallback cascade (all logged per atom in `metrics.json`, `fallback` field):
1. no positive inside the concept region: constraint dropped (2 atoms: coco_580, coco_750);
2. no same-category silent negative with h < 0: h constraint dropped, z = 0 only (6 atoms end here);
3. still none: category relaxed, nearest silent image with h < 0 (11 atoms, 9 ImageNet + 2 COCO);
4. no pair above the floor with a positive kNN margin: the pair with the largest margin is kept (3 atoms).

**Served: 120 / 120 pool atoms** (no atom is without images); 20 atoms use at least one fallback
(`neg_level`: 103 at level 0, 6 at level 1, 11 at level 2). The level-2 atoms are mostly ImageNet atoms
whose concept is the class itself: every held-out image of the class has h_a > 0 or fires a namesake,
so a same-class silent negative does not exist; the nearest silent image of another class is used.

## Common metrics, medians over the 120 pool atoms (means in parentheses)

| metric | this rule | current manifest |
|---|---|---|
| m1 margin, nearest-centroid (lower = harder without name) | **0.227** (0.238) | 0.484 (0.514) |
| m1 kNN margin (5-NN fraction high, pos minus neg) | 0.20 (0.33) | 0.20 (0.33) |
| m1 sign > 0 (solvable) | 120 / 120 | 117 / 120 |
| kNN margin > 0 | 117 / 120 | 83 / 120 |
| m2 z_a(pos) / max held-out z_a | 0.73 (0.75) | 1.00 (0.90) |
| m2 z_a(neg) = 0 and namesakes silent | 120 / 120 | 120 / 120 |
| m3 TopK-support Jaccard of the pair | 0.016 (0.028) | 0.016 (0.042) |
| m4 cos(refs_low centroid, refs_high centroid) | **0.341** (0.363) | -0.079 (-0.063) |
| m4 same-category fraction of refs_low | **0.44** (0.50) | 0.00 (0.33) |
| m5 SALT name in pos text and not in neg text | 0 (0.25) | 0 (0.24) |
| m5 CD name in pos text and not in neg text | 0 (0.19) | 0 (0.16) |
| pair cos | 0.075 (0.110) | 0.064 (0.126) |
| pair label Jaccard | 0.33 (0.54) | 1.00 (0.82) |
| mean pairwise cos inside refs_high | 0.44 (0.42) | 0.46 (0.43) |
| max h_a over refs_low | -0.05 | -3.01 |
| h_a(neg) | -0.44 | -0.03 |

Per dataset (median m1 margin, this rule vs manifest): COCO 0.164 vs 0.518; ImageNet 0.262 vs 0.449.
m4 row cos: COCO 0.32 vs -0.04, ImageNet 0.35 vs -0.12. The same-category fraction of refs_low is
0.94 on COCO and 0.00 on ImageNet: on ImageNet the concept is usually the class and a class image on
which the atom is silent with h < 0 rarely exists, so the hard negatives are the neighbouring classes
(spoonbills and black swans for the flamingo atom, cosmetics for the pill-jar atom, street scenes
without cars for the taxi atom), which is the contrast one wants.

Where the halving of the margin comes from (sweep, same pair rule everywhere): the pair rule alone
(min-margin pair, positive inside the concept) brings the median from 0.484 (manifest) to 0.325 with
the manifest's rows; replacing the "9 lowest pre-code" row by the hard-negative row brings it to
0.202 (top-9 high row) / 0.227 (de-duplicated high row). The hard-negative row is also what makes the
kNN margin positive on 117 atoms instead of 83: with unrelated "least activating" images, the 5-NN
vote against the low row is uninformative.

## Threshold sweep (median over the 120 atoms; full table in `metrics.json` -> `summary.sweep`)

| change w.r.t. the final rule | fallbacks | kNN>0 | m1 margin | m1 kNN | z_pos/max | m3 | m4 cos | m4 same-cat | pair cos |
|---|---|---|---|---|---|---|---|---|---|
| final rule (dedup / hardneg / FLOOR 0.02) | 20 | 117 | 0.227 | 0.20 | 0.73 | 0.016 | 0.34 | 0.44 | 0.07 |
| FLOOR 0.0 / 0.03 / 0.04 / 0.05 | 20 | 117 | 0.227 | 0.20 | 0.72 | 0.016 | 0.34 | 0.44 | 0.07 |
| FLOOR 0.10 | 20 | 117 | 0.227 | 0.40 | 0.72 | 0.016 | 0.34 | 0.44 | 0.08 |
| rows of the manifest (top9 / baseline low) | 18 | 110 | 0.325 | 0.20 | 0.67 | 0.016 | -0.08 | 0.00 | 0.09 |
| high row top-9 (no dedup), hardneg low | 20 | 117 | 0.202 | 0.20 | 0.74 | 0.016 | 0.34 | 0.44 | 0.07 |
| high row farthest-point sampling, hardneg low | 28 | 117 | 0.194 | 0.20 | 0.73 | 0.016 | 0.36 | 0.67 | 0.07 |
| H_MAX None (refs_low: z = 0 only) | 29 | 117 | 0.206 | 0.20 | 0.75 | 0.008 | 0.42 | 0.44 | 0.09 |
| H_MAX -1.0 | 18 | 114 | 0.244 | 0.20 | 0.69 | 0.016 | 0.26 | 0.33 | 0.08 |
| H_NEG_MAX None (neg: z = 0 only) | 15 | 118 | 0.190 | 0.20 | 0.73 | 0.016 | 0.34 | 0.44 | 0.11 |
| pair objective = closest pair (max cos) | 20 | 117 | 0.361 | 0.40 | 0.75 | 0.049 | 0.34 | 0.44 | 0.23 |
| N_NEG_NEAR 10 | 20 | 117 | 0.254 | 0.40 | 0.73 | 0.016 | 0.34 | 0.44 | 0.12 |
| Z_REL_MIN 0 | 15 | 118 | 0.154 | 0.20 | 0.59 | 0.016 | 0.34 | 0.44 | 0.09 |
| Z_REL_MIN 0.75 | 37 | 115 | 0.301 | 0.20 | 0.95 | 0.016 | 0.34 | 0.44 | 0.07 |
| POS_INSIDE off | 14 | 117 | 0.188 | 0.20 | 0.69 | 0.016 | 0.34 | 0.44 | 0.07 |
| POS_KNN_MIN 0.8 | 25 | 117 | 0.229 | 0.20 | 0.75 | 0.016 | 0.34 | 0.44 | 0.07 |
| LOW_MAX_PER_CAT 9 / 2 | 21 / 20 | 115 / 117 | 0.227 / 0.227 | 0.20 | 0.73 | 0.016 | 0.32 / 0.35 | 0.44 | 0.07 / 0.09 |
| DUP_HIGH 0.75 | 21 | 117 | 0.220 | 0.20 | 0.74 | 0.016 | 0.35 | 0.44 | 0.08 |

Reading: **the floor does not bind.** Once the positive is forced inside the concept region, the
smallest achievable margin is above 0.1 on 93 atoms and above 0.03 on 113; only 7 atoms sit at the
floor. The difficulty is set by the data (how close the nearest silent same-category image is), not by
the threshold. The knobs that really move the median margin are the positive's activation floor
(Z_REL_MIN 0 -> 0.154, but z_pos/max falls to 0.59 and off-concept positives return) and the pair
objective (closest pair instead of smallest margin: 0.361, pair cos 0.23, m3 0.049, i.e. the most
similar pair is not the hardest one against the rows). The two versions that were tried and rejected
after looking at the montage are in the table: farthest-point sampling of the high row (median 0.194,
but it pulls the outliers of the top-25 into the row: kites for "meals", a skunk and a zebra for
"flamingo", a skier for "train", and the hard-negative row then chases those outliers) and no
constraint on the positive (0.188, but the smallest-margin pair then lands on an off-concept
activation: horses for "meals", a skunk for "flamingo").

## Honest assessment from the montage (12 atoms)

Good trials (rows close, concept readable, pair minimal): coco_2745 meals (plated meals vs
sandwiches; people eating vs a man in a kitchen), coco_5723 train (trains vs buses, boats and train
interiors; station vs airplane wing), coco_2234 pizza (pizzas vs other baked food; pizza on a plate vs
a wedding cake), imagenet_517 (jars and pill bottles vs cosmetics; a cosmetics bottle vs lipsticks),
imagenet_4351 (cars in streets vs the same streets without cars), imagenet_3283 (wooden crates vs
chests and baskets), imagenet_3022 (foliage vs insects on leaves; a fence with foliage vs a bare
fence), imagenet_2825 (coral vs anemone fish and urchins).

Where the rule fails or is debatable:
- **Within-class atoms on ImageNet become unsolvable by a class-level name.** imagenet_116
  "flamingo": the low row is 3 flamingo close-ups plus spoonbills and swans, the pair is a flamingo on
  grass vs a flamingo close-up. This is what the atom encodes (it is silent, with h < 0, on close-ups),
  so the trial is honest, but neither "flamingo" (SALT and CD) can help: condition B = condition A on
  such atoms. The per-category cap on the low row (at most 3 flamingos) keeps the class contrast
  visible; it does not change the pair. Dropping the same-category constraint on the pair would make
  these trials solvable by the name but would measure the class, not the atom.
- **Off-concept positives still pass when they share the context.** coco_821 "pizza" fires on a
  fruit plate (z = 0.78 max) which passes the "inside the concept region" test because it is food on
  a plate; the pair becomes fruit plate vs dark restaurant. The positive is the atom's own choice, so
  this is a property of the atom (and the m2 metric records it), but the name "pizza" then misleads.
- **Negatives of broad COCO categories can be far from the positive.** coco_3855 (canine): the
  positive is a woman with a dog, the negative a child with a kite, same category "person". The
  N_NEG_NEAR=30 window on a 1000-image held-out split is not always tight; N_NEG_NEAR=10 raises the
  pair cos (0.12) at the price of a larger margin (0.254).
- **Noisy atoms stay noisy.** coco_1210 (canine | dog) has an incoherent high row (dogs, a dog on a
  plane, vegetables); no selection rule can fix the atom, and its hard-negative row (sheep, zebra,
  bear, cats) is the best one can show.
- **m5 does not move** (0.25 / 0.19 vs 0.24 / 0.16 in means): same-category negatives share the
  caption vocabulary with the positive by construction, so caption presence is a weak proxy here; the
  interesting counts are "name in pos text" (SALT 36 atoms vs 42) and "name in neg text" (6 vs 13).
- The level-2 fallback (11 atoms) drops the semantic control; the negative is the nearest silent
  other-class image, which is close in feature space but not of the same class.

## Reproduction

`cd explore/A_feature_hardneg && python3 select.py --sweep && python3 select.py` with the login-node
venv (`/lustre/work/pdl16831/udl5a0991/workspace/.venv/bin/python3`, numpy + Pillow; BLAS threads are
pinned to 4 inside the script because the 128-core login node oversubscribes otherwise). The final
run takes about 1.5 min, the sweep about 12 min. `select_trial(D, a, rng, cfg=None)` is importable
(load the module under another name: the file is called select.py and would shadow the stdlib module
if its directory were on sys.path; the script removes its own directory from sys.path for that
reason).

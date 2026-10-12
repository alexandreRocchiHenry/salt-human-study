# B_category_control: Colin's Experiment II with labels, captions and WordNet

Directory: `human_exp/stimuli_gen/explore/B_category_control/` (`select.py`, `metrics.json`, `contact_sheet.html`,
`montage.png`). Run: `cd human_exp && .venv python3 stimuli_gen/explore/B_category_control/select.py` (25 s on the
login node, numpy only; run it from any directory other than its own, the file name shadows the stdlib `select`).
Nothing in `make_stimuli.py`, `site/` or the manifest is modified.

## The rule

Only the atom's and the other atoms' TopK codes, the pre-code h_a, the standardized DINOv2 features, the dataset
labels (ImageNet wnid, COCO 80 labels), the COCO caption words (`img_to_words.json`) and WordNet 3.0 (raw
`data.noun`, hypernym pointers) are used. Names enter only metric m5.

* **refs_high**: unchanged (9 naming-split images with the highest z_a).
* **refs_low**: one image l_i per high reference h_i, chosen among the naming-split images on which the atom AND
  every namesake (same SALT or same CLIP-Dissect name, the symmetric rule of the manifest) is silent (z = 0).
  Primary key = the **category level** of the candidate w.r.t. h_i:
  * ImageNet: 0 same wnid; L = 1..4 the two wnids share a WordNet hypernym within L steps (symmetric); 5 none.
  * COCO: 0 identical 80-label set; 1 label Jaccard >= 0.5; 2 Jaccard > 0; 3 caption-word Jaccard >= 0.10
    (`img_to_words`); 5 none.
  Within the lowest available level: candidates with h_a <= 0 are preferred (the atom's linear detector says no,
  not only the TopK), then the **closest to h_i in standardized DINOv2 space** (cosine). Rows already used are
  excluded, so the 9 low references are distinct and the low row mirrors the category distribution of the high
  row (a "wheel" atom whose high row spans 9 classes gets a low row spanning the same 9 classes).
* **query pair**: the N_POS_TOP = 10 most activating held-out images are each paired with their best silent
  held-out negative (same procedure: lowest level, h_a <= 0 preferred, then a positive nearest-centroid margin
  with the chosen rows, then the highest cosine to the positive). The pair kept is the **most activating positive
  whose negative is category-matched** (level 0 on ImageNet, level <= 1 on COCO), else the most activating one
  with any level <= 4. Query positives are therefore the same as the manifest for 111/120 atoms; the change is in
  the negative (identical to the manifest's for 57/120, the manifest draws it at random among the same-category
  candidates) and above all in the low row.

A first version chose, among the 10 positives, the **hardest** pair (highest DINOv2 cosine between positive and
negative). It is kept in `select_trial(..., policy='maxcos')` and in `metrics.json`
(`summary_maxcos_variant_rejected`) and **rejected**: an outlier positive always has a close silent neighbour,
so the rule picked positives where the atom fires by accident (coco_2745 "meals" -> a horse field,
coco_821 "pizza" -> a tennis player, z_rel 0.38), median z_rel 0.51 and m5 SALT on COCO falling from 0.50 to
0.12. "Hard" must come from the negative and from the low row, never from a weak positive.

## Metrics (medians over the 120 pool atoms; means in parentheses where informative)

| metric | new | current manifest | rejected maxcos |
|---|---|---|---|
| m1 margin, nearest centroid (lower = harder) | **0.416** | 0.484 | 0.184 |
| m1 margin, kNN-5 | 0.400 | 0.200 | 0.200 |
| m1 sign > 0 (fraction) | 0.992 | 0.975 | 0.950 |
| m2 z_a(q_pos) / max held-out z_a | 1.000 (0.88) | 1.000 (0.90) | 0.513 |
| m2 z_a(q_neg) = 0 and namesakes silent | 1 / 1 | 1 / 1 | 1 / 1 |
| m2 h_a(q_neg) > 0 (count of atoms) | 29 | 59 | 27 |
| m3 Jaccard of TopK supports | 0.016 | 0.016 | 0.103 |
| m3 cos(q_pos, q_neg) DINOv2 | 0.107 | 0.064 | 0.309 |
| m4 cos(centroid low, centroid high) | **0.187** | -0.079 | 0.187 |
| m4 mean pairwise cos low x high | 0.058 | -0.023 | 0.058 |
| m4 same-category fraction of refs_low, strict (same wnid / identical label set) | **0.333** (0.375) | 0.000 (0.026) | 0.333 |
| m4 same-category fraction, loose (same wnid / shares a label) | **1.000** (0.73) | 0.000 (0.33) | 1.000 |
| m4 refs_low on which a namesake fires (mean fraction) | 0.000 | 0.159 | 0.000 |
| m5 SALT name in captions/labels of q_pos and not q_neg (mean) | 0.267 | 0.275 | 0.075 |
| m5 CLIP-Dissect name, same (mean) | 0.225 | 0.217 | 0.042 |
| pair strictly same category (mean) | 0.617 | 0.608 | 0.858 |

Per dataset (median, new vs manifest): m1 centroid COCO 0.458 vs 0.518, ImageNet 0.393 vs 0.449; m3 cos COCO
0.054 vs 0.027, ImageNet 0.144 vs 0.123; m4 cos of centroids COCO 0.198 vs -0.036, ImageNet 0.175 vs -0.124;
m4 strict same-category COCO 0.222 vs 0.000, ImageNet 0.444 vs 0.000; m5 SALT mean COCO 0.50 vs 0.50, ImageNet
0.03 vs 0.05. Full per-atom values: `metrics.json` (`atoms[aid].metrics`, `.baseline_metrics`,
`.maxcos_variant`), per-dataset summaries in `by_dataset`.

Reading. The manifest's low row is anti-correlated with the high row (centroid cosine -0.08: pineapples and
planes for an elephant atom) and 16 % of its low images actually fire a namesake. The new low row is in the same
categories (loose fraction 1.0 on COCO, 0.44 on ImageNet strict), positively correlated with the high row (+0.19)
and silent on every namesake. The pair is only slightly harder (margin 0.42 vs 0.48, cos 0.11 vs 0.06) because the
pool of same-category silent held-out images is small (ImageNet: ~10 held-out images per class). The m1 sign
stays positive on 119/120 atoms (centroid): the trials remain solvable by a DINOv2 nearest-centroid reader.
The kNN margin goes UP (0.4 vs 0.2): with a category-matched low row, the wrong query's nearest references are
now low references, i.e. the row contrast carries the concept instead of the object class. That is the point of
the control, not an easier trial for a human who does not have DINOv2.

## Coverage and fallbacks

* Atoms served: **120 / 120**, no level-5 (category-free) fallback anywhere, no unreadable image.
* ImageNet low row: 235/540 references at level 0 (same wnid, silent), **305/540 = 56.5 % need the WordNet
  fallback** (159 at 1 step, 94 at 2, 34 at 3, 18 at 4); 53/60 atoms have at least one fallback reference, 7/60
  have all nine at level 0. The reason is structural: an atom that IS the class detector (flamingo, coral) has no
  silent image of its own class among the 40 train images, so its low row is made of the WordNet siblings
  (other wading birds, other anthozoans) or, when the class has silent members, of its atypical members
  (flamingo close-ups of neck and beak for atom 116, a limousine for the "limo" atom 4351).
* COCO low row: 130/540 identical label set, 362 Jaccard >= 0.5, 35 Jaccard > 0, **13 caption-word level
  (2.4 %)**, 0 beyond; 2/60 atoms have all nine at level 0.
* Query pairs: ImageNet 60/60 same wnid (as in the manifest); COCO 14 identical label set + 46 Jaccard >= 0.5,
  none lower.
* Positives: rank 1 by z_a for 75/120 atoms (COCO 46/60, ImageNet 29/60; the ImageNet walk goes down to
  rank 10 when every same-class held-out image fires, exactly as the manifest does; the distribution is identical
  to the manifest's).

## Where the rule fails (seen on `montage.png`)

1. **COCO level 1 is a loose match.** Jaccard >= 0.5 with {dog, person} is satisfied by {person} alone, and the
   DINOv2-closest silent {person} image can be anything: the low row of coco_1210 ("canine") has a wounded face
   (l0), a fridge, a dark room, a golf course. It is "same context" by the labels, not by the eye. The identical
   label set (level 0) is rarely available because the atom and its 45 "dog"/"canine" namesakes fire on almost
   every dog image. A finer COCO level (Jaccard >= 0.5 AND the largest object shared) would need box areas, which
   the cache does not have.
2. **Class-detector atoms cannot have a same-class negative that the name can solve.** For imagenet_116 both
   queries are flamingos (one a beak close-up); the name "flamingo" is useless by construction, which is Colin's
   semantic control but also removes the room for the name to help. 25 % of the ImageNet SALT names appear in
   the caption of the NEGATIVE too (m5_salt_neg mean 0.25, vs 0.05 in the manifest where the low row differed).
   The m5 proxy says the name discriminates the pair on 27 % of atoms (same as the manifest): the pair is not
   where this rule gains, the rows are.
3. **The silent same-class image is sometimes a weird member, not a concept-free one** (coco_2234 "pizza": the
   positive is a hot dog on which a pizza atom fires at 0.40 of its max; imagenet_517 "pharmaceuticals": a brown
   lipstick tube vs red lipsticks, the concept being the jar/packaging of the high row). This is a property of
   the SAE (split features), not of the selection, but the trials will be hard in a way the name cannot fix.
4. **h_a(q_neg) > 0 on 29 atoms**: the negative is silent only because 32 other atoms beat it. The rule prefers
   h_a <= 0 but does not enforce it; enforcing it would empty the same-category pool on ~15 ImageNet atoms.
5. **Content.** The DINOv2-closest silent image can be unpleasant (coco_1210 l0). A content check of the low row
   is needed before deployment; the manifest's random bottom-9 had the same exposure.
6. Not addressed: the pair is barely harder than the manifest's (cos 0.11 vs 0.06). Making it harder requires
   a larger held-out pool (the naming split, 40 images per ImageNet class, holds 4x more candidates but is used
   for the references) or dropping the strict same-wnid rule in favour of level <= 1, which this lens keeps as
   primary by design.

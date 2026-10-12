# Lens C_code_context: stimulus selection driven by the SAE code (context = the other active atoms)

Directory: `human_exp/stimuli_gen/explore/C_code_context/` (nothing outside it was modified).
Files: `select.py` (rule + metrics + baseline, `select_trial(D, a, rng, space='code'|'recon', div='greedy'|'fps')`),
`sheet.py` (contact sheet + montage), `metrics.json` (per atom: ours, baseline, recon variant, FPS variant, summaries),
`contact_sheet.html` (relative links to the real image files, the 12 requested atoms), `montage.png` (same 12 atoms,
224 px thumbnails, labels drawn), `sweep.json` / `sweep.log` (MU x LAMBDA sweep, metrics only), `decoder_<key>.npz`
(decoder rows read from the paper checkpoints without torch, for the reconstruction variant).
Run: `cd <this dir> && OMP_NUM_THREADS=8 python3 select.py` (login node, numpy + PIL; ~8 min; 128 BLAS threads make it 10x slower).

## Rule (no name, no text embedding, no CLIP anywhere in the selection)

Everything is computed from the TopK codes of the cache, the pre-code h_a, the DINOv2 features (m1 only) and the
dataset categories. "Code minus a" = the sparse code with the target coordinate zeroed; similarity = cosine.

* **refs_high** (9): candidates = naming-split top-50 by z_a with z >= 0.3 z_top1. Greedy from the top-1:
  next = argmax z_rel - 0.5 * max cos(code minus a, already chosen). The 9 share the concept and differ in their
  other active atoms. Pure farthest-point sampling (the lens as stated) is kept as a reported variant: it is worse
  (see "where it fails").
* **refs_low** (9): naming-split rows on which the atom AND its namesakes (same SALT or CLIP-Dissect name, the
  symmetric rule of the manifest) are silent AND whose pre-code h_a <= 0 (the atom itself says "absent", not just
  "cut by the TopK"); for each refs_high image in turn, the still unused silent row with the closest code minus a.
  Each reference gets a twin with the concept removed (semantic control row).
* **query_pos / query_neg**: positives = the top-10 held-out rows by z_a restricted to z >= 0.5 z_max (at least the
  top 3). For each positive, the negative is the silent held-out row (atom + namesakes, same as the manifest)
  maximizing the code cosine minus a inside the best non-empty tier: (same category, h_a <= 0) > (same category) >
  (same category weak, COCO only) > (h_a <= 0) > any silent. Same category = same wnid on ImageNet, label-Jaccard
  >= 0.5 on COCO (weak: > 0). The pair kept maximizes (tier, z_rel(pos) + 0.5 * code cosine): a closer pair is
  taken only if the positive stays strong.
* Variant `recon`: the same rule with the decoder reconstruction x_hat = sum_j z_j d_j (j != a) in place of the
  sparse code (cosine in the 768-d space of the SAE).

Parameters: TAU_HIGH 0.3, LAMBDA 0.5, POS_FRAC 0.5, POS_MIN 3, MU 0.5, N_POS_TOP 10 (all in `metrics.json: params`).

## Served atoms and fallbacks

120 / 120 pool atoms served, 0 unserved (the 9-with-z>0 condition of the manifest is the only hard one and the
pool already satisfies it). Tiers of the chosen pair: 104 same category + h_a <= 0, 9 same category (h_a > 0 on
the negative, as in the manifest), 7 "any silent image with h_a <= 0" (coco_2237, coco_3834, imagenet_2574,
imagenet_762, imagenet_1055, imagenet_5452, imagenet_4027): none of the strong positives has a silent
same-category held-out image, the manifest reached one by walking down to a weaker positive. The strict refs_low
pool (silent + h_a <= 0) was never short (never fell back to "silent only").

## Medians over the 120 pool atoms (ours vs the current manifest; per-dataset values in metrics.json)

| metric | ours (greedy, code) | baseline (manifest) | recon variant | pure-FPS variant |
|---|---|---|---|---|
| m1 margin, nearest centroid (lower = harder without name) | **0.383** | 0.484 | 0.383 | 0.323 |
| m1 margin, 5-NN among the 18 refs | 0.40 | 0.20 | 0.40 | 0.20 |
| m1 sign > 0 (atoms) | 119 / 120 | 117 / 120 | | |
| m2 z_a(q_pos) / max held-out | 1.00 (mean 0.87) | 1.00 (mean 0.90) | 1.00 | 1.00 |
| m2 z_a(q_neg) = 0 and namesakes silent | 120 / 120 | 120 / 120 | | |
| m3 Jaccard of TopK supports (pos, neg) | 0.032 | 0.016 | 0.032 | 0.032 |
| m4 cos(centroid refs_low, centroid refs_high) | **0.287** (mean 0.28) | -0.079 (mean -0.06) | 0.31 | 0.356 |
| m4 same-category fraction of refs_low | 0.22 (mean 0.28) | 0.00 (mean 0.08) | 0.22 | 0.33 |
| m5 SALT name in pos text and not in neg text (mean) | 0.267 | 0.275 | | |
| m5 CD name in pos text and not in neg text (mean) | 0.225 | 0.217 | | |
| pair cos in standardized DINOv2 | 0.107 | 0.064 | 0.119 | 0.107 |
| pair code cosine minus a | 0.064 | 0.021 | 0.060 | 0.064 |
| mean code cosine of the 9 (high, low) twins | 0.282 | 0.005 | 0.278 | 0.391 |
| context diversity of refs_high (1 - mean pairwise cos) | 0.832 | 0.643 | 0.830 | 0.945 |
| min z_rel inside refs_high | 0.51 | (top-9 by z) | | 0.33 |
| low-level similarity of the pair (16x16 thumbnails) | 0.755 | 0.748 | 0.750 | 0.755 |
| low-level similarity of the twins | 0.739 | 0.737 | 0.743 | 0.743 |

Paired reading: the centroid margin is lower than the manifest on 69 % of the atoms (median -0.084); the row
cosine is higher on 97 % (from about -0.07 to +0.28, i.e. the two rows now live in the same region of the DINOv2
space instead of opposite ones); 75 / 120 positives and 33 / 120 negatives are the same images as the manifest.
m5 does not move: the "name helps" proxy is unchanged, so the trials are not made easier for the names.

By dataset (medians, ours / baseline): m1 centroid COCO 0.359 / 0.518, ImageNet 0.418 / 0.449; row cos COCO
0.251 / -0.036, ImageNet 0.299 / -0.124; pair DINOv2 cos COCO 0.050 / 0.027, ImageNet 0.145 / 0.123.

## Does code overlap capture low-level similarity? No.

Over the silent held-out candidates of each atom (300 per atom, 40 atoms per dataset), the code cosine minus a
correlates with the DINOv2 cosine to the positive (Pearson 0.27 COCO / 0.29 ImageNet, Spearman 0.10 / 0.11) and
not at all with the 16x16-thumbnail similarity (Pearson 0.016 / -0.015; DINOv2 itself 0.035 / -0.01). The pairs
and twins we pick are no more similar in pixels than the manifest's (0.755 vs 0.748). The code context is a
compositional/semantic similarity (same objects and scene type), not colour or layout. Consequence for the author:
this lens makes the rows and pairs semantically close; it does not make them visually close in the low-level sense
(a lens on DINOv2 patch features or pixels would be needed for that).

## Sparse code vs decoder reconstruction

The two spaces agree: 94 / 120 identical query pairs, medians within 0.01-0.03 on every metric (the reconstruction
is marginally more "DINOv2-like": row cos 0.31 vs 0.29, pair cos 0.119 vs 0.107). The 768-d reconstruction is
the code projected through the dictionary, so it adds the correlations between atoms (two different "dog" atoms
count as similar) and loses nothing visible here. Keep the sparse code (cheaper, exact "concept removed").

## Solvability check (m1)

All pairs but one keep a positive centroid margin (coco_1006, -0.017; the manifest has 3 negative margins,
coco_1006 among them). 7 atoms have a margin below 0.1 (manifest: 9). The 5-NN margin is HIGHER than the
manifest's (0.40 vs 0.20): because the negative resembles the low row by construction, its nearest references are
low ones, while the manifest's unrelated low row (pineapples, planes) never captures a same-category negative.
So "harder" holds for the centroid reading and "better separated" for the kNN reading; the two readings of m1
disagree and the honest statement is: the rows isolate the concept better, the pair is only slightly closer.

## Where the rule fails (seen on the montage)

1. **COCO atoms are too sparse for this lens.** 5-11 held-out positives, 17-44 naming-split positives, and the
   secondary activations are often spurious. Any diversity criterion surfaces them: pure FPS put kites, a boat and
   a laptop in a "meals" row and boats / cats / an airplane in a "canine" row (that is why FPS was replaced by the
   greedy with the z_rel term; even so coco_2745 keeps a kite image and coco_3855 a ship). Likewise, choosing the
   pair by closeness alone (first version, no z weighting) picked positives at 0.7 of the max that do not show the
   concept (a boat pair for "canine", a tennis pair for "pizza"): the pair closeness (code cos 0.19, DINOv2 0.19)
   was bought with unsolvable trials. With MU = 0.5 the rule keeps the top-1 positive on most COCO atoms and the
   pair is barely closer than the manifest's (0.050 vs 0.027). The sweep (`sweep.log`) shows that no MU / LAMBDA
   setting changes the COCO margin much (0.29-0.38): the margin reduction comes from the low row, not the pair.
2. **The twins expose that the atom is narrower than its name.** For imagenet_116 ("flamingo") the low row
   contains flamingos in profile / head down and spoonbills, on which the atom is silent and h_a <= 0: the atom
   encodes a specific view of a flamingo, not "flamingo". This is exactly the semantic control the author asked
   for, but with the name "flamingo" shown the participant sees flamingos in BOTH rows; names that are broader
   than the atom will be penalized by this design, and that is a property of the atom, not of the name.
3. **Greedy diversity still admits off-concept references on ImageNet** when the atom genuinely fires on them
   (skunk, ferret and a bird in the flamingo row at z_rel >= 0.5; a woman with a basket in the crate row). LAMBDA
   = 0.3 removes most of them (min z_rel 0.70) at the price of no diversity gain over the manifest (0.644 vs 0.643,
   `sweep.log`); LAMBDA = 0.5 was kept as the compromise. The author may prefer 0.3 for a cleaner concept row.
4. **The pair is sometimes close for the wrong reason**: coco_5723 ("train") picks a red car with a tram in the
   background (z_rel 0.58) against a school bus; coco_2745 ("meals") pairs a man with plates against people
   walking in a room (same labels, different scene). Code cosine with 32 active atoms is a coarse scene signature.
5. m5 is unchanged, so this lens does not create more trials where the name is a decisive cue; it does not destroy
   them either.
6. No content screening of the images (the manifest only blocklists names); one refs_low twin of imagenet_3283
   is a woman lying on a bed, which the author may want to veto by hand.

## Recommendation

Keep the twin construction of refs_low (the clearest gain: row cosine -0.07 -> +0.28, same-category fraction
0 -> 0.22, h_a <= 0 on every low image) and the greedy refs_high at LAMBDA 0.3-0.5. For the pair, the code
context brings little on COCO; on ImageNet it gives taxi-vs-London-cab, pallet-vs-man-with-boxes, patio-with-plants
vs patio-without, which are the intended hard pairs. If the author wants the pairs visually closer, the
similarity has to come from the DINOv2 features themselves (allowed by the fairness rule), not from the code.

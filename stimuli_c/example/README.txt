Images for the illustrated example page of the instructions (stimuli version 2026-10-12-v3).
Atom: imagenet_5844 (ImageNet SAE atom 5844, outside the test pool, the practice set and the catch set).
SALT name (B): scoreboard | permuted name (C): slug | CLIP-Dissect name (D): scoreboard
Category of the two queries: barbershop

h0.jpg ... h8.jpg  most activating images (h0 = highest)
l0.jpg ... l8.jpg  least activating images (l0 = lowest pre-code)
qpos.jpg           query that activates the atom (correct answer)
qneg.jpg           query of the same category that does not activate it
example.json       same schema as a manifest atom, plus "atom_id"

Unlike test atoms, the example query_pos is the highest-activating held-out image that has a
same-category negative (not a seeded random draw), so that the illustration is clear-cut.

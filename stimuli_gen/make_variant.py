"""Prototype stimulus sets for the human study (9 Oct. 2026), built with the hard-negative rule of explore/A_feature_hardneg/select.py
on the SAME atom pool, lists, practice / catch atoms, permuted names and example as site/stimuli/manifest.json.
  variant a : query_neg of the same category as query_pos (cascade of select.py)      -> site/stimuli_a/
  variant b : query_neg = nearest silent image of ANY category (NEG_CAT = False)        -> site/stimuli_b/
  variant c : query_neg = nearest silent image of a DIFFERENT category (NEG_CAT = 'different') -> site/stimuli_c/
Both: refs_high = top by z without near-duplicates; refs_low = the 9 nearest images (DINOv2) silent on the atom and its namesakes, h < 0,
at most 3 per category; pair = smallest centroid margin >= 0.02 (solvable but hard). Catch atoms and the example are copied from site/stimuli.
Usage: python3 make_variant.py a|b|c   (login node, numpy + PIL; needs stimuli_gen/cache/codes_*.npz)."""
import os, sys, json, shutil, time, importlib.util
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.abspath(f'{HERE}/../site')
sys.path.insert(0, HERE)
from make_stimuli import Data, load_names, save_square, KEYS
spec = importlib.util.spec_from_file_location('selA', f'{HERE}/explore/A_feature_hardneg/select.py'); selA = importlib.util.module_from_spec(spec); spec.loader.exec_module(selA)
VARIANT = sys.argv[1]; assert VARIANT in ('a', 'b', 'c')
CFG = {'a': {}, 'b': {'NEG_CAT': False}, 'c': {'NEG_CAT': 'different'}}[VARIANT]
STIM = f'{SITE}/stimuli_{VARIANT}'; T0 = time.time(); log = lambda *a: print(f'[{time.time() - T0:5.0f}s]', *a, flush=True)

man = json.load(open(f'{SITE}/stimuli/manifest.json'))
D_all, names_all = {}, {}
for key in KEYS:
    D = Data(key); names = load_names(key); D.set_namesakes(names); selA.prep(D); D_all[key] = D; names_all[key] = names; log(key, 'ready')
if os.path.isdir(STIM): shutil.rmtree(STIM)
os.makedirs(f'{STIM}/img'); shutil.copytree(f'{SITE}/stimuli/example', f'{STIM}/example')
out = dict(version=f"{man['version']}-proto{VARIANT}", variant=VARIANT, rule=dict(selA.CFG, **CFG), lists=man['lists'], atoms={}, practice=man['practice'], catch=man['catch'])
stats = dict(served=0, fallback_to_current=0, fallbacks={}, m1=[], m1_knn=[], m5_salt=[], m5_cd=[], pair_same_cat=0, row_cos=[])
for aid, cur in man['atoms'].items():
    key = cur['dataset']; a = int(aid.split('_')[1]); D = D_all[key]; rel = f'stimuli_{VARIANT}/img/{aid}'; os.makedirs(f'{SITE}/{rel}')
    r = None if cur['stratum'] == 'catch' else selA.select_trial(D, a, np.random.default_rng(a), CFG)
    e = json.loads(json.dumps(cur)); e['meta'] = dict(e['meta']); e['meta']['variant'] = VARIANT
    if r is None:                                                       # catch atoms, or no valid trial: copy the current images
        for f in os.listdir(f"{SITE}/stimuli/img/{aid}"): shutil.copy(f"{SITE}/stimuli/img/{aid}/{f}", f'{SITE}/{rel}/{f}')
        if cur['stratum'] != 'catch': stats['fallback_to_current'] += 1
        e['meta']['selection'] = 'current manifest (catch atom)' if cur['stratum'] == 'catch' else 'current manifest (no valid trial under the rule)'
    else:
        m = selA.trial_metrics(D, a, r['refs_high'], r['refs_low'], r['query_pos'], r['query_neg'], names=names_all[key][a])
        for i, row in enumerate(r['refs_high']): save_square(D.path(row), f'{SITE}/{rel}/h{i}.jpg')
        for i, row in enumerate(r['refs_low']): save_square(D.path(row), f'{SITE}/{rel}/l{i}.jpg')
        save_square(D.path(r['query_pos']), f'{SITE}/{rel}/qpos.jpg'); save_square(D.path(r['query_neg']), f'{SITE}/{rel}/qneg.jpg')
        did = (lambda row: int(D.image_ids[row])) if key == 'coco' else (lambda row: int(row))
        e['meta'].update(selection=f'explore/A_feature_hardneg/select.py, variant {VARIANT}', category=D.category_name(D.category(r['query_pos'])),
                         z_pos=float(D.z(r['query_pos'], a)), h_neg=float(D.h(r['query_neg'], a)), z_neg=float(D.z(r['query_neg'], a)), pos_rank_ev=r['pos_rank_ev'],
                         pair_same_cat=r['pair_same_cat'], neg_level=r['neg_level'], fallback=r['fallback'],
                         metrics={k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in m.items()},
                         src=dict(refs_high=[did(x) for x in r['refs_high']], refs_low=[did(x) for x in r['refs_low']], query_pos=did(r['query_pos']), query_neg=did(r['query_neg']),
                                  id_kind='COCO image id' if key == 'coco' else 'ImageNet val row (= id)'))
        assert e['meta']['z_neg'] == 0.0
        stats['served'] += 1; stats['m1'].append(m['m1_margin']); stats['m1_knn'].append(m['m1_knn']); stats['m5_salt'].append(m['m5_salt']); stats['m5_cd'].append(m['m5_cd'])
        stats['row_cos'].append(m['m4_row_cos']); stats['pair_same_cat'] += int(r['pair_same_cat'])
        if r['fallback']: stats['fallbacks'][aid] = r['fallback']
    e['refs_high'] = [f'{rel}/h{i}.jpg' for i in range(9)]; e['refs_low'] = [f'{rel}/l{i}.jpg' for i in range(9)]; e['query_pos'] = f'{rel}/qpos.jpg'; e['query_neg'] = f'{rel}/qneg.jpg'
    out['atoms'][aid] = e
    if stats['served'] % 20 == 0 and r is not None: log('rendered', stats['served'])
json.dump(out, open(f'{STIM}/manifest.json', 'w'), indent=1)
summ = dict(variant=VARIANT, served=stats['served'], fallback_to_current=stats['fallback_to_current'], n_fallback_rule=len(stats['fallbacks']), pair_same_cat=stats['pair_same_cat'],
            median_m1=float(np.median(stats['m1'])), median_m1_knn=float(np.median(stats['m1_knn'])), sign_pos=int(sum(x > 0 for x in stats['m1'])),
            mean_m5_salt=float(np.mean(stats['m5_salt'])), mean_m5_cd=float(np.mean(stats['m5_cd'])), median_row_cos=float(np.median(stats['row_cos'])), fallbacks=stats['fallbacks'])
json.dump(summ, open(f'{HERE}/variant_{VARIANT}_summary.json', 'w'), indent=1); log({k: v for k, v in summ.items() if k != 'fallbacks'}); print('VARIANT_DONE')

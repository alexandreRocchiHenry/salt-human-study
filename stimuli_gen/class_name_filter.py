"""Eligibility of atoms for the human study (12 Oct. 2026): keep atoms whose names are NOT class names.
An atom is excluded when its SALT name OR its CLIP-Dissect name (the same rule for both methods) is
  - a class name of the dataset: a curated class name or one of its WordNet lemmas, or the head noun of a multi-word one
    (COCO: the 80 categories; ImageNet: the 1 000 classes; lexicon of paper_proto/abl/e2_lex.py, out/abl/E2/lex_<jeu>.json);
  - a WordNet hypernym of a class (e.g. dog, canine, bird, vehicle), except the most abstract ones (entity, object, artifact...);
  - not a dictionary word (absent from WordNet: giclee, worldcat, cation...), or a proper noun (every noun sense is a WordNet instance).
Words are compared after lower-casing, plural folding (common.variants) and WordNet lemmatisation (morphy).
Run once on the login node (needs nltk + WordNet: PYTHONPATH=<scratch>/nltk_pkg, NLTK_DATA=<scratch>/nltk_data).
Writes class_name_filter_<key>.json = {atom: {"eligible": bool, "reason": str, "salt": ..., "cd": ...}}; make_stimuli.py reads it."""
import os, sys, re, json, csv
import nltk
from nltk.corpus import wordnet as wn
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(f'{HERE}/../..')
TOK = re.compile(r'[a-z0-9]+')
ABSTRACT = {'entity', 'object', 'whole', 'physical entity', 'abstraction', 'artifact', 'artefact', 'matter', 'thing', 'unit', 'part',
            'living thing', 'organism', 'being', 'causal agent', 'cause', 'physical object', 'instrumentality', 'instrumentation', 'group'}

def norm(t):
    return ' '.join(TOK.findall(re.sub(r'\(.*?\)', '', str(t).replace('_', ' ').lower())))

def folds(w):
    out = {w}
    if len(w) >= 4 and w.endswith('s'): out.add(w[:-1])
    if len(w) >= 5 and w.endswith('es'): out.add(w[:-2])
    if len(w) >= 5 and w.endswith('ies'): out.add(w[:-3] + 'y')
    m = wn.morphy(w.replace(' ', '_'), 'n')
    if m: out.add(m.replace('_', ' '))
    return out

def term_forms(t):
    t = norm(t)
    if not t: return set()
    out = folds(t)
    head = t.split()[-1]
    out |= folds(head)
    return out

for key in ('coco', 'imagenet'):
    L = json.load(open(f'{ROOT}/paper_proto/out/abl/E2/lex_{key}.json'))
    cls = set()
    for ts in L['termes']:
        for t in ts: cls |= term_forms(t)
    hyp = set()
    for h in L['hyperonymes']:
        for t in h:
            t = norm(t)
            if t and t not in ABSTRACT: hyp |= folds(t)
    hyp -= ABSTRACT
    names = {}
    for r in csv.DictReader(open(f'{ROOT}/paper_proto/out/{key}_atomes.csv')):
        if r['regime'] == 'ouvert' and r['methode'] in ('tete_s0', 'cd_off_20k'):
            names.setdefault(int(r['atome']), {})['salt' if r['methode'] == 'tete_s0' else 'cd'] = norm(r['nom'])
    out, counts = {}, {}
    for a, v in sorted(names.items()):
        nm = [v.get('salt', ''), v.get('cd', '')]; F = [folds(x) for x in nm]
        if any(f & cls for f in F): why = 'class name'
        elif any(f & hyp for f in F): why = 'hypernym of a class'
        elif not all(wn.synsets(x.replace(' ', '_')) for x in nm): why = 'not a dictionary word'
        elif any(all(s_.instance_hypernyms() for s_ in wn.synsets(x.replace(' ', '_'), 'n')) and wn.synsets(x.replace(' ', '_'), 'n')
                 and not wn.synsets(x.replace(' ', '_'), 'a') + wn.synsets(x.replace(' ', '_'), 's') + wn.synsets(x.replace(' ', '_'), 'v') for x in nm):
            why = 'proper noun'        # every noun sense is an instance (a place, a person, a river): Tucson, Thames, Roswell
        else: why = ''
        out[str(a)] = dict(eligible=not why, reason=why or 'eligible', salt=nm[0], cd=nm[1])
        counts[why or 'eligible'] = counts.get(why or 'eligible', 0) + 1
    json.dump(dict(rule=__doc__.split('\n')[0], counts=counts, atoms=out), open(f'{HERE}/class_name_filter_{key}.json', 'w'), indent=0)
    print(key, counts)

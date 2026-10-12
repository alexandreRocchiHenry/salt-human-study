"""Lens C_code_context: stimulus selection driven by the SAE code itself (context = other active atoms).

Rule (per atom a; nothing here reads a name, a text embedding or CLIP):
  refs_high : candidates = naming-split top-50 rows by z_a with z >= TAU_HIGH * z_top1 (at least 9 of them);
              greedy from the top-1: next = argmax z_rel - LAMBDA * max cos(code minus a, chosen) => the 9 share
              the concept but differ in their other active atoms, without drifting to the weak (spurious)
              firings. Pure farthest-point sampling (div='fps') is kept as a reported variant.
  refs_low  : naming-split rows on which a AND its namesakes are silent (z = 0) and the pre-code h_a <= 0;
              for each refs_high image (in order) the still unused silent row whose code (minus a) is the
              closest (cosine)  => a "twin" of every reference with the concept removed.
  query_pos / query_neg : positives = the top N_POS_TOP held-out rows by z_a restricted to z >= POS_FRAC * z_max
              (at least the top POS_MIN; a weak positive is a spurious firing); for each positive the best
              negative is the silent (group) held-out row maximizing the code cosine (minus a) inside the best
              non-empty tier: (same category, h_a <= 0) > (same category) > (h_a <= 0) > any silent.
              The pair kept is the one with the best (tier, z_rel(pos) + MU * code cosine) over the positives.
              Same category: imagenet same wnid; coco label-Jaccard >= 0.5 (weak tier: > 0).
  Variant 'recon': the same rule with the decoder reconstruction x_hat = sum_j z_j d_j (j != a) in place of
              the sparse code (cosine in the 768-d DINOv2 space of the SAE).

Metrics m1..m5 (common definitions of the workflow) are computed for every trial and for the current
manifest (baseline).  Usage: python3 select.py [--space code|recon] [--no-sheet]
"""
import os, sys
# this file is named select.py (imposed): keep its own directory off sys.path so the stdlib `select` module wins
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != _HERE]
import json, math, re, time
import numpy as np

ROOT = '/lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE'
GEN = f'{ROOT}/human_exp/stimuli_gen'
EXP = f'{GEN}/explore/C_code_context'
sys.path.insert(0, GEN)
import make_stimuli as M                                   # Data, load_names (no side effect on import)

N_REF, N_POS_TOP = 9, 10
TAU_HIGH = 0.3             # refs_high candidates: z >= TAU_HIGH * z_top1
LAMBDA = 0.5               # refs_high greedy: z_rel - LAMBDA * max cos(code minus a) to the already chosen
POS_FRAC, POS_MIN = 0.5, 3  # query_pos candidates: z >= POS_FRAC * z_max over held-out (at least the top POS_MIN)
MU = 0.5                   # query pair: score = z_rel(pos) + MU * code cos(pos, best neg) inside the best tier
COCO_JAC_STRONG, COCO_JAC_WEAK = 0.5, 0.0
SHEET_ATOMS = ["coco_2745", "coco_1210", "coco_3855", "coco_5723", "coco_821", "coco_2234",
               "imagenet_116", "imagenet_517", "imagenet_4351", "imagenet_3283", "imagenet_3022", "imagenet_2825"]


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ------------------------------------------------------------------ data with the extra arrays of this lens
class DataC(M.Data):
    def __init__(self, key):
        super().__init__(key)
        names = M.load_names(key)
        self.names = names
        self.set_namesakes(names)
        A = np.asarray(self.A, np.float32)
        self.X = (A - self.sc_mean) / self.sc_scale                 # standardized DINOv2 (N x 768)
        self.Xn = self.X / np.linalg.norm(self.X, axis=1, keepdims=True)
        dec = np.load(f'{EXP}/decoder_{key}.npz')
        Dw = dec['sae_dictionary__weights'].astype(np.float32)
        self.Dn = Dw / np.linalg.norm(Dw, axis=1, keepdims=True)    # DictionaryLayer: l2 rows (x exp(mult), irrelevant for cos)
        # reconstruction x_hat = sum_j z_j d_j for every row (chunked)
        self.Xhat = np.zeros((self.N, 768), np.float32)
        for s in range(0, self.N, 4096):
            idx = self.z_idx[s:s + 4096].astype(np.int64); val = self.z_val[s:s + 4096]
            self.Xhat[s:s + 4096] = np.einsum('nk,nkd->nd', val, self.Dn[idx])
        self.tr_set = set(self.tr.tolist())
        self.znorm2 = (self.z_val ** 2).sum(1)                       # ||z||^2 per row
        self.xhat_n2 = (self.Xhat ** 2).sum(1)                       # ||x_hat||^2 per row
        self._cache = {}
        self.caps = json.load(open(f'{self.CD}/caps_by_img.json'))
        self.i2c = json.load(open(f'{self.CD}/img_to_cats.json'))
        self.row_of_id = {int(i): r for r, i in enumerate(self.image_ids.tolist())}

    # --- atom-level helpers
    def hcol(self, a):
        return self.X @ self.We[a] + self.be[a]

    def zcol(self, a):
        """Dense z_a over all rows."""
        hit = self.z_idx == a
        return (self.z_val * hit).sum(1)

    def silent_rows(self, a):
        grp = self.namesakes.get(a, [a])
        g = np.zeros(self.m, bool); g[grp] = True
        return ~g[self.z_idx].any(1)                                 # (N,) True if no namesake (incl. a) fires

    def code_cos(self, ref, rows, a, space='code'):
        """cos between the code of row `ref` and the codes of `rows`, coordinate a removed (space 'code'),
        or between the decoder reconstructions without atom a (space 'recon')."""
        rows = np.asarray(rows)
        if space == 'recon':
            # x_s = Xhat[s] - z_a(s) d_a : one full matvec, then the closed-form correction on the rows where a fires
            za_ref = self.z(ref, a); zr = self.zcol_rows(rows, a); d = self.Dn[a]
            xr = self.Xhat[ref] - za_ref * d
            if self._cache.get('a') != a:                        # per-atom cache of Xhat . d_a
                self._cache = dict(a=a, xd=self.Xhat @ d)
            xd = self._cache['xd'][rows]
            num = (self.Xhat @ xr)[rows] - zr * (d @ xr)
            n2 = self.xhat_n2[rows] - 2 * zr * xd + zr ** 2
            return num / (np.sqrt(np.maximum(n2, 1e-12)) * np.linalg.norm(xr) + 1e-9)
        v = np.zeros(self.m, np.float32)
        v[self.z_idx[ref]] = self.z_val[ref]; v[a] = 0.0
        num = (self.z_val[rows] * v[self.z_idx[rows]]).sum(1)
        za = self.zcol_rows(rows, a)
        n_rows = np.sqrt(np.maximum(self.znorm2[rows] - za ** 2, 1e-12))
        return num / (n_rows * (np.linalg.norm(v) + 1e-9))

    def zcol_rows(self, rows, a):
        hit = self.z_idx[rows] == a
        return (self.z_val[rows] * hit).sum(1)

    def support_jaccard(self, r1, r2, excl=None):
        s1 = set(self.z_idx[r1][self.z_val[r1] > 0].tolist()); s2 = set(self.z_idx[r2][self.z_val[r2] > 0].tolist())
        if excl is not None:
            s1.discard(excl); s2.discard(excl)
        return len(s1 & s2) / max(1, len(s1 | s2))

    def same_cat(self, r1, r2):
        """(strong, weak) same-category flags."""
        if self.key == 'imagenet':
            s = self.wnid[r1] == self.wnid[r2]
            return s, s
        P, Q = self.labels[r1], self.labels[r2]
        u = (P | Q).sum()
        j = (P & Q).sum() / u if u else 0.0
        return j >= COCO_JAC_STRONG, j > COCO_JAC_WEAK

    def label_jaccard_vec(self, r, rows):
        if self.key == 'imagenet':
            return (self.wnid[rows] == self.wnid[r]).astype(float)
        P = self.labels[r]; L = self.labels[rows]
        inter = (L & P).sum(1); union = (L | P).sum(1)
        return np.where(union > 0, inter / np.maximum(union, 1), 0.0)

    def text_of(self, r):
        """Captions + labels / class name of a row (lower-case), for the diagnostic m5 only."""
        if self.key == 'coco':
            caps = self.caps.get(str(int(self.image_ids[r])), [])
            labs = [self.label_names[i] for i in np.where(self.labels[r])[0]]
        else:
            caps = self.caps.get(str(int(r)), [])
            labs = self.i2c.get(str(int(r)), [])
        return ' '.join(caps + labs).lower()

    def dataset_id(self, r):
        return int(self.image_ids[r]) if self.key == 'coco' else int(r)

    def row_of(self, i):
        return self.row_of_id[int(i)] if self.key == 'coco' else int(i)


# ------------------------------------------------------------------ selection
def diverse_refs(D, cand, zrel, a, n, space, div):
    """9 references among `cand` (sorted by decreasing z, zrel = z / z_top1), starting at the top-1.
    div 'fps'    : farthest-point sampling on 1 - cos(code minus a)  (pure diversity; on COCO it picks the
                   spurious firings, whose context is by construction the most different)
    div 'greedy' : next = argmax  zrel - LAMBDA * max_j cos(code minus a, chosen_j)  (diversity traded against
                   activation strength: a weaker reference is taken only when it is a really new context)"""
    cand = [int(c) for c in cand]
    S = np.zeros((len(cand), len(cand)))
    for i, r in enumerate(cand):
        S[i] = D.code_cos(r, cand, a, space)
    chosen = [0]
    maxcos = S[0].copy()
    while len(chosen) < n:
        score = (1 - maxcos) if div == 'fps' else (zrel - LAMBDA * maxcos)
        score[chosen] = -9
        j = int(np.argmax(score)); chosen.append(j)
        maxcos = np.maximum(maxcos, S[j])
    return [cand[j] for j in chosen]


def select_trial(D, a, rng=None, space='code', div='greedy'):
    """Rows (and dataset ids) of one trial of atom a, or None with a reason. rng unused (rule deterministic)."""
    top, topv = D.top_tr[a], D.top_tr_val[a]
    if (topv[:N_REF] <= 0).any():
        return None, 'fewer than 9 naming-split images with z>0'
    h = D.hcol(a); silent = D.silent_rows(a)
    # refs_high: diverse contexts among the strong activations
    keep = (topv > 0) & (topv >= TAU_HIGH * topv[0])
    if keep.sum() < N_REF:
        keep = topv > 0
    cand = top[keep]
    refs_high = diverse_refs(D, cand, topv[keep] / topv[0], a, N_REF, space, div)
    # refs_low: one silent (group) naming-split twin per reference, h_a <= 0 preferred
    is_tr = np.zeros(D.N, bool); is_tr[D.tr] = True
    base = is_tr & silent
    pool_strict = np.where(base & (h <= 0))[0]
    pool_any = np.where(base)[0]
    low_pool = pool_strict if len(pool_strict) >= N_REF else pool_any
    refs_low, low_cos, used = [], [], set()
    for r in refs_high:
        c = D.code_cos(r, low_pool, a, space)
        for j in np.argsort(-c):
            if int(low_pool[j]) not in used:
                used.add(int(low_pool[j])); refs_low.append(int(low_pool[j])); low_cos.append(float(c[j])); break
    # queries
    zev = D.Zev[:, a]
    order = np.argsort(-zev, kind='stable')
    # positives: top N_POS_TOP held-out by z_a, restricted to z >= POS_FRAC * z_max (at least POS_MIN of them):
    # a weak positive is a spurious firing whose context is generic, and the pair search would pick it
    pos_cands = [int(D.ev[i]) for i in order[:N_POS_TOP] if zev[i] > 0]
    strong = [int(D.ev[i]) for i in order[:N_POS_TOP] if zev[i] >= POS_FRAC * zev[order[0]]]
    pos_cands = pos_cands[:max(POS_MIN, len(strong))]
    if not pos_cands:
        return None, 'no held-out image with z>0'
    is_ev = np.zeros(D.N, bool); is_ev[D.ev] = True
    neg_base = np.where(is_ev & silent)[0]
    best = None
    for rank, pos in enumerate(pos_cands):
        nb = neg_base[neg_base != pos]
        jac = D.label_jaccard_vec(pos, nb)
        strong = jac >= (COCO_JAC_STRONG if D.key == 'coco' else 1.0)
        weak = jac > COCO_JAC_WEAK
        hs = h[nb] <= 0
        c = D.code_cos(pos, nb, a, space)
        tiers = [('cat_strong+h<=0', strong & hs), ('cat_strong', strong), ('cat_weak+h<=0', weak & hs),
                 ('cat_weak', weak), ('any+h<=0', hs), ('any', np.ones(len(nb), bool))]
        zrel = float(zev[order[rank]] / zev[order[0]])
        for t, (tname, mask) in enumerate(tiers):
            if mask.any():
                j = int(np.argmax(np.where(mask, c, -9)))
                key = (-t, zrel + MU * float(c[j]))        # a closer pair is worth it only if the positive stays strong
                if best is None or key > best[0]:
                    best = (key, pos, int(nb[j]), tname, rank + 1, float(c[j]))
                break
    if best is None:
        return None, 'no silent held-out image'
    _, pos, neg, tier, pos_rank, pair_cos = best
    return dict(refs_high=refs_high, refs_low=refs_low, pos=pos, neg=neg, tier=tier, pos_rank=pos_rank,
                pair_code_cos=pair_cos, low_cos=low_cos, n_high_cand=int(keep.sum()),
                low_pool='strict' if len(pool_strict) >= N_REF else 'any', space=space), None


# ------------------------------------------------------------------ metrics
_STOP = {'the', 'and', 'with', 'of', 'a', 'an', 'in', 'on'}


def _variants(t):
    v = {t}
    if len(t) >= 4 and t.endswith('s'): v.add(t[:-1])
    if len(t) >= 5 and t.endswith('es'): v.add(t[:-2])
    if len(t) >= 5 and t.endswith('ies'): v.add(t[:-3] + 'y')
    if not t.endswith('s'): v.add(t + 's'); v.add(t + 'es')
    if t.endswith('y'): v.add(t[:-1] + 'ies')
    return v


def name_in_text(name, text):
    toks = [t for t in re.findall(r'[a-z]+', name.lower()) if t not in _STOP]
    if not toks:
        return 0
    words = set(re.findall(r'[a-z]+', text))
    return int(all(_variants(t) & words for t in toks))


def metrics(D, a, t, nm):
    hi, lo, pos, neg = t['refs_high'], t['refs_low'], t['pos'], t['neg']
    ch = D.Xn[hi].mean(0); cl = D.Xn[lo].mean(0)
    ch /= np.linalg.norm(ch); cl /= np.linalg.norm(cl)
    s = lambda q: float(D.Xn[q] @ ch - D.Xn[q] @ cl)
    refs = np.array(hi + lo); is_hi = np.r_[np.ones(N_REF), np.zeros(N_REF)]
    knn = lambda q: float(is_hi[np.argsort(-(D.Xn[refs] @ D.Xn[q]))[:5]].mean())
    zev = D.Zev[:, a]
    grp = D.namesakes.get(a, [a])
    cat_h = [D.category(r) for r in hi]
    if D.key == 'imagenet':
        same = [float(D.category(r) in set(cat_h)) for r in lo]
    else:
        same = []
        for r in lo:
            Q = D.labels[r]
            jm = max(((D.labels[x] & Q).sum() / max(1, (D.labels[x] | Q).sum())) for x in hi)
            same.append(float(jm >= COCO_JAC_STRONG))
    tp, tn = D.text_of(pos), D.text_of(neg)
    m5 = {k: int(name_in_text(v, tp) and not name_in_text(v, tn)) for k, v in (('salt', nm['salt']), ('cd', nm['cd']))}
    m5_pos = {k: name_in_text(v, tp) for k, v in (('salt', nm['salt']), ('cd', nm['cd']))}
    return dict(
        m1_margin_centroid=s(pos) - s(neg), m1_s_pos=s(pos), m1_s_neg=s(neg),
        m1_margin_knn=knn(pos) - knn(neg), m1_sign=int(np.sign(s(pos) - s(neg))),
        m2_zpos_rel=float(D.z(pos, a) / max(zev.max(), 1e-9)), m2_zneg=float(D.z(neg, a)),
        m2_namesakes_silent=int(all(D.z(neg, b) == 0.0 for b in grp)),
        m3_jaccard=D.support_jaccard(pos, neg), m3_jaccard_minus_a=D.support_jaccard(pos, neg, excl=a),
        m4_row_cos=float(ch @ cl), m4_same_cat_frac=float(np.mean(same)),
        m5_salt=m5['salt'], m5_cd=m5['cd'], m5_salt_in_pos=m5_pos['salt'], m5_cd_in_pos=m5_pos['cd'],
        pair_dino_cos=float(D.Xn[pos] @ D.Xn[neg]), pair_code_cos_minus_a=float(D.code_cos(pos, [neg], a, 'code')[0]),
        pair_recon_cos_minus_a=float(D.code_cos(pos, [neg], a, 'recon')[0]),
        h_neg=float(D.hcol(a)[neg]), same_cat_pair=[bool(x) for x in D.same_cat(pos, neg)],
        rows_mean_code_cos=float(np.mean([D.code_cos(h_, [l_], a, 'code')[0] for h_, l_ in zip(hi, lo)])),
        high_diversity=float(1 - np.mean([D.code_cos(hi[i], hi[i + 1:], a, 'code').mean() for i in range(N_REF - 1)])),
    )


def lowlevel_sim(D, r1, r2):
    """Cheap low-level similarity of the two real images: 1 - mean |diff| of 16x16 RGB thumbnails (in [0,1])."""
    from PIL import Image
    th = []
    for r in (r1, r2):
        with Image.open(D.path(r)) as im:
            th.append(np.asarray(im.convert('RGB').resize((16, 16), Image.BILINEAR), np.float32) / 255)
    return float(1 - np.abs(th[0] - th[1]).mean())


# ------------------------------------------------------------------ main
def summarize(rows, keys):
    out = {}
    for k in keys:
        v = np.array([r[k] for r in rows if r.get(k) is not None], float)
        if len(v):
            out[k] = dict(median=float(np.median(v)), mean=float(v.mean()), n=int(len(v)))
    return out


def main():
    space = 'recon' if '--space' in sys.argv and sys.argv[sys.argv.index('--space') + 1] == 'recon' else 'code'
    manifest = json.load(open(f'{ROOT}/human_exp/site/stimuli/manifest.json'))
    pool = [k for k, v in manifest['atoms'].items() if v['stratum'] in ('R', 'Delta')]
    assert len(pool) == 120
    out = dict(rule=__doc__, space=space, params=dict(TAU_HIGH=TAU_HIGH, LAMBDA=LAMBDA, POS_FRAC=POS_FRAC, POS_MIN=POS_MIN, MU=MU, N_POS_TOP=N_POS_TOP),
               atoms={}, baseline={}, unserved=[], variant_recon={}, variant_fps={})
    MK = ['m1_margin_centroid', 'm1_margin_knn', 'm1_sign', 'm2_zpos_rel', 'm2_zneg', 'm2_namesakes_silent', 'm3_jaccard',
          'm3_jaccard_minus_a', 'm4_row_cos', 'm4_same_cat_frac', 'm5_salt', 'm5_cd', 'm5_salt_in_pos', 'm5_cd_in_pos',
          'pair_dino_cos', 'pair_code_cos_minus_a', 'pair_recon_cos_minus_a', 'h_neg', 'rows_mean_code_cos',
          'high_diversity', 'lowlevel_pair', 'lowlevel_rows']
    for key in M.KEYS:
        D = DataC(key)
        log(key, 'loaded')
        for aid in pool:
            if not aid.startswith(key):
                continue
            a = int(aid.split('_')[1]); nm = D.names[a]
            # baseline = current manifest
            src = manifest['atoms'][aid]['meta']['src']
            tb = dict(refs_high=[D.row_of(i) for i in src['refs_high']], refs_low=[D.row_of(i) for i in src['refs_low']],
                      pos=D.row_of(src['query_pos']), neg=D.row_of(src['query_neg']))
            mb = metrics(D, a, tb, nm)
            mb['lowlevel_pair'] = lowlevel_sim(D, tb['pos'], tb['neg'])
            mb['lowlevel_rows'] = float(np.mean([lowlevel_sim(D, h_, l_) for h_, l_ in zip(tb['refs_high'], tb['refs_low'])]))
            out['baseline'][aid] = dict(src=src, **mb)
            # ours
            t, why = select_trial(D, a, None, space)
            if t is None:
                out['unserved'].append(dict(atom=aid, reason=why)); continue
            mt = metrics(D, a, t, nm)
            mt['lowlevel_pair'] = lowlevel_sim(D, t['pos'], t['neg'])
            mt['lowlevel_rows'] = float(np.mean([lowlevel_sim(D, h_, l_) for h_, l_ in zip(t['refs_high'], t['refs_low'])]))
            ids = dict(refs_high=[D.dataset_id(r) for r in t['refs_high']], refs_low=[D.dataset_id(r) for r in t['refs_low']],
                       query_pos=D.dataset_id(t['pos']), query_neg=D.dataset_id(t['neg']),
                       id_kind='COCO image id' if key == 'coco' else 'ImageNet val row (= id)')
            paths = dict(refs_high=[D.path(r) for r in t['refs_high']], refs_low=[D.path(r) for r in t['refs_low']],
                         query_pos=D.path(t['pos']), query_neg=D.path(t['neg']))
            out['atoms'][aid] = dict(src=ids, paths=paths, names=dict(B=nm['salt'], D=nm['cd']),
                                     category_pos=D.category_name(D.category(t['pos'])), category_neg=D.category_name(D.category(t['neg'])),
                                     tier=t['tier'], pos_rank=t['pos_rank'], low_pool=t['low_pool'], n_high_cand=t['n_high_cand'],
                                     z_pos=float(D.z(t['pos'], a)), refs_high_z_rel_min=float(min(D.z(r, a) for r in t['refs_high']) / D.top_tr_val[a][0]), **mt)
            # the other space, for the comparison (queries + rows), metrics only
            t2, _ = select_trial(D, a, None, 'recon' if space == 'code' else 'code')
            if t2 is not None:
                m2_ = metrics(D, a, t2, nm)
                m2_['lowlevel_pair'] = lowlevel_sim(D, t2['pos'], t2['neg'])
                m2_['lowlevel_rows'] = float(np.mean([lowlevel_sim(D, h_, l_) for h_, l_ in zip(t2['refs_high'], t2['refs_low'])]))
                out['variant_recon'][aid] = dict(src=dict(refs_high=[D.dataset_id(r) for r in t2['refs_high']], refs_low=[D.dataset_id(r) for r in t2['refs_low']],
                                                          query_pos=D.dataset_id(t2['pos']), query_neg=D.dataset_id(t2['neg'])),
                                                 same_pair_as_code=(t2['pos'] == t['pos'] and t2['neg'] == t['neg']),
                                                 tier=t2['tier'], **m2_)
            # pure farthest-point sampling for refs_high (and its twins), same queries rule
            t3, _ = select_trial(D, a, None, 'code', 'fps')
            if t3 is not None:
                m3_ = metrics(D, a, t3, nm)
                m3_['lowlevel_pair'] = lowlevel_sim(D, t3['pos'], t3['neg'])
                m3_['lowlevel_rows'] = float(np.mean([lowlevel_sim(D, h_, l_) for h_, l_ in zip(t3['refs_high'], t3['refs_low'])]))
                m3_['refs_high_z_rel_min'] = float(min(D.z(r, a) for r in t3['refs_high']) / D.top_tr_val[a][0])
                out['variant_fps'][aid] = dict(src=dict(refs_high=[D.dataset_id(r) for r in t3['refs_high']], refs_low=[D.dataset_id(r) for r in t3['refs_low']]),
                                               n_high_shared_with_greedy=len(set(t3['refs_high']) & set(t['refs_high'])), **m3_)
        log(key, 'done', sum(k.startswith(key) for k in out['atoms']), 'served')
        # does code overlap capture low-level similarity? correlation, over silent same-category held-out candidates,
        # between code-cos(-a) to the positive and DINOv2 cosine / 16x16 thumbnail similarity (subsample)
        corr = []
        rng = np.random.default_rng(0)
        for aid in [k for k in out['atoms'] if k.startswith(key)][:40]:
            a = int(aid.split('_')[1]); pos = D.row_of(out['atoms'][aid]['src']['query_pos'])
            is_ev = np.zeros(D.N, bool); is_ev[D.ev] = True
            nb = np.where(is_ev & D.silent_rows(a))[0]; nb = nb[nb != pos]
            if len(nb) > 300: nb = rng.choice(nb, 300, replace=False)
            c = D.code_cos(pos, nb, a, 'code'); d = D.Xn[nb] @ D.Xn[pos]
            ll = np.array([lowlevel_sim(D, pos, int(r)) for r in nb[:120]])
            corr.append(dict(atom=aid, pearson_code_dino=float(np.corrcoef(c, d)[0, 1]),
                             spearman_code_dino=float(np.corrcoef(np.argsort(np.argsort(c)), np.argsort(np.argsort(d)))[0, 1]),
                             pearson_code_lowlevel=float(np.corrcoef(c[:120], ll)[0, 1]),
                             pearson_dino_lowlevel=float(np.corrcoef(d[:120], ll)[0, 1])))
        out.setdefault('code_vs_lowlevel', {})[key] = dict(per_atom=corr, median={k: float(np.median([c[k] for c in corr]))
                                                                                   for k in corr[0] if k != 'atom'})
        del D
    out['summary'] = dict(ours=summarize(list(out['atoms'].values()), MK), baseline=summarize(list(out['baseline'].values()), MK),
                          variant_recon=summarize(list(out['variant_recon'].values()), MK),
                          variant_fps=summarize(list(out['variant_fps'].values()), MK + ['refs_high_z_rel_min', 'n_high_shared_with_greedy']),
                          refs_high_z_rel_min=summarize(list(out['atoms'].values()), ['refs_high_z_rel_min']),
                          ours_by_dataset={k: summarize([v for i, v in out['atoms'].items() if i.startswith(k)], MK) for k in M.KEYS},
                          baseline_by_dataset={k: summarize([v for i, v in out['baseline'].items() if i.startswith(k)], MK) for k in M.KEYS},
                          n_served=len(out['atoms']), n_unserved=len(out['unserved']),
                          tiers={t: sum(v['tier'] == t for v in out['atoms'].values()) for t in sorted({v['tier'] for v in out['atoms'].values()})},
                          recon_same_pair=int(sum(v['same_pair_as_code'] for v in out['variant_recon'].values())),
                          pos_rank_median=float(np.median([v['pos_rank'] for v in out['atoms'].values()])))
    json.dump(out, open(f'{EXP}/metrics.json', 'w'), indent=1)
    log('summary', json.dumps(out['summary']['tiers']), 'served', out['summary']['n_served'])
    for k in MK:
        o, b = out['summary']['ours'].get(k), out['summary']['baseline'].get(k)
        if o and b:
            print(f'{k:28s} ours {o["median"]:+.4f} (mean {o["mean"]:+.4f})   baseline {b["median"]:+.4f} (mean {b["mean"]:+.4f})')
    if '--no-sheet' not in sys.argv:
        import importlib.util
        spec = importlib.util.spec_from_file_location('sheet', f'{EXP}/sheet.py')
        sheet = importlib.util.module_from_spec(spec); spec.loader.exec_module(sheet)
        sheet.build(out, manifest)


if __name__ == '__main__':
    main()

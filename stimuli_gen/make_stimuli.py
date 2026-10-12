"""Build the stimuli of the SALT human study (2AFC task, Colin thesis ch. 3).

Writes site/stimuli/manifest.json, site/stimuli/img/<atom_id>/*.jpg, site/stimuli/example/,
stimuli_gen/selection_log.json and stimuli_gen/contact_sheet.html.

Stage 1 (needs torch, so an aarch64 GPU node): sparse SAE codes for coco and imagenet, cached in
stimuli_gen/cache/codes_<key>.npz. Stage 2 (numpy + Pillow only): selection, images, manifest.
If the cache exists, stage 1 is skipped, so stage 2 can be rerun anywhere.

Usage: python3 make_stimuli.py [--recompute]
"""
import csv, json, math, os, shutil, sys, time
import numpy as np
from PIL import Image

ROOT = '/lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE'
HX = f'{ROOT}/human_exp'
GEN = f'{HX}/stimuli_gen'
SITE = f'{HX}/site'
STIM = f'{SITE}/stimuli'
CACHE = f'{GEN}/cache'
VERSION = '2026-10-12-v3'   # v3 : atomes sans nom de classe, non détecteurs de classe, cohérents (>= 0.15)
HERE = os.path.dirname(os.path.abspath(__file__))
CLASS_CORR_MAX = 0.4         # an eligible atom correlates < 0.4 with every class indicator (not a class detector)
COHERENCE_MIN = 0.15         # and its 9 top images are visually coherent (mean pairwise DINOv2 cosine >= 0.15)
KEYS = ('coco', 'imagenet')
DS_OFFSET = {'coco': 0, 'imagenet': 1}     # added to per-atom seeds so the two datasets never share a seed

# Seeds and sizes (all recorded in selection_log.json).
SEED_R = 0                 # stratum R draw (per dataset: default_rng(SEED_R) on the sorted evaluable atoms)
SEED_ATOM = lambda key, a: 1000003 * a + 7 + DS_OFFSET[key]   # query pair draw of one atom
SEED_LISTS = 1             # list assignment
SEED_CNAMES = 2            # derangements for condition C
SEED_CATCH = 3             # catch atoms and their reference index
N_R, N_DELTA = 30, 30      # per dataset
N_PRACTICE = {'coco': 5, 'imagenet': 4}
N_CATCH = {'coco': 3, 'imagenet': 2}
N_REF = 9
# Example atom of the instructions (imagenet), fixed after a visual check of the top candidates by corr_salt:
# refs = mortars and pestles; query pair = guacamole in a stone mortar vs guacamole in a bowl.
EXAMPLE_ATOM = 4999
TOP_FRAC = 0.05            # (kept for the log only)
N_POS_TOP = 10             # query_pos: the most activating held-out image, walking the top 10 by decreasing z_a until one has a same-category negative
K = 32
IMG_SIZE, JPEG_Q = 224, 85

# Names that must never be shown to participants (substring match on the lowercased name).
BLOCK_SUB = ['sex', 'porn', 'nude', 'naked', 'nsfw', 'fuck', 'shit', 'rape', 'nazi', 'hitler', 'nigg', 'fag',
             'slut', 'whore', 'bitch', 'cunt', 'dick', 'penis', 'vagina', 'boob', 'tits', 'erotic', 'xxx',
             'suicide', 'murder', 'corpse', 'gore', 'kill', 'terror', 'retard']
BLOCK_WORD = {'ass', 'anal', 'cock', 'dead', 'blood', 'gun', 'guns', 'drug', 'drugs', 'weapon', 'weapons'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def blocked(name):
    n = name.lower()
    return any(s in n for s in BLOCK_SUB) or any(t in BLOCK_WORD for t in n.replace('_', ' ').split())


# ---------------------------------------------------------------- stage 1: codes (torch)
def compute_codes(key):
    import pickle, torch
    sys.path.insert(0, f'{ROOT}/paper_proto')
    from common import DS, cache, keep_of, split, rows, pre_code
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    probe, nsub, ck, sc = DS[key][:4]
    CD, VOC = cache(probe)
    N0 = np.load(f'{CD}/Y_vlgbce{VOC}.npy', mmap_mode='r').shape[0]
    KEEP = keep_of(probe, N0, nsub)
    assert nsub == 0 and (KEEP == np.arange(N0)).all(), 'paper SAEs of coco/imagenet use the full cache'
    N = len(KEEP)
    ev, tr = split(N, key)
    PRE, We, be = pre_code(ck, dev)
    m = PRE.m
    scal = pickle.load(open(sc, 'rb'))
    A = scal.transform(rows(f'{CD}/A_img.npy', KEEP)).astype('float32')
    is_tr = np.zeros(N, bool); is_tr[tr] = True
    z_idx = np.zeros((N, K), np.int32); z_val = np.zeros((N, K), np.float32)
    NT = 50
    top_v = torch.full((NT, m), -1.0, device=dev); top_i = torch.full((NT, m), -1, dtype=torch.long, device=dev)
    low_v = torch.full((N_REF, m), float('inf'), device=dev); low_i = torch.full((N_REF, m), -1, dtype=torch.long, device=dev)
    nact_tr = torch.zeros(m, dtype=torch.long, device=dev)
    with torch.no_grad():
        for s in range(0, N, 8192):
            h = PRE(torch.from_numpy(A[s:s + 8192]).to(dev))
            v, j = h.relu().topk(K, -1)
            z_idx[s:s + 8192] = j.cpu().numpy(); z_val[s:s + 8192] = v.cpu().numpy()
            rows_g = torch.arange(s, s + h.shape[0], device=dev)
            trm = torch.from_numpy(is_tr[s:s + 8192]).to(dev)
            z = torch.zeros_like(h).scatter_(1, j, v)
            zt, ht, rt = z[trm], h[trm], rows_g[trm]
            nact_tr += (zt > 0).sum(0)
            # running top-50 of z and bottom-9 of h over TRAIN rows, per atom
            cv = torch.cat([top_v, zt]); ci = torch.cat([top_i, rt[:, None].expand(-1, m)])
            o = cv.topk(NT, 0).indices; top_v = cv.gather(0, o); top_i = ci.gather(0, o)
            cv = torch.cat([low_v, ht]); ci = torch.cat([low_i, rt[:, None].expand(-1, m)])
            o = (-cv).topk(N_REF, 0).indices; low_v = cv.gather(0, o); low_i = ci.gather(0, o)
    # control against the paper bundle (same check as paper_proto/paper_eval.py)
    bz = np.load(f'{ROOT}/bundles/bundle_{key}.npz', allow_pickle=True)
    Zb = np.asarray(bz['codes'][:2000]); Zr = np.zeros((2000, m), np.float32)
    np.put_along_axis(Zr, z_idx[:2000].astype(np.int64), z_val[:2000], 1)
    ec = float(np.abs(Zb - Zr).max()); log(key, 'max |codes - bundle| on 2000 rows =', ec)
    del bz, Zb
    out = dict(ev=ev, tr=tr, z_idx=z_idx, z_val=z_val, top_tr=top_i.T.cpu().numpy(), top_tr_val=top_v.T.cpu().numpy(),
               low_tr=low_i.T.cpu().numpy(), low_tr_val=low_v.T.cpu().numpy(), nact_tr=nact_tr.cpu().numpy(),
               We=We.cpu().numpy(), be=be.cpu().numpy(), sc_mean=scal.mean_.astype('float32'),
               sc_scale=scal.scale_.astype('float32'), bundle_err=np.float64(ec), N=np.int64(N), m=np.int64(m),
               ckpt=np.array(ck), scaler=np.array(sc), cache_dir=np.array(CD))
    os.makedirs(CACHE, exist_ok=True)
    np.savez(f'{CACHE}/codes_{key}.npz', **out)
    log(key, 'codes saved: N', N, 'atoms', m, 'EVAL', len(ev), 'TRAIN', len(tr))


# ---------------------------------------------------------------- stage 2: selection and images
def load_names(key):
    """SALT ('tete_s0') and CLIP-Dissect ('cd_off_20k') open-vocabulary names and held-out UF_correlation."""
    d = {}
    for x in csv.DictReader(open(f'{ROOT}/paper_proto/out/{key}_atomes.csv')):
        if x['regime'] == 'ouvert' and x['methode'] in ('tete_s0', 'cd_off_20k'):
            d.setdefault(int(x['atome']), {})[x['methode']] = x
    out = {}
    for a, v in d.items():
        if len(v) != 2:
            continue
        s, c = v['tete_s0'], v['cd_off_20k']
        out[a] = dict(salt=s['nom'].replace('_', ' ').strip(), cd=c['nom'].replace('_', ' ').strip(),
                      corr_salt=float(s['UF_correlation']), corr_cd=float(c['UF_correlation']),
                      salt_evaluable=s['nom_evaluable'] == '1', cd_evaluable=c['nom_evaluable'] == '1')
    return out


class Data:
    def __init__(self, key):
        self.key = key
        c = np.load(f'{CACHE}/codes_{key}.npz')
        for k in c.files:
            setattr(self, k, c[k])
        self.CD = str(c['cache_dir'])
        self.N, self.m = int(self.N), int(self.m)
        self.id2path = json.load(open(f'{self.CD}/id2path.json'))
        self.image_ids = np.load(f'{self.CD}/image_ids.npy')
        assert len(set(self.id2path.values())) == len(self.id2path) == self.N, 'id2path must map rows to distinct files'
        if key == 'coco':
            self.labels = np.load(f'{self.CD}/Y_vlgbce.npy') > 0
            self.label_names = json.load(open(f'{self.CD}/vlgbce_concepts.json'))
            assert self.labels.shape[1] == 80
        else:
            assert (self.image_ids == np.arange(self.N)).all(), 'imagenet: row index must equal image id'
            self.wnid = np.array([os.path.basename(os.path.dirname(self.id2path[str(r)])) for r in range(self.N)])
            i2c = json.load(open(f'{self.CD}/img_to_cats.json'))
            self.cls_name = {}
            for r in range(self.N):
                self.cls_name.setdefault(self.wnid[r], i2c[str(r)][0])
        self.ev_set = set(self.ev.tolist())
        # dense EVAL codes (n_ev x m) for the query search
        self.Zev = np.zeros((len(self.ev), self.m), np.float32)
        np.put_along_axis(self.Zev, self.z_idx[self.ev].astype(np.int64), self.z_val[self.ev], 1)
        self.n_top = int(math.ceil(TOP_FRAC * len(self.ev)))
        A = np.load(f'{self.CD}/A_img.npy', mmap_mode='r')
        self.A = A

    def path(self, r):
        p = self.id2path[str(int(r))]
        if self.key == 'coco':
            assert f'{int(self.image_ids[int(r)]):012d}' in os.path.basename(p), f'coco id trap at row {r}'
        return p

    def h(self, r, a):
        """Pre-code h_a of one row (numpy, same as stage 1)."""
        x = (np.asarray(self.A[int(r)], np.float32) - self.sc_mean) / self.sc_scale
        return float(x @ self.We[a] + self.be[a])

    def z(self, r, a):
        hit = np.where(self.z_idx[int(r)] == a)[0]
        return float(self.z_val[int(r), hit[0]]) if len(hit) else 0.0

    def evaluable_live(self):
        """Live on TRAIN and active on >= k_b EVAL images (paper_eval.py definition), to check the CSV atom set."""
        kb = max(1, int(round(0.005 * len(self.ev))))
        live = self.nact_tr > 0
        nact_ev = (self.Zev > 0).sum(0)
        return set(np.where(live & (nact_ev >= kb))[0].tolist()), nact_ev

    def category(self, r):
        if self.key == 'imagenet':
            return self.wnid[int(r)]
        return frozenset(np.where(self.labels[int(r)])[0].tolist())

    def category_name(self, cat):
        if self.key == 'imagenet':
            return self.cls_name[cat]
        return ', '.join(sorted(self.label_names[i] for i in cat))

    def set_namesakes(self, names):
        """Split features (9 Oct. 2026): many atoms share one open-vocabulary name (e.g. 45 COCO atoms are
        named 'pizza'). A wrong query on which a namesake fires is a trial that no name can solve, so the
        negative must be silent on every atom that shares the target's SALT name OR its CLIP-Dissect name."""
        by = {'salt': {}, 'cd': {}}
        for b, v in names.items():
            for k in by:
                by[k].setdefault(v[k].lower(), set()).add(b)
        self.namesakes = {b: sorted(by['salt'][v['salt'].lower()] | by['cd'][v['cd'].lower()] | {b}) for b, v in names.items()}

    def find_negative(self, a, pos_row, rng):
        """Held-out row of the same category as pos_row on which atom a AND every namesake of a
        (same SALT or same CLIP-Dissect name) is silent; None if there is none."""
        grp = getattr(self, 'namesakes', {}).get(a, [a])
        silent = (self.Zev[:, grp] == 0).all(1)
        inactive = self.ev[silent]
        inactive = inactive[inactive != pos_row]
        if self.key == 'imagenet':
            cand = inactive[self.wnid[inactive] == self.wnid[pos_row]]
            if len(cand) == 0:
                return None
            return int(cand[rng.integers(len(cand))]), self.wnid[pos_row]
        P = self.labels[pos_row]
        if not P.any():
            return None
        L = self.labels[inactive]
        inter = (L & P).sum(1); union = (L | P).sum(1)
        jac = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
        best = jac.max() if len(jac) else 0.0
        if best <= 0:
            return None
        cand = inactive[jac == best]
        neg = int(cand[rng.integers(len(cand))])
        shared = frozenset(np.where(self.labels[pos_row] & self.labels[neg])[0].tolist())
        return neg, shared

    def build_atom(self, a, pos_order='seeded'):
        """Reference and query rows of atom a, or (None, reason).
        pos_order 'seeded': candidates walked in a seeded random order (test, practice).
        pos_order 'top': candidates walked by decreasing z_a (illustrated example only, to get a clear-cut pair)."""
        top, topv = self.top_tr[a], self.top_tr_val[a]
        if (topv[:N_REF] <= 0).any():
            return None, 'fewer than 9 naming-split images with z>0'
        refs_high = [int(r) for r in top[:N_REF]]
        refs_low = [int(r) for r in self.low_tr[a]]
        assert not set(refs_high) & set(refs_low)
        zcol = self.Zev[:, a]
        order = np.argsort(-zcol, kind='stable')[:self.n_top]
        cand = [int(i) for i in order if zcol[i] > 0]
        if not cand:
            return None, 'no held-out image with z>0'
        rng = np.random.default_rng(SEED_ATOM(self.key, a))
        rank_of = {i: k for k, i in enumerate(order.tolist())}
        # 8 Oct. 2026: positives taken among the MOST activating held-out images (decreasing z_a, top N_POS_TOP);
        # the earlier seeded draw over the top 5 % gave ImageNet positives that barely fired (median rank 34.5)
        walk = cand[:N_POS_TOP]
        for i in walk:
            pos = int(self.ev[i])
            r = self.find_negative(a, pos, rng if pos_order == 'seeded' else np.random.default_rng(SEED_ATOM(self.key, a)))
            if r is not None:
                neg, cat = r
                return dict(refs_high=refs_high, refs_low=refs_low, pos=pos, neg=neg, cat=cat,
                            z_pos=float(zcol[i]), pos_rank_ev=int(rank_of[int(i)]) + 1,
                            n_pos_candidates=len(cand)), None
        return None, 'no held-out negative of the same category'

    def build_catch(self, a, rng):
        top, topv = self.top_tr[a], self.top_tr_val[a]
        if (topv[:N_REF] <= 0).any():
            return None, 'fewer than 9 naming-split images with z>0'
        refs_high = [int(r) for r in top[:N_REF]]
        k = int(rng.integers(N_REF))
        pos = refs_high[k]
        r = self.find_negative(a, pos, rng)
        if r is None:
            return None, 'no held-out negative of the same category as the copied reference'
        neg, cat = r
        return dict(refs_high=refs_high, refs_low=[int(x) for x in self.low_tr[a]], pos=pos, neg=neg, cat=cat,
                    z_pos=float(topv[k]), pos_rank_ev=None, catch_ref_index=k, n_pos_candidates=None), None


def check_images(D, rows):
    for r in rows:
        try:
            with Image.open(D.path(r)) as im:
                im.convert('RGB').size
        except Exception as e:
            return f'image {D.path(r)} unreadable: {e}'
    return None


def save_square(src, dst):
    """Shorter side resized to 224 (bicubic), centre crop 224x224, RGB, JPEG q85, no EXIF."""
    with Image.open(src) as im:
        im = im.convert('RGB')
        w, h = im.size
        s = IMG_SIZE / min(w, h)
        nw, nh = max(IMG_SIZE, round(w * s)), max(IMG_SIZE, round(h * s))
        im = im.resize((nw, nh), Image.BICUBIC)
        l, t = (nw - IMG_SIZE) // 2, (nh - IMG_SIZE) // 2
        im = im.crop((l, t, l + IMG_SIZE, t + IMG_SIZE))
        im.save(dst, 'JPEG', quality=JPEG_Q, optimize=True)


def derange(ids, salt, cd, rng, outside=()):
    """sigma over ids with no fixed point such that SALT(sigma(a)) differs from SALT(a) and CD(a).
    If no such derangement is found, sources may come from `outside` (other non-pool atoms)."""
    ids = list(ids)
    ok = lambda a, b: a != b and salt[b] != salt[a] and salt[b] != cd[a]
    for _ in range(20000):
        p = list(rng.permutation(ids))
        if all(ok(a, b) for a, b in zip(ids, p)):
            return dict(zip(ids, p)), 0
    sig, used = {}, set()
    pool = list(rng.permutation(list(outside)))
    for a in ids:
        b = next(b for b in pool if b not in used and ok(a, b))
        sig[a] = b; used.add(b)
    return sig, 1


def main():
    if '--recompute' in sys.argv or not all(os.path.exists(f'{CACHE}/codes_{k}.npz') for k in KEYS):
        for k in KEYS:
            if '--recompute' in sys.argv or not os.path.exists(f'{CACHE}/codes_{k}.npz'):
                compute_codes(k)
    LOG = dict(version=VERSION, created=time.strftime('%Y-%m-%d %H:%M:%S'),
               seeds=dict(R=SEED_R, atom='1000003*atom + 7 + (0 coco, 1 imagenet)', lists=SEED_LISTS,
                          c_names=SEED_CNAMES, catch=SEED_CATCH, split='paper_proto/common.split(N, key): default_rng(0) permutation, first 20 % held-out'),
               rules=dict(names="paper_proto/out/<key>_atomes.csv, regime 'ouvert', SALT = methode 'tete_s0', CLIP-Dissect = 'cd_off_20k'",
                          code='z = TopK_32(ReLU(h)), h = scaler(A_img) @ We.T + be, SAE = DS[key] of paper_proto/common.py',
                          refs_high='9 naming-split images with the highest z_a (h0 = highest)',
                          refs_low='9 naming-split images with the lowest pre-code h_a (l0 = lowest)',
                          query_pos=f'held-out, the highest-z_a image among the top {N_POS_TOP} held-out images by z_a that has a same-category negative; '
                                    'candidates walked by decreasing z_a until a negative exists',
                          query_neg='held-out, z = 0 for the atom AND for every atom sharing its SALT or CLIP-Dissect name (split features), same category: imagenet same wnid; coco max Jaccard of the 80-label sets (> 0), ties by seed',
                          example=f'imagenet atom {EXAMPLE_ATOM} fixed after visual check; its query_pos walks held-out candidates by decreasing z_a',
                          crop='shorter side to 224 (bicubic) + centre crop 224, JPEG q85, optimize, EXIF stripped',
                          blocklist=dict(substrings=BLOCK_SUB, words=sorted(BLOCK_WORD))),
               datasets={})
    manifest = dict(version=VERSION, lists=[], atoms={}, practice=[], catch=[])
    chosen = {}       # atom_id -> (key, a, build, stratum)
    names_all, D_all = {}, {}
    rng_lists = np.random.default_rng(SEED_LISTS)
    rng_c = np.random.default_rng(SEED_CNAMES)
    rng_catch = np.random.default_rng(SEED_CATCH)
    list_sets = {j: [] for j in range(3)}
    for key in KEYS:
        D = Data(key); D_all[key] = D
        names = load_names(key); names_all[key] = names
        D.set_namesakes(names)
        eva, nact_ev = D.evaluable_live()
        L = dict(N=D.N, n_eval=len(D.ev), n_train=len(D.tr), n_atoms=D.m, bundle_err=float(D.bundle_err),
                 n_csv_atoms=len(names), n_recomputed_evaluable=len(eva),
                 csv_equals_recomputed=set(names) == eva, n_top_pos=D.n_top)
        assert set(names) == eva, f'{key}: CSV atoms differ from the recomputed evaluable set ({len(names)} vs {len(eva)})'
        log(key, L)
        cache_build = {}

        def get(a):
            if a not in cache_build:
                nm = names[a]
                if not nm['salt'] or not nm['cd']:
                    cache_build[a] = (None, 'empty name')
                elif blocked(nm['salt']) or blocked(nm['cd']):
                    cache_build[a] = (None, f"blocklisted name: SALT '{nm['salt']}', CD '{nm['cd']}'")
                else:
                    b, why = D.build_atom(a)
                    if b is not None:
                        why = check_images(D, b['refs_high'] + b['refs_low'] + [b['pos'], b['neg']])
                        if why:
                            b = None
                    cache_build[a] = (b, why)
            return cache_build[a]

        atoms_sorted = sorted(names)
        # 12 Oct. 2026: test and practice atoms must not be named by a class name (class_name_filter.py: neither the SALT nor the
        # CLIP-Dissect name is a class name, a class hypernym or a non-dictionary word; the same rule for both methods)
        ELIG = json.load(open(f'{HERE}/class_name_filter_{key}.json'))['atoms']
        eligible = sorted(a for a in atoms_sorted if ELIG[str(a)]['eligible'])
        # and the atom itself must not be a class detector, whatever its names say (a giraffe atom named 'tucson'): Pearson correlation
        # between its code and every class indicator (ImageNet: 1 000 classes; COCO: 80 labels) over all images < CLASS_CORR_MAX
        Zall = np.zeros((D.N, D.m), np.float32); np.put_along_axis(Zall, D.z_idx.astype(np.int64), D.z_val, 1)
        if key == 'imagenet':
            _u, _inv = np.unique(D.wnid, return_inverse=True); Ycls = np.zeros((D.N, len(_u)), np.float32); Ycls[np.arange(D.N), _inv] = 1
        else:
            Ycls = D.labels.astype(np.float32)
        Ze = Zall[:, eligible]; Ze = (Ze - Ze.mean(0)) / (Ze.std(0) + 1e-9); Yc = (Ycls - Ycls.mean(0)) / (Ycls.std(0) + 1e-9)
        cmax = (Ze.T @ Yc / D.N).max(1); del Zall, Ze
        n_name = len(eligible); eligible = [a for a, cm in zip(eligible, cmax) if cm < CLASS_CORR_MAX]
        n_cls = len(eligible)
        # 12 Oct. 2026: the atom must be visually coherent, whatever its names: mean pairwise cosine (standardised, L2-normalised DINOv2)
        # between its 9 top naming-split images (top 25 by z, near-duplicates cos > 0.85 skipped, the refs_high rule of the prototypes)
        Xs = (np.asarray(D.A, np.float32) - D.sc_mean) / D.sc_scale; Xn = Xs / np.maximum(np.linalg.norm(Xs, axis=1, keepdims=True), 1e-6); del Xs
        COH = {}
        for a in eligible:
            hi = []
            for r, v in zip(D.top_tr[a][:25], D.top_tr_val[a][:25]):
                if v <= 0 or (hi and (Xn[hi] @ Xn[int(r)]).max() > 0.85):
                    continue
                hi.append(int(r))
                if len(hi) == N_REF:
                    break
            if len(hi) == N_REF:
                S_ = Xn[hi] @ Xn[hi].T; COH[a] = float((S_.sum() - N_REF) / (N_REF * (N_REF - 1)))
        del Xn
        eligible = [a for a in eligible if COH.get(a, -1) >= COHERENCE_MIN]
        L['class_name_filter'] = dict(n_evaluable=len(atoms_sorted), n_name_ok=n_name, n_not_class_detector=n_cls, n_eligible=len(eligible),
                                      class_corr_max=CLASS_CORR_MAX, coherence_min=COHERENCE_MIN)
        # stratum R: seeded draw, invalid atoms replaced by the next ones of the draw
        draw = np.random.default_rng(SEED_R).permutation(eligible)
        R, repl_R = [], []
        for a in draw:
            if len(R) == N_R:
                break
            b, why = get(int(a))
            if b is None:
                repl_R.append(dict(atom=int(a), reason=why))
            else:
                R.append(int(a))
        # stratum Delta: largest |corr_salt - corr_cd| among atoms with different names, not in R
        dl = [a for a in eligible if a not in R and names[a]['salt'] != names[a]['cd']]
        dl.sort(key=lambda a: (-abs(names[a]['corr_salt'] - names[a]['corr_cd']), a))
        Dl, repl_D = [], []
        for a in dl:
            if len(Dl) == N_DELTA:
                break
            b, why = get(a)
            if b is None:
                repl_D.append(dict(atom=a, reason=why))
            else:
                Dl.append(a)
        assert len(R) == N_R and len(Dl) == N_DELTA
        pool = set(R) | set(Dl)
        # practice: clear-cut atoms outside the pool (largest min(corr_salt, corr_cd), z_pos above the pool median,
        # distinct SALT names, both names evaluable on held-out captions)
        zmed = float(np.median([get(a)[0]['z_pos'] for a in pool]))
        pr_cand = sorted([a for a in eligible if a not in pool and names[a]['salt_evaluable'] and names[a]['cd_evaluable']],
                         key=lambda a: (-min(names[a]['corr_salt'], names[a]['corr_cd']), a))
        P, seen, repl_P = [], set(), []
        for a in pr_cand:
            if len(P) == N_PRACTICE[key]:
                break
            if names[a]['salt'] in seen:
                continue
            b, why = get(a)
            if b is None:
                repl_P.append(dict(atom=a, reason=why)); continue
            if b['z_pos'] <= zmed:
                continue
            P.append(a); seen.add(names[a]['salt'])
        # example (imagenet only): outside pool and practice, high corr_salt, both names evaluable, names differ
        EX = None
        if key == 'imagenet':
            ex_cand = sorted([a for a in atoms_sorted if a not in pool and a not in P and names[a]['salt_evaluable']
                              and names[a]['cd_evaluable'] and names[a]['salt'] not in seen],
                             key=lambda a: (-names[a]['corr_salt'], a))
            for a in ([EXAMPLE_ATOM] if EXAMPLE_ATOM in ex_cand else []) + ex_cand:
                b, why = get(a)
                if b is not None and b['z_pos'] > zmed:
                    EX = a; break
            ex_build = D.build_atom(EX, pos_order='top')[0]
        # catch: uniform draw among the remaining atoms
        rest = [a for a in atoms_sorted if a not in pool and a not in P and a != EX]
        Cc, repl_C = [], []
        for a in rng_catch.permutation(rest):
            a = int(a)
            if len(Cc) == N_CATCH[key]:
                break
            nm = names[a]
            if blocked(nm['salt']) or blocked(nm['cd']) or not nm['salt'] or not nm['cd']:
                repl_C.append(dict(atom=a, reason='name')); continue
            b, why = D.build_catch(a, rng_catch)
            if b is not None:
                why = check_images(D, b['refs_high'] + b['refs_low'] + [b['neg']])
            if b is None or why:
                repl_C.append(dict(atom=a, reason=why)); continue
            cache_build[('catch', a)] = (b, None)
            Cc.append(a)
        # condition C names: fixed derangements within (dataset, group)
        salt = {a: names[a]['salt'] for a in names}; cd = {a: names[a]['cd'] for a in names}
        outside = [a for a in rest if a not in Cc and not blocked(salt[a]) and not blocked(cd[a]) and salt[a]]
        c_src, c_fallback = {}, {}
        for grp, ids in (('pool', sorted(pool)), ('practice', P), ('catch', Cc)):
            sig, fb = derange(ids, salt, cd, rng_c, outside)
            c_src.update(sig); c_fallback[grp] = fb
        if EX is not None:
            sig, _ = derange([EX], salt, cd, rng_c, outside)      # one atom: source taken from another non-pool atom
            c_src.update(sig)
        # list assignment: blocks of 3 in sorted order, random permutation of lists inside each block
        for stratum, ids, sk in (('R', R, lambda a: (names[a]['corr_salt'], a)),
                                 ('Delta', Dl, lambda a: (abs(names[a]['corr_salt'] - names[a]['corr_cd']), a))):
            srt = sorted(ids, key=sk)
            for s in range(0, len(srt), 3):
                for a, j in zip(srt[s:s + 3], rng_lists.permutation(3)):
                    list_sets[int(j)].append(f'{key}_{a}')
        for a in R: chosen[f'{key}_{a}'] = (key, a, get(a)[0], 'R', c_src[a])
        for a in Dl: chosen[f'{key}_{a}'] = (key, a, get(a)[0], 'Delta', c_src[a])
        for a in P: chosen[f'{key}_{a}'] = (key, a, get(a)[0], 'practice', c_src[a])
        for a in Cc: chosen[f'{key}_{a}'] = (key, a, cache_build[('catch', a)][0], 'catch', c_src[a])
        if EX is not None:
            chosen['__example__'] = (key, EX, ex_build, 'example', c_src[EX])
        signs = [int(np.sign(names[a]['corr_salt'] - names[a]['corr_cd'])) for a in Dl]
        L.update(dict(
            n_R=len(R), n_Delta=len(Dl), n_practice=len(P), n_catch=len(Cc), example=EX,
            replacements=dict(R=len(repl_R), Delta=len(repl_D), practice=len(repl_P), catch=len(repl_C)),
            replaced_atoms=dict(R=repl_R, Delta=repl_D, practice=repl_P, catch=repl_C),
            n_atoms_with_blocklisted_name=sum(blocked(names[a]['salt']) or blocked(names[a]['cd']) for a in names),
            blocklisted_names=sorted({n_ for a in names for n_ in (names[a]['salt'], names[a]['cd']) if blocked(n_)}),
            n_delta_candidates=len(dl), pool_z_pos_median=zmed, c_name_fallback=c_fallback,
            delta_signs={'+1 (SALT higher)': signs.count(1), '-1 (CD higher)': signs.count(-1), '0': signs.count(0)},
            delta_abs=dict(min=float(min(abs(names[a]['corr_salt'] - names[a]['corr_cd']) for a in Dl)),
                           max=float(max(abs(names[a]['corr_salt'] - names[a]['corr_cd']) for a in Dl))),
            delta_name_not_evaluable=dict(salt=sum(not names[a]['salt_evaluable'] for a in Dl),
                                          cd=sum(not names[a]['cd_evaluable'] for a in Dl)),
            R_same_name=sum(names[a]['salt'] == names[a]['cd'] for a in R),
            R_mean_corr=dict(salt=float(np.mean([names[a]['corr_salt'] for a in R])), cd=float(np.mean([names[a]['corr_cd'] for a in R]))),
            Delta_mean_corr=dict(salt=float(np.mean([names[a]['corr_salt'] for a in Dl])), cd=float(np.mean([names[a]['corr_cd'] for a in Dl]))),
        ))
        LOG['datasets'][key] = L

    # ---------------- images and manifest
    if os.path.isdir(f'{STIM}/img'):
        shutil.rmtree(f'{STIM}/img')
    if os.path.isdir(f'{STIM}/example'):
        shutil.rmtree(f'{STIM}/example')
    os.makedirs(f'{STIM}/img', exist_ok=True); os.makedirs(f'{STIM}/example', exist_ok=True)

    def entry(aid, key, a, b, stratum, csrc, folder):
        D, nm = D_all[key], names_all[key][a]
        rel = f'stimuli/{folder}'
        os.makedirs(f'{SITE}/{rel}', exist_ok=True)
        hi, lo = [], []
        for i, r in enumerate(b['refs_high']):
            save_square(D.path(r), f'{SITE}/{rel}/h{i}.jpg'); hi.append(f'{rel}/h{i}.jpg')
        for i, r in enumerate(b['refs_low']):
            save_square(D.path(r), f'{SITE}/{rel}/l{i}.jpg'); lo.append(f'{rel}/l{i}.jpg')
        save_square(D.path(b['pos']), f'{SITE}/{rel}/qpos.jpg')
        save_square(D.path(b['neg']), f'{SITE}/{rel}/qneg.jpg')
        dataset_id = (lambda r: int(D.image_ids[r])) if key == 'coco' else (lambda r: int(r))
        meta = dict(corr_salt=nm['corr_salt'], corr_cd=nm['corr_cd'],
                    delta_sign=int(np.sign(nm['corr_salt'] - nm['corr_cd'])), category=D.category_name(b['cat']),
                    same_name=nm['salt'] == nm['cd'], c_source=f'{key}_{csrc}', z_pos=b['z_pos'],
                    h_neg=D.h(b['neg'], a), z_neg=D.z(b['neg'], a), pos_rank_ev=b['pos_rank_ev'],
                    n_pos_candidates=b['n_pos_candidates'], nact_ev=int((D.Zev[:, a] > 0).sum()),
                    salt_name_evaluable=nm['salt_evaluable'], cd_name_evaluable=nm['cd_evaluable'],
                    src=dict(refs_high=[dataset_id(r) for r in b['refs_high']], refs_low=[dataset_id(r) for r in b['refs_low']],
                             query_pos=dataset_id(b['pos']), query_neg=dataset_id(b['neg']),
                             id_kind='COCO image id' if key == 'coco' else 'ImageNet val row (= id)'))
        if stratum == 'catch':
            meta['catch_ref_index'] = b['catch_ref_index']
        assert meta['z_neg'] == 0.0
        return dict(dataset=key, stratum=stratum, refs_high=hi, refs_low=lo,
                    query_pos=f'{rel}/qpos.jpg', query_neg=f'{rel}/qneg.jpg',
                    names=dict(A=None, B=nm['salt'], C=names_all[key][csrc]['salt'], D=nm['cd']), meta=meta)

    n = 0
    for aid, (key, a, b, stratum, csrc) in chosen.items():
        if aid == '__example__':
            continue
        manifest['atoms'][aid] = entry(aid, key, a, b, stratum, csrc, f'img/{aid}')
        n += 1
        if n % 20 == 0:
            log('rendered', n, 'atoms')
    manifest['practice'] = [k for k, v in manifest['atoms'].items() if v['stratum'] == 'practice']
    manifest['catch'] = [k for k, v in manifest['atoms'].items() if v['stratum'] == 'catch']
    manifest['lists'] = [dict(list=j, test_atoms=list_sets[j]) for j in range(3)]
    json.dump(manifest, open(f'{STIM}/manifest.json', 'w'), indent=1)

    # example page (imagenet atom outside pool, practice and catch)
    key, a, b, stratum, csrc = chosen['__example__']
    ex = entry(f'{key}_{a}', key, a, b, 'practice', csrc, 'example')
    ex = dict(atom_id=f'{key}_{a}', **ex)
    json.dump(ex, open(f'{STIM}/example/example.json', 'w'), indent=1)
    with open(f'{STIM}/example/README.txt', 'w') as f:
        f.write(f'Images for the illustrated example page of the instructions (stimuli version {VERSION}).\n'
                f'Atom: {key}_{a} (ImageNet SAE atom {a}, outside the test pool, the practice set and the catch set).\n'
                f'SALT name (B): {ex["names"]["B"]} | permuted name (C): {ex["names"]["C"]} | CLIP-Dissect name (D): {ex["names"]["D"]}\n'
                f'Category of the two queries: {ex["meta"]["category"]}\n\n'
                'h0.jpg ... h8.jpg  most activating images (h0 = highest)\n'
                'l0.jpg ... l8.jpg  least activating images (l0 = lowest pre-code)\n'
                'qpos.jpg           query that activates the atom (correct answer)\n'
                'qneg.jpg           query of the same category that does not activate it\n'
                'example.json       same schema as a manifest atom, plus "atom_id"\n\n'
                'Unlike test atoms, the example query_pos is the highest-activating held-out image that has a\n'
                'same-category negative (not a seeded random draw), so that the illustration is clear-cut.\n')

    # contact sheet for the author (not deployed)
    rows_html = []
    for aid, e in list(manifest['atoms'].items()) + [(ex['atom_id'] + ' (example)', ex)]:
        im = lambda p: f'<img src="../site/{p}" width="80">'
        rows_html.append(f'<h3>{aid} [{e["stratum"]}] category: {e["meta"]["category"]}</h3>'
                         f'<p>B (SALT): <b>{e["names"]["B"]}</b> ({e["meta"]["corr_salt"]:+.3f}) | C: {e["names"]["C"]} | '
                         f'D (CD): <b>{e["names"]["D"]}</b> ({e["meta"]["corr_cd"]:+.3f})</p>'
                         f'<div>high: {"".join(im(p) for p in e["refs_high"])}</div>'
                         f'<div>low: {"".join(im(p) for p in e["refs_low"])}</div>'
                         f'<div>pos: {im(e["query_pos"])} neg: {im(e["query_neg"])}</div><hr>')
    open(f'{GEN}/contact_sheet.html', 'w').write('<!doctype html><meta charset="utf-8"><title>Contact sheet</title>'
                                                 '<body style="font-family:sans-serif">' + ''.join(rows_html))

    # sizes
    tot, nfiles = 0, 0
    for dp, _, fs in os.walk(STIM):
        for f in fs:
            tot += os.path.getsize(os.path.join(dp, f)); nfiles += 1
    LOG['output'] = dict(n_pool=sum(v['stratum'] in ('R', 'Delta') for v in manifest['atoms'].values()),
                         n_practice=len(manifest['practice']), n_catch=len(manifest['catch']),
                         list_sizes=[len(l['test_atoms']) for l in manifest['lists']],
                         stimuli_bytes=tot, stimuli_files=nfiles)
    LOG['lists'] = []
    for l in manifest['lists']:
        es = [manifest['atoms'][x] for x in l['test_atoms']]
        LOG['lists'].append(dict(list=l['list'], **{f'{d}_{s}': sum(e['dataset'] == d and e['stratum'] == s for e in es)
                                                     for d in KEYS for s in ('R', 'Delta')},
                                 mean_corr_salt=float(np.mean([e['meta']['corr_salt'] for e in es])),
                                 mean_corr_cd=float(np.mean([e['meta']['corr_cd'] for e in es])),
                                 mean_abs_delta_Delta=float(np.mean([abs(e['meta']['corr_salt'] - e['meta']['corr_cd']) for e in es if e['stratum'] == 'Delta'])),
                                 delta_sign_plus=sum(e['meta']['delta_sign'] == 1 for e in es if e['stratum'] == 'Delta'),
                                 delta_sign_minus=sum(e['meta']['delta_sign'] == -1 for e in es if e['stratum'] == 'Delta')))
    json.dump(LOG, open(f'{GEN}/selection_log.json', 'w'), indent=1)
    log('done', LOG['output'])


if __name__ == '__main__':
    main()

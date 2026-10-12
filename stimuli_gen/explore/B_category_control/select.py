"""Lens B_category_control: Colin's Experiment II (semantic control) done with labels, captions and WordNet.

Rule (no name, no CLIP, no text embedding is used in the selection):
  refs_high : unchanged (9 naming-split images with the highest z_a, h0 = highest).
  refs_low  : one image per high reference h_i, taken among the naming-split images on which the atom AND
              every namesake (same SALT or CLIP-Dissect name, symmetric rule) is silent (z = 0), at the
              closest CATEGORY level to h_i, and within that level the closest to h_i in standardized
              DINOv2 space (cosine), preferring images whose pre-code h_a <= 0.
              Category levels. ImageNet: 0 same wnid, L = 1..4 share a WordNet hypernym within L steps
              (symmetric), 5 no category constraint (nearest silent image, fallback).
              COCO: 0 identical 80-label set, 1 Jaccard >= 0.5, 2 Jaccard > 0, 3 caption-word Jaccard
              (img_to_words) >= WORD_JAC, 5 fallback.
  query_pos / query_neg : among the N_POS_TOP most activating held-out images, each is paired with its best
              silent held-out negative (lowest level, then h_a <= 0, then highest cosine to the positive);
              the pair kept is the one with the lowest level, then with a positive nearest-centroid margin
              (DINOv2, so that the trial is solvable), then the HIGHEST cosine (hardest), ties by z_a.
Names are used ONLY in metric m5.
"""
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != _HERE]   # this file is named select.py: keep the stdlib 'select' reachable
import collections, json, math, re, time
import numpy as np

ROOT = '/lustre/work/pdl16831/udl5a0991/workspace/Supervised_concept_SAE'
HX = f'{ROOT}/human_exp'
GEN = f'{HX}/stimuli_gen'
OUT = f'{GEN}/explore/B_category_control'
WN = '/lustre/work/pdl16831/udl5a0991/nltk_data/corpora/wordnet/data.noun'
sys.path.insert(0, GEN)
from make_stimuli import Data, load_names, N_REF, K  # noqa: E402  (read only; make_stimuli.py is not modified)

N_POS_TOP = 10
MAX_WN_LEVEL = 4
WORD_JAC = 0.10
KNN = 5
SHOW = ["coco_2745", "coco_1210", "coco_3855", "coco_5723", "coco_821", "coco_2234", "imagenet_116", "imagenet_517",
        "imagenet_4351", "imagenet_3283", "imagenet_3022", "imagenet_2825"]
STOP = {'bird', 'whose', 'the', 'has', 'have', 'with', 'than', 'and', 'that', 'its', 'this', 'which', 'about', 'same',
        'from', 'are', 'very', 'all', 'some', 'like', 'their', 'other', 'more', 'less', 'not', 'can', 'see'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def tok(s):
    return [t for t in re.findall(r'[a-z]+', str(s).lower()) if len(t) >= 3 and t not in STOP]


def variants(t):
    v = {t}
    if len(t) >= 4 and t.endswith('s'): v.add(t[:-1])
    if len(t) >= 5 and t.endswith('es'): v.add(t[:-2])
    if len(t) >= 5 and t.endswith('ies'): v.add(t[:-3] + 'y')
    return v


def expand(tokens):
    out = set()
    for t in tokens:
        out |= variants(t)
    return out


# ---------------------------------------------------------------- WordNet (raw data.noun, no nltk)
def wordnet_hypernyms():
    """offset -> list of hypernym offsets ('@' and '@i' pointers) of WordNet 3.0 nouns."""
    hyp = {}
    for line in open(WN, encoding='utf-8', errors='replace'):
        if line.startswith(' '):
            continue
        head = line.split('|', 1)[0].split()
        off = head[0]
        wcnt = int(head[3], 16)
        i = 4 + 2 * wcnt
        pcnt = int(head[i]); i += 1
        hs = []
        for _ in range(pcnt):
            sym, tgt, pos, _st = head[i:i + 4]; i += 4
            if sym in ('@', '@i') and pos == 'n':
                hs.append(tgt)
        hyp[off] = hs
    return hyp


def ancestors_within(hyp, off, L):
    """Set of offsets reachable by at most L hypernym steps (includes off itself)."""
    seen, frontier = {off}, {off}
    for _ in range(L):
        nxt = set()
        for o in frontier:
            nxt |= set(hyp.get(o, []))
        nxt -= seen
        seen |= nxt
        frontier = nxt
    return seen


# ---------------------------------------------------------------- context
class Ctx:
    def __init__(self, key):
        self.key = key
        D = Data(key); self.D = D
        names = load_names(key); self.names = names
        D.set_namesakes(names)
        self.N = D.N
        X = (np.asarray(D.A, np.float32) - D.sc_mean) / D.sc_scale      # standardized DINOv2 space
        self.X = X
        self.Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-8)
        self.tr = np.sort(D.tr); self.ev = np.sort(D.ev)
        self.ev_pos = {int(r): i for i, r in enumerate(D.ev.tolist())}      # row -> index in D.Zev
        self.zmax_ev = D.Zev.max(0)
        self.caps = json.load(open(f'{D.CD}/caps_by_img.json'))
        if key == 'imagenet':
            self.wnid = D.wnid
            ws = sorted(set(self.wnid.tolist())); self.widx = {w: i for i, w in enumerate(ws)}
            self.wi = np.array([self.widx[w] for w in self.wnid])
            hyp = wordnet_hypernyms()
            anc = [[ancestors_within(hyp, w[1:], L) for L in range(MAX_WN_LEVEL + 1)] for w in ws]
            nW = len(ws)
            lvl = np.full((nW, nW), MAX_WN_LEVEL + 1, np.int8)
            for L in range(MAX_WN_LEVEL, -1, -1):
                by = collections.defaultdict(set)
                for i in range(nW):
                    for o in anc[i][L]:
                        by[o].add(i)
                for i in range(nW):
                    for o in anc[i][L]:
                        for j in by[o]:
                            lvl[i, j] = L
            self.lvl = lvl
            self.cls_name = D.cls_name
            self.i2c = json.load(open(f'{D.CD}/img_to_cats.json'))
            self.text_tok = lambda r: expand(tok(' '.join(self.caps.get(str(int(r)), [])) + ' ' + ' '.join(self.i2c[str(int(r))])))
        else:
            self.labels = D.labels
            self.label_names = D.label_names
            i2w = json.load(open(f'{D.CD}/img_to_words.json'))
            self.words = [set(i2w.get(str(int(cid)), [])) for cid in D.image_ids]
            self.cid = {int(c): r for r, c in enumerate(D.image_ids.tolist())}
            self.text_tok = lambda r: expand(tok(' '.join(self.caps.get(str(int(D.image_ids[int(r)])), [])) + ' '
                                                + ' '.join(self.label_names[i] for i in np.where(self.labels[int(r)])[0])))

    def dataset_id(self, r):
        return int(self.D.image_ids[int(r)]) if self.key == 'coco' else int(r)

    def row_of_id(self, i):
        return self.cid[int(i)] if self.key == 'coco' else int(i)

    def z_of(self, r, a):
        return self.D.z(r, a)

    def h_rows(self, rows, a):
        return self.X[rows] @ self.D.We[a] + self.D.be[a]

    def silent_mask(self, rows, grp):
        return ~np.isin(self.D.z_idx[rows], grp).any(1)

    def levels(self, ref, cands):
        """Category level (0 = same category ... 5 = none) of each candidate row w.r.t. the reference row."""
        if self.key == 'imagenet':
            return self.lvl[self.wi[ref], self.wi[cands]].astype(np.int8)
        P = self.labels[ref]; L = self.labels[cands]
        out = np.full(len(cands), MAX_WN_LEVEL + 1, np.int8)
        if P.any():
            inter = (L & P).sum(1); union = (L | P).sum(1)
            jac = inter / np.maximum(union, 1)
            out[jac > 0] = 2; out[jac >= 0.5] = 1; out[jac >= 1.0] = 0
        W = self.words[ref]
        if W:
            for k, c in enumerate(cands):
                if out[k] <= 2:
                    continue
                Wc = self.words[int(c)]
                if Wc:
                    j = len(W & Wc) / len(W | Wc)
                    if j >= WORD_JAC:
                        out[k] = 3
        return out

    def category_name(self, r):
        if self.key == 'imagenet':
            return self.cls_name[self.wnid[int(r)]]
        return ', '.join(sorted(self.label_names[i] for i in np.where(self.labels[int(r)])[0])) or '(no label)'

    def same_cat(self, r1, r2):
        if self.key == 'imagenet':
            return self.wnid[int(r1)] == self.wnid[int(r2)]
        return (self.labels[int(r1)] == self.labels[int(r2)]).all() and self.labels[int(r1)].any()

    def loose_cat(self, r1, r2):
        if self.key == 'imagenet':
            return self.wnid[int(r1)] == self.wnid[int(r2)]
        return (self.labels[int(r1)] & self.labels[int(r2)]).any()


def pick(ctx, ref, cands, a, used, prefer_margin=None):
    """Best candidate for a reference row: lowest level, then h_a <= 0, then (optionally) positive margin, then max cos.
    Returns (row, level, cos, h) or None."""
    cands = np.asarray([c for c in cands if c not in used], np.int64)
    if len(cands) == 0:
        return None
    lv = ctx.levels(ref, cands)
    best = int(lv.min())
    sel = cands[lv == best]
    h = ctx.h_rows(sel, a)
    cos = ctx.Xn[sel] @ ctx.Xn[ref]
    good = h <= 0
    if good.any():
        sel, h, cos = sel[good], h[good], cos[good]
    if prefer_margin is not None:
        mg = np.array([prefer_margin(int(c)) for c in sel])
        if (mg > 0).any():
            sel, h, cos, mg = sel[mg > 0], h[mg > 0], cos[mg > 0], mg[mg > 0]
    j = int(np.argmax(cos))
    return int(sel[j]), best, float(cos[j]), float(h[j])


CAT_OK = {'imagenet': 0, 'coco': 1}      # pair accepted as "category-matched": same wnid / label Jaccard >= 0.5


def select_trial(ctx, a, rng=None, policy='rank'):
    """-> dict(refs_high, refs_low, query_pos, query_neg as dataset ids, rows, levels, metrics) or None.
    policy 'rank'  : category-matched pair (level <= CAT_OK) with the MOST activating positive, then by level, then rank.
    policy 'maxcos': lowest level, then positive margin, then the hardest pair (highest cos) -- rejected, see REPORT.md."""
    D = ctx.D
    top, topv = D.top_tr[a], D.top_tr_val[a]
    if (topv[:N_REF] <= 0).any():
        return None
    refs_high = [int(r) for r in top[:N_REF]]
    grp = np.asarray(D.namesakes.get(a, [a]))
    # references low: silent naming-split rows, one per high reference
    tr_sil = ctx.tr[ctx.silent_mask(ctx.tr, grp)]
    refs_low, low_lv, low_cos, low_h = [], [], [], []
    used = set(refs_high)
    for hr in refs_high:
        p = pick(ctx, hr, tr_sil, a, used)
        if p is None:
            return None
        r, lv, c, h = p
        refs_low.append(r); low_lv.append(lv); low_cos.append(c); low_h.append(h); used.add(r)
    # queries
    zcol = D.Zev[:, a]
    order = np.argsort(-zcol, kind='stable')
    pos_cands = [int(D.ev[i]) for i in order[:N_POS_TOP] if zcol[i] > 0]
    ev_sil = ctx.ev[ctx.silent_mask(ctx.ev, grp)]
    ch = ctx.Xn[refs_high].mean(0); cl = ctx.Xn[refs_low].mean(0)
    ch /= np.linalg.norm(ch); cl /= np.linalg.norm(cl)
    score = lambda r: float(ctx.Xn[r] @ ch - ctx.Xn[r] @ cl)
    pairs = []
    for rank, pr in enumerate(pos_cands):
        sp = score(pr)
        p = pick(ctx, pr, ev_sil, a, {pr}, prefer_margin=lambda c: sp - score(c))
        if p is None:
            continue
        nr, lv, c, h = p
        pairs.append(dict(pos=pr, neg=nr, level=lv, cos=c, h_neg=h, margin=sp - score(nr), rank=rank + 1,
                          z_pos=float(zcol[ctx.ev_pos[pr]])))
    if not pairs:
        return None
    if policy == 'maxcos':
        pairs.sort(key=lambda p: (p['level'], 0 if p['margin'] > 0 else 1, -p['cos'], p['rank']))
    else:
        pairs.sort(key=lambda p: (0 if p['level'] <= CAT_OK[ctx.key] else 1, p['rank'], p['level']))
    q = pairs[0]
    return dict(rows=dict(refs_high=refs_high, refs_low=refs_low, query_pos=q['pos'], query_neg=q['neg']),
                refs_high=[ctx.dataset_id(r) for r in refs_high], refs_low=[ctx.dataset_id(r) for r in refs_low],
                query_pos=ctx.dataset_id(q['pos']), query_neg=ctx.dataset_id(q['neg']),
                low_levels=low_lv, low_cos=low_cos, low_h=low_h, pair_level=q['level'], pair_cos=q['cos'],
                pos_rank_ev=q['rank'], n_pairs=len(pairs), n_tr_silent=int(len(tr_sil)), n_ev_silent=int(len(ev_sil)))


# ---------------------------------------------------------------- metrics (common definitions)
def name_hit(ctx, r, name):
    T = expand(tok(name))
    return bool(T & ctx.text_tok(r)) if T else False


def metrics(ctx, a, rows, nm):
    D = ctx.D
    H, Lo, p, n = rows['refs_high'], rows['refs_low'], rows['query_pos'], rows['query_neg']
    ch = ctx.Xn[H].mean(0); cl = ctx.Xn[Lo].mean(0)
    ch /= np.linalg.norm(ch); cl /= np.linalg.norm(cl)
    s = lambda r: float(ctx.Xn[r] @ ch - ctx.Xn[r] @ cl)
    refs = np.asarray(H + Lo); is_hi = np.r_[np.ones(len(H)), np.zeros(len(Lo))]
    def knn(r):
        c = ctx.Xn[refs] @ ctx.Xn[r]
        return float(is_hi[np.argsort(-c)[:KNN]].mean())
    grp = D.namesakes.get(a, [a])
    zp, zn = D.z(p, a), D.z(n, a)
    sup_p, sup_n = set(D.z_idx[p].tolist()), set(D.z_idx[n].tolist())
    same = [any(ctx.same_cat(l, h) for h in H) for l in Lo]
    loose = [any(ctx.loose_cat(l, h) for h in H) for l in Lo]
    m = dict(
        m1_margin_centroid=s(p) - s(n), m1_s_pos=s(p), m1_s_neg=s(n), m1_margin_knn=knn(p) - knn(n),
        m1_sign_positive=int(s(p) - s(n) > 0),
        m2_z_pos_rel=zp / float(ctx.zmax_ev[a]) if ctx.zmax_ev[a] > 0 else 0.0, m2_z_pos=zp, m2_z_neg=zn,
        m2_z_neg_zero=int(zn == 0.0), m2_namesakes_silent=int(all(D.z(n, b) == 0.0 for b in grp)),
        m2_h_neg=float(D.h(n, a)), m2_n_namesakes=len(grp),
        m3_jaccard_support=len(sup_p & sup_n) / len(sup_p | sup_n),
        m3_cos_pos_neg=float(ctx.Xn[p] @ ctx.Xn[n]),
        m4_cos_centroids=float(ch @ cl),
        m4_mean_pairwise_cos_low_high=float((ctx.Xn[Lo] @ ctx.Xn[H].T).mean()),
        m4_same_cat_frac_strict=float(np.mean(same)), m4_same_cat_frac_loose=float(np.mean(loose)),
        m4_low_z_high_frac=float(np.mean([any(D.z(l, b) > 0 for b in grp) for l in Lo])),
        m5_salt=int(name_hit(ctx, p, nm['salt']) and not name_hit(ctx, n, nm['salt'])),
        m5_cd=int(name_hit(ctx, p, nm['cd']) and not name_hit(ctx, n, nm['cd'])),
        m5_salt_pos=int(name_hit(ctx, p, nm['salt'])), m5_salt_neg=int(name_hit(ctx, n, nm['salt'])),
        m5_cd_pos=int(name_hit(ctx, p, nm['cd'])), m5_cd_neg=int(name_hit(ctx, n, nm['cd'])),
        cat_pos=ctx.category_name(p), cat_neg=ctx.category_name(n),
        same_cat_pair_strict=int(ctx.same_cat(p, n)), same_cat_pair_loose=int(ctx.loose_cat(p, n)),
    )
    return m


MED_KEYS = ['m1_margin_centroid', 'm1_margin_knn', 'm1_sign_positive', 'm2_z_pos_rel', 'm2_z_neg_zero', 'm2_namesakes_silent',
            'm3_jaccard_support', 'm3_cos_pos_neg', 'm4_cos_centroids', 'm4_mean_pairwise_cos_low_high', 'm4_same_cat_frac_strict',
            'm4_same_cat_frac_loose', 'm5_salt', 'm5_cd', 'same_cat_pair_strict', 'same_cat_pair_loose']


def summarize(per):
    out = {}
    for k in MED_KEYS:
        v = np.array([x[k] for x in per.values()], float)
        out[k] = dict(median=float(np.median(v)), mean=float(v.mean()), frac_positive=float((v > 0).mean()), n=int(len(v)))
    return out


# ---------------------------------------------------------------- outputs
def contact_sheet(ctx_all, man, mine, path):
    rel = lambda p: os.path.relpath(p, OUT)
    im = lambda p: f'<img src="{rel(p)}" width="110" title="{os.path.basename(p)}">'
    H = ['<!doctype html><meta charset="utf-8"><title>B_category_control contact sheet</title>',
         '<body style="font-family:sans-serif;font-size:13px"><h2>B_category_control: new rule (top) vs current manifest (bottom) for 12 atoms</h2>',
         '<p>Low row: l_i is the category-matched silent image paired with h_i (level: 0 same category, 1-4 WordNet / Jaccard tiers, 3 caption words (COCO), 5 no category).</p>']
    for aid in SHOW:
        key, a = aid.split('_'); a = int(a); ctx = ctx_all[key]; e = man['atoms'][aid]
        nm = ctx.names[a]
        for tag, R, M in (('NEW', mine[aid]['rows'], mine[aid]['metrics']), ('CURRENT manifest', mine[aid]['baseline_rows'], mine[aid]['baseline_metrics'])):
            H.append(f'<h3>{aid} [{tag}] SALT: <b>{nm["salt"]}</b> | CD: <b>{nm["cd"]}</b> | namesakes {M["m2_n_namesakes"]}</h3>')
            if tag == 'NEW':
                H.append('<p>low levels: ' + ' '.join(map(str, mine[aid]['low_levels'])) + f' | pair level {mine[aid]["pair_level"]} | pos rank {mine[aid]["pos_rank_ev"]}</p>')
            H.append(f'<p>m1 margin {M["m1_margin_centroid"]:+.3f} (kNN {M["m1_margin_knn"]:+.2f}) | m2 z_rel {M["m2_z_pos_rel"]:.2f} h_neg {M["m2_h_neg"]:+.2f} | '
                     f'm3 jacc {M["m3_jaccard_support"]:.2f} cos(pos,neg) {M["m3_cos_pos_neg"]:.2f} | m4 cos rows {M["m4_cos_centroids"]:.2f} same-cat {M["m4_same_cat_frac_strict"]:.2f}/{M["m4_same_cat_frac_loose"]:.2f} | '
                     f'm5 SALT {M["m5_salt"]} CD {M["m5_cd"]} | cat pos: {M["cat_pos"]} / neg: {M["cat_neg"]}</p>')
            H.append('<div>high: ' + ''.join(im(ctx.D.path(r)) for r in R['refs_high']) + '</div>')
            H.append('<div>low:&nbsp; ' + ''.join(im(ctx.D.path(r)) for r in R['refs_low']) + '</div>')
            H.append('<div>pos: ' + im(ctx.D.path(R['query_pos'])) + ' &nbsp; neg: ' + im(ctx.D.path(R['query_neg'])) + '</div>')
        H.append('<hr>')
    open(path, 'w').write('\n'.join(H))


def montage(ctx_all, mine, path, size=224):
    from PIL import Image, ImageDraw, ImageFont
    try:
        import matplotlib
        font = ImageFont.truetype(os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data/fonts/ttf/DejaVuSans.ttf'), 16)
        fontb = ImageFont.truetype(os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data/fonts/ttf/DejaVuSans-Bold.ttf'), 20)
    except Exception:
        font = fontb = ImageFont.load_default()
    def thumb(p):
        with Image.open(p) as im:
            im = im.convert('RGB'); w, h = im.size; s = size / min(w, h)
            im = im.resize((max(size, round(w * s)), max(size, round(h * s))), Image.BICUBIC)
            l, t = (im.size[0] - size) // 2, (im.size[1] - size) // 2
            return im.crop((l, t, l + size, t + size))
    gap, head = 4, 60
    W = 9 * (size + gap) + gap
    blockH = head + 3 * (size + gap) + gap
    canvas = Image.new('RGB', (W, blockH * len(SHOW)), 'white')
    d = ImageDraw.Draw(canvas)
    for bi, aid in enumerate(SHOW):
        key, a = aid.split('_'); a = int(a); ctx = ctx_all[key]; nm = ctx.names[a]; R = mine[aid]['rows']; M = mine[aid]['metrics']
        y0 = bi * blockH
        d.text((gap, y0 + 4), f'{aid}   SALT: {nm["salt"]}   CD: {nm["cd"]}   (NEW rule)', fill='black', font=fontb)
        d.text((gap, y0 + 32), f'm1 {M["m1_margin_centroid"]:+.3f}  kNN {M["m1_margin_knn"]:+.2f} | z_rel {M["m2_z_pos_rel"]:.2f} | jacc {M["m3_jaccard_support"]:.2f} cos(p,n) {M["m3_cos_pos_neg"]:.2f} | '
                f'rows cos {M["m4_cos_centroids"]:.2f} same-cat {M["m4_same_cat_frac_strict"]:.2f} | low levels {"".join(map(str, mine[aid]["low_levels"]))} pair lvl {mine[aid]["pair_level"]}',
               fill='black', font=font)
        for row, (lab, rows) in enumerate((('H', R['refs_high']), ('L', R['refs_low']))):
            y = y0 + head + row * (size + gap)
            for i, r in enumerate(rows):
                x = gap + i * (size + gap)
                canvas.paste(thumb(ctx.D.path(r)), (x, y))
                d.rectangle([x, y, x + 34, y + 20], fill='white'); d.text((x + 3, y + 1), f'{lab}{i}', fill='black', font=font)
        y = y0 + head + 2 * (size + gap)
        for i, (lab, r, col) in enumerate((('POS', R['query_pos'], 'green'), ('NEG', R['query_neg'], 'red'))):
            x = gap + i * (size + gap)
            canvas.paste(thumb(ctx.D.path(r)), (x, y))
            d.rectangle([x, y, x + size - 1, y + size - 1], outline=col, width=4)
            d.rectangle([x, y, x + 46, y + 20], fill='white'); d.text((x + 3, y + 1), lab, fill=col, font=font)
        d.text((gap + 2 * (size + gap) + 8, y + 4), f'pos: {M["cat_pos"][:60]}\nneg: {M["cat_neg"][:60]}\nh_a(neg) {M["m2_h_neg"]:+.2f}  z(neg) {M["m2_z_neg"]:.0f}',
               fill='black', font=font)
    canvas.save(path, 'PNG', optimize=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    man = json.load(open(f'{HX}/site/stimuli/manifest.json'))
    pool = [k for k, v in man['atoms'].items() if v['stratum'] in ('R', 'Delta')]
    assert len(pool) == 120
    ctx_all = {k: Ctx(k) for k in ('coco', 'imagenet')}
    log('contexts loaded')
    mine, per_new, per_base, unserved = {}, {}, {}, []
    for aid in pool:
        key, a = aid.split('_'); a = int(a); ctx = ctx_all[key]; e = man['atoms'][aid]; nm = ctx.names[a]
        src = e['meta']['src']
        brows = dict(refs_high=[ctx.row_of_id(i) for i in src['refs_high']], refs_low=[ctx.row_of_id(i) for i in src['refs_low']],
                     query_pos=ctx.row_of_id(src['query_pos']), query_neg=ctx.row_of_id(src['query_neg']))
        assert all(ctx.D.z(r, a) > 0 for r in brows['refs_high']) and ctx.D.z(brows['query_neg'], a) == 0
        t = select_trial(ctx, a)
        t2 = select_trial(ctx, a, policy='maxcos')
        if t is None:
            unserved.append(aid)
            continue
        t['metrics'] = metrics(ctx, a, t['rows'], nm)
        t['baseline_rows'] = brows; t['baseline_metrics'] = metrics(ctx, a, brows, nm)
        t['names'] = dict(salt=nm['salt'], cd=nm['cd']); t['stratum'] = e['stratum']; t['dataset'] = key
        t['maxcos_variant'] = dict(rows=t2['rows'], metrics=metrics(ctx, a, t2['rows'], nm), pos_rank_ev=t2['pos_rank_ev'], pair_level=t2['pair_level'])
        mine[aid] = t; per_new[aid] = t['metrics']; per_base[aid] = t['baseline_metrics']
    log('selected', len(mine), 'unserved', unserved)
    lv_low = collections.Counter(l for t in mine.values() for l in t['low_levels'])
    lv_pair = collections.Counter(t['pair_level'] for t in mine.values())
    by_ds = {}
    for ds in ('coco', 'imagenet'):
        ids = [k for k in mine if mine[k]['dataset'] == ds]
        by_ds[ds] = dict(n=len(ids), low_levels=dict(collections.Counter(l for k in ids for l in mine[k]['low_levels'])),
                         pair_levels=dict(collections.Counter(mine[k]['pair_level'] for k in ids)),
                         new=summarize({k: per_new[k] for k in ids}), baseline=summarize({k: per_base[k] for k in ids}))
    out = dict(rule=__doc__, n_pool=len(pool), n_served=len(mine), unserved=unserved,
               low_level_counts=dict(lv_low), pair_level_counts=dict(lv_pair),
               summary_new=summarize(per_new), summary_baseline=summarize(per_base), by_dataset=by_ds,
               summary_maxcos_variant_rejected=summarize({k: v['maxcos_variant']['metrics'] for k, v in mine.items()}),
               atoms={k: {kk: vv for kk, vv in v.items() if kk != 'rows' and kk != 'baseline_rows'} | dict(rows=v['rows'], baseline_rows=v['baseline_rows']) for k, v in mine.items()})
    json.dump(out, open(f'{OUT}/metrics.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    contact_sheet(ctx_all, man, mine, f'{OUT}/contact_sheet.html')
    montage(ctx_all, mine, f'{OUT}/montage.png')
    print('\nmetric                          new_median  base_median  maxcos_median')
    for k in MED_KEYS:
        print(f'{k:32s} {out["summary_new"][k]["median"]:10.3f} {out["summary_baseline"][k]["median"]:12.3f} {out["summary_maxcos_variant_rejected"][k]["median"]:12.3f}')
    print('low levels', dict(lv_low), 'pair levels', dict(lv_pair))
    log('done')


if __name__ == '__main__':
    main()

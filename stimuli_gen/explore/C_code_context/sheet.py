"""Contact sheet (HTML, relative links to the real image files) and PNG montage (PIL) for the 12 sheet atoms."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

EXP = os.path.dirname(os.path.abspath(__file__))
SHEET_ATOMS = ["coco_2745", "coco_1210", "coco_3855", "coco_5723", "coco_821", "coco_2234",
               "imagenet_116", "imagenet_517", "imagenet_4351", "imagenet_3283", "imagenet_3022", "imagenet_2825"]
T = 224


def thumb(path, size=T):
    with Image.open(path) as im:
        im = im.convert('RGB'); w, h = im.size; s = size / min(w, h)
        im = im.resize((max(size, round(w * s)), max(size, round(h * s))), Image.BICUBIC)
        l, t = (im.width - size) // 2, (im.height - size) // 2
        return im.crop((l, t, l + size, t + size))


def font(sz):
    for p in ('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def fmt(e):
    return (f"m1 centroid {e['m1_margin_centroid']:+.3f} knn {e['m1_margin_knn']:+.2f} | m2 z_pos/max {e['m2_zpos_rel']:.2f} "
            f"| m3 jac {e['m3_jaccard']:.2f} | m4 row cos {e['m4_row_cos']:.2f} same-cat {e['m4_same_cat_frac']:.2f} "
            f"| m5 salt {e['m5_salt']} cd {e['m5_cd']} | pair dino cos {e['pair_dino_cos']:.2f} code cos {e['pair_code_cos_minus_a']:.2f}")


def build(out, manifest, atoms=SHEET_ATOMS, size=T, png='montage.png', html='contact_sheet.html'):
    rel = lambda p: os.path.relpath(p, EXP)
    blocks = []
    F, Fs = font(18), font(14)
    tiles = []
    for aid in atoms:
        e = out['atoms'].get(aid)
        if e is None:
            blocks.append(f'<h3>{aid}</h3><p>not served</p><hr>'); continue
        b = out['baseline'][aid]
        im = lambda p: f'<img src="{rel(p)}" width="112" title="{os.path.basename(p)}">'
        blocks.append(
            f'<h3>{aid} &mdash; SALT (B): <b>{e["names"]["B"]}</b> | CLIP-Dissect (D): <b>{e["names"]["D"]}</b></h3>'
            f'<p>pos category: {e["category_pos"]} | neg category: {e["category_neg"]} | tier {e["tier"]} | pos rank {e["pos_rank"]} | z_pos {e["z_pos"]:.2f}</p>'
            f'<p>ours: {fmt(e)}</p><p>baseline: {fmt(b)}</p>'
            f'<div>high: {"".join(im(p) for p in e["paths"]["refs_high"])}</div>'
            f'<div>low: {"".join(im(p) for p in e["paths"]["refs_low"])}</div>'
            f'<div>pos: {im(e["paths"]["query_pos"])} &nbsp; neg: {im(e["paths"]["query_neg"])}</div><hr>')
        # montage block: 3 rows of tiles (high, low, pair) + a text band
        W = 9 * size; H = 3 * size + 70
        blk = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(blk)
        d.text((4, 2), f"{aid}  SALT: {e['names']['B']}  |  CD: {e['names']['D']}  |  pos cat: {e['category_pos'][:40]}  |  tier {e['tier']}", fill='black', font=F)
        d.text((4, 26), 'ours ' + fmt(e), fill='black', font=Fs)
        d.text((4, 44), 'base ' + fmt(b), fill='gray', font=Fs)
        for row, key in enumerate(('refs_high', 'refs_low')):
            for i, p in enumerate(e['paths'][key]):
                blk.paste(thumb(p, size), (i * size, 70 + row * size))
            d.text((4, 70 + row * size + 4), 'HIGH' if row == 0 else 'LOW', fill='yellow', font=F, stroke_width=2, stroke_fill='black')
        blk.paste(thumb(e['paths']['query_pos'], size), (0, 70 + 2 * size))
        blk.paste(thumb(e['paths']['query_neg'], size), (size + 10, 70 + 2 * size))
        d.text((4, 70 + 2 * size + 4), 'POS', fill='lime', font=F, stroke_width=2, stroke_fill='black')
        d.text((size + 14, 70 + 2 * size + 4), 'NEG', fill='red', font=F, stroke_width=2, stroke_fill='black')
        tiles.append(blk)
    open(f'{EXP}/{html}', 'w').write('<!doctype html><meta charset="utf-8"><title>C_code_context contact sheet</title>'
                                      '<body style="font-family:sans-serif">' + ''.join(blocks))
    if tiles:
        W = tiles[0].width; H = sum(t.height + 8 for t in tiles)
        mont = Image.new('RGB', (W, H), 'black'); y = 0
        for t in tiles:
            mont.paste(t, (0, y)); y += t.height + 8
        mont.save(f'{EXP}/{png}')

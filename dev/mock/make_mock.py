#!/usr/bin/env python3
"""Build a local test tree for the experiment page (dev only, never deployed).

Creates HX/dev/mock/serve/ with:
  index.html, css/, js/config.js, js/experiment.js  -> symlinks to HX/site/
  js/texts.js       -> HX/site/js/texts.js if it exists, else dev/mock/texts.js
                       (--mock-texts forces the mock)
  stimuli_mock/     -> mock manifest.json, example/, img/<atom_id>/*.jpg
  stimuli/example/  -> copy of the mock example (texts may reference it)
If HX/site/stimuli/manifest.json exists, serve/stimuli is a symlink to the real
folder instead, so ?debug=1 without ?stim also runs on real stimuli.

Run:  python3 dev/mock/make_mock.py
      cd dev/mock/serve && python3 -m http.server 8000
      open http://localhost:8000/?debug=1&stim=stimuli_mock&cond=B&list=1
"""
import argparse
import json
import os
import random
import shutil

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HX = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.join(HX, "site")
SERVE = os.path.join(HERE, "serve")
STIM = "stimuli_mock"
FONT = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


F_BIG, F_SMALL = font(30), font(20)


def make_img(path, hue, label, sub):
    """224x224 RGB JPEG: coloured square with a large label."""
    img = Image.new("RGB", (224, 224), hue)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 223, 223], outline=(40, 40, 40), width=2)
    d.text((112, 95), label, fill=(20, 20, 20), font=F_BIG, anchor="mm")
    d.text((112, 140), sub, fill=(20, 20, 20), font=F_SMALL, anchor="mm")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=80)


def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def build_atom(root, prefix, atom_id, dataset, stratum, rng, catch_k=None):
    """Write the 20 images of one atom and return its manifest entry."""
    hue = tuple(rng.randint(90, 230) for _ in range(3))
    other = tuple(255 - c // 2 for c in hue)
    d = os.path.join(root, atom_id)
    rel = lambda name: "%s/%s.jpg" % (prefix, name)
    short = atom_id.replace("imagenet", "imnet")
    for i in range(9):
        make_img(os.path.join(d, "h%d.jpg" % i), shade(hue, 1.0 + 0.02 * (8 - i)), short, "h%d high" % i)
        make_img(os.path.join(d, "l%d.jpg" % i), shade(other, 0.75), short, "l%d low" % i)
    if catch_k is None:
        make_img(os.path.join(d, "qpos.jpg"), hue, short, "qpos")
    else:
        shutil.copyfile(os.path.join(d, "h%d.jpg" % catch_k), os.path.join(d, "qpos.jpg"))
    make_img(os.path.join(d, "qneg.jpg"), shade(other, 0.75), short, "qneg")
    meta = {"corr_salt": round(rng.uniform(0, 0.5), 4), "corr_cd": round(rng.uniform(0, 0.5), 4),
            "category": "mockcat%d" % rng.randint(0, 9)}
    meta["delta_sign"] = (meta["corr_salt"] > meta["corr_cd"]) - (meta["corr_salt"] < meta["corr_cd"])
    if catch_k is not None:
        meta["catch_ref_index"] = catch_k
    return {
        "dataset": dataset, "stratum": stratum,
        "refs_high": [rel("h%d" % i) for i in range(9)],
        "refs_low": [rel("l%d" % i) for i in range(9)],
        "query_pos": rel("qpos"), "query_neg": rel("qneg"),
        "names": {"A": None, "B": "salt_%s" % short, "C": None, "D": "cd %s" % short},
        "meta": meta,
    }


def derange(atoms, ids, rng):
    """C name = SALT name of another atom in the same group (cyclic shift)."""
    order = ids[:]
    rng.shuffle(order)
    for i, a in enumerate(order):
        src = order[(i + 1) % len(order)]
        atoms[a]["names"]["C"] = atoms[src]["names"]["B"]
        atoms[a]["meta"]["c_source"] = src


def link(src, dst):
    if os.path.lexists(dst):
        os.remove(dst)
    os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock-texts", action="store_true", help="use dev/mock/texts.js even if site/js/texts.js exists")
    args = ap.parse_args()
    rng = random.Random(12345)

    if os.path.isdir(SERVE):
        shutil.rmtree(SERVE)
    os.makedirs(os.path.join(SERVE, "js"))
    link(os.path.join(SITE, "index.html"), os.path.join(SERVE, "index.html"))
    link(os.path.join(SITE, "css"), os.path.join(SERVE, "css"))
    for f in ("config.js", "experiment.js"):
        link(os.path.join(SITE, "js", f), os.path.join(SERVE, "js", f))
    real_texts = os.path.join(SITE, "js", "texts.js")
    use_real = os.path.isfile(real_texts) and not args.mock_texts
    link(real_texts if use_real else os.path.join(HERE, "texts.js"), os.path.join(SERVE, "js", "texts.js"))

    stim = os.path.join(SERVE, STIM)
    img_root = os.path.join(stim, "img")
    atoms, n = {}, [1000]

    def new(dataset, stratum, catch_k=None):
        n[0] += 1
        aid = "%s_%d" % (dataset, n[0])
        atoms[aid] = build_atom(img_root, "%s/img/%s" % (STIM, aid), aid, dataset, stratum, rng, catch_k)
        return aid

    lists = [[] for _ in range(3)]
    pool = []
    for ds in ("coco", "imagenet"):
        for stratum in ("R", "Delta"):
            for j in range(3):
                ids = [new(ds, stratum) for _ in range(10)]
                lists[j] += ids
                pool += ids
    practice = [new("coco", "practice") for _ in range(5)] + [new("imagenet", "practice") for _ in range(4)]
    catch = [new("coco", "catch", rng.randrange(9)) for _ in range(3)] + \
            [new("imagenet", "catch", rng.randrange(9)) for _ in range(2)]
    for ds in ("coco", "imagenet"):
        for group in (pool, practice, catch):
            derange(atoms, [a for a in group if atoms[a]["dataset"] == ds], rng)
    for a in atoms.values():
        a["meta"]["same_name"] = a["names"]["B"] == a["names"]["D"]

    manifest = {
        "version": "mock-1",
        "lists": [{"list": j, "test_atoms": lists[j]} for j in range(3)],
        "atoms": atoms, "practice": practice, "catch": catch,
    }
    with open(os.path.join(stim, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    # Example atom, written for both ?stim=stimuli_mock and plain stimuli/.
    for folder in (STIM, "stimuli"):
        ex_dir = os.path.join(SERVE, folder, "example")
        os.makedirs(ex_dir, exist_ok=True)
    tmp = os.path.join(SERVE, "_ex")
    ex = build_atom(tmp, "X", "imagenet_9999", "imagenet", "practice", rng)
    ex["names"]["C"] = "salt_imnet_8888"
    ex["meta"]["c_source"] = "imagenet_8888"
    for folder in (STIM, "stimuli"):
        ex_dir = os.path.join(SERVE, folder, "example")
        for fn in os.listdir(os.path.join(tmp, "imagenet_9999")):
            shutil.copyfile(os.path.join(tmp, "imagenet_9999", fn), os.path.join(ex_dir, fn))
        e = json.loads(json.dumps(ex).replace('"X/', '"%s/example/' % folder))
        e["atom_id"] = "imagenet_9999"
        with open(os.path.join(ex_dir, "example.json"), "w") as f:
            json.dump(e, f, indent=1)
    shutil.rmtree(tmp)

    real_stim = os.path.join(SITE, "stimuli")
    if os.path.isfile(os.path.join(real_stim, "manifest.json")):
        shutil.rmtree(os.path.join(SERVE, "stimuli"))
        link(real_stim, os.path.join(SERVE, "stimuli"))

    print("serve tree:", SERVE)
    print("texts.js:", "site/js/texts.js" if use_real else "dev/mock/texts.js (MOCK)")
    print("atoms: %d pool, %d practice, %d catch" % (len(pool), len(practice), len(catch)))
    print("run: cd %s && python3 -m http.server 8000" % SERVE)
    print("open: http://localhost:8000/?debug=1&stim=%s&cond=B&list=1" % STIM)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Static cross-check of the page code against the shared contract (SPEC.md 5.1-5.5).

Checks:
  1. every EXP_TEXTS key used by experiment.js (tx("...")) is in the contract and in texts.js;
  2. every manifest field read by experiment.js is a contract field, and exists in the manifest(s);
  3. index.html loads exactly the pinned scripts of SPEC Part 4, in order;
  4. config.js is the SPEC 5.4 block verbatim;
  5. every CSS class emitted by experiment.js is styled in style.css.

texts.js is evaluated with node when available (--node PATH or `node` on PATH);
otherwise its keys are checked with a regex (weaker).

Usage: python3 dev/mock/check_contract.py [--node /path/to/node] [--manifest PATH ...]
Exit code 1 on any error.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HX = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.join(HX, "site")

TEXT_KEYS = [
    "title", "consentHtml", "instructionPages", "practiceIntroHtml", "testIntroHtml", "trialPrompt",
    "nameLabel", "referenceLabels", "referenceLabels.high", "referenceLabels.low", "confidencePrompt",
    "confidenceLabels", "feedback", "feedback.correct", "feedback.incorrect", "questionnaire", "endHtml",
    "prolificCompletionUrl", "ui",
] + ["ui." + k for k in (
    "consentAgree consentDecline noConsentHtml browserExclusionHtml fullscreenHtml fullscreenButton "
    "nextButton previousButton continueButton submitButton exampleTargetCaption yourChoice progressLabel "
    "savingHtml saveErrorHtml loadingHtml loadErrorHtml endButton").split()]

ATOM_FIELDS = {"dataset", "stratum", "refs_high", "refs_low", "query_pos", "query_neg", "names", "meta", "atom_id"}
META_FIELDS = {"corr_salt", "corr_cd", "delta_sign", "category"}
MANIFEST_TOP = {"version", "lists", "atoms", "practice", "catch"}

PINNED = [
    "https://unpkg.com/jspsych@8.3.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-browser-check@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-html-button-response@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-call-function@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-fullscreen@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-preload@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-instructions@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych/plugin-survey-html-form@2.1.0/dist/index.browser.min.js",
    "https://unpkg.com/@jspsych-contrib/plugin-pipe@0.6.0/dist/index.browser.min.js",
    "js/config.js", "js/texts.js", "js/experiment.js",
]
PINNED_CSS = ["https://unpkg.com/jspsych@8.3.0/css/jspsych.css", "css/style.css"]

errors, notes = [], []


def err(m):
    errors.append(m)


def read(p):
    with open(p, encoding="utf8") as f:
        return f.read()


def load_texts(node):
    """Return EXP_TEXTS as a dict (node) or None (regex fallback)."""
    path = os.path.join(SITE, "js", "texts.js")
    if not os.path.isfile(path):
        err("site/js/texts.js missing")
        return None, ""
    src = read(path)
    if node:
        js = "global.window={};" + src + ";process.stdout.write(JSON.stringify(window.EXP_TEXTS))"
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout), src
        err("node could not evaluate texts.js: " + r.stderr.strip()[:300])
    notes.append("texts.js checked by regex only (no node)")
    return None, src


def get(d, dotted):
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default=shutil.which("node"))
    ap.add_argument("--manifest", nargs="*", default=None)
    a = ap.parse_args()

    exp = read(os.path.join(SITE, "js", "experiment.js"))

    # 1. text keys
    used = sorted(set(re.findall(r'\btx\("([A-Za-z0-9_.]+)"', exp)))
    used += sorted(set("instructionPages" for _ in re.findall(r"TX\.instructionPages", exp)))
    for k in used:
        if k not in TEXT_KEYS:
            err("experiment.js uses text key not in contract: " + k)
    texts, src = load_texts(a.node)
    for k in TEXT_KEYS:
        if texts is not None:
            v = get(texts, k)
            if v is None or v == "" or v == []:
                err("texts.js: missing or empty key " + k)
        else:
            leaf = k.split(".")[-1]
            if not re.search(r"\b%s\s*:" % re.escape(leaf), src):
                err("texts.js: key not found (regex) " + k)
    if texts is not None:
        pages = texts.get("instructionPages", {})
        for c in "ABCD":
            p = pages.get(c) or []
            if not p or "{{EXAMPLE_TRIAL}}" not in p[-1]:
                err("texts.js: {{EXAMPLE_TRIAL}} not on last instruction page of " + c)
        if len(texts.get("confidenceLabels", [])) != 5:
            err("texts.js: confidenceLabels must hold 5 strings")
        if texts.get("nameLabel") != "This concept:":
            err('texts.js: nameLabel must be "This concept:"')
        for q in texts.get("questionnaire", []):
            if q.get("type") not in ("text", "multi-choice"):
                err("texts.js: bad questionnaire type " + str(q.get("type")))
            if q.get("name") == "used_name" and sorted(q.get("conditions") or []) != ["B", "C", "D"]:
                err("texts.js: used_name must be restricted to B/C/D")
        if pages.get("B") != pages.get("C") or pages.get("B") != pages.get("D"):
            err("texts.js: instruction pages differ between B, C and D")

    # 2. manifest fields read by experiment.js
    atom_reads = set(re.findall(r"\b(?:atom|exampleAtom|it\.atom|item\.atom|a|ex)\.(\w+)", exp))
    atom_reads -= {"length", "atom"}
    for f in sorted(atom_reads):
        if f not in ATOM_FIELDS:
            err("experiment.js reads atom field not in contract: " + f)
    meta_reads = set(re.findall(r"\bmeta\.(\w+)", exp))
    for f in sorted(meta_reads):
        if f not in META_FIELDS:
            err("experiment.js reads meta field not in contract: " + f)
    top_reads = set(re.findall(r"\b(?:M|m|STATE\.manifest)\.(\w+)", exp)) & (MANIFEST_TOP | {"version"})
    manifests = a.manifest
    if manifests is None:
        manifests = [p for p in (os.path.join(SITE, "stimuli", "manifest.json"),
                                 os.path.join(HERE, "serve", "stimuli_mock", "manifest.json")) if os.path.isfile(p)]
    for mp in manifests:
        m = json.loads(read(mp))
        for k in top_reads:
            if k not in m:
                err("%s: missing top-level key %s" % (mp, k))
        for aid, at in m.get("atoms", {}).items():
            for f in atom_reads - {"atom_id"}:
                if f not in at:
                    err("%s: atom %s lacks %s" % (mp, aid, f))
            for f in META_FIELDS:
                if f not in at.get("meta", {}):
                    err("%s: atom %s lacks meta.%s" % (mp, aid, f))
        notes.append("manifest checked: " + mp)

    # 3. index.html
    html = read(os.path.join(SITE, "index.html"))
    scripts = re.findall(r'<script src="([^"]+)"', html)
    if scripts != PINNED:
        err("index.html scripts differ from SPEC Part 4: " + json.dumps(scripts))
    css = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
    if css != PINNED_CSS:
        err("index.html stylesheets differ from SPEC Part 4: " + json.dumps(css))
    if 'id="jspsych-target"' not in html or "<noscript>" not in html:
        err("index.html: jspsych-target div or noscript missing")
    if texts is not None:
        t = re.search(r"<title>(.*?)</title>", html)
        if not t or t.group(1) != texts.get("title"):
            err("index.html <title> differs from EXP_TEXTS.title (%r)" % texts.get("title"))
    if "fonts.googleapis" in html:
        err("index.html loads Google Fonts")

    # 4. config.js verbatim from SPEC 5.4
    spec = read(os.path.join(HX, "SPEC.md"))
    blk = re.search(r"### 5\.4.*?```js\n(.*?)```", spec, re.S)
    if blk and blk.group(1).strip() != read(os.path.join(SITE, "js", "config.js")).strip():
        err("config.js differs from SPEC 5.4")

    # 5. CSS coverage of emitted classes
    style = read(os.path.join(SITE, "css", "style.css"))
    spec_classes = {"trial", "concept-name", "concept-name-value", "ref-block", "ref-high", "ref-low", "ref-label",
                    "ref-row", "ref-img", "trial-prompt", "query-btn", "query-img", "trial-confidence", "query-pair",
                    "query-static", "is-chosen", "query-caption", "conf-btn", "conf-num", "conf-label",
                    "trial-feedback", "feedback", "feedback-correct", "feedback-incorrect", "is-target",
                    "example-trial", "debug-badge"}
    emitted = set(spec_classes)
    for cls in re.findall(r'class="([^"]+)"', exp):
        emitted.update(c for c in cls.split() if re.fullmatch(r"[a-z][\w-]*", c) and c != "cls")
    emitted.update(re.findall(r'css_classes: \["([\w-]+)"\]', exp))
    for c in sorted(spec_classes):
        if not re.search(r'["\' ]%s["\' ]' % re.escape(c), exp):
            err("experiment.js never emits SPEC 5.5 class ." + c)
    for c in sorted(emitted):
        if c in ("jspsych-btn",):
            continue
        if not re.search(r"\.%s\b" % re.escape(c), style):
            err("style.css has no rule for class ." + c)

    for n in notes:
        print("note:", n)
    for e in errors:
        print("ERROR:", e)
    print("OK" if not errors else "%d error(s)" % len(errors))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

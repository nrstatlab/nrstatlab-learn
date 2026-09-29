"""Read the site's five syllabus maps (BUILD-GUIDE Steps 5 and 12).

Each map is read through the content repository's own generator
(tools/exams/*_map.py, csirmap.py), from the same row functions that print the
map pages. So each line is the map's own wording, each grade the map's own, and
the generators' own checks (contiguous item ranges, evidence found in each
course page) run on every import.

For each exam: its groups, as the map heads them, each with its items; each item
with its text (HTML, as the map prints it), its grade and its links. A link is a
site path, followed through any redirect stub, with a depth:

* UGC NET: the link to the UGC NET unit's section is "brief", and each course
  unit the generator has checked is "deep" (ugc_map.py derives the row's grade
  the same way);
* the other maps grade the row, and each of its links takes that grade.
"""
from __future__ import annotations

import io
import posixpath
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

from .importer import _load

EXAMS = ["ugc-net", "csir-net", "asrb-net", "iss", "appsc"]
# The pages of each exam that are its syllabus map (the readiness box goes on them).
MAP_PAGES = {
    "ugc-net": ["exams/ugc-net/index.html"],
    "csir-net": ["exams/csir-net/index.html"],
    "asrb-net": ["exams/asrb-net/index.html"],
    "iss": ["exams/iss/index.html"] + [f"exams/iss/paper{p}.html" for p in (1, 2, 3, 4)],
    "appsc": ["exams/appsc/index.html", "exams/appsc/assistant-director.html",
              "exams/appsc/assistant-statistical-officer.html"],
}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


class SyllabusError(Exception):
    """A map cannot be read as expected. Nothing is stored."""


def _generator(root: Path, name: str):
    exams = root / "tools" / "exams"
    for p in (str(exams), str(root / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)
    with redirect_stdout(io.StringIO()):          # a generator may print as it loads
        return _load(exams / f"{name}.py", f"_content_{name}")


def _dests(x):
    """None, one path, several, or (path, label) pairs -- always a list of paths."""
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    return [d[0] if isinstance(d, tuple) else d for d in x]


class Resolver:
    """Site paths for a map's links: relative to the map's folder, without the
    fragment, and followed through redirect stubs to the page they lead to."""

    def __init__(self, stubs: dict, markable):
        self.stubs, self.markable = stubs, markable

    def __call__(self, base: str, dest: str) -> str:
        path = posixpath.normpath(posixpath.join(base, dest.split("#")[0]))
        seen = set()
        while path in self.stubs and path not in seen:
            seen.add(path)
            target = self.stubs[path]
            if target.startswith(("http://", "https://")):
                break
            path = target.split("#")[0]
        return path


def _item(text, grade, links):
    """links: [(path, depth)]. One link per path, keeping the deeper depth."""
    best = {}
    for path, depth in links:
        if best.get(path) != "deep":
            best[path] = depth
    return {"text": text, "grade": grade, "links": list(best.items())}


def read_iss(root, resolve):
    gen = _generator(root, "iss_map")
    groups = []
    for p in (1, 2, 3, 4):
        info = gen.D.PAPERS[p]
        by_section = {}
        for rn, sname, (line, dest, grade) in gen.rows_of(p):
            key = f"P{p}-{rn}"
            if key not in by_section:
                by_section[key] = {"code": key, "items": [],
                                   "title": f"Paper {ROMAN[p]} ({info['code'].title()}), section ({rn}): {sname}"}
                groups.append(by_section[key])
            by_section[key]["items"].append(
                _item(line, grade, [(resolve("exams/iss", d), grade) for d in _dests(dest)]))
    return groups


def read_asrb(root, resolve):
    gen = _generator(root, "asrb_map")
    return [{"code": f"U{num}", "title": f"Unit {num}: {gen.esc(title)}",
             "items": [_item(gen.esc(line), grade, [(resolve("exams/asrb-net", d), grade) for d in _dests(dest)])
                       for line, dest, grade in rows]}
            for num, title, rows in gen.build_rows()]


def read_ugc(root, resolve):
    gen = _generator(root, "ugc_map")
    groups = []
    for roman, title, rows in gen.build_rows():
        items = []
        for line, dests, grade in rows:
            links = []
            for path, _label in dests:
                # the UGC NET unit's own section is exam-level; a checked course unit is deep
                depth = "brief" if re.match(r"unit\d+\.html#", path) else "deep"
                links.append((resolve("exams/ugc-net", path), depth))
            items.append(_item(gen.esc(line), grade, links))
        groups.append({"code": f"U{roman}", "title": f"Unit {roman}: {gen.esc(title)}", "items": items})
    return groups


def read_appsc(root, resolve):
    gen = _generator(root, "appsc_map")
    groups, by_title = [], {}
    for title, (line, dest, grade) in gen.all_rows("ASO"):     # both posts map the same rows
        if title not in by_title:
            by_title[title] = {"code": f"G{len(groups) + 1}", "title": title, "items": []}
            groups.append(by_title[title])
        by_title[title]["items"].append(
            _item(line, grade, [(resolve("exams/appsc", d), grade) for d in _dests(dest)]))
    return groups


def read_csir(root, resolve):
    gen = _generator(root, "csirmap")
    source = (root / "tools" / "exams" / "csirmap.py").read_text(encoding="utf-8")
    titles = dict(re.findall(r"^# ---- UNIT (\d+): (.+?) ----$", source, re.M))
    units = sorted(int(n) for n in titles)
    if not units:
        raise SyllabusError("csirmap.py: no UNIT headings found")
    return [{"code": f"U{n}", "title": f"Unit {n}: {titles[str(n)]}",
             "items": [_item(text, grade, [(resolve("", p), grade) for p in _dests(dests)])
                       for text, dests, grade in getattr(gen, f"UNIT{n}")]}
            for n in units]


READERS = {"ugc-net": read_ugc, "csir-net": read_csir, "asrb-net": read_asrb, "iss": read_iss, "appsc": read_appsc}


def read_syllabus(root, stubs, markable, pages):
    """{exam slug: [group]} for the five exams. Every link must lead to a page of the
    site, so a map can never point readiness at nothing."""
    root = Path(root)
    resolve = Resolver(stubs, markable)
    out = {}
    for slug in EXAMS:
        groups = READERS[slug](root, resolve)
        for g in groups:
            for n, item in enumerate(g["items"], 1):
                item["code"] = f"{g['code']}-{n:02d}"
                for path, _ in item["links"]:
                    if path not in pages:
                        raise SyllabusError(f"{slug} {item['code']}: {path} is not a page of the site")
        out[slug] = groups
    return out


def counts(groups, markable):
    """For one exam: its items, and how many link to a markable unit, only to other
    pages of the site, or nowhere."""
    c = {"items": 0, "with a unit": 0, "page only": 0, "not here": 0}
    for g in groups:
        for item in g["items"]:
            paths = [p for p, _ in item["links"]]
            c["items"] += 1
            c["with a unit" if any(p in markable for p in paths) else "page only" if paths else "not here"] += 1
    return c

"""Read the question bank out of the static site (BUILD-GUIDE Step 9).

Only keyed sources are read:

* exams/ugc-net/mcqs.html: 500 MCQs in ten units of 50. The key is the first
  letter of the answer paragraph; anything after it is the explanation.
* exams/ugc-net/solved-2026.html: the June 2026 paper, 150 questions, key in
  "Answer: (D) ...". Four comprehension passages each serve the five questions
  after them. The page ties no question to a unit, so these stay in the exam
  bank and are never drawn for a unit test.
* The APPSC Assistant Statistical Officer Paper-II of 2025 and of 2022, through
  the site's own generator (tools/exams/appsc_paper.py), so each question is
  stored exactly as its solved page shows it. The key is the Commission's; the
  "Study this" link of each question names the unit that teaches it.

A question is flagged, and so never scored, when the site says its key is in
doubt: the six keys the September 2026 audit contested (docs/AUDIT-2026-09.md
§5, item 1), every question whose solved page carries a warning note, and the three
the Commission withdrew. The owner can publish a flagged question in the admin
once it is settled.

Unit pages were searched for practice sets with answers; there are none yet.
"""
from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .importer import _load

UGC_MCQS = "exams/ugc-net/mcqs.html"
UGC_2026 = "exams/ugc-net/solved-2026.html"
LABELS = "ABCD"
AUDIT = "docs/AUDIT-2026-09.md"
KEY_CHECKED = f"Key recomputed and confirmed in the September 2026 audit ({AUDIT} §3.3, content repository)."
COMMISSION_KEY = "Key: the Commission's own, as marked in its question paper ({pdf}, content repository)."

# The six keys the audit contested (docs/AUDIT-2026-09.md §5, item 1), in its words.
CONTESTED = {
    (5, 50): "An exact test for p = 0.5 uses the binomial, which is option A; the key says C.",
    (7, 14): "The random walk's E(Yt) = Y0, so B, unless the stem fixes Y0 = 0.",
    (8, 16): "\"All of the above\" includes a false \"only\".",
    (3, 39): "Murthy's estimator is not always better than Hansen–Hurwitz.",
    (5, 41): "A and C are both right.",
    (2, 45): "Sharing trace, determinant and eigenvalues does not imply similarity.",
}
AUDIT_FLAG = "Contested in the September 2026 audit (" + AUDIT + " §5, item 1): {}"
PASSAGE_SPAN = 5  # a comprehension passage on the 2026 page serves the five questions after it
UGC_2026_PAPER_I, UGC_2026_PAPER_II = "Paper I — General Paper", "Paper II — Statistics"


@dataclass
class Bank:
    """Everything read, before anything is written."""

    sources: dict = field(default_factory=dict)   # uid prefix -> list of items
    papers: list = field(default_factory=list)
    expected: dict = field(default_factory=dict)  # uid prefix -> count the source itself states

    def count(self, prefix):
        return len(self.sources[prefix])


def inner(el):
    return "".join(str(c) for c in el.contents).strip()


def _soup(root, rel):
    return BeautifulSoup((root / rel).read_text(encoding="utf-8"), "lxml")


# ---------------------------------------------------------------- UGC NET MCQs

def read_ugc_mcqs(root):
    soup = _soup(root, UGC_MCQS)
    items, seen_units = [], []
    for h in soup.select("h2"):
        m = re.match(r"Unit (\d+) — .*\((\d+) MCQs\)", h.get_text(" ", strip=True))
        if not m:
            continue
        unit, stated = int(m.group(1)), int(m.group(2))
        seen_units.append((unit, stated))
        n = 0
        for el in h.find_all_next(["h2", "div"]):
            if el.name == "h2":
                break
            if "mcq" not in (el.get("class") or []):
                continue
            n += 1
            q = el.select_one("div.q")
            num = re.match(r"\s*(\d+)\.\s*", q.get_text())
            if not num or int(num.group(1)) != n:
                raise ValueError(f"{UGC_MCQS} Unit {unit}: question {n} is numbered {num and num.group(1)}")
            stem = re.sub(r"^\s*\d+\.\s*", "", inner(q), count=1)
            options = [inner(li) for li in el.select("ol.options > li")]
            answer = el.select_one("details p")
            key_m = re.match(r"\s*([A-D])\b\.?\s*", answer.get_text())
            if not key_m or len(options) != 4:
                raise ValueError(f"{UGC_MCQS} Unit {unit} Q{n}: no key letter, or not four options")
            key = key_m.group(1)
            solution = re.sub(r"^\s*[A-D]\b\.?\s*", "", inner(answer), count=1).strip()
            contested = CONTESTED.get((unit, n))
            items.append({
                "uid": f"ugc-mcq-u{unit:02d}-q{n:02d}", "qtype": "single", "stem_html": stem,
                "solution_html": solution,
                "choices": [(LABELS[i], o, LABELS[i] == key) for i, o in enumerate(options)],
                "source": UGC_MCQS, "source_ref": f"Unit {unit} Q{n}",
                "flag_reason": AUDIT_FLAG.format(contested) if contested else "",
                "units": [f"exams/ugc-net/unit{unit}.html"], "recompute_log": KEY_CHECKED,
            })
        if n != stated:
            raise ValueError(f"{UGC_MCQS} Unit {unit}: heading says {stated} MCQs, found {n}")
    return items, sum(s for _, s in seen_units)


# ---------------------------------------------------------------- UGC NET June 2026 paper

def read_ugc_2026(root):
    soup = _soup(root, UGC_2026)
    items, passage, left = [], "", 0
    for el in soup.select("div.comp, div.mcq"):
        if "comp" in el.get("class"):
            passage, left = str(el), PASSAGE_SPAN
            continue
        qn = el.select_one("span.qn")
        n = int(re.match(r"Q(\d+)\.", qn.get_text()).group(1))
        if n != len(items) + 1:
            raise ValueError(f"{UGC_2026}: Q{n} follows Q{len(items)}")
        q = el.select_one("div.q")
        qn.extract()
        stem = inner(q)
        if left:
            stem, left = passage + stem, left - 1
        options = [inner(li) for li in el.select("ol.options > li")]
        answer = el.select_one("details p")
        key_m = re.match(r"Answer: \(([A-D])\)", answer.select_one("strong").get_text(strip=True))
        if not key_m or len(options) != 4:
            raise ValueError(f"{UGC_2026} Q{n}: no key, or not four options")
        flag = el.select_one(".flag")
        reason = ""
        if flag:
            reason = "The solved page notes: " + flag.get_text(" ", strip=True).lstrip("⚠ ").strip()
            flag.extract()
        items.append({
            "uid": f"ugc-2026-q{n:03d}", "qtype": "single", "stem_html": stem,
            "solution_html": inner(answer),
            "choices": [(LABELS[i], o, LABELS[i] == key_m.group(1)) for i, o in enumerate(options)],
            "source": UGC_2026, "source_ref": f"Q{n}", "flag_reason": reason, "units": [],
            "recompute_log": "Key checked in the September 2026 audit (" + AUDIT + " §3.3, content repository).",
        })
    paper = {"slug": "ugc-net-june-2026", "exam": "ugc-net", "title": "UGC NET June 2026, Statistics (Code 107)",
             "held_on": None, "page_path": UGC_2026, "source": UGC_2026,
             # The page records no official duration or marking scheme, so none is claimed.
             "duration_minutes": None, "marking_scheme": None,
             "questions": [{"number": int(i["source_ref"][1:]), "uid": i["uid"],
                            "official_key": next(c[0] for c in i["choices"] if c[2]),
                            # The page's own two halves: Q1-50 and Q51-150.
                            "section": UGC_2026_PAPER_I if int(i["source_ref"][1:]) <= 50 else UGC_2026_PAPER_II}
                           for i in items]}
    return items, 150, paper


# ---------------------------------------------------------------- APPSC papers

def _appsc_generator(root):
    exams = root / "tools" / "exams"
    for p in (str(exams), str(root / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return _load(exams / "appsc_paper.py", "_content_appsc_paper")


def read_appsc(root):
    gen = _appsc_generator(root)
    out = []
    for paper in gen.PAPERS:
        year, maths = paper["year"], paper["maths"]
        header, images, links, rows = gen.build(paper)
        raw = json.loads((root / "tools" / "exams" / f"appsc_paper_{year}.json").read_text(encoding="utf-8"))
        notes = {q["n"]: q.get("note", "") for q in raw["questions"]}
        topics = paper["data"].TOPICS
        # The page's own parts (Economics, Financial Accounting, Statistics, Computers), by syllabus item.
        section_of = {item: label for _slug, label, members in paper["data"].GROUPS for item in members}
        pdf = paper["source"]
        items, pqs = [], []
        for q, item_no, topic, working, flag in rows:
            n, key = q["n"], q["key"]
            options = [gen.option_html(o, images, maths) for o in q["options"]]
            unit_path = topics[topic][1]
            if key is None:
                reason = "Withdrawn by the Commission: " + html.unescape(notes[n])
            elif flag:
                # the note is HTML on the solved page; the reason is shown as text
                reason = "The solved page notes: " + html.unescape(re.sub(r"<[^>]+>", "", flag))
            else:
                reason = ""
            items.append({
                "uid": f"appsc-aso-{year}-q{n:03d}", "qtype": "single",
                "stem_html": gen.stem_html(q, images, maths), "solution_html": working,
                "choices": [(str(i + 1), o, key == i + 1) for i, o in enumerate(options)],
                "source": paper["out"], "source_ref": f"Q{n}", "flag_reason": reason,
                "scorable": key is not None,
                "units": [unit_path] if unit_path else [], "recompute_log": COMMISSION_KEY.format(pdf=pdf),
            })
            pqs.append({"number": n, "uid": items[-1]["uid"], "official_key": str(key) if key else "",
                        "withdrawn": key is None, "withdrawn_note": notes[n] if key is None else "",
                        "section": section_of[item_no]})
        negative = header.get("Section Negative Marks")
        out.append((f"appsc-aso-{year}-", items, int(header["Number of Questions"]), {
            "slug": f"appsc-aso-{year}-paper-ii", "exam": "appsc",
            "title": f"APPSC Assistant Statistical Officer, Paper-II, {year}",
            "held_on": datetime.strptime(paper["date"], "%d %B %Y").date(),
            "page_path": "exams/appsc/" + paper["out"], "source": pdf,
            "duration_minutes": int(header["Duration"]),
            "duration_source": f"The question paper's header ({pdf})",
            "marking_scheme": {"correct": 1, "wrong": -float(negative)} if negative else None,
            "marking_source": f"The question paper's header and each question's marks line ({pdf})",
            "questions": pqs}))
    return out


def read_bank(root) -> Bank:
    root = Path(root)
    bank = Bank()
    items, stated = read_ugc_mcqs(root)
    bank.sources["ugc-mcq-"], bank.expected["ugc-mcq-"] = items, stated
    items, stated, paper = read_ugc_2026(root)
    bank.sources["ugc-2026-"], bank.expected["ugc-2026-"] = items, stated
    bank.papers.append(paper)
    for prefix, items, stated, paper in read_appsc(root):
        bank.sources[prefix], bank.expected[prefix] = items, stated
        bank.papers.append(paper)
    return bank

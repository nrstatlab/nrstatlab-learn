"""Load the static site in content/ into the database (BUILD-GUIDE Step 5).

The static site stays the place content is written. This module reads it and
stores what Django needs to serve every page at its current path:

* every HTML page, split into the parts the site's generators already mark,
  so that study.pages.assemble() gives back the original file byte for byte;
* every redirect stub, as a Redirect row (served as a 301);
* the courses and their markable units, from course_catalogue.py and
  assets/progress-index.json;
* the five exams, and each one's syllabus map: its items, graded, and their
  links to the pages that teach them (apps/core/syllabus.py);
* every non-HTML site file, copied to SITE_ROOT_DIR at the same path, where
  WhiteNoise serves it.

The question banks are imported by import_questions (Phase 3).

The counts it stores are checked against the counts it read, so nothing can be
silently dropped. It is idempotent: an unchanged page is not written again.
"""
from __future__ import annotations

import html
import importlib.util
import json
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from apps.examinations import services as examinations
from apps.study import services as study

REFRESH_URL_RE = re.compile(r'http-equiv="refresh"\s+content="[^"]*?url=([^"]+)"', re.I)

# Folders in the content repository that are not part of the site.
NOT_SITE = ("tools/", "Webapp/", ".github/")
PROGRAMMES = {"statistics": "Statistics", "data-science": "Data Science", "exams": "Examinations"}
# The exam hubs, in the order the site's menu lists them (tools/site_nav_model.py).
EXAMS = ["ugc-net", "csir-net", "asrb-net", "iss", "appsc"]


class ImportError_(Exception):
    """The content does not match what was stored. Nothing is committed."""


# ---------------------------------------------------------------- sources

def _load(path: Path, name: str):
    """Load one of the content repository's tools. No bytecode is written, so the
    content submodule stays exactly as checked out."""
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.dont_write_bytecode = before


# What the content repository's .gitignore leaves out, for when git is not there.
UNTRACKED_DIRS = {".git", "_site", ".jekyll-cache", "__pycache__", "node_modules"}
UNTRACKED_NAMES = {".DS_Store", "Thumbs.db"}


def site_files(root: Path):
    """The content repository's files: git's own list; or, where there is no git (a
    Docker build copies the files without it), every file except what the content
    repository's .gitignore excludes. tests/test_importer.py holds the two to be equal."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True).stdout
        return sorted(f for f in out.split("\0") if f)
    except (OSError, subprocess.CalledProcessError):
        return walk_files(root)


def walk_files(root: Path):
    root = Path(root)
    out = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in UNTRACKED_DIRS for part in rel.parts[:-1]) or not path.is_file():
            continue
        if rel.name in UNTRACKED_NAMES or rel.suffix in (".pyc", ".pyo", ".pyd") or rel.parts[0] in UNTRACKED_DIRS:
            continue
        out.append(rel.as_posix())
    return sorted(out)


@dataclass
class Source:
    """Everything read from content/, before anything is written."""

    root: Path
    pages: dict = field(default_factory=dict)       # rel -> text
    stubs: dict = field(default_factory=dict)       # rel -> target rel
    indexed: set = field(default_factory=set)
    courses: list = field(default_factory=list)     # dicts
    markable: dict = field(default_factory=dict)    # rel -> (course path, order)
    exams: list = field(default_factory=list)
    site_files: list = field(default_factory=list)  # rel paths of non-HTML files
    syllabus: dict = field(default_factory=dict)    # exam slug -> groups (apps/core/syllabus.py)

    @classmethod
    def read(cls, root: Path) -> Source:
        root = Path(root)
        tools = root / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        stubs_mod = _load(tools / "stubs.py", "_content_stubs")
        sitemap = _load(tools / "build_sitemap.py", "_content_sitemap")
        catalogue = _load(tools / "course_catalogue.py", "_content_catalogue")
        nav = _load(tools / "site_nav_model.py", "_content_nav")
        src = cls(root=root)

        tracked = [f for f in site_files(root) if f and not f.startswith(NOT_SITE) and not Path(f).name.startswith(".git")]
        for rel in tracked:
            path = root / rel
            if not path.is_file():
                continue
            if rel.endswith(".html"):
                if stubs_mod.is_stub(path):
                    src.stubs[rel] = src._stub_target(rel, path.read_text(errors="replace"))
                else:
                    src.pages[rel] = path.read_text(errors="replace")
            else:
                src.site_files.append(rel)
        src.indexed = {p.relative_to(root).as_posix() for p in sitemap.pages()}

        levels = {f"statistics/{f}": (lvl or "", g) for f, lvl, g in catalogue.statistics_courses()}
        levels.update({f"data-science/{s}": ("", g) for s, g in catalogue.data_science_courses()})
        index = json.loads((root / "assets" / "progress-index.json").read_text())
        for order, (cpath, files) in enumerate(index["courses"].items()):
            level, group = levels.get(cpath, ("", "Examinations" if cpath.startswith("exams/") else ""))
            title = nav.label_of(root / cpath / "index.html")
            src.courses.append({"path": cpath, "title": re.sub(r"&amp;", "&", title), "level": level,
                                "group": re.sub(r"&amp;", "&", group), "order": order,
                                "programme": cpath.split("/")[0]})
            for i, fname in enumerate(files):
                src.markable[f"{cpath}/{fname}"] = (cpath, i)
        for order, slug in enumerate(EXAMS):
            hub = f"exams/{slug}/index.html"
            src.exams.append({"slug": slug, "name": html.unescape(nav.label_of(root / hub, drop_artefact=True)),
                              "hub_path": hub, "order": order})
        from . import syllabus
        try:
            src.syllabus = syllabus.read_syllabus(root, src.stubs, src.markable, src.pages)
        except syllabus.SyllabusError as e:
            raise ImportError_(str(e)) from e
        return src

    @staticmethod
    def _stub_target(rel: str, text: str) -> str:
        m = REFRESH_URL_RE.search(text)
        if not m:
            raise ImportError_(f"{rel}: a redirect stub with no target")
        url = m.group(1).strip()
        if url.startswith(("http://", "https://")):
            return url
        target, frag = (url.split("#", 1) + [""])[:2]
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
        return resolved + (f"#{frag}" if frag else "")

    def check(self) -> None:
        """What the source must satisfy before anything is written."""
        missing = [p for p in self.markable if p not in self.pages]
        if missing:
            raise ImportError_(f"{len(missing)} markable pages are missing, e.g. {missing[:3]}")
        not_page = [p for p in self.indexed if p not in self.pages]
        if not_page:
            raise ImportError_(f"{len(not_page)} sitemap pages are not pages, e.g. {not_page[:3]}")
        for rel, target in self.stubs.items():
            if not target.startswith("http") and target.split("#")[0] not in self.pages:
                raise ImportError_(f"{rel} redirects to {target}, which is not a page")


# ---------------------------------------------------------------- writing

def copy_site_files(src: Source, dest: Path) -> dict:
    """Copy every non-HTML site file to dest at the same path. Returns counts."""
    counts = {"copied": 0, "unchanged": 0}
    for rel in src.site_files:
        a, b = src.root / rel, dest / rel
        if b.exists() and b.stat().st_size == a.stat().st_size and b.read_bytes() == a.read_bytes():
            counts["unchanged"] += 1
            continue
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a, b)
        counts["copied"] += 1
    return counts


def write_database(src: Source) -> dict:
    """Store everything read. Each app stores its own tables through its services
    (ARCHITECTURE.md §3); core stores only its redirects. Call inside a transaction."""
    from .models import Redirect

    counts = study.store_site(
        programmes=PROGRAMMES, courses=src.courses, pages=src.pages,
        markable=src.markable, indexed=src.indexed)
    Redirect.objects.exclude(old_path__in=src.stubs).delete()
    for old, new in src.stubs.items():
        Redirect.objects.update_or_create(old_path=old, defaults={"new_path": new})
    examinations.store_exams(src.exams)
    counts["syllabus"] = examinations.store_syllabus(src.syllabus)
    return counts


def verify_database(src: Source) -> dict:
    """What was stored must equal what was read. Returns the stored counts."""
    from .models import Redirect

    stored = {**study.stored_counts(), "redirects": Redirect.objects.count(),
              "exams": examinations.exam_count()}
    expected = {
        "courses": len(src.courses),
        "markable units": len(src.markable),
        "indexed pages": len(src.indexed),
        "other pages": len(src.pages) - len(src.indexed),
        "redirects": len(src.stubs),
        "exams": len(src.exams),
    }
    wrong = {k: (stored[k], expected[k]) for k in expected if stored[k] != expected[k]}
    from . import syllabus
    have = examinations.syllabus_counts()
    for slug, groups in src.syllabus.items():
        if have.get(slug) != syllabus.counts(groups, src.markable):
            wrong[f"syllabus of {slug}"] = (have.get(slug), syllabus.counts(groups, src.markable))
    if wrong:
        raise ImportError_(f"stored counts differ from the source: {wrong}")
    stored["syllabus items"] = sum(c["items"] for c in have.values())
    return stored

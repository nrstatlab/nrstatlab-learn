"""Load the static site in content/ into the database (BUILD-GUIDE Step 5).

The static site stays the place content is written. This module reads it and
stores what Django needs to serve every page at its current path:

* every HTML page, split into the parts the site's generators already mark,
  so that study.pages.assemble() gives back the original file byte for byte;
* every redirect stub, as a Redirect row (served as a 301);
* the courses and their markable units, from course_catalogue.py and
  assets/progress-index.json;
* the five exams;
* every non-HTML site file, copied to SITE_ROOT_DIR at the same path, where
  WhiteNoise serves it.

Question banks and syllabus maps are imported in the phases that use them
(Phase 3 and Phase 5).

The counts it stores are checked against the counts it read, so nothing can be
silently dropped. It is idempotent: an unchanged page is not written again.
"""
from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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

        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                                 text=True, check=True).stdout.split("\0")
        tracked = [f for f in tracked if f and not f.startswith(NOT_SITE) and not Path(f).name.startswith(".git")]
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
            src.exams.append({"slug": slug, "name": re.sub(r"&amp;", "&", nav.label_of(root / hub)),
                              "hub_path": hub, "order": order})
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
    if wrong:
        raise ImportError_(f"stored counts differ from the source: {wrong}")
    return stored

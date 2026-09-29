"""Exam readiness (BUILD-GUIDE Step 12), from the site's own syllabus maps.

    weight(link)   = 2 if deep else 1
    item_readiness = sum of weight x [unit passed] / sum of weight, over the item's links to units
    exam_readiness = mean of item_readiness over the items with at least one link to a unit

Only passed units count (the owner's decision): a unit is passed by passing its unit
test. Studied units are shown, and do not count. Two kinds of item are left out of
the figure, and listed: items taught only on pages with nothing to mark (a course
index, a guide), and items not taught on this site. The ceiling is the same
arithmetic with every unit that has a test counted as passed: the most a learner
can reach until more tests exist.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.assessments import services as assessments
from apps.progress import services as progress
from apps.study import services as study

from .models import ExamTarget, SyllabusItem

WEIGHT = {"deep": 2, "brief": 1}


@dataclass
class Link:
    path: str
    depth: str
    title: str = ""
    unit: bool = False          # the target is a markable unit
    order: tuple = ()           # (course order, unit order), for ranking


@dataclass
class Item:
    code: str
    text: str
    grade: str
    group: str
    links: list = field(default_factory=list)

    @property
    def unit_links(self):
        return [lk for lk in self.links if lk.unit]


def item_readiness(item, passed):
    """0..1 for an item with links to units; None for an item without any."""
    links = item.unit_links
    if not links:
        return None
    total = sum(WEIGHT[lk.depth] for lk in links)
    return sum(WEIGHT[lk.depth] for lk in links if lk.path in passed) / total


def exam_readiness(items, passed):
    """0..100: the mean of item_readiness over the items that have one."""
    values = [v for v in (item_readiness(i, passed) for i in items) if v is not None]
    return 100 * sum(values) / len(values) if values else 0.0


def next_units(items, status, tested, n=3):
    """Units not yet passed, ranked by how many of the exam's items they serve, then by
    course order. A unit already studied that has no test is skipped: nothing more can
    be done there yet."""
    served, first = {}, {}
    for item in items:
        for lk in {lk.path: lk for lk in item.unit_links}.values():
            served[lk.path] = served.get(lk.path, 0) + 1
            first.setdefault(lk.path, lk)
    out = []
    for path in sorted(served, key=lambda p: (-served[p], first[p].order, p)):
        st = status.get(path)
        if st == "passed" or (st == "studied" and path not in tested):
            continue
        if st == "studied":
            step = "Take its test"
        elif path in tested:
            step = "Study it, then take its test"
        else:
            step = "Study it; its test is not written yet"
        out.append({"path": path, "title": first[path].title, "items": served[path], "step": step,
                    "status": st or "not_started"})
        if len(out) == n:
            break
    return out


def compute(items, status, tested):
    """Everything the readiness page shows, from the items, the learner's unit statuses
    ({path: status}) and the units that have a test."""
    passed = {p for p, s in status.items() if s == "passed"}
    counted = [i for i in items if i.unit_links]
    needed = {lk.path for i in counted for lk in i.unit_links}
    groups, by_group = [], {}
    for item in items:
        if item.group not in by_group:
            by_group[item.group] = {"title": item.group, "items": []}
            groups.append(by_group[item.group])
        v = item_readiness(item, passed)
        by_group[item.group]["items"].append({
            "code": item.code, "text": item.text, "grade": item.grade,
            "percent": None if v is None else round(100 * v),
            "links": [{"path": lk.path, "title": lk.title, "depth": lk.depth, "unit": lk.unit,
                       "status": status.get(lk.path, "not_started") if lk.unit else None,
                       "has_test": lk.path in tested} for lk in item.links],
        })
    return {
        "percent": round(exam_readiness(items, passed), 1),
        "ceiling": round(exam_readiness(items, passed | (tested & needed)), 1),
        "units_needed": len(needed),
        "units_tested": len(tested & needed),
        "units_passed": len(passed & needed),
        "units_studied": len({p for p in needed if status.get(p) == "studied"}),
        "items": len(items),
        "counted": len(counted),
        "groups": groups,
        "page_only": [i for i in items if i.links and not i.unit_links],
        "not_here": [i for i in items if not i.links],
        "next": next_units(items, status, tested),
    }


def load_items(exam):
    """The exam's stored syllabus as Items."""
    qs = list(SyllabusItem.objects.filter(exam=exam).select_related("paper")
              .prefetch_related("links__unit__course").order_by("order"))
    names = study.titles({sl.target_path for si in qs for sl in si.links.all() if sl.unit is None})
    out = []
    for si in qs:
        links = []
        for sl in sorted(si.links.all(), key=lambda x: x.target_path):
            u = sl.unit
            links.append(Link(path=sl.target_path, depth=sl.depth, unit=u is not None,
                              title=u.title if u else names.get(sl.target_path, sl.target_path),
                              order=(u.course.order, u.order) if u else ()))
        out.append(Item(code=si.code, text=si.text, grade=si.grade,
                        group=si.paper.title if si.paper else "", links=links))
    return out


def readiness(user, exam):
    items = load_items(exam)
    paths = {lk.path for i in items for lk in i.unit_links}
    status = {p: s for p, s in progress.status_map(user).items() if p in paths}
    return compute(items, status, assessments.tested_units(paths))


def summary(user, exam):
    """The figure and the next unit, for the dashboard and the exam's own pages."""
    r = readiness(user, exam)
    return {"slug": exam.slug, "name": exam.name, "percent": r["percent"], "ceiling": r["ceiling"],
            "url": f"/readiness/{exam.slug}/", "next": r["next"][0] if r["next"] else None}


def target_of(user):
    t = ExamTarget.objects.select_related("exam").filter(user=user).first()
    return t.exam if t else None


def set_target(user, exam):
    ExamTarget.objects.update_or_create(user=user, defaults={"exam": exam})


def clear_target(user):
    ExamTarget.objects.filter(user=user).delete()


def export(user):
    t = ExamTarget.objects.select_related("exam").filter(user=user).first()
    return {"exam": t.exam.slug, "exam_date": t.exam_date.isoformat() if t.exam_date else None} if t else None

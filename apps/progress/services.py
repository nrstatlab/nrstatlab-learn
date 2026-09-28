"""The progress app's interface (ARCHITECTURE.md §3). This module is the only writer
of UnitProgress and ActivityEvent. A page id is a unit's path from the site root,
e.g. statistics/sampling-theory/unit2.html: the id assets/progress.js already uses.

Marking by hand moves a unit between "not started" and "studied" only. "Passed"
is set by the unit test (Phase 3) and is never changed by marking or by an import.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts import services as accounts
from apps.study import services as study

from .models import ActivityEvent
from .models import UnitProgress as UP

MAX_IMPORT_IDS = 400
MAX_ID_LENGTH = 300
LOCAL = ZoneInfo(settings.TIME_ZONE)
DONE = (UP.STUDIED, UP.PASSED)


class NotAUnit(Exception):
    """The page id is not a markable unit."""


def _local_date(dt):
    return timezone.localtime(dt, LOCAL).date()


def status_map(user):
    """{page id: status} for every unit this learner has a record for."""
    return dict(UP.objects.filter(user=user).values_list("unit__legacy_path", "status"))


def done_map(user):
    """{page id: "YYYY-MM-DD"} for every unit studied or passed: the shape of the
    browser's own progress entry, so assets/progress.js can draw it unchanged.
    progress.js treats an empty value as not done, so there is always a date."""
    out = {}
    for path, studied_at, passed_at, first_seen in UP.objects.filter(user=user, status__in=DONE).values_list(
            "unit__legacy_path", "studied_at", "passed_at", "first_seen"):
        out[path] = _local_date(studied_at or passed_at or first_seen).isoformat()
    return out


@transaction.atomic
def mark_studied(user, page_id, done=True):
    """Mark a unit studied (done=True) or not (done=False). Returns the new status."""
    unit = study.unit_by_path(page_id) if isinstance(page_id, str) else None
    if unit is None:
        raise NotAUnit(page_id)
    row = UP.objects.select_for_update().filter(user=user, unit=unit).first()
    if row is not None and row.status == UP.PASSED:
        return row.status
    if done:
        if row is None:
            row = UP(user=user, unit=unit)
        if row.status != UP.STUDIED:
            row.status, row.studied_at, row.source = UP.STUDIED, timezone.now(), "web"
            row.save()
            ActivityEvent.objects.create(user=user, kind="studied", unit=unit)
        return row.status
    if row is not None and row.status == UP.STUDIED:
        row.status, row.studied_at = UP.NOT_STARTED, None
        row.save()
        ActivityEvent.objects.create(user=user, kind="unstudied", unit=unit)
    return row.status if row is not None else UP.NOT_STARTED


def _valid_ids(ids):
    if not isinstance(ids, list) or len(ids) > MAX_IMPORT_IDS:
        raise ValueError(f"expected a list of at most {MAX_IMPORT_IDS} page ids")
    if not all(isinstance(i, str) and 0 < len(i) <= MAX_ID_LENGTH for i in ids):
        raise ValueError(f"each page id must be text of 1 to {MAX_ID_LENGTH} characters")
    return list(dict.fromkeys(ids))


@transaction.atomic
def import_browser(user, ids):
    """Bring over the units a browser had marked done. They become "studied" (never
    "passed"), no status is lowered, and ids that are not units are ignored.
    Closes the import offer. Returns {"imported", "already", "ignored"}."""
    ids = _valid_ids(ids)
    units = study.units_by_path(ids)
    rows = {r.unit_id: r for r in UP.objects.select_for_update().filter(user=user, unit__in=units.values())}
    imported = already = 0
    now = timezone.now()
    for path in ids:
        unit = units.get(path)
        if unit is None:
            continue
        row = rows.get(unit.pk)
        if row is not None and UP.RANK[row.status] >= UP.RANK[UP.STUDIED]:
            already += 1
            continue
        row = row or UP(user=user, unit=unit)
        row.status, row.studied_at, row.source = UP.STUDIED, now, "browser_import"
        row.save()
        imported += 1
    ignored = sorted(i for i in ids if i not in units)
    ActivityEvent.objects.create(user=user, kind="imported", data={"imported": imported, "already": already,
                                                                   "ignored": len(ignored)})
    accounts.mark_import_done(user)
    return {"imported": imported, "already": already, "ignored": ignored}


def dismiss_import(user):
    """"Not now": close the import offer without bringing anything over."""
    accounts.mark_import_done(user)


def course_summaries(user):
    """Courses with any progress: studied and passed counts of the course's units."""
    rows = list(UP.objects.filter(user=user, status__in=DONE).values_list("unit__course_id", "status"))
    if not rows:
        return []
    studied, passed = {}, {}
    for course_id, status in rows:
        studied[course_id] = studied.get(course_id, 0) + 1
        if status == UP.PASSED:
            passed[course_id] = passed.get(course_id, 0) + 1
    out = []
    for course, units in study.units_by_course(studied).items():
        s, total = studied[course.pk], len(units)
        out.append({"title": course.title, "path": course.path + "/index.html", "studied": s,
                    "passed": passed.get(course.pk, 0), "total": total, "percent": round(100 * s / total)})
    return out


def status_of(user, page_id):
    """The learner's status for one unit (not_started when there is no record)."""
    row = UP.objects.filter(user=user, unit__legacy_path=page_id).values_list("status", flat=True).first()
    return row or UP.NOT_STARTED


@transaction.atomic
def record_test(user, page_id, *, score, passed, attempt_id):
    """A submitted unit test (called by assessments): keeps the best score, and a
    pass makes the unit "passed". Nothing lowers a status. Returns the new status."""
    unit = study.unit_by_path(page_id)
    if unit is None:
        raise NotAUnit(page_id)
    row, _ = UP.objects.select_for_update().get_or_create(user=user, unit=unit)
    row.best_score = score if row.best_score is None else max(row.best_score, score)
    if passed and row.status != UP.PASSED:
        row.status, row.passed_at = UP.PASSED, timezone.now()
        row.studied_at = row.studied_at or row.passed_at
    row.save()
    ActivityEvent.objects.create(user=user, kind="test", unit=unit,
                                 data={"score": str(score), "passed": passed, "attempt": str(attempt_id)})
    return row.status


def recent_tests(user, n=5):
    """The last n unit tests submitted: [{title, path, score, passed, attempt, at}]."""
    out = []
    for e in ActivityEvent.objects.filter(user=user, kind="test").select_related("unit").order_by("-at")[:n]:
        out.append({"title": e.unit.title if e.unit else "", "path": e.unit.legacy_path if e.unit else "",
                    "score": e.data.get("score"), "passed": e.data.get("passed"), "attempt": e.data.get("attempt"),
                    "at": e.at})
    return out


def record_paper(user, *, title, slug, score, max_score, attempt_id):
    """An old paper sat in exam mode (called by papers), for the dashboard and the streak."""
    ActivityEvent.objects.create(user=user, kind="paper", data={
        "title": title, "slug": slug, "score": score, "max_score": max_score, "attempt": str(attempt_id)})


def recent_papers(user, n=5):
    return [dict(e.data, at=e.at) for e in ActivityEvent.objects.filter(user=user, kind="paper").order_by("-at")[:n]]


STREAK_KINDS = ("studied", "test", "paper")


def streak(user, today=None):
    """Consecutive days (Asia/Kolkata) with a unit marked studied, a unit test
    submitted or a paper sat as an exam, ending today or yesterday; a streak is not broken until a whole day
    passes without one."""
    days = {_local_date(at) for at in
            ActivityEvent.objects.filter(user=user, kind__in=STREAK_KINDS).values_list("at", flat=True)}
    day = today or _local_date(timezone.now())
    if day not in days:
        day -= timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


def last_studied(user):
    """The unit most recently marked studied, and the next unit of its course not yet
    done, as {"title", "path"} dicts (either may be None)."""
    row = (UP.objects.filter(user=user, status__in=DONE, studied_at__isnull=False)
           .select_related("unit__course").order_by("-studied_at").first())
    if row is None:
        return None, None
    done = set(done_map(user))
    course_units = study.units_by_course([row.unit.course_id]).get(row.unit.course, [])
    after = [u for u in course_units if u.order > row.unit.order and u.legacy_path not in done]
    nxt = after[0] if after else None

    def card(u):
        return {"title": u.title, "path": u.legacy_path} if u else None
    return card(row.unit), card(nxt)


def export(user):
    """This app's part of /me/export."""
    def iso(dt):
        return dt.isoformat() if dt else None
    return {
        "units": [{"page": r.unit.legacy_path, "status": r.status, "studied_at": iso(r.studied_at),
                   "passed_at": iso(r.passed_at), "best_score": str(r.best_score) if r.best_score is not None else None,
                   "source": r.source}
                  for r in UP.objects.filter(user=user).select_related("unit").order_by("unit__legacy_path")],
        "activity": [{"kind": e.kind, "page": e.unit.legacy_path if e.unit else None, "at": iso(e.at), "data": e.data}
                     for e in ActivityEvent.objects.filter(user=user).select_related("unit").order_by("at")],
    }

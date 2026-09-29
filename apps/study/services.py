"""The study app's interface. Other apps find, render and store pages only through
these functions; nothing outside this app reads or writes Unit or Page directly
(ARCHITECTURE.md §3)."""
import re

from django.conf import settings
from django.templatetags.static import static

from .models import Course, Page, Programme, Unit
from .pages import assemble, page_fields

# The site was built for https://nrstatlab.github.io/planning-for-future/. Two things
# in the stored HTML depend on that address, and both are rewritten when a page is
# served: the absolute origin in canonical and og: tags, and the few root-absolute
# paths ("/planning-for-future/assets/…", only in 404.html).
BUILT_ORIGIN = "https://nrstatlab.github.io/planning-for-future"
BUILT_BASE = "/planning-for-future/"
_BASE_IN_ATTR = re.compile(r"""(["'(])/planning-for-future/""")
UNIT_NO_RE = re.compile(r"unit(\d+)\.html$")
# The pages load MathJax 3 from a CDN; the app serves its own copy (static/vendor/mathjax),
# so formulas draw with no internet connection and the CSP names no outside host for them.
MATHJAX_CDN = re.compile(r"https://cdn\.jsdelivr\.net/npm/mathjax@3/es5/([\w.-]+\.js)")


# ---------------------------------------------------------------- reading

def find(legacy_path):
    """The Unit or Page stored at this path, or None."""
    return (Unit.objects.filter(legacy_path=legacy_path, published=True).first()
            or Page.objects.filter(legacy_path=legacy_path, published=True).first())


def titles(paths):
    """{legacy path: page title} for the stored pages among these paths."""
    paths = list(paths)
    out = dict(Page.objects.filter(legacy_path__in=paths).values_list("legacy_path", "title"))
    out.update(Unit.objects.filter(legacy_path__in=paths).values_list("legacy_path", "title"))
    return out


def exists(legacy_path):
    return (Unit.objects.filter(legacy_path=legacy_path).exists()
            or Page.objects.filter(legacy_path=legacy_path).exists())


def rewrite_for_origin(html, origin=None, base=None):
    """A stored page as served: its origin and base path for this host, and MathJax from
    the app's own copy."""
    origin = (origin or settings.SITE_ORIGIN).rstrip("/")
    base = base or settings.SITE_BASE_PATH
    if origin != BUILT_ORIGIN:
        html = html.replace(BUILT_ORIGIN, origin)
    if base != BUILT_BASE:
        html = _BASE_IN_ATTR.sub(lambda m: m.group(1) + base, html)
    return MATHJAX_CDN.sub(lambda m: static("vendor/mathjax/es5/" + m.group(1)), html)


def render_html(page):
    """The page as served: the original file, with the address rewrites above."""
    return rewrite_for_origin(assemble(page))


# ---------------------------------------------------------------- storing (import_site)

def store_site(*, programmes, courses, pages, markable, indexed):
    """Upsert programmes, courses and every page. Unchanged pages are not written.

    programmes: {slug: title}; courses: [dict]; pages: {rel: html};
    markable: {rel: (course path, order)}; indexed: set of rel.
    Returns {"created", "updated", "unchanged", "deleted"}.
    """
    counts = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    progs = {}
    for order, (slug, title) in enumerate(programmes.items()):
        progs[slug], _ = Programme.objects.update_or_create(slug=slug, defaults={"title": title, "order": order})

    by_path = {}
    for c in courses:
        by_path[c["path"]], _ = Course.objects.update_or_create(
            path=c["path"],
            defaults={"title": c["title"], "level": c["level"], "group": c["group"], "order": c["order"],
                      "programme": progs.get(c["programme"])})
    Course.objects.exclude(path__in=by_path).delete()

    def course_for(rel):
        best = max((p for p in by_path if rel.startswith(p + "/")), key=len, default=None)
        return by_path.get(best)

    existing = {u.legacy_path: u for u in Unit.objects.all()}
    existing.update({p.legacy_path: p for p in Page.objects.all()})
    for rel, text in pages.items():
        fields = page_fields(text)
        fields["indexed"] = rel in indexed
        is_unit = rel in markable
        model = Unit if is_unit else Page
        if is_unit:
            cpath, order = markable[rel]
            num = UNIT_NO_RE.search(rel)
            fields.update(course=by_path[cpath], order=order, number=int(num.group(1)) if num else None)
        else:
            fields["course"] = course_for(rel)
        old = existing.pop(rel, None)
        if old is not None and not isinstance(old, model):
            old.delete()  # a page became markable, or stopped being
            old = None
        if old is None:
            model.objects.create(legacy_path=rel, **fields)
            counts["created"] += 1
        elif (old.content_hash != fields["content_hash"] or old.indexed != fields["indexed"] or old.title != fields["title"]
              or old.course_id != (fields["course"].pk if fields["course"] else None)):
            for k, v in fields.items():
                setattr(old, k, v)
            old.save()
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    for gone in existing.values():  # pages removed from the site
        gone.delete()
        counts["deleted"] += 1
    return counts


def stored_counts():
    return {
        "courses": Course.objects.count(),
        "markable units": Unit.objects.count(),
        "indexed pages": Unit.objects.filter(indexed=True).count() + Page.objects.filter(indexed=True).count(),
        "other pages": Unit.objects.filter(indexed=False).count() + Page.objects.filter(indexed=False).count(),
    }


# ---------------------------------------------------------------- units, for progress

def unit_by_path(legacy_path):
    """The markable unit at this path (its page id), or None."""
    return Unit.objects.filter(legacy_path=legacy_path).select_related("course").first()


def units_by_path(paths):
    """{legacy path: unit} for the markable units among these paths."""
    return {u.legacy_path: u for u in Unit.objects.filter(legacy_path__in=list(paths)).select_related("course")}


def units_by_course(course_ids=None):
    """{course: [units in order]}, for every course or only these."""
    qs = Unit.objects.select_related("course").order_by("course__order", "order")
    if course_ids is not None:
        qs = qs.filter(course_id__in=list(course_ids))
    out = {}
    for u in qs:
        out.setdefault(u.course, []).append(u)
    return out


def course_home(page_id):
    """The course home a unit belongs to, e.g. statistics/sampling-theory/index.html."""
    unit = unit_by_path(page_id)
    return unit.course.path + "/index.html" if unit else None

"""Fetch the corpus SPEC.md 8a publishes on. Run this before anything else.

    uv run python scripts/fetch_corpus.py

§8a's argument for swapping in openly licensed material was that numbers
computed over files nobody else can obtain are assertions rather than evidence:
*"With a public corpus the ingest and the eval harness run anywhere and the
numbers reproduce."* That was not true until this script existed. `data/raw/` is
gitignored — the corpus is not this project's to redistribute — so a fresh clone
got an empty directory and no way to fill it, and every measurement in the repo
was unreproducible in practice while being reproducible in principle.

What it fetches: MIT OpenCourseWare 6.02, Fall 2012 — 23 lecture slide decks and
9 problem sets as published PDFs, plus a syllabus rendered from the course's
syllabus *page*, because OCW publishes syllabi as HTML and no networking course
checked publishes one as a PDF. `data/CORPUS.md` records that distinction; so
does this script, by building that one file rather than downloading it.

The material is CC BY-NC-SA 4.0 and stays so. This script downloads it for local
use; it does not relicense it.

**This scrapes a website and will break when that website changes.** It checks
what it got and fails loudly rather than leaving a half-corpus that would
silently change every measurement downstream.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://ocw.mit.edu"
COURSE = "6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012"
PAGES = {"lecture-slides": "lecture", "assignments": "problem set"}

EXPECTED_LECTURES = 23
EXPECTED_PROBLEM_SETS = 9
TIMEOUT = 120


class FetchError(RuntimeError):
    """The corpus could not be fetched completely."""


def get(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc


def resource_slugs(page: str) -> list[str]:
    body = get(f"{BASE}/courses/{COURSE}/pages/{page}/")
    found = re.findall(rf'href="/courses/{COURSE}/resources/([^"/]+)/?"', body)
    return sorted(set(found))


def pdf_url(slug: str) -> str | None:
    body = get(f"{BASE}/courses/{COURSE}/resources/{slug}/")
    match = re.search(rf'/courses/{COURSE}/[a-f0-9]{{32}}_[^"]+\.pdf', body)
    return match.group(0) if match else None


def download(url: str, target: Path) -> None:
    try:
        with urllib.request.urlopen(BASE + url, timeout=TIMEOUT) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        raise FetchError(f"could not download {url}: {exc}") from exc
    if not data.startswith(b"%PDF"):
        raise FetchError(f"{url} did not return a PDF")
    target.write_bytes(data)


def syllabus_blocks() -> list[tuple[str, str]]:
    """The syllabus page's own headings and paragraphs, in order."""
    raw = get(f"{BASE}/courses/{COURSE}/pages/syllabus/")
    starts = [m.end() for m in re.finditer(r"<h2[^>]*>\s*Syllabus\s*</h2>", raw)]
    if not starts:
        raise FetchError("the syllabus page no longer has a Syllabus heading")
    body = raw[starts[-1]:]
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", body, flags=re.S)
    cut = re.search(r"<footer|Course Info|Give Now", body)
    if cut:
        body = body[: cut.start()]

    skip = {"Calendar", "Readings", "Open Textbook", "Lecture Slides",
            "Lecture Videos", "Tutorials", "Assignments", "Exams", "Syllabus Software"}
    blocks = []
    for tag, text in re.findall(r"<(h[1-6]|p|li|td|th)[^>]*>(.*?)</\1>", body, re.S):
        clean = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
        if clean and clean not in skip:
            blocks.append((tag, clean))
    if len(blocks) < 20:
        raise FetchError(f"syllabus page yielded only {len(blocks)} blocks; layout changed?")
    return blocks


def render_syllabus(blocks: list[tuple[str, str]], target: Path) -> None:
    """Render the syllabus page to PDF, keeping OCW's own heading case.

    Reshaping the headings to suit this project's syllabus chunker would make
    the corpus prove something about the input rather than about the chunker.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate
    except ImportError as exc:  # pragma: no cover - depends on install
        raise FetchError(
            "rendering the syllabus needs reportlab. Install it with: uv sync"
        ) from exc

    ss = getSampleStyleSheet()
    head = ParagraphStyle("Sec", parent=ss["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6)
    title = ParagraphStyle("T", parent=ss["Title"], fontSize=17, spaceAfter=16)
    para = ParagraphStyle("P", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    bullet = ParagraphStyle("B", parent=para, leftIndent=18, bulletIndent=6)

    story = [Paragraph("6.02 Introduction to EECS II: Digital Communication Systems", title),
             Paragraph("Syllabus", head)]
    for tag, text in blocks:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if tag.startswith("h"):
            story.append(Paragraph(safe, head))
        elif tag == "li":
            story.append(Paragraph(safe, bullet, bulletText="•"))
        else:
            story.append(Paragraph(safe, para))
    SimpleDocTemplate(str(target), pagesize=letter, leftMargin=inch, rightMargin=inch,
                      topMargin=inch, bottomMargin=inch, title="6.02 Syllabus").build(story)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the MIT OCW 6.02 corpus.")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"MIT OpenCourseWare 6.02 (Fall 2012) -> {args.out}")
    print("CC BY-NC-SA 4.0. See data/CORPUS.md.\n")

    counts = {"lecture": 0, "problem set": 0}
    for page, prefix in PAGES.items():
        for slug in resource_slugs(page):
            url = pdf_url(slug)
            if not url:
                continue
            name = re.sub(r"^[a-f0-9]{32}_", "", url.rsplit("/", 1)[-1])
            target = args.out / f"{prefix} {name}"
            counts[prefix] += 1
            if target.exists() and not args.force:
                print(f"  have {target.name}")
                continue
            download(url, target)
            print(f"  got  {target.name}")

    syllabus = args.out / "syllabus.pdf"
    if syllabus.exists() and not args.force:
        print(f"  have {syllabus.name}")
    else:
        render_syllabus(syllabus_blocks(), syllabus)
        print(f"  made {syllabus.name}  (rendered from the syllabus page, not downloaded)")

    problems = []
    if counts["lecture"] != EXPECTED_LECTURES:
        problems.append(f"expected {EXPECTED_LECTURES} lectures, found {counts['lecture']}")
    if counts["problem set"] != EXPECTED_PROBLEM_SETS:
        problems.append(
            f"expected {EXPECTED_PROBLEM_SETS} problem sets, found {counts['problem set']}"
        )
    if problems:
        # Loudly, because a half-corpus silently changes every number downstream.
        raise FetchError(
            "the corpus is not what this project measured: "
            + "; ".join(problems)
            + ". OCW's site layout may have changed; the figures in SPEC.md "
            "describe 23 lectures, 9 problem sets and 1 syllabus."
        )

    total = len(list(args.out.glob("*.pdf")))
    print(f"\n{total} PDFs in {args.out}")
    print("Next:  uv run recall-ingest data/raw  &&  uv run recall-index")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FetchError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        sys.exit(1)

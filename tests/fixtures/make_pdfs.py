"""Generate synthetic PDFs that reproduce the structures the chunkers target.

Synthetic rather than real: the course material this project was built for is
the instructor's copyright and does not belong in a public repository. Building
the fixtures also forces the edge cases to be explicit — a same-title run, a
"(cont.)" continuation, a non-adjacent title repeat, a page with no text layer,
and a numbered line that breaks sequence — rather than hoping a real file
happens to contain them.

Runnable directly to drop the fixtures somewhere for inspection:

    uv run python tests/fixtures/make_pdfs.py data/sample
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

BOILERPLATE = "(c) Example Course, Networks 101"
TITLE_SIZE = 30
BODY_SIZE = 12
FOOTER_SIZE = 8


def _slide(
    pdf: canvas.Canvas, title: str | None, body: list[str], number: int, footer: bool = True
) -> None:
    width, height = landscape(letter)
    if title:
        pdf.setFont("Helvetica-Bold", TITLE_SIZE)
        pdf.drawString(50, height - 80, title)
    pdf.setFont("Helvetica", BODY_SIZE)
    y = height - 140
    for line in body:
        pdf.drawString(50, y, line)
        y -= 20
    if footer:
        # The real decks print the slide number trailing the footer on the same
        # line, which makes the footer unique per page unless it is removed.
        pdf.setFont("Helvetica", FOOTER_SIZE)
        pdf.drawString(50, 30, f"{BOILERPLATE} {number}")
    pdf.showPage()


def make_deck(path: Path) -> Path:
    """10 slides: a 3-slide same-title run (one marked cont.), a non-adjacent
    repeat of that title, a page with no text layer at all, a title-only
    divider slide, and a slide whose text is all one size and so has no
    title at all."""
    pdf = canvas.Canvas(str(path), pagesize=landscape(letter))
    _slide(pdf, "Introduction", ["Course overview and goals", "What we will build"], 1)
    _slide(pdf, "Web caching", ["A cache stores responses near the client"], 2)
    _slide(pdf, "Web caching", ["Hit ratio determines the saving"], 3)
    _slide(pdf, "Web caching (cont.)", ["Conditional GET revalidates a stale copy"], 4)
    _slide(pdf, None, [], 5, footer=False)  # no text layer at all
    _slide(pdf, "Routing", ["Hot potato routing hands traffic off early"], 6)
    _slide(pdf, "Web caching", ["Revisited later in the deck, deliberately"], 7)
    _slide(pdf, "Summary", ["Caching and routing both trade cost for latency"], 8)
    _slide(pdf, "Topology diagram", [], 9)  # title over a diagram: nothing to retrieve
    # No title: every line at one font size, so nothing is a heading.
    _slide(pdf, None, ["Every line on this slide is the same size",
                       "so none of them is a title",
                       "and all of them are body text"], 10)
    pdf.save()
    return path


def make_problem_sheet(path: Path) -> Path:
    """Two pages, numbered 1-3 with sub-parts, plus a line that looks numbered
    but breaks the sequence and must not open a new problem."""
    width, height = letter
    pdf = canvas.Canvas(str(path), pagesize=letter)

    pdf.setFont("Helvetica", BODY_SIZE)
    lines_p1 = [
        "Page 1 of 2",
        "CS 101 - Networks",
        "Homework 9",
        "",
        "1. A link transmits 3 MB of data at rate R. How long does it take?",
        "",
        "2. Consider two routers exchanging traffic.",
        "a) What policy does each operator choose?",
        "b) Which operator loses more than under the optimal policy?",
        "7. This line looks numbered but breaks the sequence.",
    ]
    y = height - 80
    for line in lines_p1:
        pdf.drawString(60, y, line)
        y -= 18
    pdf.showPage()

    pdf.setFont("Helvetica", BODY_SIZE)
    y = height - 80
    for line in ["Page 2 of 2", "", "3. Explain the layers of the protocol stack."]:
        pdf.drawString(60, y, line)
        y -= 18
    pdf.showPage()
    pdf.save()
    return path


def make_syllabus(path: Path) -> Path:
    """Two pages with five ALL-CAPS section headings."""
    width, height = letter
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pages = [
        [
            ("INSTRUCTOR", ["Office hours are held on Tuesday afternoons."]),
            ("COURSE ORGANIZATION", ["Weekly lectures with online sessions."]),
            ("COURSE MATERIALS", ["Slides are posted after each lecture."]),
        ],
        [
            ("ASSESSMENT METHODS AND RULES", ["Quizzes are worth 25 of the grade.",
                                              "The final exam is worth 40."]),
            ("OTHER RULES AND INFORMATION", ["Late submissions are not accepted."]),
        ],
    ]
    for page in pages:
        pdf.setFont("Helvetica", BODY_SIZE)
        y = height - 80
        for heading, body in page:
            pdf.setFont("Helvetica-Bold", BODY_SIZE)
            pdf.drawString(60, y, heading)
            y -= 20
            pdf.setFont("Helvetica", BODY_SIZE)
            for line in body:
                pdf.drawString(60, y, line)
                y -= 18
            y -= 10
        pdf.showPage()
    pdf.save()
    return path


def make_all(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "deck": make_deck(directory / "example deck.pdf"),
        "problem_sheet": make_problem_sheet(directory / "homework 9.pdf"),
        "syllabus": make_syllabus(directory / "Syllabus_example.pdf"),
    }


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample")
    for name, path in make_all(target).items():
        print(f"{name}: {path}")

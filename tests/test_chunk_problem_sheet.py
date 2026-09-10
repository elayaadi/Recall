from recall.ingestion.boilerplate import find_boilerplate
from recall.ingestion.chunkers.problem_sheet import chunk_problem_sheet
from recall.ingestion.pdf import load


def _chunks(path):
    document = load(path)
    return chunk_problem_sheet(document, find_boilerplate(document))


def test_one_chunk_per_numbered_problem(problem_sheet_path):
    assert [c.locator.problem for c in _chunks(problem_sheet_path)] == ["1", "2", "3"]


def test_sub_parts_stay_with_their_parent_problem(problem_sheet_path):
    second = _chunks(problem_sheet_path)[1]
    assert second.locator.parts == ("a", "b")
    assert "What policy does each operator choose?" in second.raw_text
    assert "Which operator loses more" in second.raw_text


def test_a_line_that_breaks_the_sequence_does_not_open_a_problem(problem_sheet_path):
    second = _chunks(problem_sheet_path)[1]
    assert "breaks the sequence" in second.raw_text


def test_digits_in_prose_do_not_split_a_problem(problem_sheet_path):
    first = _chunks(problem_sheet_path)[0]
    assert "3 MB" in first.raw_text


def test_the_page_recorded_is_where_the_problem_starts(problem_sheet_path):
    chunks = _chunks(problem_sheet_path)
    assert chunks[0].locator.pages == (1,)
    assert chunks[2].locator.pages == (2,)


def test_the_problem_number_prefixes_the_text(problem_sheet_path):
    assert _chunks(problem_sheet_path)[2].text.startswith("homework 9 — Problem 3")


def _document(tmp_path, pages):
    """A portrait PDF with the given lines on the given pages.

    Built here rather than in `make_pdfs.py` because these cases are about one
    chunker's boundaries, not about the shared corpus fixtures.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = tmp_path / "sheet.pdf"
    pdf = canvas.Canvas(str(path), pagesize=letter)
    for lines in pages:
        y = letter[1] - 80
        pdf.setFont("Helvetica", 12)
        for line in lines:
            pdf.drawString(60, y, line)
            y -= 20
        pdf.showPage()
    pdf.save()
    return load(path)


def test_a_multi_page_problem_records_every_page_it_covers(tmp_path):
    """SPEC.md 0 promises a citation resolves to a location.

    Before the 8a swap every problem fitted on one page, so recording the page
    a problem started on was indistinguishable from recording where it was. On
    MIT 6.02's sheets a problem can run thirteen pages, and all four chunks of
    ps1 were cited as page 2.
    """
    doc = _document(
        tmp_path,
        pages=[
            ["Problem 1.", "The first problem starts here."],
            ["It continues onto the second page."],
            ["And finishes on the third.", "Problem 2.", "The second problem."],
        ],
    )
    chunks = chunk_problem_sheet(doc, frozenset())

    assert [c.locator.problem for c in chunks] == ["1", "2"]
    assert chunks[0].locator.pages == (1, 2, 3)
    assert chunks[1].locator.pages == (3,)


def test_a_multi_page_problem_cites_pp_not_p(tmp_path):
    doc = _document(
        tmp_path,
        pages=[["Problem 1.", "starts"], ["continues"], ["Problem 2.", "next"]],
    )
    chunks = chunk_problem_sheet(doc, frozenset())
    assert chunks[0].locator.cite().startswith("pp.1")
    assert chunks[1].locator.cite().startswith("p.3")


def test_sub_questions_do_not_become_problems(tmp_path):
    """The defect the 8a swap exposed, at the chunker level."""
    doc = _document(
        tmp_path,
        pages=[[
            "Problem 1. Information",
            "Answer each:",
            "1. The Bofa alone?",
            "2. Yertle alone?",
            "Problem 2. Coding",
            "Explain.",
        ]],
    )
    chunks = chunk_problem_sheet(doc, frozenset())
    assert [c.locator.problem for c in chunks] == ["1", "2"]
    assert "The Bofa alone?" in chunks[0].raw_text

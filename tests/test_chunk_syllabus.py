from recall.ingestion.boilerplate import find_boilerplate
from recall.ingestion.chunkers.syllabus import chunk_syllabus
from recall.ingestion.pdf import load


def _chunks(path):
    document = load(path)
    return chunk_syllabus(document, find_boilerplate(document))


def test_one_chunk_per_all_caps_section(syllabus_path):
    assert [c.locator.title for c in _chunks(syllabus_path)] == [
        "INSTRUCTOR",
        "COURSE ORGANIZATION",
        "COURSE MATERIALS",
        "ASSESSMENT METHODS AND RULES",
        "OTHER RULES AND INFORMATION",
    ]


def test_section_body_excludes_its_own_heading(syllabus_path):
    first = _chunks(syllabus_path)[0]
    assert first.raw_text == "Office hours are held on Tuesday afternoons."


def test_sections_carry_the_page_they_start_on(syllabus_path):
    assert _chunks(syllabus_path)[3].locator.pages == (2,)


def test_the_section_name_prefixes_the_text(syllabus_path):
    assert _chunks(syllabus_path)[3].text.startswith("Syllabus_example — ASSESSMENT METHODS AND RULES")

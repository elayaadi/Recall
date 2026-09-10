"""The corpus fetcher's offline halves. SPEC.md 8c.

Nothing here touches the network. What is worth testing is the parsing and the
verification: the script scrapes a website, so the interesting failure is not
"the download broke" but "the site changed shape and we quietly fetched less
than the corpus every number in this repo describes".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_corpus import COURSE, FetchError, main  # noqa: E402
import fetch_corpus  # noqa: E402


def test_resource_slugs_are_extracted_and_deduplicated(monkeypatch):
    page = f'''
      <a href="/courses/{COURSE}/resources/lec01/">Lecture 1</a>
      <a href="/courses/{COURSE}/resources/lec01/">Lecture 1 again</a>
      <a href="/courses/{COURSE}/resources/lec02/">Lecture 2</a>
      <a href="/courses/{COURSE}/pages/syllabus/">not a resource</a>
    '''
    monkeypatch.setattr(fetch_corpus, "get", lambda url: page)
    assert fetch_corpus.resource_slugs("lecture-slides") == ["lec01", "lec02"]


def test_the_pdf_url_is_found_on_a_resource_page(monkeypatch):
    href = f"/courses/{COURSE}/{'a1'*16}_MIT6_02F12_lec01.pdf"
    monkeypatch.setattr(fetch_corpus, "get", lambda url: f'<a href="{href}">pdf</a>')
    assert fetch_corpus.pdf_url("lec01") == href


def test_a_resource_page_with_no_pdf_returns_none(monkeypatch):
    """The syllabus resource is a thumbnail image, not a PDF — it must not crash."""
    monkeypatch.setattr(fetch_corpus, "get", lambda url: '<img src="/x.jpg">')
    assert fetch_corpus.pdf_url("syllabus") is None


def test_a_download_that_is_not_a_pdf_is_refused(monkeypatch, tmp_path):
    class NotAPdf:
        def read(self): return b"<html>404</html>"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(fetch_corpus.urllib.request, "urlopen", lambda *a, **k: NotAPdf())
    with pytest.raises(FetchError, match="did not return a PDF"):
        fetch_corpus.download("/x.pdf", tmp_path / "x.pdf")


def test_a_syllabus_page_that_changed_shape_raises(monkeypatch):
    monkeypatch.setattr(fetch_corpus, "get", lambda url: "<h2>Syllabus</h2><p>one block</p>")
    with pytest.raises(FetchError, match="layout changed"):
        fetch_corpus.syllabus_blocks()


def test_a_syllabus_page_with_no_heading_raises(monkeypatch):
    monkeypatch.setattr(fetch_corpus, "get", lambda url: "<h2>Something Else</h2>")
    with pytest.raises(FetchError, match="no longer has a Syllabus heading"):
        fetch_corpus.syllabus_blocks()


def test_a_short_corpus_fails_loudly_rather_than_being_accepted(monkeypatch, tmp_path):
    """The defect worth guarding: a partial corpus changes every number silently.

    Every figure in SPEC.md describes 23 lectures and 9 problem sets. Fetching
    fewer and carrying on would leave the repo reporting measurements of a
    corpus nobody else has.
    """
    monkeypatch.setattr(fetch_corpus, "resource_slugs", lambda page: ["only-one"])
    monkeypatch.setattr(fetch_corpus, "pdf_url", lambda slug: f"/courses/x/{'a'*32}_one.pdf")
    monkeypatch.setattr(fetch_corpus, "download", lambda url, target: target.write_bytes(b"%PDF-1"))
    monkeypatch.setattr(fetch_corpus, "syllabus_blocks", lambda: [("p", "x")] * 30)
    monkeypatch.setattr(fetch_corpus, "render_syllabus", lambda b, t: t.write_bytes(b"%PDF-1"))

    with pytest.raises(FetchError) as exc:
        main(["--out", str(tmp_path)])
    assert "expected 23 lectures" in str(exc.value)
    assert "23 lectures, 9 problem sets and 1 syllabus" in str(exc.value)


def test_existing_files_are_not_refetched(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fetch_corpus, "resource_slugs",
                        lambda page: [f"s{i}" for i in range(23 if page == "lecture-slides" else 9)])
    monkeypatch.setattr(fetch_corpus, "pdf_url", lambda slug: f"/courses/x/{'a'*32}_{slug}.pdf")
    monkeypatch.setattr(fetch_corpus, "download",
                        lambda url, target: (calls.append(url), target.write_bytes(b"%PDF-1")))
    monkeypatch.setattr(fetch_corpus, "syllabus_blocks", lambda: [("p", "x")] * 30)
    monkeypatch.setattr(fetch_corpus, "render_syllabus", lambda b, t: t.write_bytes(b"%PDF-1"))

    assert main(["--out", str(tmp_path)]) == 0
    first = len(calls)
    assert main(["--out", str(tmp_path)]) == 0
    assert len(calls) == first, "a second run re-downloaded files it already had"

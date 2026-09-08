from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fixtures.make_pdfs import make_all  # noqa: E402


@pytest.fixture(scope="session")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Synthetic PDFs, built once per test session."""
    return make_all(tmp_path_factory.mktemp("corpus"))


@pytest.fixture(scope="session")
def deck_path(corpus: dict[str, Path]) -> Path:
    return corpus["deck"]


@pytest.fixture(scope="session")
def problem_sheet_path(corpus: dict[str, Path]) -> Path:
    return corpus["problem_sheet"]


@pytest.fixture(scope="session")
def syllabus_path(corpus: dict[str, Path]) -> Path:
    return corpus["syllabus"]

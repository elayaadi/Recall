"""The protocol's two jobs: reading a response, and failing usefully.

The transport half is here because of a defect the rest of the suite passed
over. A read timeout is a `TimeoutError`, not a `urllib.error.URLError`, so
catching only the latter let it escape `recall-answer` as a traceback — which
SPEC.md 5b forbids in as many words. The suite was green; running the command
was what found it. These tests pin every way the call can fail to a
`GenerationError`, without opening a socket.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from recall.generation.generate import (
    GenerationError,
    LocalGenerator,
    make_generator,
    parse_response,
)

SCHEMA: dict = {"type": "object"}


def raising(exc):
    def _open(*args, **kwargs):
        raise exc
    return _open


def test_a_well_formed_response_parses(monkeypatch):
    text, claims, abstained, reason = parse_response(
        json.dumps(
            {
                "answer": "a",
                "claims": [{"text": "c", "chunk_ids": ["x"]}],
                "abstained": False,
                "reason": "",
            }
        )
    )
    assert (text, abstained, reason) == ("a", False, "")
    assert claims[0].chunk_ids == ("x",)


@pytest.mark.parametrize(
    "raw, fragment",
    [
        ("not json", "not JSON"),
        ("[1, 2]", "not an object"),
        (json.dumps({"claims": [], "abstained": False}), "'answer'"),
        (json.dumps({"answer": "a", "abstained": False}), "'claims'"),
        (json.dumps({"answer": "a", "claims": [], "abstained": "no"}), "'abstained'"),
        (json.dumps({"answer": "a", "claims": ["x"], "abstained": False}), "not an object"),
        (
            json.dumps({"answer": "a", "claims": [{"chunk_ids": ["x"]}], "abstained": False}),
            "no text",
        ),
        (
            json.dumps({"answer": "a", "claims": [{"text": "c", "chunk_ids": "x"}], "abstained": False}),
            "chunk_ids",
        ),
    ],
)
def test_every_malformed_shape_is_a_generation_error(raw, fragment):
    with pytest.raises(GenerationError) as exc:
        parse_response(raw)
    assert fragment in str(exc.value)


def test_a_missing_reason_defaults_to_empty_rather_than_failing():
    """`reason` is only read when the model abstains, so absence is not an error."""
    _, _, _, reason = parse_response(
        json.dumps({"answer": "a", "claims": [], "abstained": False})
    )
    assert reason == ""


def test_a_read_timeout_becomes_a_generation_error(monkeypatch):
    """The defect: TimeoutError is not a URLError, and escaped as a traceback."""
    monkeypatch.setattr(urllib.request, "urlopen", raising(TimeoutError()))
    with pytest.raises(GenerationError) as exc:
        LocalGenerator("m", timeout=7).complete("p", SCHEMA)
    assert "within 7s" in str(exc.value)


def test_an_unreachable_server_becomes_a_generation_error(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", raising(urllib.error.URLError("refused"))
    )
    with pytest.raises(GenerationError) as exc:
        LocalGenerator("m").complete("p", SCHEMA)
    assert "could not reach Ollama" in str(exc.value)


def test_an_http_error_names_the_model_to_pull(monkeypatch):
    error = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    monkeypatch.setattr(error, "read", lambda: b'{"error":"model not found"}')
    monkeypatch.setattr(urllib.request, "urlopen", raising(error))

    with pytest.raises(GenerationError) as exc:
        LocalGenerator("some-model").complete("p", SCHEMA)
    assert "HTTP 404" in str(exc.value)
    assert "ollama pull some-model" in str(exc.value)


def test_the_generator_reports_the_model_as_its_name():
    """5e: an answer must record exactly what produced it."""
    assert LocalGenerator("qwen2.5:7b-instruct").name == "qwen2.5:7b-instruct"


def test_a_deferred_hosted_generator_is_refused_rather_than_guessed():
    """SPEC.md 5a defers it to the end of the project; 8 carries the trigger."""
    with pytest.raises(ValueError) as exc:
        make_generator("hosted")
    assert "deferred" in str(exc.value)


def test_the_model_and_timeout_survive_make_generator():
    generator = make_generator(model="gemma3:4b", timeout=42)
    assert generator.name == "gemma3:4b"
    assert generator._timeout == 42

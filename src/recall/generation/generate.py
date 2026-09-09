"""Generation behind one interface, the way SPEC.md 3a did for embedding.

The protocol here is doing a different job than the `Embedder` protocol did.
3a kept a close call open; 5a expects the local/hosted gap to be wide and uses
the protocol to keep the credential-free path working while module 6 measures
how wide. That is why the local implementation is the default even though it is
the one expected to score worse.

The interface is **blocking, not streaming**: 5c's check needs the whole answer
before it can verify anything, so a streaming interface would buffer to the same
place. Streaming is additive to this if module 7 wants it.

Ollama is reached over plain HTTP with the standard library rather than through
a client package. It is one POST to localhost, and the repo already prefers a
dependency it can see the whole of — the same reasoning 3b applied to storage.

The hosted implementation is deferred to the end of the project — SPEC.md 5a
records the deferral and 8 carries the trigger. It adds nothing to this module
beyond another class, so the shape here does not change when it lands. Until it
does, module 6 measures the local path alone and reports no delta, which 5a
states outright rather than leaving its description of one standing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol, Sequence, runtime_checkable

from .models import Claim

LOCAL = "local"

# A starting value, not a measured choice. Module 6 compares candidates; this is
# what the module is developed against in the meantime, and it is a constructor
# argument so that comparison does not require editing code.
LOCAL_MODEL = "qwen2.5:7b-instruct"
LOCAL_HOST = "http://127.0.0.1:11434"

# Deterministic output, so that re-running the eval set measures a change to the
# system rather than the model's sampling noise.
TEMPERATURE = 0.0

# Generous, because the local path runs on CPU and a slow answer is a result
# while a spurious timeout is a lost one.
TIMEOUT_SECONDS = 180


class GenerationError(RuntimeError):
    """The model produced nothing usable.

    SPEC.md 5b makes this a first-class outcome rather than an error path
    assumed not to be taken: malformed output is surfaced, never coerced into
    an answer and never reported as a refusal the model did not make.
    """


@runtime_checkable
class Generator(Protocol):
    """What generation is allowed to assume about a model."""

    @property
    def name(self) -> str:
        """Identifies the model on every answer it produces."""

    def complete(self, prompt: str, schema: dict[str, Any]) -> str:
        """Return the model's raw response text, expected to satisfy `schema`."""


def parse_response(raw: str) -> tuple[str, list[Claim], bool, str]:
    """Turn the model's raw output into the pieces of an `Answer`.

    Every field is checked rather than trusted. The schema in `prompt.py`
    constrains this on a backend that enforces it, and 5b records that the
    default backend is the one least able to — so a shape error here is an
    expected outcome on the default path, not a defensive nicety.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"response was not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise GenerationError(f"response was {type(data).__name__}, not an object")

    for field, kind in (("answer", str), ("abstained", bool), ("claims", list)):
        if field not in data:
            raise GenerationError(f"response has no {field!r}")
        if not isinstance(data[field], kind):
            raise GenerationError(
                f"{field!r} was {type(data[field]).__name__}, not {kind.__name__}"
            )

    claims: list[Claim] = []
    for i, item in enumerate(data["claims"]):
        if not isinstance(item, dict):
            raise GenerationError(f"claim {i} was {type(item).__name__}, not an object")
        text, ids = item.get("text"), item.get("chunk_ids")
        if not isinstance(text, str):
            raise GenerationError(f"claim {i} has no text")
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise GenerationError(f"claim {i} has no list of chunk_ids")
        claims.append(Claim(text=text, chunk_ids=tuple(ids)))

    reason = data.get("reason", "")
    return data["answer"], claims, data["abstained"], reason if isinstance(reason, str) else ""


class LocalGenerator:
    """A model served by Ollama on this machine, over its HTTP API.

    Nothing is imported and no socket is opened until `complete` is called, so
    importing this module — which the CLI and the tests both do — stays free.
    """

    def __init__(
        self,
        model: str = LOCAL_MODEL,
        *,
        host: str = LOCAL_HOST,
        temperature: float = TEMPERATURE,
        timeout: int = TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._temperature = temperature
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._model

    def complete(self, prompt: str, schema: dict[str, Any]) -> str:
        body = json.dumps(
            {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "format": schema,
                "stream": False,
                "options": {"temperature": self._temperature},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip()
            raise GenerationError(
                f"Ollama returned HTTP {exc.code}: {detail or exc.reason}. "
                f"If the model is not pulled: ollama pull {self._model}"
            ) from exc
        except TimeoutError as exc:
            # A read timeout is a TimeoutError, not a URLError, so catching only
            # the latter let it escape as a traceback — which 5b forbids. Found
            # by running the command, not by the suite.
            raise GenerationError(
                f"Ollama did not respond within {self._timeout}s. A larger model "
                f"generating schema-constrained JSON on CPU can take longer than "
                f"this; raise it with --timeout."
            ) from exc
        except OSError as exc:
            raise GenerationError(
                f"could not reach Ollama at {self._host} ({exc}). "
                f"Start it with: ollama serve — and pull the model with: "
                f"ollama pull {self._model}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise GenerationError(f"Ollama returned non-JSON: {exc}") from exc

        content = payload.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise GenerationError("Ollama returned an empty message")
        return content


def make_generator(
    kind: str = LOCAL, *, model: str | None = None, timeout: int = TIMEOUT_SECONDS
) -> Generator:
    if kind != LOCAL:
        raise ValueError(
            f"unknown generator {kind!r}. The hosted implementation is deferred to "
            f"the end of the project (SPEC.md 5a, trigger in 8), so only "
            f"{LOCAL!r} exists."
        )
    return LocalGenerator(model or LOCAL_MODEL, timeout=timeout)


def generator_names() -> Sequence[str]:
    return (LOCAL,)

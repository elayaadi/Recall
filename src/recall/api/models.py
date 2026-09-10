"""Request and response shapes. SPEC.md 7b.

The four outcomes §5d built are a **discriminated union** here rather than a
string field on one flat object. CLAUDE.md forbids collapsing them into a
boolean, and a union is what makes that structural instead of a convention: a
client switching on `outcome` gets the fields that outcome actually carries, and
a response that claimed to be `answered` with no claims would not serialise.

That is the specific thing FastAPI was adopted for in §7a — validating this
shape at the boundary, so a malformed outcome cannot leave the process.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, description="the question to search for")
    k: int = Field(default=5, ge=1, le=50)
    doc_type: str | None = Field(default=None, description="deck | problem_sheet | syllabus")
    source_file: str | None = None


class Hit(BaseModel):
    """One passage. Citations is a list because §4d merges duplicates.

    A collapsed hit stands for the same passage in several places, and flattening
    it back to one location would discard exactly what §4d exists to preserve.
    """

    score: float
    chunk_id: str
    text: str
    citations: list[str]


class SearchResponse(BaseModel):
    query: str
    abstained: bool
    reason: str = ""
    hits: list[Hit] = []
    collapsed: int = 0


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=50)


class Claim(BaseModel):
    text: str
    citations: list[str]


class Answered(BaseModel):
    outcome: Literal["answered"]
    text: str
    claims: list[Claim]
    generator: str
    dropped: int = Field(default=0, description="claims §5c's check removed")


class Refused(BaseModel):
    """A refusal is a successful response: the request was understood.

    Three distinct outcomes share this shape and stay distinguishable by the
    discriminator — `no_passages` is §4b's threshold, `model_abstained` is the
    model's own judgement, `unverified` is §5c's check failing. §6 scores them
    separately and so should a client.
    """

    outcome: Literal["no_passages", "model_abstained", "unverified"]
    reason: str
    generator: str


AnswerResponse = Annotated[Union[Answered, Refused], Field(discriminator="outcome")]


class Health(BaseModel):
    status: Literal["ok"]
    entries: int
    embedder: str
    retriever: dict
    generation_configured: bool
    corpus_notice: str

"""Keep a chunk inside the embedder's window. SPEC.md 2b, amended.

`bge-base-en-v1.5` truncates at 512 tokens without raising anything, so text
past that point in a chunk is not ranked badly — it is not represented at all.
On the §8a corpus that was 29% of every token in the corpus, and 91% of the
largest chunk. §2b's rule that a problem keeps its sub-parts was written against
documents where this could not happen.

Two passes, in this order, because the first preserves meaning and the second
only preserves size:

1. **Split at internal sub-items** — lettered parts, or the numbered
   sub-questions MIT 6.02 uses instead of them. Boundaries the document itself
   provides.
2. **Window whatever is still too long**, with an overlap so a sentence
   straddling a boundary survives in one of the pieces.

The second pass exists because measurement said the first is not enough: 19 of
the 29 oversized chunks have no internal structure to split on at all.

The bound is in **characters, not tokens**, so that ingestion keeps knowing
nothing about which embedder will be used — the conversion is a measured 3.30
characters per token against bge, recorded in §2b. It is a property of the
embedder, so it is an argument with an uncalibrated default and never a constant
read at a call site, exactly as §4e requires of the retrieval thresholds.
"""

from __future__ import annotations

from ..structure import sub_item_indices

# ~1,688 characters is the measured 512-token window on this corpus. The default
# sits under it rather than on it, because chars-per-token varies by passage and
# a chunk that is a little too short costs nothing while one a little too long
# loses its tail silently. Uncalibrated: module 6 is what sets it.
UNCALIBRATED_MAX_CHARS = 1600

# One line, so a sentence split across a window boundary survives whole in one
# of the two pieces.
DEFAULT_OVERLAP_LINES = 1

Located = list[tuple[int, str]]


def _size(block: Located) -> int:
    return len("\n".join(line for _, line in block))


def _window(block: Located, max_chars: int, overlap_lines: int) -> list[Located]:
    """Fixed-size windows over lines, with overlap. The fallback, not the plan."""
    out: list[Located] = []
    start = 0
    while start < len(block):
        end = start
        size = 0
        while end < len(block):
            size += len(block[end][1]) + 1
            if size > max_chars and end > start:
                break
            end += 1
        out.append(block[start:end])
        if end >= len(block):
            break
        start = max(end - overlap_lines, start + 1)
    return out


def bounded_blocks(
    located: Located,
    *,
    max_chars: int = UNCALIBRATED_MAX_CHARS,
    overlap_lines: int = DEFAULT_OVERLAP_LINES,
) -> list[Located]:
    """Split `(page, line)` pairs into blocks that each fit the window.

    A block that already fits comes back untouched and alone, so a corpus like
    CS447's — where almost nothing exceeds the bound — is unaffected by this
    existing at all.
    """
    if not located or _size(located) <= max_chars:
        return [located] if located else []

    lines = [line for _, line in located]
    cuts = sub_item_indices(lines)
    pieces: list[Located] = []
    if len(cuts) >= 2:
        # Anything before the first sub-item stays with it: a problem's stem is
        # not answerable on its own, and neither is its first part without it.
        bounds = [0] + [c for c in cuts if c > 0] + [len(located)]
        bounds = sorted(set(bounds))
        pieces = [located[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]
    else:
        pieces = [located]

    out: list[Located] = []
    for piece in pieces:
        if _size(piece) <= max_chars:
            out.append(piece)
        else:
            out.extend(_window(piece, max_chars, overlap_lines))
    return [p for p in out if p]

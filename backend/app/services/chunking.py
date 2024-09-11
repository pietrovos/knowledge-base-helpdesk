"""Structure-aware chunking for Markdown and plain text.

Chunks never cross a heading boundary, carry their heading path ("Refunds > Exceptions"), and
are exact slices of the normalized source (`text == source[char_start:char_end]`), so the UI can
show any cited passage in its original context.
"""

import re
from dataclasses import dataclass

MAX_CHARS = 1000
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkSpan:
    ordinal: int
    heading: str
    text: str
    char_start: int
    char_end: int

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")


def _blocks(source: str, markdown: bool) -> list[tuple[int, int, str]]:
    """Paragraph blocks as (start, end, heading_path). Heading lines are not part of any block."""
    blocks: list[tuple[int, int, str]] = []
    path: list[tuple[int, str]] = []
    start: int | None = None
    end = 0
    in_fence = False
    pos = 0

    def flush() -> None:
        nonlocal start
        if start is not None:
            blocks.append((start, end, " > ".join(t for _, t in path)))
            start = None

    for line in source.split("\n"):
        line_start, line_end = pos, pos + len(line)
        pos = line_end + 1
        if markdown and _FENCE.match(line):
            in_fence = not in_fence
        heading = _HEADING.match(line) if markdown and not in_fence else None
        if heading:
            flush()
            level, title = len(heading.group(1)), heading.group(2).strip()
            path = [(lvl, t) for lvl, t in path if lvl < level] + [(level, title)]
        elif not line.strip() and not in_fence:
            flush()
        else:
            if start is None:
                start = line_start
            end = line_end
    flush()
    return blocks


def _split_long(source: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split an oversized block on sentence boundaries, hard-splitting runaway sentences."""
    pieces: list[tuple[int, int]] = []
    cur_start = start
    last_break = None
    for m in _SENTENCE_END.finditer(source, start, end):
        if m.start() - cur_start > MAX_CHARS and last_break is not None:
            pieces.append((cur_start, last_break[0]))
            cur_start = last_break[1]
        last_break = (m.start(), m.end())
    tail = (cur_start, end)
    if last_break and tail[1] - tail[0] > MAX_CHARS and last_break[0] > cur_start:
        pieces.append((cur_start, last_break[0]))
        tail = (last_break[1], end)
    pieces.append(tail)
    out: list[tuple[int, int]] = []
    for s, e in pieces:
        while e - s > MAX_CHARS:
            out.append((s, s + MAX_CHARS))
            s += MAX_CHARS
        out.append((s, e))
    return out


def chunk_document(source: str, *, markdown: bool) -> list[ChunkSpan]:
    spans: list[tuple[int, int, str]] = []
    for start, end, heading in _blocks(source, markdown):
        parts = _split_long(source, start, end) if end - start > MAX_CHARS else [(start, end)]
        for s, e in parts:
            prev = spans[-1] if spans else None
            # Pack consecutive paragraphs of the same section while they fit.
            if prev and prev[2] == heading and e - prev[0] <= MAX_CHARS:
                spans[-1] = (prev[0], e, heading)
            else:
                spans.append((s, e, heading))
    return [
        ChunkSpan(ordinal=i, heading=h, text=source[s:e], char_start=s, char_end=e)
        for i, (s, e, h) in enumerate(spans)
        if source[s:e].strip()
    ]

"""Citation markers: `[1042]` after a claim, where 1042 is a chunk ID.

The validator is deliberately strict: a marker is valid only if that chunk was retrieved for
this exact request. Anything else (hallucinated IDs, IDs from earlier turns, chunks the user
can't read) is removed from the text and reported.
"""

import re
from dataclasses import dataclass

# [12] or grouped [12, 34]
_MARKER = re.compile(r"\[(\d{1,18}(?:\s*,\s*\d{1,18})*)\]")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True)
class CitationCheck:
    text: str  # reply with only valid markers, normalized to [a][b]
    cited_ids: list[int]  # valid, in order of first appearance
    invalid_ids: list[int]  # removed


def _tidy(text: str) -> str:
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return "\n".join(_MULTI_SPACE.sub(" ", line).rstrip() for line in text.split("\n"))


def validate(reply: str, allowed_ids: set[int]) -> CitationCheck:
    cited: list[int] = []
    invalid: list[int] = []

    def repl(m: re.Match) -> str:
        ids = [int(x) for x in m.group(1).split(",")]
        keep = []
        for i in ids:
            if i in allowed_ids:
                keep.append(i)
                if i not in cited:
                    cited.append(i)
            elif i not in invalid:
                invalid.append(i)
        return "".join(f"[{i}]" for i in keep)

    return CitationCheck(text=_tidy(_MARKER.sub(repl, reply)), cited_ids=cited, invalid_ids=invalid)


def markers(text: str) -> list[int]:
    out: list[int] = []
    for m in _MARKER.finditer(text):
        out.extend(int(x) for x in m.group(1).split(","))
    return out


def strip_markers(text: str) -> str:
    """What the customer receives: the same text without internal chunk references."""
    return _tidy(_MARKER.sub("", text)).strip()

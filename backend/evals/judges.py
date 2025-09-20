"""Faithfulness judges: is every claim in an answer supported by the passages it cites?

- LexicalJudge (default, free, deterministic): a claim is supported when most of its content
  words appear in the passages cited for it. A cheap proxy that catches invented numbers and
  facts from nowhere, but it can't recognise paraphrase.
- ClaudeJudge: asks Claude to split the answer into claims and check each against the cited
  passages. Costs money; opt in with --judge claude.
"""

import re
import time
from dataclasses import dataclass

from pydantic import BaseModel

from app.services.citations import markers, strip_markers
from app.services.embeddings import tokenize

_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_BOILERPLATE = re.compile(
    r"^(hi|hello|dear|thanks|thank you|let me know|best|kind regards|happy to help)\b", re.I
)


@dataclass
class Verdict:
    claims: int
    supported: int
    unsupported_claims: list[str]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    @property
    def score(self) -> float | None:
        return self.supported / self.claims if self.claims else None


_TRAILING_MARKERS = re.compile(r"([.!?])\s*((?:\[\d+(?:\s*,\s*\d+)*\])+)")


def claims_of(reply: str) -> list[str]:
    # "Claim. [12]" → "Claim [12]." so a marker stays with the sentence it supports.
    reply = _TRAILING_MARKERS.sub(r" \2\1", reply)
    out = []
    for s in _SENT.split(reply):
        s = s.strip()
        if not s or _BOILERPLATE.match(s):
            continue
        if len(tokenize(strip_markers(s))) >= 3:
            out.append(s)
    return out


class LexicalJudge:
    name = "lexical"

    def judge(self, reply: str, sources: dict[int, str]) -> Verdict:
        claims = claims_of(reply)
        unsupported = []
        for claim in claims:
            cited = [sources[i] for i in markers(claim) if i in sources] or list(sources.values())
            words = set(tokenize(strip_markers(claim)))
            evidence = set(tokenize(" ".join(cited)))
            if not words or len(words & evidence) / len(words) < 0.5:
                unsupported.append(strip_markers(claim))
        return Verdict(len(claims), len(claims) - len(unsupported), unsupported)


class _Claim(BaseModel):
    claim: str
    supported: bool


class _Judgement(BaseModel):
    claims: list[_Claim]


JUDGE_PROMPT = """You check customer-support answers for faithfulness to their sources.

Split the answer into its factual claims (skip greetings, sign-offs and offers of further help). For each claim, decide whether the cited sources state it or directly imply it. A claim with a number, time frame, price or policy detail that the sources don't contain is unsupported. Judge only against the sources below, never against general knowledge."""


class ClaudeJudge:
    name = "claude"

    def __init__(self, model: str) -> None:
        import anthropic

        self.model = model
        self._client = anthropic.Anthropic(max_retries=2, timeout=120.0)

    def judge(self, reply: str, sources: dict[int, str]) -> Verdict:
        src = "\n\n".join(f'<source id="{i}">\n{t}\n</source>' for i, t in sources.items())
        started = time.perf_counter()
        r = self._client.messages.parse(
            model=self.model,
            max_tokens=8000,
            system=JUDGE_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"<sources>\n{src}\n</sources>\n\n<answer>\n{reply}\n</answer>",
                }
            ],
            output_format=_Judgement,
            output_config={"effort": "low"},
        )
        latency = int((time.perf_counter() - started) * 1000)
        if r.stop_reason == "refusal" or r.parsed_output is None:
            return Verdict(
                0,
                0,
                ["judge declined or returned no verdict"],
                r.usage.input_tokens,
                r.usage.output_tokens,
                latency,
            )
        claims = r.parsed_output.claims
        return Verdict(
            len(claims),
            sum(c.supported for c in claims),
            [c.claim for c in claims if not c.supported],
            r.usage.input_tokens,
            r.usage.output_tokens,
            latency,
        )

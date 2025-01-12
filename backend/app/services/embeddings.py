"""Embedding providers behind one interface.

`name` is stored alongside every vector so different models never share a vector space.
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class Embedder(Protocol):
    name: str
    dim: int
    # Below this cosine similarity, the best match is treated as unrelated to the question.
    # Calibrated per model on the eval set (see evals/).
    min_similarity: float

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "of",
        "on",
        "or",
        "our",
        "so",
        "that",
        "the",
        "their",
        "there",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    ]
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for t in _TOKEN.findall(text.lower()):
        if t in _STOP:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        tokens.append(t)
    return tokens


class FakeEmbedder:
    """Deterministic feature-hashing embedder: no network, no model download.

    Lexically similar texts get similar vectors, which is enough for retrieval tests and
    for running the eval suite offline.
    """

    name = "fake-hash-384"
    dim = 384
    min_similarity = 0.15

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = tokenize(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
        for f in feats:
            h = hashlib.blake2b(f.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            v[idx] += 1.0 if h[4] & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class LocalEmbedder:
    """fastembed (ONNX) model; runs on CPU with no API key. Default provider."""

    dim = 384
    min_similarity = 0.6

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self.name = f"local:{model_name}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


class VoyageEmbedder:
    dim = 1024
    min_similarity = 0.35

    def __init__(self, model: str, api_key: str | None) -> None:
        import voyageai

        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY is required for EMBEDDING_PROVIDER=voyage")
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self.name = f"voyage:{model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 128):
            res = self._client.embed(texts[i : i + 128], model=self._model, input_type="document")
            out.extend(res.embeddings)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._client.embed([text], model=self._model, input_type="query").embeddings[0]


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "fake":
        return FakeEmbedder()
    if s.embedding_provider == "voyage":
        return VoyageEmbedder(s.voyage_model, s.voyage_api_key)
    return LocalEmbedder(s.local_embedding_model)

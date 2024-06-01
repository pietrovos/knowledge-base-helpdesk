import math

from app.services.embeddings import FakeEmbedder, tokenize


def cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_is_deterministic_and_normalized():
    e = FakeEmbedder()
    a, b = e.embed_documents(["Refunds are issued within 14 days"] * 2)
    assert a == b
    assert len(a) == e.dim
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)


def test_fake_embedder_ranks_lexical_overlap_higher():
    e = FakeEmbedder()
    q = e.embed_query("how long do refunds take")
    refund = e.embed_documents(["Refunds are processed within 14 days of the request."])[0]
    vpn = e.embed_documents(["Connect to the VPN before accessing the admin console."])[0]
    assert cos(q, refund) > cos(q, vpn)


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("The refunds are for orders") == ["refund", "order"]

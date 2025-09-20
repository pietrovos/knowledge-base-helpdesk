from evals.judges import LexicalJudge, claims_of

SOURCES = {
    1: "Refunds are issued within 5 business days after inspection.",
    2: "Gift cards are non-refundable.",
}


def test_markers_after_the_period_stay_with_their_sentence():
    assert claims_of(
        "Hi Sam,\n\nRefunds take 5 business days after inspection. [1] Gift cards are non-refundable. [2]"
    ) == [
        "Refunds take 5 business days after inspection [1].",
        "Gift cards are non-refundable [2].",
    ]


def test_supported_and_unsupported_claims():
    v = LexicalJudge().judge(
        "Refunds are issued within 5 business days after inspection [1]. We also price match competitors forever [2].",
        SOURCES,
    )
    assert (v.claims, v.supported) == (2, 1)
    assert v.unsupported_claims == ["We also price match competitors forever."]


def test_greetings_are_not_claims():
    assert (
        claims_of(
            "Hi Casey,\n\nThanks for reaching out.\n\nLet me know if there's anything else I can help with."
        )
        == []
    )

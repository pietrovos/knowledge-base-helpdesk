from app.services.chunking import MAX_CHARS, chunk_document, normalize

DOC = """# Refund Policy

Customers may request a refund within 30 days of purchase.

Refunds go back to the original payment method.

## Exceptions

Gift cards are non-refundable.

```
# not a heading
```

## Processing time

Refunds are processed within 5 business days.
"""


def test_chunks_follow_headings_and_are_exact_slices():
    chunks = chunk_document(DOC, markdown=True)
    assert [c.heading for c in chunks] == [
        "Refund Policy",
        "Refund Policy > Exceptions",
        "Refund Policy > Processing time",
    ]
    for c in chunks:
        assert DOC[c.char_start : c.char_end] == c.text
    assert "original payment method" in chunks[0].text  # paragraphs in one section are packed
    assert "# not a heading" in chunks[1].text  # fenced code isn't parsed as a heading


def test_heading_levels_reset_path():
    doc = "# A\n\n## B\n\ntext b\n\n# C\n\ntext c\n"
    assert [c.heading for c in chunk_document(doc, markdown=True)] == ["A > B", "C"]


def test_plain_text_ignores_hash_lines():
    chunks = chunk_document("# not markdown\nline two\n\nsecond para", markdown=False)
    assert all(c.heading == "" for c in chunks)
    assert chunks[0].text.startswith("# not markdown")


def test_long_paragraphs_split_on_sentences_within_limit():
    sentence = "This sentence is about warranty coverage for hardware devices. "
    doc = "# W\n\n" + sentence * 60
    chunks = chunk_document(doc, markdown=True)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= MAX_CHARS
        assert doc[c.char_start : c.char_end] == c.text
    assert all(c.text.rstrip().endswith(".") for c in chunks)


def test_runaway_text_without_punctuation_is_hard_split():
    doc = "x" * (MAX_CHARS * 2 + 10)
    chunks = chunk_document(doc, markdown=False)
    assert [len(c.text) for c in chunks] == [MAX_CHARS, MAX_CHARS, 10]


def test_normalize_line_endings():
    assert normalize("a\r\nb\rc") == "a\nb\nc"


def test_empty_document_has_no_chunks():
    assert chunk_document("\n\n   \n", markdown=True) == []

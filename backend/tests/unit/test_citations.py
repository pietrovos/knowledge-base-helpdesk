from app.services.citations import markers, strip_markers, validate


def test_valid_markers_are_kept_and_ordered():
    r = validate("Refunds take 5 days [12]. Gift cards are final [13][12].", {12, 13})
    assert r.text == "Refunds take 5 days [12]. Gift cards are final [13][12]."
    assert r.cited_ids == [12, 13]
    assert r.invalid_ids == []


def test_unretrieved_ids_are_removed_and_reported():
    r = validate("We price match forever [999]. Refunds take 5 days [12].", {12})
    assert r.text == "We price match forever. Refunds take 5 days [12]."
    assert r.invalid_ids == [999]
    assert r.cited_ids == [12]


def test_grouped_markers_are_split_and_filtered():
    r = validate("Shipping is free [12, 77, 13].", {12, 13})
    assert r.text == "Shipping is free [12][13]."
    assert r.invalid_ids == [77]


def test_no_markers_means_no_citations():
    r = validate("Sure, we can do that!", {1, 2})
    assert r.cited_ids == [] and r.invalid_ids == []


def test_non_numeric_brackets_untouched():
    r = validate("See [the policy] and [12].", {12})
    assert r.text == "See [the policy] and [12]."


def test_strip_markers_for_customer():
    assert (
        strip_markers("Hi Sam,\n\nRefunds take 5 days [12][13]. Thanks [9].")
        == "Hi Sam,\n\nRefunds take 5 days. Thanks."
    )


def test_markers_lists_all_ids():
    assert markers("a [1] b [2, 3] c [1]") == [1, 2, 3, 1]

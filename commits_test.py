from commits import merge_titles, dedupe_texts


def test_merge_titles():
    # returns common substring stripped
    assert (
        merge_titles(
            [
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 abc",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 def",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 xyz",
            ],
        )
        == "D\u00e9cret n\u00b02023-198 du 23 mars 2023"
    )
    # returns both if no common substring
    assert merge_titles(["a", "b"]) == "a & b"
    # removes art. prefix and junk
    assert (
        merge_titles(
            [
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2",
            ]
        )
        == "D\u00e9cret n\u00b02023-198 du 23 mars 2023"
    )


def test_dedupe_texts():
    # returns unique if twice the exact same
    assert dedupe_texts([("a", "b"), ("a", "b")]) == [("a", "b")]
    # returns both if different cids
    assert dedupe_texts([("a", "b"), ("c", "d")]) == [("a", "b"), ("c", "d")]
    # merge titles if same cid
    t1 = "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1"
    t2 = "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2"
    assert dedupe_texts(
        [
            (
                "JORFTEXT000047340945",
                t1,
            ),
            (
                "JORFTEXT000047340945",
                t2,
            ),
        ],
    ) == [("JORFTEXT000047340945", merge_titles([t1, t2]))]

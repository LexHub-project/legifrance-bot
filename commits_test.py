from commits import TextCidAndTitle, merge_titles, dedupe_modifs


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


def test_dedupe_modifs():
    # returns unique if twice the exact same
    assert dedupe_modifs(
        [
            TextCidAndTitle(textCid="a", textTitle="b"),
            TextCidAndTitle(textCid="a", textTitle="b"),
        ]
    ) == [TextCidAndTitle(textCid="a", textTitle="b")]
    # returns both if different cids
    assert dedupe_modifs(
        [
            TextCidAndTitle(textCid="a", textTitle="b"),
            TextCidAndTitle(textCid="c", textTitle="d"),
        ]
    ) == [
        TextCidAndTitle(textCid="a", textTitle="b"),
        TextCidAndTitle(textCid="c", textTitle="d"),
    ]
    # merge titles if same cid
    t1 = "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1"
    t2 = "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2"
    assert dedupe_modifs(
        [
            TextCidAndTitle(
                textCid="JORFTEXT000047340945",
                textTitle=t1,
            ),
            TextCidAndTitle(
                textCid="JORFTEXT000047340945",
                textTitle=t2,
            ),
        ],
    ) == [
        TextCidAndTitle(
            textCid="JORFTEXT000047340945", textTitle=merge_titles([t1, t2])
        )
    ]

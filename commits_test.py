import pytest

from commits import TextCidAndTitle, _clean_html, _dedupe_modified_by, _merge_titles


@pytest.mark.parametrize(
    "inp,expected",
    [
        # returns common substring stripped
        (
            [
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 abc",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 def",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 xyz",
            ],
            "D\u00e9cret n\u00b02023-198 du 23 mars 2023",
        ),
        # returns both if no common substring
        (["a", "b"], "a & b"),
        # removes art. prefix and junk
        (
            [
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1",
                "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2",
            ],
            "D\u00e9cret n\u00b02023-198 du 23 mars 2023",
        ),
    ],
)
def test_merge_titles(inp, expected):
    assert _merge_titles(inp) == expected


@pytest.mark.parametrize(
    "inp,expected",
    [
        # returns unique if twice the exact same
        (
            [
                TextCidAndTitle(cid="a", title="b"),
                TextCidAndTitle(cid="a", title="b"),
            ],
            [TextCidAndTitle(cid="a", title="b")],
        ),
        # returns both if different cids
        (
            [
                TextCidAndTitle(cid="a", title="b"),
                TextCidAndTitle(cid="c", title="d"),
            ],
            [
                TextCidAndTitle(cid="a", title="b"),
                TextCidAndTitle(cid="c", title="d"),
            ],
        ),
        # merge titles if same cid
        (
            [
                TextCidAndTitle(
                    cid="JORFTEXT000047340945",
                    title="D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1",
                ),
                TextCidAndTitle(
                    cid="JORFTEXT000047340945",
                    title="D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2",
                ),
            ],
            [
                TextCidAndTitle(
                    cid="JORFTEXT000047340945",
                    title=_merge_titles(
                        [
                            "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 1",
                            "D\u00e9cret n\u00b02023-198 du 23 mars 2023 - art. 2",
                        ]
                    ),
                )
            ],
        ),
    ],
)
def test_dedupe_modified_by(inp, expected):
    assert list(_dedupe_modified_by(inp)) == expected


def test_clean_article_html_double_p():
    assert (
        _clean_html(
            """
<p></p><p><br/>Lorsque le</p>
""",
        )
        == """<p><br/>Lorsque le</p>"""
    )


def test_clean_article_html_strip():
    assert (
        _clean_html(
            """
    Le marin est tenu
""",
        )
        == """Le marin est tenu"""
    )

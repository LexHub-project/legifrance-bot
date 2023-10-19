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


def test_clean_article_html_strip_multiline():
    assert (
        _clean_html(
            """
    Aucune avance de salaires ne peut être faite au marin qu'en présence et sous le contrôle de l'autorité maritime.
    Les avances, quel qu'en soit le montant, ne sont imputables sur les salaires ou parts à échoir au marin que jusqu'à concurrence de :
 trois mois de salaires pour les voiliers effectuant une navigation au long cours dépassant le cap Horn ou le cap de Bonne-Espérance ; deux mois pour les voiliers de long cours ne dépassant pas les caps, et un mois pour toutes les autres navigations. Les règlements prévus à l'article 34 détermineront pour la navigation de grande pêche, le montant des avances qui peuvent être accordées aux marins. La partie de l'avance dépassant les sommes ainsi fixées reste acquise au marin à titre de prime d'engagement ou avance perdue.
    Toutefois, des avances peuvent être accordées, au-delà des maxima prévus au paragraphe précédent, sous forme de délégation.
""",
        )
        == """Aucune avance de salaires ne peut être faite au marin qu'en présence et sous le contrôle de l'autorité maritime.

Les avances, quel qu'en soit le montant, ne sont imputables sur les salaires ou parts à échoir au marin que jusqu'à concurrence de :

trois mois de salaires pour les voiliers effectuant une navigation au long cours dépassant le cap Horn ou le cap de Bonne-Espérance ; deux mois pour les voiliers de long cours ne dépassant pas les caps, et un mois pour toutes les autres navigations. Les règlements prévus à l'article 34 détermineront pour la navigation de grande pêche, le montant des avances qui peuvent être accordées aux marins. La partie de l'avance dépassant les sommes ainsi fixées reste acquise au marin à titre de prime d'engagement ou avance perdue.

Toutefois, des avances peuvent être accordées, au-delà des maxima prévus au paragraphe précédent, sous forme de délégation."""
    )

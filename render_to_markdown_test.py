from render_to_markdown import _clean_article_html, _is_tm_active


def test_clean_article_html():
    assert (
        _clean_article_html(
            """
<p></p><p><br/>
Lorsque les cinq territoires mentionnés à l'article <a href='/affichCodeArticle.do?cidTexte=LEGITEXT000044595989&idArticle=LEGIARTI000044597999&dateTexte=&categorieLien=cid' title='Code des impositions sur les biens et services - art. L112-4 (V)'>L. 112-4 </a>sont regardés comme distincts pour une imposition donnée, sont assimilés à des territoires tiers au sens de l'article <a href='/affichCodeArticle.do?cidTexte=LEGITEXT000044595989&idArticle=LEGIARTI000044597993&dateTexte=&categorieLien=cid' title='Code des impositions sur les biens et services - art. L112-2 (V)'>L. 112-2 </a>:<br/><br/>
1° Chacun de ces territoires vis-à-vis des autres ;<br/><br/>
2° Les territoires des autres Etats membres de l'Union européenne vis-à-vis des territoires mentionnés aux 2° à 5° de l'article L. 112-4.</p><p></p>
""",
            {
                "LEGITEXT000044595989": {
                    "LEGIARTI000044597999": "article-l112-4",
                    "LEGIARTI000044597993": "article-l112-2",
                }
            },
        )
        == """
<p><br/>
Lorsque les cinq territoires mentionnés à l'article <a href='#article-l112-4' title='Code des impositions sur les biens et services - art. L112-4 (V)'>L. 112-4 </a>sont regardés comme distincts pour une imposition donnée, sont assimilés à des territoires tiers au sens de l'article <a href='#article-l112-2' title='Code des impositions sur les biens et services - art. L112-2 (V)'>L. 112-2 </a>:<br/><br/>
1° Chacun de ces territoires vis-à-vis des autres ;<br/><br/>
2° Les territoires des autres Etats membres de l'Union européenne vis-à-vis des territoires mentionnés aux 2° à 5° de l'article L. 112-4.</p>
"""
    )


def test_is_tm_active():
    tm = {"dateDebut": "1926-05-12", "dateFin": "1971-01-02", "articles": [0, 1]}
    assert _is_tm_active(tm, 0)
    assert not _is_tm_active(tm, 1697451195000)
    assert not _is_tm_active(tm, -5364619761000)
    assert _is_tm_active({}, 1697451194000)

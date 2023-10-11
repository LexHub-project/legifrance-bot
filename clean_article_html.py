def clean_article_html(html: str, text_to_cid_to_anchor: dict[str, dict[str, str]]):
    html = html.replace("<p></p>", "")

    for text_cid, article_cid_to_anchor in text_to_cid_to_anchor.items():
        for article_cid, anchor in article_cid_to_anchor.items():
            look_for = f"/affichCodeArticle.do?cidTexte={article_cid}&idArticle={text_cid}&dateTexte=&categorieLien=cid"
            replace = f"#{anchor}"

            html = html.replace(look_for, replace)

    return html

import io
import re
from datetime import datetime
from typing import Generator

from commits import ArticleJSON, CodeJSON, Commit, StateAtCommit
from tqdm import tqdm


def _header(level: int, text: str) -> str:
    # TODO, for now limited to level 6
    return ("#" * min(level, 6)) + " " + text


def _article_to_header_text(article: ArticleJSON) -> str:
    return f"Article {article['num']}"


def _header_to_anchor(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


def _last_text(commits: list[Commit], cid: str) -> str | None:
    for c in reversed(commits):
        if cid in c.article_changes:
            return c.article_changes[cid]

    # There is no text yet
    return None


def _clean_article_html(
    html: str | None, text_to_cid_to_anchor: dict[str, dict[str, str]]
):
    if html is None:
        return None

    html = html.replace("<p></p>", "")

    look_for = r"/affichCodeArticle\.do\?cidTexte=(LEGI[A-Z0-9]+)&idArticle=(LEGI[A-Z0-9]+)&dateTexte=&categorieLien=cid"
    matches = re.finditer(look_for, html)
    for match in matches:
        text_cid = match.group(1)
        article_cid = match.group(2)
        try:
            anchor = text_to_cid_to_anchor[text_cid][article_cid]
            replace = f"#{anchor}"
            html = html.replace(match.group(0), replace)
        except KeyError:
            pass

    return html.strip()


def _has_been_created(tm: CodeJSON, timestamp: int) -> bool:
    if tm.get("nature", None) == "CODE":
        return True

    return timestamp >= int(
        datetime.strptime(tm["dateDebut"], "%Y-%m-%d").timestamp() * 1000
    )


def _is_article_en_vigeur(article: ArticleJSON, timestamp: int) -> bool:
    # ["etat"] != "ABROGE"
    return True


def _tm_to_markdown(
    tm: CodeJSON,
    commits: list[Commit],
    file,
    level=1,
) -> None:
    # TODO
    if tm["etat"] == "ABROGE" or not _has_been_created(tm, commits[-1].timestamp):
        return

    print(_header(level, tm["title"]), file=file)

    for article in tm["articles"]:
        if _is_article_en_vigeur(article, commits[-1].timestamp):
            text = _last_text(commits, article["cid"])

            if text is not None:
                print(_header(level + 1, _article_to_header_text(article)), file=file)
                print(
                    text,
                    file=file,
                )
                print("\n", file=file)

    for section in tm["sections"]:
        _tm_to_markdown(section, commits, file=file, level=level + 1)

    if "commentaire" in tm and tm["commentaire"] is not None:
        print(tm["commentaire"], file=file)
    # assert False, tm
    # TODO


def generate_markdown(
    code_tms: list[CodeJSON], articles: list[ArticleJSON], sorted_commits: list[Commit]
) -> Generator[StateAtCommit, None, None]:
    text_to_cid_to_anchor = {
        tm["cid"]: {
            article["listArticle"][0]["cid"]: _header_to_anchor(
                _article_to_header_text(article["listArticle"][0])
            )
            for article in articles
        }
        for tm in code_tms
    }

    cleaned_commits = [
        Commit(
            timestamp=c.timestamp,
            modified_by=c.modified_by,
            article_changes={
                article_cid: _clean_article_html(text, text_to_cid_to_anchor)
                for article_cid, text in c.article_changes.items()
            },
        )
        for c in tqdm(sorted_commits, "Cleaning HTML")
    ]

    for i in tqdm(range(0, len(cleaned_commits) - 1), desc="Processing"):
        full_code_texts = []
        for tm in code_tms:
            f = io.StringIO()

            print("=" * 6 + f" {i} " + "=" * 6)
            print(cleaned_commits[i])
            print("\n\n")
            _tm_to_markdown(tm, cleaned_commits[: (i + 1)], file=f)
            full_code_texts.append((tm["title"], f.getvalue()))

        yield StateAtCommit(
            title=cleaned_commits[i].title,
            timestamp=cleaned_commits[i].timestamp,
            full_code_texts=full_code_texts,
        )

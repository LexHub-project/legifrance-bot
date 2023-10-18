import io
import re
from datetime import datetime
from typing import Generator
from copy import deepcopy

from tqdm import tqdm

from commits import ArticleJSON, CodeJSON, Commit, StateAtCommit


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


def _is_tm_in_force(tm: CodeJSON, timestamp: int) -> bool:
    if tm.get("nature", None) == "CODE":
        return True  # root
    start_timestamp = int(
        datetime.fromisoformat(f"{tm['dateDebut']} 00:00").timestamp() * 1000
    )
    end_timestamp = int(
        datetime.fromisoformat(f"{tm['dateFin']} 23:59").timestamp() * 1000
    )

    return start_timestamp <= timestamp <= end_timestamp


def _tm_to_markdown(
    tm: CodeJSON,
    commits: list[Commit],
    file,
    level=1,
) -> None:
    # TODO
    if not _is_tm_in_force(tm, commits[-1].timestamp):
        return

    print(_header(level, tm["title"]), file=file)

    for article in tm["articles"]:
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


def _get_section_by_path(tm: CodeJSON, path: [str]) -> CodeJSON:
    if len(path) == 0:
        return tm

    for section in tm["sections"]:
        if section["cid"] == path[0]:
            return _get_section_by_path(section, path[1:])

    raise KeyError(f"Section {path} not found in tm")


def _format_path(titresTm):
    return "/".join([t["cid"] for t in titresTm])


def _test_paths(tm: CodeJSON, paths: [str], article_cid: str) -> ([str], [str]):
    valid = []
    missing = []

    for path in paths:
        try:
            section = _get_section_by_path(tm, path.split("/"))
            found = [a for a in section["articles"] if a["cid"] == article_cid]
            assert len(found) == 1
            valid.append(path)
        except AssertionError:
            missing.append(path)

    return valid, missing


def _fix_tm_multiple_paths(tm: CodeJSON, articles: [ArticleJSON]) -> CodeJSON:
    fixed_tm = deepcopy(tm)

    for article in articles:
        v_0 = article["listArticle"][0]
        if v_0["textTitles"][0]["cid"] == tm["cid"]:
            paths = {
                _format_path(v["context"]["titresTM"]) for v in article["listArticle"]
            }
            if len(paths) > 1:
                valid, missing = _test_paths(tm, paths, v_0["cid"])

                # print(
                #     f"🟡 {len(paths)} paths for {v_0['num']}, {v_0['cid']} 🟢 {len(valid)} 🔴 {len(missing)}"
                # )
                article_ref = next(
                    a
                    for a in _get_section_by_path(tm, valid[0].split("/"))["articles"]
                    if a["cid"] == v_0["cid"]
                )
                for m in missing:
                    _get_section_by_path(fixed_tm, m.split("/"))["articles"] = sorted(
                        _get_section_by_path(fixed_tm, m.split("/"))["articles"]
                        + [article_ref],
                        key=lambda x: x["num"],
                    )
    return fixed_tm


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
            fixed_tm = _fix_tm_multiple_paths(tm, articles)
            f = io.StringIO()

            print("=" * 6 + f" {i} " + "=" * 6)
            print(cleaned_commits[i])
            print("\n\n")
            _tm_to_markdown(fixed_tm, cleaned_commits[: (i + 1)], file=f)
            full_code_texts.append((tm["title"], f.getvalue()))

        yield StateAtCommit(
            title=cleaned_commits[i].title,
            timestamp=cleaned_commits[i].timestamp,
            full_code_texts=full_code_texts,
        )

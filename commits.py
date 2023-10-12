from dataclasses import dataclass
from typing import Tuple

ArticleJSON = dict
CodeJSON = dict


@dataclass
class Commit:
    title: str
    timestamp: int
    article_changes: dict[str, str]


@dataclass
class StateAtCommit:
    title: str
    timestamp: int
    full_code_texts: list[Tuple[str, str]]


def _commits_for_article(article: ArticleJSON) -> dict[str, Commit]:
    commits = {}
    for version in article["listArticle"]:
        # TODO: not sure what to do with MODIFIE_MORT_NE
        if version["etat"] != "MODIFIE_MORT_NE":
            modifs = version["lienModifications"]
            timestamp: int = version["dateDebut"]
            textCids: list[str] = sorted({m["textCid"] for m in modifs})

            if len(textCids) == 0:
                textCids = ["???"]
                # TODO

            commitId = f"{timestamp}-{'-'.join(textCids)}"

            # TODO
            # TODO add nota?
            commitTitle = "Modifications par " + " & ".join(
                {
                    m["textTitle"] if m["textTitle"] is not None else "?TODO?"
                    for m in modifs
                }
            )
            text = version["texteHtml"]

            assert (
                commitId not in commits
            ), f"cid: {version['cid']} commitId: {commitId}"
            commits[commitId] = Commit(
                title=commitTitle,
                timestamp=timestamp,
                article_changes={version["cid"]: text},
            )

    return commits


def _merge_commits(all_commits: list[dict[str, Commit]]) -> dict[str, Commit]:
    merged: dict[str, Commit] = {}
    for partial in all_commits:
        for commit_id, c in partial.items():
            if commit_id in merged:
                assert merged[commit_id].timestamp == c.timestamp
                # TODO: humans ...
                # assert merged[commit_id].title == c.title, merged[commit_id].title  + " !== " + c.title

                for article_cid, text in c.article_changes.items():
                    assert article_cid not in merged[commit_id].article_changes, (
                        commit_id,
                        article_cid,
                        text,
                    )
                    merged[commit_id].article_changes[article_cid] = text

            else:
                merged[commit_id] = c

    return merged


def get_commits(articles: list[ArticleJSON]) -> list[Commit]:
    all_commits = [_commits_for_article(a) for a in articles]
    merged = _merge_commits(all_commits)
    return sorted(merged.values(), key=lambda c: c.timestamp)

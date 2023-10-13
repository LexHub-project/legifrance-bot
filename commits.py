from dataclasses import dataclass
from typing import Tuple
from difflib import SequenceMatcher
import re

ArticleJSON = dict
CodeJSON = dict


def merge_titles(titles: list[str]) -> str:
    if len(titles) == 1:
        cleaned = re.sub(r"-?\s?art(icle)?\.?", "", titles[0])
        return cleaned.strip()
    t1, t2 = titles[0], titles[1]
    match = SequenceMatcher(None, t1, t2).find_longest_match()
    if match.size == 0:
        return t1 + " & " + merge_titles(titles[1:])
    return merge_titles([t1[match.a : match.a + match.size]] + titles[2:])


def dedupe_texts(texts: list[Tuple[str, str]]) -> list[Tuple[str, str]]:
    deduped = {}
    for textCid, textTitle in texts:
        if textCid in deduped.keys():
            deduped[textCid] = merge_titles([deduped[textCid], textTitle])
        else:
            deduped[textCid] = textTitle

    return list(deduped.items())


@dataclass
class Commit:
    title: str
    texts: list[Tuple[str, str]]  # [(textCid, textTitle)]
    timestamp: int
    article_changes: dict[str, str]

    def __post_init__(self):
        self.build_title()

    def build_title(self):
        self.title = "Modifications par " + " & ".join([t[1] for t in self.texts])

    def merge(self, other: "Commit"):
        assert self.timestamp == other.timestamp
        self.text = dedupe_texts(self.texts + other.texts)

        for article_cid, text in other.article_changes.items():
            assert article_cid not in self.article_changes, (
                article_cid,
                text,
            )
            self.article_changes[article_cid] = text

        self.build_title()


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
            texts = [(m["textCid"], m["textTitle"]) for m in modifs]

            if len(textCids) == 0:
                textCids = ["???"]
                # TODO

            commitId = f"{timestamp}-{'-'.join(sorted(textCids))}"

            # TODO
            # TODO add nota?
            commitTitle = "Modifications par " + " & ".join(
                sorted(
                    {
                        m["textTitle"] if m["textTitle"] is not None else "?TODO?"
                        for m in modifs
                    }
                )
            )
            text = version["texteHtml"]

            assert (
                commitId not in commits
            ), f"cid: {version['cid']} commitId: {commitId}"
            commits[commitId] = Commit(
                title=commitTitle,
                timestamp=timestamp,
                article_changes={version["cid"]: text},
                texts=texts,
            )

    return commits


def _merge_commits(all_commits: list[dict[str, Commit]]) -> dict[str, Commit]:
    merged: dict[str, Commit] = {}
    for partial in all_commits:
        for commit_id, c in partial.items():
            if commit_id in merged:
                merged[commit_id].merge(c)

            else:
                merged[commit_id] = c

    return merged


def get_commits(articles: list[ArticleJSON]) -> list[Commit]:
    all_commits = [_commits_for_article(a) for a in articles]
    merged = _merge_commits(all_commits)
    return sorted(merged.values(), key=lambda c: c.timestamp)

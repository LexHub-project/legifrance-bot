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


def dedupe_modifs(modifs: list[Tuple[str, str]]) -> list[Tuple[str, str]]:
    deduped = {}
    for textCid, textTitle in modifs:
        if textCid in deduped.keys():
            deduped[textCid] = merge_titles([deduped[textCid], textTitle])
        else:
            deduped[textCid] = textTitle

    return list(deduped.items())


@dataclass
class Commit:
    modifs: list[Tuple[str, str]]  # [(textCid, textTitle)]
    timestamp: int
    article_changes: dict[str, str]

    @property
    def title(self):
        return "Modifications par " + " & ".join([t[1] for t in self.modifs])


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
            timestamp: int = version["dateDebut"]
            modifs = [
                (lm["textCid"], lm["textTitle"]) for lm in version["lienModifications"]
            ]
            textCids: list[str] = sorted(
                {m["textCid"] for m in version["lienModifications"]}
            )

            if len(textCids) == 0:
                textCids = ["???"]
                # TODO

            commitId = f"{timestamp}-{'-'.join(sorted(textCids))}"

            text = version["texteHtml"]

            assert (
                commitId not in commits
            ), f"cid: {version['cid']} commitId: {commitId}"
            commits[commitId] = Commit(
                timestamp=timestamp,
                article_changes={version["cid"]: text},
                modifs=modifs,
            )

    return commits


def _merge_commits(all_commits: list[dict[str, Commit]]) -> dict[str, Commit]:
    merged: dict[str, Commit] = {}
    for partial in all_commits:
        for commit_id, c in partial.items():
            if commit_id in merged:
                assert merged[commit_id].timestamp == c.timestamp
                for article_cid, text in c.article_changes.items():
                    assert article_cid not in merged[commit_id].article_changes, (
                        article_cid,
                        text,
                    )
                    merged[commit_id].article_changes[article_cid] = text
                merged[commit_id].text = dedupe_modifs(
                    merged[commit_id].modifs + c.modifs
                )
            else:
                merged[commit_id] = c

    return merged


def get_commits(articles: list[ArticleJSON]) -> list[Commit]:
    all_commits = [_commits_for_article(a) for a in articles]
    merged = _merge_commits(all_commits)
    return sorted(merged.values(), key=lambda c: c.timestamp)

import itertools
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Generator

ArticleJSON = dict
CodeJSON = dict


@dataclass
class TextCidAndTitle:
    cid: str
    title: str


empty_text_cid_and_title = TextCidAndTitle(
    cid="", title="un texte d’une portée générale"
)


@dataclass
class Commit:
    modified_by: list[TextCidAndTitle]
    timestamp: int

    # None means abrogated
    article_changes: dict[str, str | None]

    @property
    def title(self):
        return "Modifications par " + " & ".join([t.title for t in self.modified_by])

    @property
    def merge_id(self) -> str:
        modified_by_cids: list[str] = sorted({m.cid for m in self.modified_by})

        assert len(modified_by_cids) > 0

        return f"{self.timestamp}-{'-'.join(modified_by_cids)}"


def _merge_titles(titles: list[str]) -> str:
    if len(titles) == 1:
        cleaned = re.sub(r"-?\s?art(icle)?\.?", "", titles[0])
        return cleaned.strip()
    t1, t2 = titles[0], titles[1]
    match = SequenceMatcher(None, t1, t2).find_longest_match()
    if match.size == 0:
        return t1 + " & " + _merge_titles(titles[1:])
    return _merge_titles([t1[match.a : match.a + match.size]] + titles[2:])


def _dedupe_modified_by(
    modified_by: list[TextCidAndTitle],
) -> Generator[TextCidAndTitle, None, None]:
    sorted_by_cid = sorted(modified_by, key=lambda m: m.cid)

    for cid, group in itertools.groupby(sorted_by_cid, key=lambda m: m.cid):
        yield TextCidAndTitle(
            cid=cid, title=_merge_titles(list({m.title for m in group}))
        )


def _commits_for_article(article: ArticleJSON) -> Generator[Commit, None, None]:
    for version in article["listArticle"]:
        if version["etat"] != "MODIFIE_MORT_NE":
            timestamp_start: int = version["dateDebut"]
            timestamp_end: int = version["dateFin"]
            if timestamp_start == timestamp_end:
                timestamp_end += 1

            modified_by = [
                TextCidAndTitle(cid=lm["textCid"], title=lm["textTitle"])
                for lm in version["lienModifications"]
                # if
            ]
            if len(modified_by) == 0:
                modified_by = [empty_text_cid_and_title]

            # TODO: 2 commits in 1 version? What about other states
            # TRANSFERE	51
            # ABROGE_DIFF	38
            # PERIME

            yield Commit(
                timestamp=timestamp_start,
                modified_by=modified_by,
                article_changes={version["cid"]: version["texteHtml"]},
            )

            if version["etat"] == "ABROGE":
                yield Commit(
                    timestamp=timestamp_end,
                    modified_by=modified_by,
                    article_changes={version["cid"]: None},
                )


def _merge_commits(all_commits: list[Commit]) -> Generator[Commit, None, None]:
    sorted_by_id = sorted(all_commits, key=lambda c: c.merge_id)

    for _, group in itertools.groupby(sorted_by_id, key=lambda c: c.merge_id):
        to_merge = list(group)

        timestamps = {c.timestamp for c in to_merge}
        assert len(timestamps) == 1
        timestamp = timestamps.pop()

        modified_by = list(
            _dedupe_modified_by([m for c in to_merge for m in c.modified_by])
        )

        article_changes: dict[str, str | None] = {}
        for c in to_merge:
            for cid, text in c.article_changes.items():
                assert (
                    cid not in article_changes
                ), f"{cid} already changed in commit {article_changes}"

                article_changes[cid] = text

        yield Commit(
            timestamp=timestamp,
            modified_by=modified_by,
            article_changes=article_changes,
        )


def _clean_html(html: str | None) -> str | None:
    if html is None:
        return None

    return html.replace("<p></p>", "").strip()


def _clean_commits(commits: list[Commit]):
    for commit in commits:
        for cid in commit.article_changes:
            commit.article_changes[cid] = _clean_html(commit.article_changes[cid])


def get_commits(articles: list[ArticleJSON]) -> list[Commit]:
    commits = [c for a in articles for c in _commits_for_article(a)]
    commits = sorted(_merge_commits(commits), key=lambda c: c.timestamp)

    _clean_commits(commits)

    return commits

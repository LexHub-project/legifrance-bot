import itertools
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Generator, Tuple

ArticleJSON = dict
CodeJSON = dict
CodeListJSON = list[dict]


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


@dataclass
class TextCidAndTitle:
    cid: str
    title: str

    def __post_init__(self):
        if self.cid is None:
            self.cid = ""
        if self.title is None:
            self.title = ""


def _version_uri(version: dict):
    first_titles = {}

    # TODO titles have a validity period ?
    for t in version["context"]["titresTM"]:
        if t["xPath"] not in first_titles:
            first_titles[t["xPath"]] = t["titre"]

    titles: list[str] = [version["textTitles"][0]["titre"]] + [
        t for _, t in sorted(first_titles.items(), key=lambda i: i[0])
    ]

    trunacted = [t[:255] for t in titles]

    file_name = f"{slugify(version['num'])}.md"
    return "/".join([slugify(t) for t in trunacted] + [file_name])


Uri = str
Cid = str
DEFAULT_COMMIT_MESSAGE = "Modifié par un texte d'une portée générale"


@dataclass
class Commit:
    modified_by: list[TextCidAndTitle]
    timestamp: int

    # None means abrogated
    article_changes: dict[Cid, Tuple[Uri, str | None]]

    @property
    def title(self):
        return (
            "Modifications par "
            + " & ".join(sorted({t.title for t in self.modified_by}))
            if len(self.modified_by) > 0
            else DEFAULT_COMMIT_MESSAGE
        )

    @property
    def merge_id(self) -> str:
        modified_by_cids: list[str] = sorted({m.cid for m in self.modified_by})
        return f"{self.timestamp}-{'-'.join(modified_by_cids)}"


def _merge_titles(titles: list[str]) -> str:
    if len(titles) == 0:
        return ""
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
            cid=cid, title=_merge_titles(sorted(list({m.title for m in group})))
        )


END_TIME = 32472144000000


ARTICLES_THAT_NEED_TO_BE_RESORTED = {
    "LEGIARTI000006295155",
    "LEGIARTI000006296297",
    "LEGIARTI000006315989",
    "LEGIARTI000006346140",
    "LEGIARTI000006346820",
    "LEGIARTI000006347017",
    "LEGIARTI000006347020",
    "LEGIARTI000006348294",
    "LEGIARTI000006349185",
    "LEGIARTI000006349241",
    "LEGIARTI000006349245",
}

ALLOWED_WITH_VERSION_SORTING_NOT_MATCHING_TIMESTAMP = {
    "LEGIARTI000006301265",
    "LEGIARTI000006354138",
    "LEGIARTI000006354149",
    "LEGIARTI000006410087",
    "LEGIARTI000006418954",
    "LEGIARTI000006449852",
    "LEGIARTI000006556514",
    "LEGIARTI000006654207",
    "LEGIARTI000006840894",
}


def sorted_versions(article: ArticleJSON):
    versions = list(
        filter(lambda v: v["etat"] != "MODIFIE_MORT_NE", article["listArticle"])
    )
    cid = versions[0]["cid"]

    sorted_by_version = sorted(
        versions,
        key=lambda v: (float(v["versionArticle"]), v["dateFin"], v["dateDebut"]),
        reverse=True,
    )
    sorted_by_timestamp = sorted(
        versions,
        key=lambda v: (v["dateFin"], v["dateDebut"], float(v["versionArticle"])),
        reverse=True,
    )

    if cid in ARTICLES_THAT_NEED_TO_BE_RESORTED:
        assert sorted_by_version == sorted_by_timestamp

        return sorted_by_timestamp

    # if versions != sorted_by_version != sorted_by_timestamp:
    #     print(
    #         "foobar "
    #         + str(
    #             (
    #                 cid,
    #                 [v["id"] for v in sorted_by_timestamp],
    #             )
    #         )
    #     )

    # if not (
    #     cid in ALLOWED_WITH_VERSION_SORTING_NOT_MATCHING_TIMESTAMP
    #     or has_duplicate_versions
    #     or sorted_by_version == sorted_by_timestamp
    # ):
    #     print("order of versions doesn't match timestamps: " + cid)
    return sorted_by_timestamp


def _begin(v):
    return v["dateDebut"] + 1 if v["dateDebut"] != v["dateFin"] else v["dateDebut"]


def _end(v):
    end = v["dateFin"] if v["dateDebut"] != v["dateFin"] else v["dateFin"] + 1

    if end <= _begin(v):
        end = _begin(v) + 1

        # if v["id"] not in VERSIONS_WITH_END_BEFORE_BEGIN:
        #     print("end < begin, id: " + v["id"])

    return end


def _commits_for_article(article: ArticleJSON) -> Generator[Commit, None, None]:
    """
    Generates commits from an article. The datamodel of legifrance has versions
    with states. That proved hard to work with. Instead we rebuild changes over
    time. We assert the state match the assumtpions we have linked to timing.
    In other words, we look at time, not state of a version.
    """

    ALLOW_LIST_END_DATE_NOT_ABROGATED = {
        "LEGIARTI000006313581",
        "LEGIARTI000048183284",
        "LEGIARTI000006595289",
        "LEGIARTI000006595291",
        "LEGIARTI000006811763",
        "LEGIARTI000006595293",
        "LEGIARTI000006595299",
        "LEGIARTI000006598952",
        "LEGIARTI000024391416",
        "LEGIARTI000006810235",
        "LEGIARTI000006811763",
        "LEGIARTI000018496248",
        "LEGIARTI000018496250",
        "LEGIARTI000018496254",
        "LEGIARTI000021710041",
        "LEGIARTI000021853229",
        "LEGIARTI000021853231",
        "LEGIARTI000023245726",
        "LEGIARTI000006688358",
        "LEGIARTI000006692951",
        "LEGIARTI000006918472",
        "LEGIARTI000042501924",
        "LEGIARTI000044598833",
        "LEGIARTI000025025824",
        "LEGIARTI000048391647",
    }

    last_commit_begin: int = END_TIME
    i = 0

    versions = sorted_versions(article)
    assert len(versions) > 0, article
    cid = versions[0]["cid"]
    uri = _version_uri(versions[0])

    if _end(versions[0]) != END_TIME:
        # assert (
        #     versions[0]["etat"]
        #     in {
        #         "ABROGE",
        #         "ABROGE_DIFF",
        #         "PERIME",
        #         "ANNULE",
        #         "TRANSFERE",
        #     }
        #     or cid in ALLOW_LIST_END_DATE_NOT_ABROGATED
        # ), f"cid: {cid} etat: {versions[0]['etat']}" # TODO conflict has end date / not abrogated

        yield Commit(
            timestamp=_end(versions[0]),
            modified_by=[
                TextCidAndTitle(cid=lm["textCid"], title=lm["textTitle"])
                for lm in versions[0]["lienModifications"]
            ],
            article_changes={cid: (uri, None)},
        )

        last_commit_begin = _end(versions[0])

    while i < len(versions):
        v = versions[i]
        uri = _version_uri(v)

        assert _begin(v) < _end(v)

        if last_commit_begin <= _begin(v) < _end(v):
            # Ignore version
            i += 1
        elif _end(v) - last_commit_begin >= -1:
            # delta = _end(v) - last_commit_begin
            # if delta >= 100 and cid not in ALLOW_LIST_OVERLAP:
            #     # TODO
            #     print(f"overlap but not in list: {cid}")
            # assert (
            #     delta < 100
            # ), f"{cid} {time} We tolerate very small overlaps due to changes valid only for a day."

            modified_by = [
                TextCidAndTitle(cid=lm["textCid"], title=lm["textTitle"])
                for lm in v["lienModifications"]
            ]

            html = f"# Article {v['num']}\n" + (
                v["texteHtml"]
                if v["notaHtml"] == ""
                else v["texteHtml"] + "<br/><br/><i>NOTA:" + v["notaHtml"] + "</i>"
            )

            yield Commit(
                timestamp=_begin(v),
                modified_by=modified_by,
                article_changes={cid: (uri, html)},
            )

            last_commit_begin = _begin(v)
            i += 1

        else:
            # Gap in time between versions. TODO come up with something better
            yield Commit(
                timestamp=_end(v),
                modified_by=[],
                article_changes={
                    cid: (
                        uri,
                        f"# Article {v['num']}\n⚠️Missing data from [legifrance](https://www.legifrance.gouv.fr/codes/article_lc/{cid})⚠️",
                    )
                },
            )

            last_commit_begin = _end(v)


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

        article_changes: dict[str, Tuple[Uri, str | None]] = {}
        for c in to_merge:
            for cid, (uri, html) in c.article_changes.items():
                assert (
                    cid not in article_changes
                ), f"several commits change {cid} ({uri}) at timestamp {timestamp}"

                article_changes[cid] = (uri, html)

        yield Commit(
            timestamp=timestamp,
            modified_by=modified_by,
            article_changes=article_changes,
        )


def _clean_html(html: str | None) -> str | None:
    if html is None:
        return None

    html = html.replace("<p></p>", "")

    lines = html.strip().split("\n")

    return "\n\n".join([line.strip() for line in lines])


def _clean_commits(commits: list[Commit]):
    for commit in commits:
        for cid, (uri, text) in commit.article_changes.items():
            commit.article_changes[cid] = (uri, _clean_html(text))


def get_commits(articles: list[ArticleJSON]) -> list[Commit]:
    commits = [c for a in articles for c in _commits_for_article(a)]
    commits = sorted(_merge_commits(commits), key=lambda c: c.timestamp)

    _clean_commits(commits)

    return commits

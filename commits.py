import itertools
import re
import unicodedata
from collections import OrderedDict
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


def _dedupe(arr: list[str]):
    return list(OrderedDict.fromkeys(arr))


def _version_uri(version: dict):
    titles: list[str] = [version["textTitles"][0]["titre"]] + [
        t["titre"] for t in version["context"]["titresTM"]
    ]
    file_name = f"{slugify(version['num'])}.md"
    return "/".join(_dedupe([slugify(t) for t in titles] + [file_name]))


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
            "Modifications par " + " & ".join([t.title for t in self.modified_by])
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
            cid=cid, title=_merge_titles(list({m.title for m in group}))
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

VERSIONS_WITH_END_BEFORE_BEGIN = {
    "LEGIARTI000037201762",
    "LEGIARTI000037208076",
    "LEGIARTI000021450417",
    "LEGIARTI000023419369",
    "LEGIARTI000043808350",
    "LEGIARTI000039778443",
    "LEGIARTI000023419375",
    "LEGIARTI000042061923",
    "LEGIARTI000039119779",
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
    has_duplicate_versions = len(versions) != len(
        {v["versionArticle"] for v in versions}
    )

    if cid in ARTICLES_THAT_NEED_TO_BE_RESORTED:
        assert sorted_by_version == sorted_by_timestamp

        return sorted_by_timestamp

    if versions != sorted_by_version != sorted_by_timestamp:
        print(
            "foobar "
            + str(
                (
                    cid,
                    [v["id"] for v in sorted_by_timestamp],
                )
            )
        )

    if not (
        cid in ALLOWED_WITH_VERSION_SORTING_NOT_MATCHING_TIMESTAMP
        or has_duplicate_versions
        or sorted_by_version == sorted_by_timestamp
    ):
        print("order of versions doesn't match timestamps: " + cid)
    return sorted_by_timestamp


def _begin(v):
    return v["dateDebut"] + 1 if v["dateDebut"] != v["dateFin"] else v["dateDebut"]


def _end(v):
    end = v["dateFin"] if v["dateDebut"] != v["dateFin"] else v["dateFin"] + 1

    if end <= _begin(v):
        end = _begin(v) + 1

        if v["id"] not in VERSIONS_WITH_END_BEFORE_BEGIN:
            print("end < begin, id: " + v["id"])

    return end


def _commits_for_article(article: ArticleJSON) -> Generator[Commit, None, None]:
    """
    Generates commits from an article. The datamodel of legifrance has versions
    with states. That proved hard to work with. Instead we rebuild changes over
    time. We assert the state match the assumtpions we have linked to timing.
    In other words, we look at time, not state of a version.
    """

    ALLOW_LIST_OVERLAP = {
        "LEGIARTI000006293330",
        "LEGIARTI000006293336",
        "LEGIARTI000006293897",
        "LEGIARTI000006294674",
        "LEGIARTI000006294700",
        "LEGIARTI000006294706",
        "LEGIARTI000006294708",
        "LEGIARTI000006347017",
        # not checked under this
        "LEGIARTI000006294710",
        "LEGIARTI000006295099",
        "LEGIARTI000006295137",
        "LEGIARTI000006295148",
        "LEGIARTI000006295632",
        "LEGIARTI000006295643",
        "LEGIARTI000006295648",
        "LEGIARTI000006295653",
        "LEGIARTI000006295656",
        "LEGIARTI000006296213",
        "LEGIARTI000006296256",
        "LEGIARTI000006296297",
        "LEGIARTI000006300431",
        "LEGIARTI000006300625",
        "LEGIARTI000006300647",
        "LEGIARTI000006300654",
        "LEGIARTI000006301105",
        "LEGIARTI000006301265",
        "LEGIARTI000006301572",
        "LEGIARTI000006301691",
        "LEGIARTI000006301952",
        "LEGIARTI000006314988",
        "LEGIARTI000006315125",
        "LEGIARTI000006315189",
        "LEGIARTI000006315260",
        "LEGIARTI000006315634",
        "LEGIARTI000006315682",
        "LEGIARTI000006315701",
        "LEGIARTI000006315733",
        "LEGIARTI000006315855",
        "LEGIARTI000006315978",
        "LEGIARTI000006315989",
        "LEGIARTI000006316446",
        "LEGIARTI000006316613",
        "LEGIARTI000006316697",
        "LEGIARTI000006316705",
        "LEGIARTI000006346140",
        "LEGIARTI000006346518",
        "LEGIARTI000006346820",
        "LEGIARTI000034701432",
        "LEGIARTI000006348051",
        "LEGIARTI000006348094",
        "LEGIARTI000006348099",
        "LEGIARTI000006348130",
        "LEGIARTI000006349204",
        "LEGIARTI000006349222",
        "LEGIARTI000006350201",
        "LEGIARTI000006350773",
        "LEGIARTI000006353459",
        "LEGIARTI000006353839",
        "LEGIARTI000006353902",
        "LEGIARTI000006353907",
        "LEGIARTI000006353927",
        "LEGIARTI000006354138",
        "LEGIARTI000006354149",
        "LEGIARTI000006354587",
        "LEGIARTI000006357475",
        "LEGIARTI000006358091",
        "LEGIARTI000006361377",
        "LEGIARTI000006361392",
        "LEGIARTI000006362851",
        "LEGIARTI000006398237",
        "LEGIARTI000006410087",
        "LEGIARTI000006411212",
        "LEGIARTI000006418954",
        "LEGIARTI000006418954",
        "LEGIARTI000006419416",
        "LEGIARTI000006449584",
        "LEGIARTI000006449636",
        "LEGIARTI000006449852",
        "LEGIARTI000006464880",
        "LEGIARTI000006464880",
        "LEGIARTI000006465318",
        "LEGIARTI000006465410",
        "LEGIARTI000006465416",
        "LEGIARTI000006465425",
        "LEGIARTI000006465460",
        "LEGIARTI000006465478",
        "LEGIARTI000006465483",
        "LEGIARTI000006465489",
        "LEGIARTI000006465492",
        "LEGIARTI000006465498",
        "LEGIARTI000006465501",
        "LEGIARTI000006465505",
        "LEGIARTI000006465508",
        "LEGIARTI000006465511",
        "LEGIARTI000006465516",
        "LEGIARTI000006465521",
        "LEGIARTI000006465526",
        "LEGIARTI000006465531",
        "LEGIARTI000006465537",
        "LEGIARTI000006465542",
        "LEGIARTI000006465547",
        "LEGIARTI000006465551",
        "LEGIARTI000006465556",
        "LEGIARTI000006465561",
        "LEGIARTI000006465568",
        "LEGIARTI000006465574",
        "LEGIARTI000006465580",
        "LEGIARTI000006465584",
        "LEGIARTI000006465591",
        "LEGIARTI000006465598",
        "LEGIARTI000006465601",
        "LEGIARTI000006465604",
        "LEGIARTI000006465608",
        "LEGIARTI000006465611",
        "LEGIARTI000006465615",
        "LEGIARTI000006465620",
        "LEGIARTI000006465627",
        "LEGIARTI000006465632",
        "LEGIARTI000006465637",
        "LEGIARTI000006465642",
        "LEGIARTI000006465648",
        "LEGIARTI000006465653",
        "LEGIARTI000006465659",
        "LEGIARTI000006465664",
        "LEGIARTI000006465671",
        "LEGIARTI000006465676",
        "LEGIARTI000006465681",
        "LEGIARTI000006465686",
        "LEGIARTI000006465691",
        "LEGIARTI000006466353",
        "LEGIARTI000006466360",
        "LEGIARTI000006466538",
        "LEGIARTI000006466538",
        "LEGIARTI000006519118",
        "LEGIARTI000006520040",
        "LEGIARTI000006520044",
        "LEGIARTI000006520173",
        "LEGIARTI000006520375",
        "LEGIARTI000006520378",
        "LEGIARTI000006520394",
        "LEGIARTI000006520396",
        "LEGIARTI000006520415",
        "LEGIARTI000006520420",
        "LEGIARTI000006520798",
        "LEGIARTI000018925648",
        "LEGIARTI000039027178",
        "LEGIARTI000006555931",
        "LEGIARTI000006556989",
        "LEGIARTI000006556993",
        "LEGIARTI000006557027",
        "LEGIARTI000006579968",
        "LEGIARTI000006579973",
        "LEGIARTI000006580757",
        "LEGIARTI000006581115",
        "LEGIARTI000006581123",
        "LEGIARTI000006581357",
        "LEGIARTI000006581385",
        "LEGIARTI000006581385",
        "LEGIARTI000006615389",
        "LEGIARTI000006615720",
        "LEGIARTI000006653754",
        "LEGIARTI000006653860",
        "LEGIARTI000006653984",
        "LEGIARTI000006654207",
        "LEGIARTI000006654485",
        "LEGIARTI000006791979",
        "LEGIARTI000006792009",
        "LEGIARTI000006792016",
        "LEGIARTI000006792391",
        "LEGIARTI000006795801",
        "LEGIARTI000006795805",
        "LEGIARTI000006795808",
        "LEGIARTI000006795812",
        "LEGIARTI000006796313",
        "LEGIARTI000006796321",
        "LEGIARTI000006813235",
        "LEGIARTI000006813237",
        "LEGIARTI000006813239",
        "LEGIARTI000006813241",
        "LEGIARTI000006813244",
        "LEGIARTI000006813246",
        "LEGIARTI000006813248",
        "LEGIARTI000028777024",
        "LEGIARTI000006840181",
        "LEGIARTI000006840884",
        "LEGIARTI000006840894",
        "LEGIARTI000006840894",
        "LEGIARTI000006840900",
        "LEGIARTI000006840904",
        "LEGIARTI000006840907",
        "LEGIARTI000006841085",
        "LEGIARTI000006842790",
        "LEGIARTI000006842882",
        "LEGIARTI000006843063",
        "LEGIARTI000006843902",
        "LEGIARTI000006844353",
        "LEGIARTI000006844749",
        "LEGIARTI000006844754",
    }
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
    }

    last_commit_begin: int = END_TIME
    i = 0

    versions = sorted_versions(article)
    assert len(versions) > 0, article
    cid = versions[0]["cid"]
    uri = _version_uri(versions[0])

    if _end(versions[0]) != END_TIME:
        assert (
            versions[0]["etat"]
            in {
                "ABROGE",
                "ABROGE_DIFF",
                "PERIME",
                "ANNULE",
                "TRANSFERE",
            }
            or cid in ALLOW_LIST_END_DATE_NOT_ABROGATED
        ), f"cid: {cid} etat: {versions[0]['etat']}"

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
            delta = _end(v) - last_commit_begin

            if delta >= 100 and cid not in ALLOW_LIST_OVERLAP:
                # TODO
                print(f"overlap but not in list: {cid}")
            # assert (
            #     delta < 100
            # ), f"{cid} {time} We tolerate very small overlaps due to changes valid only for a day."

            modified_by = [
                TextCidAndTitle(cid=lm["textCid"], title=lm["textTitle"])
                for lm in v["lienModifications"]
            ]

            html = (
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
                        f"⚠️Missing data from [legifrance](https://www.legifrance.gouv.fr/codes/article_lc/{cid})⚠️",
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

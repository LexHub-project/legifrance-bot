from copy import deepcopy
from commits import ArticleJSON, CodeJSON, sorted_versions
from dataclasses import dataclass
from collections import OrderedDict


def _get_tm_by_path(tm: CodeJSON, path: list[str]) -> CodeJSON:
    if len(path) == 0:
        return tm

    for section in tm["sections"]:
        if section["cid"] == path[0]:
            return _get_tm_by_path(section, path[1:])

    raise KeyError(f"Section {path} not found in tm")


def _dedupe(arr: list[str]):
    return list(OrderedDict.fromkeys(arr))


def _parse_version_path(version) -> list[str]:
    raw_path = [t["cid"] for t in version["context"]["titresTM"]]

    return _dedupe(raw_path)  # can have duplicates, eg LEGIARTI000006812669


def _article_exists_at_path(tm: CodeJSON, path: list[str], article_cid: str) -> bool:
    section = _get_tm_by_path(tm, path)
    found = [a for a in section["articles"] if a["cid"] == article_cid]
    return len(found) >= 1


def _is_path_valid(tm: CodeJSON, path: list[str]) -> bool:
    try:
        _get_tm_by_path(tm, path)
        return True
    except KeyError:
        return False


def patch_tm_missing_sections(tm: CodeJSON, articles: list[ArticleJSON]):
    patched_tm = deepcopy(tm)
    for article in articles:
        versions = article["listArticle"]
        for version in versions:
            path = _parse_version_path(version)
            if not _is_path_valid(patched_tm, path):
                for i in range(len(path)):
                    if not _is_path_valid(patched_tm, path[: i + 1]):
                        parent_section = _get_tm_by_path(patched_tm, path[:i])
                        section_cid = path[i]
                        titres_tm = version["context"]["titresTM"]
                        # index can be other than i in case of duplicates in titresTM
                        index = [s["cid"] for s in titres_tm].index(section_cid)
                        section_base_ref = titres_tm[index]
                        section_ref = {
                            **section_base_ref,
                            "title": section_base_ref["titre"],
                            "dateDebut": section_base_ref["debut"],
                            "dateFin": section_base_ref["fin"],
                            "articles": [],
                            "sections": [],
                        }
                        parent_section["sections"] = sorted(
                            parent_section["sections"] + [section_ref],
                            key=lambda s: s["title"],
                        )

    return patched_tm


@dataclass
class TMArticlePatch:
    path: list[str]
    timestamp_start: int
    timestamp_end: int
    type: str  # "ADD" | "REMOVE"
    article_ref: dict


def get_tm_patches(tm: CodeJSON, articles: list[ArticleJSON]) -> list[TMArticlePatch]:
    patches = []
    for article in articles:
        versions = sorted_versions(
            article
        )  # versions are now sorted in reverse chronological order and non overlapping
        article_cid = versions[0]["cid"]
        paths_dateranges = {}
        for v in versions:
            path = tuple(_parse_version_path(v))
            if (
                path in paths_dateranges.keys()
                and paths_dateranges[path]["dateFin"] > v["dateFin"]
            ):
                paths_dateranges[path]["dateDebut"] = v["dateDebut"]
                paths_dateranges[path]["id"] = v["id"]
            else:
                paths_dateranges[path] = {
                    "dateDebut": v["dateDebut"],
                    "dateFin": v["dateFin"],
                    "id": v["id"],
                    "intOrdre": v["ordre"],
                }

        for raw_path in paths_dateranges.keys():
            path = list(raw_path)
            daterange = paths_dateranges[raw_path]
            if not _article_exists_at_path(tm, path, article_cid):
                # article must exist at this path -> patch to add
                patches.append(
                    TMArticlePatch(
                        timestamp_start=daterange["dateDebut"],
                        timestamp_end=daterange["dateFin"],
                        type="ADD",
                        path=path,
                        article_ref={
                            "cid": article_cid,
                            "num": versions[0]["num"],
                            "id": daterange["id"],
                            "intOrdre": daterange["intOrdre"],
                        },
                    )
                )
            other_paths = [p for p in paths_dateranges.keys() if p != raw_path]
            for raw_other_path in other_paths:
                other_path = list(raw_other_path)
                # article must not exist at this path -> patch to remove
                if _article_exists_at_path(tm, other_path, article_cid):
                    patches.append(
                        TMArticlePatch(
                            timestamp_start=daterange["dateDebut"],
                            timestamp_end=daterange["dateFin"],
                            type="REMOVE",
                            path=other_path,
                            article_ref={"cid": article_cid},
                        )
                    )

    return patches


def apply_patches(
    tm: CodeJSON, patches: list[TMArticlePatch], timestamp: int
) -> CodeJSON:
    patched_tm = deepcopy(tm)
    applicable_patches = [
        p for p in patches if p.timestamp_start <= timestamp <= p.timestamp_end
    ]
    for patch in applicable_patches:
        section = _get_tm_by_path(patched_tm, patch.path)
        if patch.type == "ADD":
            section["articles"] = sorted(
                section["articles"] + [patch.article_ref],
                key=lambda a: a["intOrdre"],
            )
        elif patch.type == "REMOVE":
            section["articles"] = [
                a for a in section["articles"] if a["cid"] != patch.article_ref["cid"]
            ]

    return patched_tm

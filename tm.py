from copy import deepcopy
from commits import ArticleJSON, CodeJSON


def _get_tm_by_path(tm: CodeJSON, path: list[str]) -> CodeJSON:
    if len(path) == 0:
        return tm

    for section in tm["sections"]:
        if section["cid"] == path[0]:
            return _get_tm_by_path(section, path[1:])

    raise KeyError(f"Section {path} not found in tm")


def _dedupe(arr: list[str]):
    out = []
    for a in arr:
        if a not in out:
            out.append(a)
    return out


def _parse_version_path(version) -> list[str]:
    raw_path = [t["cid"] for t in version["context"]["titresTM"]]

    return _dedupe(raw_path)  # can have duplicates, eg LEGIARTI000006812669


def _article_exists_at_path(tm: CodeJSON, path: list[str], article_cid: str) -> bool:
    section = _get_tm_by_path(tm, path)
    found = [a for a in section["articles"] if a["cid"] == article_cid]
    return len(found) >= 1


def _is_version_in_force(version: dict, timestamp: int):
    return version["dateDebut"] <= timestamp <= version["dateFin"]


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


def patch_tm_multiple_paths(
    tm: CodeJSON, articles: list[ArticleJSON], timestamp: int
) -> CodeJSON:
    patched_tm = deepcopy(tm)

    for article in articles:
        versions = [
            v for v in article["listArticle"] if v["etat"] != "MODIFIE_MORT_NE"
        ]  # TODO mutualize handling
        versions_in_force = [v for v in versions if _is_version_in_force(v, timestamp)]
        if len(versions_in_force) == 0:
            continue

        v_0 = versions_in_force[0]
        cid = v_0["cid"]

        all_paths = set(tuple(_parse_version_path(v)) for v in versions)
        paths_in_force = set(tuple(_parse_version_path(v)) for v in versions_in_force)
        for raw_path in paths_in_force:
            path = list(raw_path)
            if not _article_exists_at_path(patched_tm, path, cid):  # ok
                article_ref = {
                    "cid": cid,
                    "num": v_0["num"],
                    "id": v_0["id"],
                    "intOrdre": v_0["ordre"],
                }
                _get_tm_by_path(patched_tm, path)["articles"] = sorted(
                    _get_tm_by_path(patched_tm, path)["articles"] + [article_ref],
                    key=lambda a: a["intOrdre"],
                )
        for raw_path in all_paths - paths_in_force:
            path = list(raw_path)
            if _article_exists_at_path(patched_tm, path, cid):
                _get_tm_by_path(patched_tm, path)["articles"] = [
                    a
                    for a in _get_tm_by_path(patched_tm, path)["articles"]
                    if a["cid"] != cid
                ]

    return patched_tm

from copy import deepcopy
from re import sub
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


def _format_version_path(version):
    raw_path = [t["cid"] for t in version["context"]["titresTM"]]

    return _dedupe(raw_path)  # can have duplicates, eg LEGIARTI000006812669


def _article_exists_at_path(tm: CodeJSON, path: list[str], article_cid: str) -> bool:
    section = _get_tm_by_path(tm, path)
    found = [a for a in section["articles"] if a["cid"] == article_cid]
    return len(found) >= 1


def _is_version_in_force(version: dict, timestamp: int):
    return version["dateDebut"] <= timestamp <= version["dateFin"]


def _article_num_to_int(num: str) -> int:
    return int(sub(r"[^0-9]", "", num))


def patch_tm_multiple_paths(
    tm: CodeJSON, articles: list[ArticleJSON], timestamp: int
) -> CodeJSON:
    patched_tm = deepcopy(tm)

    for article in articles:
        versions = article["listArticle"]
        for v in versions:
            path = _format_version_path(v)
            if _is_version_in_force(v, timestamp):
                if _article_exists_at_path(patched_tm, path, v["cid"]):  # ok
                    continue
                else:
                    article_ref = {
                        "cid": v["cid"],
                        "num": v["num"],
                        "id": v["id"],
                    }
                    _get_tm_by_path(patched_tm, path)["articles"] = sorted(
                        _get_tm_by_path(patched_tm, path)["articles"] + [article_ref],
                        key=lambda x: _article_num_to_int(x["num"]),
                    )
            else:
                if _article_exists_at_path(patched_tm, path, v["cid"]):
                    _get_tm_by_path(patched_tm, path)["articles"] = [
                        a
                        for a in _get_tm_by_path(patched_tm, path)["articles"]
                        if a["cid"] != v["cid"]
                    ]

    return patched_tm

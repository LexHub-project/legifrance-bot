from copy import deepcopy
from typing import Tuple

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


def _format_path(titres_tm):
    raw_path = [t["cid"] for t in titres_tm]

    return "/".join(_dedupe(raw_path))  # can have duplicates, eg LEGIARTI000006812669


def _are_paths_valid(
    tm: CodeJSON, paths: set[str], article_cid: str
) -> Tuple[list[str], list[str]]:
    valid = []
    missing = []

    for path in paths:
        try:
            section = _get_tm_by_path(tm, path.split("/"))
            found = [a for a in section["articles"] if a["cid"] == article_cid]
            if len(found) >= 1:
                # can be more, eg LEGIARTI000006841453 in LEGITEXT000006070666
                valid.append(path)
            else:
                missing.append(path)

        except KeyError:
            print(f"Path {path} not found in tm {article_cid}")
            # TODO handle this case eg LEGIARTI000006812892

    return valid, missing


def patch_tm_multiple_paths(tm: CodeJSON, articles: list[ArticleJSON]) -> CodeJSON:
    patched_tm = deepcopy(tm)

    for article in articles:
        v_0 = article["listArticle"][0]
        if v_0["textTitles"][0]["cid"] == tm["cid"]:
            paths = {
                _format_path(v["context"]["titresTM"]) for v in article["listArticle"]
            }
            if len(paths) > 1:
                valid, missing = _are_paths_valid(tm, paths, v_0["cid"])
                article_ref = next(
                    a
                    for a in _get_tm_by_path(tm, valid[0].split("/"))["articles"]
                    if a["cid"] == v_0["cid"]
                )
                for m in missing:
                    _get_tm_by_path(patched_tm, m.split("/"))["articles"] = sorted(
                        _get_tm_by_path(patched_tm, m.split("/"))["articles"]
                        + [article_ref],
                        key=lambda x: x["num"],
                    )
    return patched_tm

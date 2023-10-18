from commits import ArticleJSON, CodeJSON
from copy import deepcopy


def _get_tm_by_path(tm: CodeJSON, path: [str]) -> CodeJSON:
    if len(path) == 0:
        return tm

    for section in tm["sections"]:
        if section["cid"] == path[0]:
            return _get_tm_by_path(section, path[1:])

    raise KeyError(f"Section {path} not found in tm")


def _format_path(titresTm):
    return "/".join([t["cid"] for t in titresTm])


def _are_paths_valid(tm: CodeJSON, paths: [str], article_cid: str) -> ([str], [str]):
    valid = []
    missing = []

    for path in paths:
        section = _get_tm_by_path(tm, path.split("/"))
        found = [a for a in section["articles"] if a["cid"] == article_cid]
        if len(found) == 1:
            valid.append(path)
        elif len(found) == 0:
            missing.append(path)
        else:
            raise ValueError(f"Found {len(found)} articles for {article_cid}")

    return valid, missing


def patch_tm_multiple_paths(tm: CodeJSON, articles: [ArticleJSON]) -> CodeJSON:
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

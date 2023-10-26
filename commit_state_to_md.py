import io
import re
import unicodedata
from io import TextIOWrapper

from to_commit_state import CodeArticle, CodeTree, StateAtCommit


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


def _header(level: int, text: str) -> str:
    # TODO, for now limited to level 6
    return ("#" * min(level, 6)) + " " + text


def _section(level: int, tree: CodeTree, code_cid: str):
    if tree.cid == code_cid:
        text = f"{tree.title} [🡕](https://www.legifrance.gouv.fr/codes/texte_lc/{code_cid}/)"
    else:
        text = f"{tree.title} [🡕](https://www.legifrance.gouv.fr/codes/section_lc/{code_cid}/{tree.id}/#{tree.id}/)"

    return _header(level, text)


def _article_to_header_text(article: CodeArticle) -> str:
    return f"Article {article.num} [🡕](https://www.legifrance.gouv.fr/codes/article_lc/{article.id}/)"


def _article_to_anchor(article: CodeArticle) -> str:
    return f"#article-{article.num}-🡕"


def _resolve_links(html: str | None, uri_map: dict[str, str]):
    if html is None:
        return None

    look_for = r"/affichCodeArticle\.do\?cidTexte=(LEGI[A-Z0-9]+)&idArticle=(LEGI[A-Z0-9]+)&dateTexte=&categorieLien=cid"
    matches = re.finditer(look_for, html)
    for match in matches:
        # TODO is this information we really need?
        # text_cid = match.group(1)
        article_cid = match.group(2)
        try:
            html = html.replace(match.group(0), uri_map[article_cid])
        except KeyError:
            pass

    return html


def _print_to_one_file_per_code(
    tree: CodeTree,
    uri_map: dict[str, str],
    file: TextIOWrapper,
    code_cid: str,
    level=1,
):
    print(_section(level, tree, code_cid), file=file)

    # TODO
    # if "commentaire" in tm and tm["commentaire"] is not None:
    #     print(tm["commentaire"], file=file)

    for article in sorted(tree.articles, key=lambda a: a.int_ordre):
        print(_header(level + 1, _article_to_header_text(article)), file=file)
        print(_resolve_links(article.text, uri_map), file=file)
        print("\n", file=file)

    for section in tree.sections:
        _print_to_one_file_per_code(section, uri_map, file, code_cid, level + 1)


def _to_one_file_per_code(tree: CodeTree, uri_map: dict[str, str]):
    f = io.StringIO()
    _print_to_one_file_per_code(tree, uri_map, f, tree.cid)
    return f.getvalue()


def _build_uri_maps_one_file_per_code(trees: list[CodeTree], code: str | None = None):
    map: dict[str, str] = {}

    for tree in trees:
        code_uri = "/" + slugify(tree.title) + ".md" if code is None else code

        for article in tree.articles:
            map[article.cid] = code_uri + _article_to_anchor(article)

        map |= _build_uri_maps_one_file_per_code(tree.sections, code_uri)

    return map


def to_one_file_per_code(state: StateAtCommit):
    uri_map = _build_uri_maps_one_file_per_code(state.code_trees)

    return {
        f"{slugify(code.title)}.md": _to_one_file_per_code(code, uri_map)
        for code in state.code_trees
    }


def _to_one_file_per_article(tree: CodeTree, uri_map: dict[str, str]):
    # TODO
    # if "commentaire" in tm and tm["commentaire"] is not None:
    #     print(tm["commentaire"], file=file)

    return {
        f"{slugify(article.num)}.md": _header(1, _article_to_header_text(article))
        + "\n\n"
        + _resolve_links(article.text, uri_map)
        for article in tree.articles
    } | {
        slugify(section.title): _to_one_file_per_article(section, uri_map)
        for section in tree.sections
    }


def _build_uri_maps_one_file_per_article(trees: list[CodeTree], paths=[]):
    map: dict[str, str] = {}

    for tree in trees:
        with_tree = paths + [slugify(tree.title)]
        for article in tree.articles:
            map[article.cid] = (
                "/" + "/".join(with_tree) + "/" + slugify(article.num) + ".md"
            )

        map |= _build_uri_maps_one_file_per_article(tree.sections, with_tree)

    return map


def to_one_file_per_article(state: StateAtCommit):
    uri_map = _build_uri_maps_one_file_per_article(state.code_trees)

    return {
        slugify(code.title): _to_one_file_per_article(code, uri_map)
        for code in state.code_trees
    }

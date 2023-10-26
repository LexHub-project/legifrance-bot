from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from tqdm import tqdm

from commits import ArticleJSON, CodeJSON, Commit
from tm import (
    CodeTreeStructure,
    CodeArticleRef,
    apply_patches,
    get_tm_patches,
    patch_tm_missing_sections,
)


@dataclass
class CodeArticle(CodeArticleRef):
    text: str


@dataclass
class CodeTree:
    id: str
    cid: str
    title: str
    timestamp_start: int
    timestamp_end: int
    sections: list[CodeTree]
    articles: list[CodeArticle]


@dataclass
class StateAtCommit:
    title: str
    timestamp: int
    code_trees: list[CodeTree]


# def _is_tree_structure_in_force(
#     tree_strucure: CodeTreeStructure, timestamp: int
# ) -> bool:
#     return (
#         tree_strucure.start_timestamp <= timestamp / 1000 <= tree_strucure.end_timestamp
#     )


def _tree_structure_to_code_tree(
    tree_structure: CodeTreeStructure,
    articles_text: dict[str, str | None],
    timestamp: int,
) -> CodeTree | None:
    if not tree_structure.in_force(timestamp):
        return None

    articles = []
    for article_ref in tree_structure["articles"]:
        text = articles_text.get(article_ref.cid)

        if text is not None:
            articles.append(CodeArticle(**article_ref, text=text))

    sections = []
    for section in tree_structure["sections"]:
        tree = _tree_structure_to_code_tree(section, articles_text, timestamp)

        if tree is not None:
            sections.append(tree)

    # if "commentaire" in tree_structure and tree_structure["commentaire"] is not None:
    #     print(tree_structure["commentaire"])
    #     # TODO

    return CodeTree(
        tree_structure.id, tree_structure.cid, tree_structure.title, sections, articles
    )


def generate_commit_states(
    codes: list[CodeJSON],
    commits: list[Commit],
    articles_by_code: dict[
        str, list[ArticleJSON]
    ],  # code_changes : dict[str, CodeChange],
) -> Generator[StateAtCommit, None, None]:
    assert len(commits) > 0

    codes_sections_patched = [
        patch_tm_missing_sections(c, articles_by_code[c["cid"]])
        for c in tqdm(codes, desc="Patching sections TM")
    ]
    tm_patches = {
        tm["cid"]: get_tm_patches(tm, articles_by_code[tm["cid"]])
        for tm in codes_sections_patched
    }

    articles_text: dict[str, str | None] = {}
    # code_structures = [tm_to_code_struc(code) for code in codes]
    for commit in tqdm(commits, desc="Converting to Code Tree"):
        articles_text.update(commit.article_changes)
        # code_trees.update(commit.code_changes)

        code_trees = [
            _tree_structure_to_code_tree(
                apply_patches(
                    tm, tm_patches[tm["cid"]], commit.timestamp
                ),  # apply_changes(tm, code_changes[tm["cid"]], commit.timestamp),
                articles_text,
                commit.timestamp,
            )
            for tm in codes_sections_patched
        ]
        assert None not in code_trees

        yield StateAtCommit(
            title=commit.title,
            timestamp=commit.timestamp,
            code_trees=code_trees,
        )

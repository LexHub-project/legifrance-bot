from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from tqdm import tqdm

from commits import ArticleJSON, CodeJSON, Commit
from tm import (
    CodeTreeStructure,
    CodeArticleRef,
    tree_structure_in_force,
    apply_patches,
    get_tm_patches,
    patch_tm_missing_sections,
)


@dataclass
class CodeArticle(CodeArticleRef):
    text: str | None

    @staticmethod
    def from_article_ref(article_ref: CodeArticleRef, text: str) -> CodeArticle:
        return CodeArticle(
            article_ref.id,
            article_ref.cid,
            article_ref.num,
            article_ref.int_ordre,
            text,
        )


@dataclass
class CodeTree:
    id: str
    cid: str
    title: str
    sections: list[CodeTree]
    articles: list[CodeArticle]


@dataclass
class StateAtCommit:
    title: str
    timestamp: int
    code_trees: list[CodeTree]


def _tree_structure_to_code_tree(
    tree_structure: CodeTreeStructure,
    articles_text: dict[str, str | None],
    timestamp: int,
) -> CodeTree | None:
    if not tree_structure_in_force(tree_structure, timestamp):
        return None

    articles = []
    for article_ref in tree_structure.articles:
        text = articles_text.get(article_ref.cid)

        if text is not None:
            articles.append(CodeArticle.from_article_ref(article_ref, text))

    sections = []
    for section in tree_structure.sections:
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

    for i, commit in enumerate(tqdm(commits, desc="Converting to Code Tree")):
        articles_text.update(commit.article_changes)
        # code_trees.update(commit.code_changes)
        code_tree_structures = [
            apply_patches(tm, tm_patches[tm["cid"]], commit.timestamp)
            for tm in codes_sections_patched
        ]
        code_trees = [
            _tree_structure_to_code_tree(
                tree_structure, articles_text, commit.timestamp
            )
            for tree_structure in code_tree_structures
        ]
        assert None not in code_tree_structures

        yield StateAtCommit(
            title=commit.title,
            timestamp=commit.timestamp,
            code_trees=code_trees,
        )

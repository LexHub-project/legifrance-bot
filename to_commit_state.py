from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generator

from tqdm import tqdm

from commits import ArticleJSON, CodeJSON, Commit
from tm import patch_tm_missing_sections, patch_tm_multiple_paths


@dataclass
class CodeArticle:
    id: str
    cid: str
    num: str
    text: str


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


def _is_tm_in_force(tm: CodeJSON, timestamp: int) -> bool:
    if tm.get("nature", None) == "CODE":
        return True  # root

    start_timestamp = datetime.fromisoformat(f"{tm['dateDebut']} 00:00").timestamp()
    end_timestamp = datetime.fromisoformat(f"{tm['dateFin']} 23:59").timestamp()

    return start_timestamp <= timestamp / 1000 <= end_timestamp


def _tm_to_code_tree(
    tm: CodeJSON, articles_text: dict[str, str | None], timestamp: int
) -> CodeTree | None:
    if not _is_tm_in_force(tm, timestamp):
        return None

    articles = []
    for article in tm["articles"]:
        text = articles_text.get(article["cid"])

        if text is not None:
            articles.append(
                CodeArticle(article["id"], article["cid"], article["num"], text)
            )

    sections = []
    for section in tm["sections"]:
        tree = _tm_to_code_tree(section, articles_text, timestamp)

        if tree is not None:
            sections.append(tree)

    # if "commentaire" in tm and tm["commentaire"] is not None:
    #     print(tm["commentaire"])
    #     # TODO

    return CodeTree(tm["id"], tm["cid"], tm["title"], sections, articles)


def generate_commit_states(
    codes: list[CodeJSON],
    commits: list[Commit],
    articles_by_code: dict[str, list[ArticleJSON]],
) -> Generator[StateAtCommit, None, None]:
    assert len(commits) > 0

    codes_sections_patched = [
        patch_tm_missing_sections(c, articles_by_code[c["cid"]])
        for c in tqdm(codes, desc="Patching sections TM")
    ]

    articles_text: dict[str, str | None] = {}

    for commit in tqdm(commits, desc="Converting to Code Tree"):
        articles_text.update(commit.article_changes)

        code_trees = [
            _tm_to_code_tree(
                patch_tm_multiple_paths(
                    tm, articles_by_code[tm["cid"]], commit.timestamp
                ),
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

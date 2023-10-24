from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generator

from tqdm import tqdm
from tm import patch_tm_missing_sections, patch_tm_multiple_paths
from commits import ArticleJSON, CodeJSON, Commit


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


def _last_text(commits: list[Commit], cid: str) -> str | None:
    for c in reversed(commits):
        if cid in c.article_changes:
            return c.article_changes[cid]

    # There is no text yet
    return None


def _is_tm_in_force(tm: CodeJSON, timestamp: int) -> bool:
    if tm.get("nature", None) == "CODE":
        return True  # root

    start_timestamp = datetime.fromisoformat(f"{tm['dateDebut']} 00:00").timestamp()
    end_timestamp = datetime.fromisoformat(f"{tm['dateFin']} 23:59").timestamp()

    return start_timestamp <= timestamp / 1000 <= end_timestamp


def _tm_to_code_tree(
    tm: CodeJSON,
    commits: list[Commit],
) -> CodeTree | None:
    if not _is_tm_in_force(tm, commits[-1].timestamp):
        return None

    articles = []
    for article in tm["articles"]:
        text = _last_text(commits, article["cid"])

        if text is not None:
            articles.append(
                CodeArticle(article["id"], article["cid"], article["num"], text)
            )

    sections = []
    for section in tm["sections"]:
        tree = _tm_to_code_tree(section, commits)

        if tree is not None:
            sections.append(tree)

    if "commentaire" in tm and tm["commentaire"] is not None:
        print(tm["commentaire"])
        # TODO

    return CodeTree(tm["id"], tm["cid"], tm["title"], sections, articles)


def generate_commit_states(
    codes: list[CodeJSON],
    commits: list[Commit],
    articles_by_code: dict[str, ArticleJSON],
) -> Generator[StateAtCommit, None, None]:
    sections_patched = [
        patch_tm_missing_sections(c, articles_by_code[c["cid"]])
        for c in tqdm(codes, desc="Patching sections TM")
    ]

    for i in tqdm(range(0, len(commits)), desc="Converting to Code Tree"):
        code_trees = [
            _tm_to_code_tree(
                patch_tm_multiple_paths(
                    tm, articles_by_code[tm["cid"]], commits[i].timestamp
                ),
                commits[: (i + 1)],
            )
            for tm in sections_patched
        ]
        assert None not in code_trees

        yield StateAtCommit(
            title=commits[i].title,
            timestamp=commits[i].timestamp,
            code_trees=code_trees,
        )

from __future__ import annotations

import datetime
from typing import Generator

import pytest

from commit_state_to_md import to_one_file_per_article, to_one_file_per_code
from constants import DATE_STR_FMT
from fetch_data import CachedLegifranceClient
from main import CID_CODE_DU_TRAVAIL_MARITIME, _process
from to_commit_state import CodeTree, StateAtCommit

client = CachedLegifranceClient(only_from_disk=True)


def _state_at_commit_metadata_to_md(s: StateAtCommit, date_str: str):
    assert len(s.code_trees) == 1

    return f"""
# Last Commit Timestamp
```
{s.timestamp}
```

# Title
```
{s.title}
```

# Link To Primary Source at test date
https://www.legifrance.gouv.fr/codes/texte_lc/{s.code_trees[0].cid}/{date_str}/
""".strip()


def _render_commit_num(i: int) -> str:
    return str(i).zfill(3)


@pytest.fixture(scope="module")
def states() -> list[StateAtCommit]:
    code_cids = [
        c for c in client.fetch_code_list() if c["cid"] == CID_CODE_DU_TRAVAIL_MARITIME
    ]

    code_tms = list(client.fetch_tms(code_cids))
    articles_by_code = {tm["cid"]: client.fetch_articles(tm) for tm in code_tms}
    return list(_process(code_tms, articles_by_code))


DATE_FOR_ONE_ARTICLE_PER_FILE = "2023-10-19"


def _state_at_date_str(states: list[StateAtCommit], date_str: str):
    timestamp = int(
        datetime.datetime.strptime(date_str, DATE_STR_FMT)
        .replace(tzinfo=datetime.timezone.utc)
        .timestamp()
        * 1000
    )
    return [s for s in states if s.timestamp <= timestamp][-1]


@pytest.mark.parametrize(
    "date_str",
    [
        DATE_FOR_ONE_ARTICLE_PER_FILE,
        "2016-12-20",
        "2016-12-19",
        "1926-12-16",
    ],
)
def test_snapshot(snapshot, states: list[StateAtCommit], date_str: str):
    state = _state_at_date_str(states, date_str)

    snapshots = to_one_file_per_code(state) | {
        "_meta.md": _state_at_commit_metadata_to_md(state, date_str)
    }

    snapshot.assert_match_dir(
        snapshots,
        "states",
    )


def test_one_file_per_article(snapshot, states: list[StateAtCommit]):
    state = _state_at_date_str(states, DATE_FOR_ONE_ARTICLE_PER_FILE)

    snapshots: dict[str, str] = to_one_file_per_article(state) | {
        "_meta.md": _state_at_commit_metadata_to_md(
            state, DATE_FOR_ONE_ARTICLE_PER_FILE
        )
    }

    snapshot.assert_match_dir(
        snapshots,
        "states",
    )


@pytest.mark.parametrize("to_files", [to_one_file_per_code, to_one_file_per_article])
def test_no_empty_commits(states: list[StateAtCommit], to_files):
    for i, (first, second) in enumerate(zip(states[:-1], states[1:])):
        assert len(first.code_trees) == 1
        assert len(second.code_trees) == 1

        # Same code
        assert first.code_trees[0].cid == second.code_trees[0].cid

        # Different text
        assert to_files(first) != to_files(
            second
        ), f"Text in commits {_render_commit_num(i)}, {_render_commit_num(i+1)} is the same"


def article_nums(tree: CodeTree) -> Generator[str, None, None]:
    for a in tree.articles:
        yield a.num

    for s in tree.sections:
        yield from article_nums(s)


# def test_articles_only_once_per_state(states: list[StateAtCommit]):
#     """
#     NOTE: this is a hunch based on looking at Legifrance. Might be an invalid
#     heuristic.
#     """
#     for s in states:
#         for c in s.code_trees:
#             nums = list(article_nums(c))

#             assert sorted(set(nums)) == sorted(
#                 nums
#             ), f"Articles present several times in commit at timestamp {s.timestamp}"

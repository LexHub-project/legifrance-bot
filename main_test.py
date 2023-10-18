import pytest

from commit_state_to_md import to_one_file_per_article, to_one_file_per_code
from fetch_data import fetch_articles, fetch_tms
from main import CID_CODE_DU_TRAVAIL_MARITIME, _process
from to_commit_state import StateAtCommit


def _state_at_commit_metadata_to_md(s: StateAtCommit):
    return f"""
# Timestamp
```
{s.timestamp}
```

# Title
```
{s.title}
```
""".strip()


def _render_commit_num(i: int) -> str:
    return str(i).zfill(3)


@pytest.fixture(scope="module")
def states() -> list[StateAtCommit]:
    code_cids = [CID_CODE_DU_TRAVAIL_MARITIME]

    code_tms = list(fetch_tms(code_cids, from_disk=True))
    articles = [a for tm in code_tms for a in fetch_articles(tm)]
    return list(_process(code_tms, articles))


@pytest.mark.parametrize("to_files", [to_one_file_per_code, to_one_file_per_article])
def test_snapshot(snapshot, states: list[StateAtCommit], to_files):
    snapshots: dict[str, str] = {}
    for i, s in enumerate(states):
        snapshots[f"{_render_commit_num(i)}"] = to_files(s) | {
            "_meta.md": _state_at_commit_metadata_to_md(s)
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

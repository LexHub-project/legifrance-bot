import pytest
from commits import StateAtCommit
from fetch_data import fetch_articles, fetch_tms
from main import _process


def _state_at_commit_to_md(s: StateAtCommit, text: str):
    return f"""
# Timestamp
```
{s.timestamp}
```

# Title
```
{s.title}
```

# Text
{text}
""".strip()


def _render_commit_num(i: int) -> str:
    return str(i).zfill(3)


@pytest.fixture(scope="module")
def states():
    code_cids = ["LEGITEXT000006072051"]  # Code du travail maritime

    code_tms = list(fetch_tms(code_cids, from_disk=True))
    articles = [a for tm in code_tms for a in fetch_articles(tm)]
    return list(_process(code_tms, articles))


def test_snapshot(snapshot, states):
    snapshots = {
        f"{_render_commit_num(i)}_{title}.md": _state_at_commit_to_md(s, text)
        for i, s in enumerate(states)
        for title, text in s.full_code_texts
    }

    snapshot.assert_match_dir(
        snapshots,
        "states",
    )


def test_no_empty_commits(states):
    for i, (first, second) in enumerate(zip(states[:-1], states[1:])):
        assert len(first.full_code_texts) == 1
        assert len(second.full_code_texts) == 1

        # Same code name
        assert first.full_code_texts[0][0] == second.full_code_texts[0][0]

        # Different text
        assert (
            first.full_code_texts[0][1] != second.full_code_texts[0][1]
        ), f"Text in commits {_render_commit_num(i)}, {_render_commit_num(i+1)} is the same"

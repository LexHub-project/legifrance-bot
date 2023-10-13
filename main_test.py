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


def test_snapshot(snapshot):
    code_cids = ["LEGITEXT000006072051"]  # Code du travail maritime

    code_tms = list(fetch_tms(code_cids, from_disk=True))
    articles = [a for tm in code_tms for a in fetch_articles(tm)]
    states = list(_process(code_tms, articles))

    snapshots = {
        f"{i}_{title}.md": _state_at_commit_to_md(s, text)
        for i, s in enumerate(states)
        for title, text in s.full_code_texts
    }

    snapshot.assert_match_dir(
        snapshots,
        "states",
    )

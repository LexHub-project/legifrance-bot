import os
import pytest
from commits import Commit, get_commits

from constants import DATE_STR_FMT
from datetime import datetime
from fetch_data import CachedLegifranceClient
from main import CID_CODE_DU_TRAVAIL_MARITIME, _init_repo, _play_commits

TEST_OUTPUT_REPO_PATH = "output_test"

client = CachedLegifranceClient(only_from_disk=True)


def _render_file_name(file_name: str) -> str:
    return f"\n\n*Article {file_name.replace('.md', '')}*\n"


def _render_header(title: str, depth: int):
    return f"\n\n{'#' * (depth + 1)} {title}\n"


def _render_repo_to_str(path: str, depth=0, pending_headers=[], out="") -> str:
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    if len(files) > 0:
        for header in pending_headers:
            out += header
        pending_headers = []
    for file in sorted(files):
        with open(os.path.join(path, file), "r") as f:
            out += _render_file_name(file)
            out += f.read()
    dirs = [
        d
        for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")
    ]
    for dir in sorted(dirs):
        out += _render_repo_to_str(
            os.path.join(path, dir),
            depth + 1,
            pending_headers + [_render_header(dir, depth)],
        )
    return out


@pytest.fixture(scope="module")
def commits() -> list[Commit]:
    tm = list(client.fetch_tms([{"cid": CID_CODE_DU_TRAVAIL_MARITIME}]))[0]
    articles = client.fetch_articles(tm)
    return get_commits(articles)


CODE_NAMES = ["code-du-travail-maritime"]
DATES = ["1926-12-16", "2023-10-20"]


def test_snapshot(snapshot, commits: list[Commit]):
    _init_repo(TEST_OUTPUT_REPO_PATH)
    snapshots = {t: {} for t in CODE_NAMES}
    commit = commits[0]
    for date in DATES:
        print("@date", date)
        timestamp = int(datetime.strptime(date, DATE_STR_FMT).timestamp() * 1000)
        while commit.timestamp <= timestamp and len(commits) > 0:
            _play_commits([commit], TEST_OUTPUT_REPO_PATH)
            commit = commits.pop(0)
        for code_name in CODE_NAMES:
            snapshots[code_name][f"{date}.md"] = _render_repo_to_str(
                f"{TEST_OUTPUT_REPO_PATH}/{code_name}"
            )
    snapshot.assert_match_dir(snapshots, "test_snapshots")

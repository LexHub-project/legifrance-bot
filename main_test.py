import io
import os
from datetime import datetime
from typing import TextIO

import pytest

from commits import Commit, get_commits
from constants import DATE_STR_FMT
from fetch_data import CachedLegifranceClient
from main import CID_CODE_DU_TRAVAIL_MARITIME, _clean_msg, _play_commits

TEST_OUTPUT_REPO_PATH = "output_test"

client = CachedLegifranceClient(only_from_disk=True)


def _render_repo(output_dir: str, output_file: TextIO) -> str:
    for root, dirs, files in os.walk(output_dir):
        # A bit of a hack but works: https://stackoverflow.com/questions/6670029/can-i-force-os-walk-to-visit-directories-in-alphabetical-order
        dirs.sort()

        for file in sorted(files):
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, output_dir)
            print(f"\n\n*{relative_path}*\n", file=output_file)
            with open(file_path, "r") as f:
                print(f.read(), file=output_file)


def _render_repo_to_str(output_dir: str) -> str:
    f = io.StringIO()
    _render_repo(output_dir, f)
    return f.getvalue()


@pytest.fixture(scope="module")
def commits() -> list[Commit]:
    articles = list(
        client.fetch_articles_from_codes([{"cid": CID_CODE_DU_TRAVAIL_MARITIME}])
    )
    return get_commits(articles)


@pytest.fixture(scope="module")
def all_commits() -> list[Commit]:
    code_list = client.fetch_code_list()

    articles = list(client.fetch_articles_from_codes(code_list))

    return get_commits(articles)


CODE_NAMES = ["code-du-travail-maritime"]
DATES = [
    (date, int(datetime.strptime(date, DATE_STR_FMT).timestamp() * 1000))
    for date in ["1926-12-16", "2023-10-20"]
]


def test_snapshot(snapshot, commits: list[Commit]):
    snapshots: dict[str, dict[str, str]] = {t: {} for t in CODE_NAMES}

    player = _play_commits(commits, True, TEST_OUTPUT_REPO_PATH)

    for date, timestamp in DATES:
        print("@date", date)

        while next(player).timestamp <= timestamp:
            pass

        for code_name in CODE_NAMES:
            snapshots[code_name][f"{date}.md"] = _render_repo_to_str(
                f"{TEST_OUTPUT_REPO_PATH}/{code_name}"
            )

    snapshot.assert_match_dir(snapshots, "test_snapshots")


def test_partial(snapshot, commits: list[Commit]):
    snapshots: dict[str, dict[str, str]] = {t: {} for t in CODE_NAMES}

    for _ in _play_commits(commits[:-25], True, TEST_OUTPUT_REPO_PATH):
        pass

    for code_name in CODE_NAMES:
        snapshots[f"0-init-{code_name}.md"] = _render_repo_to_str(
            f"{TEST_OUTPUT_REPO_PATH}/{code_name}"
        )

    for _ in _play_commits(commits[:-10], False, TEST_OUTPUT_REPO_PATH):
        pass

    for code_name in CODE_NAMES:
        snapshots[f"1-partial-{code_name}.md"] = _render_repo_to_str(
            f"{TEST_OUTPUT_REPO_PATH}/{code_name}"
        )

    for _ in _play_commits(commits, False, TEST_OUTPUT_REPO_PATH):
        pass

    for code_name in CODE_NAMES:
        snapshots[f"2-final-{code_name}.md"] = _render_repo_to_str(
            f"{TEST_OUTPUT_REPO_PATH}/{code_name}"
        )

    snapshot.assert_match_dir(snapshots, "test_snapshots")

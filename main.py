import argparse
import math
import os
import subprocess
from datetime import datetime
from typing import Callable, Generator

import pytz

from commit_state_to_md import to_one_file_per_article, to_one_file_per_code
from commits import ArticleJSON, CodeJSON, get_commits
from fetch_data import fetch_articles, fetch_tms
from tm import patch_tm_multiple_paths
from to_commit_state import StateAtCommit, generate_commit_states

OUTPUT_REPO_PATH = "../legifrance"
DEFAULT_COMMIT_MESSAGE = "Modifié par un texte d’une portée générale"

CID_CODE_DU_TRAVAIL_MARITIME = "LEGITEXT000006072051"
code_cids = [
    "LEGITEXT000006069568",
    "LEGITEXT000006069569",
    "LEGITEXT000006069576",
    "LEGITEXT000006069583",
    "LEGITEXT000006070162",
    "LEGITEXT000006070208",
    "LEGITEXT000006070239",
    "LEGITEXT000006070249",
    # "LEGITEXT000006070299",
    # "LEGITEXT000006070300",
    # "LEGITEXT000006070302",
    # "LEGITEXT000006070666",
    # "LEGITEXT000006070667",
    # "LEGITEXT000006070716",
    # "LEGITEXT000006070719",
    # "LEGITEXT000006070933",
    # "LEGITEXT000006070987",
    # "LEGITEXT000006071007",
    # "LEGITEXT000006071164",
    # "LEGITEXT000006071188",
    # "LEGITEXT000006071190",
    # "LEGITEXT000006071335",
    # "LEGITEXT000006071360",
    # "LEGITEXT000006071366",
    # "LEGITEXT000006071570",
    # "LEGITEXT000006071645",
    # "LEGITEXT000006071785",
    # "LEGITEXT000006072052",
    # "LEGITEXT000006072637",
    # "LEGITEXT000006074066",
    # "LEGITEXT000006074067",
    # "LEGITEXT000006074073",
    # "LEGITEXT000006074224",
    # "LEGITEXT000006074228",
    # "LEGITEXT000006074232",
    # "LEGITEXT000006074233",
    # "LEGITEXT000006074234",
    # "LEGITEXT000006074235",
    # "LEGITEXT000006074236",
    # "LEGITEXT000006074237",
    # "LEGITEXT000006075116",
    # "LEGITEXT000023501962",
    # "LEGITEXT000025024948",
    # "LEGITEXT000025244092",
    # "LEGITEXT000031366350",
    # "LEGITEXT000039086952",
    # "LEGITEXT000044416551",
    # "LEGITEXT000044595989",
    # "LEGITEXT000045476241",
    CID_CODE_DU_TRAVAIL_MARITIME,
]


def _process(
    code_tms: list[CodeJSON], articles: list[ArticleJSON]
) -> Generator[StateAtCommit, None, None]:
    commits = get_commits(articles)
    patched_code_tms = [patch_tm_multiple_paths(tm, articles) for tm in code_tms]
    yield from generate_commit_states(patched_code_tms, commits)


def _yield_entries_from_flatten_dict(d: dict | str, paths=[]):
    if isinstance(d, dict):
        for path, content in d.items():
            yield from _yield_entries_from_flatten_dict(content, paths + [path])
    else:
        yield os.path.join(*paths), d


def _build_git_repo_and_push(
    states: list[StateAtCommit],
    to_files: Callable[[StateAtCommit], dict],
    should_push: bool,
):
    subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
    os.makedirs(OUTPUT_REPO_PATH, exist_ok=True)
    subprocess.run(["git", "init", OUTPUT_REPO_PATH])

    tz = pytz.timezone("UTC")

    for s in states:
        subprocess.run(["git", "rm", "-r", "."], cwd=OUTPUT_REPO_PATH)
        for path, text in _yield_entries_from_flatten_dict(to_files(s)):
            full_path = f"{OUTPUT_REPO_PATH}/{path}"
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(text)

        # TODO ms vs s
        date_dt = datetime.fromtimestamp(math.floor(s.timestamp / 1000), tz)

        # TODO
        if date_dt.year >= 2038:
            date_dt = datetime(2038, 1, 1)
        if date_dt.year <= 1969:
            date_dt = datetime(1970, 1, 2)  # GitHub doesn't like Jan 1

        date_str = date_dt.isoformat()
        date_with_format_str = "format:iso8601:" + date_str

        env = os.environ.copy()
        env["GIT_COMMITTER_DATE"] = date_with_format_str

        subprocess.run(["git", "add", "."], cwd=OUTPUT_REPO_PATH)
        subprocess.run(
            [
                "git",
                "commit",
                "--date",
                date_with_format_str,
                "-m",
                s.title or DEFAULT_COMMIT_MESSAGE,
            ],
            env=env,
            cwd=OUTPUT_REPO_PATH,
        )

    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "git@github.com:LexHub-project/legifrance.git",
        ],
        cwd=OUTPUT_REPO_PATH,
    )

    if should_push:
        subprocess.run(
            [
                "git",
                "push",
                "-f",
                "origin",
                "main",
            ],
            cwd=OUTPUT_REPO_PATH,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="legifrance-bot")
    parser.add_argument(
        "-a",
        "--one-file-per-article",
        dest="to_files",
        action="store_const",
        default=to_one_file_per_code,
        const=to_one_file_per_article,
        help="If selected, will build the git repo with one file per article",
    )
    parser.add_argument(
        "-t",
        "--test-code",
        help="Select CODE_DU_TRAVAIL_MARITIME to process instead of all of them",
        action="store_true",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="If selected, will build the git repo and push",
    )

    args = parser.parse_args()
    if args.test_code:
        code_cids = [CID_CODE_DU_TRAVAIL_MARITIME]

    code_tms = list(fetch_tms(code_cids))
    articles = [a for tm in code_tms for a in fetch_articles(tm)]

    states = list(_process(code_tms, articles))

    _build_git_repo_and_push(states, args.to_files, args.push)

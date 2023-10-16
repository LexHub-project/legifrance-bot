import argparse
import math
import os
import subprocess
from datetime import datetime
from typing import Generator

import pytz
from commits import ArticleJSON, CodeJSON, StateAtCommit, get_commits
from fetch_data import fetch_articles, fetch_tms
from render_to_markdown import generate_markdown

OUTPUT_REPO_PATH = "../legifrance"

code_cids = [
    "LEGITEXT000006070208",
    "LEGITEXT000006070239",
    "LEGITEXT000006072051",
    "LEGITEXT000006074073",
    "LEGITEXT000006074228",
    "LEGITEXT000044595989",
]


def _process(
    code_tms: list[CodeJSON], articles: list[ArticleJSON]
) -> Generator[StateAtCommit, None, None]:
    commits = get_commits(articles)
    yield from generate_markdown(code_tms, articles, commits)


def _build_git_repo_and_push(states: list[StateAtCommit]):
    subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
    subprocess.run(["mkdir", OUTPUT_REPO_PATH])
    subprocess.run(["git", "init", OUTPUT_REPO_PATH])

    tz = pytz.timezone("UTC")

    for s in states:
        for title, full_text in s.full_code_texts:
            with open(f"{OUTPUT_REPO_PATH}/{title}.md", "w") as f:
                f.write(full_text)

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
                s.title,
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
    parser.add_argument("-c", "--code")

    args = parser.parse_args()
    if args.code is not None:
        code_cids = [args.code]

    code_tms = list(fetch_tms(code_cids))
    articles = [a for tm in code_tms for a in fetch_articles(tm)]
    states = list(_process(code_tms, articles))

    _build_git_repo_and_push(states)

import argparse
import math
import os
import re
import subprocess
from datetime import datetime
from typing import Generator

import pytz
import tqdm

from commits import Cid, Commit, Uri, get_commits
from constants import CID_CODE_DU_TRAVAIL_MARITIME
from fetch_data import CachedLegifranceClient

OUTPUT_REPO_PATH = "./output"


DATE_DUMP_GENERATED = datetime.now().isoformat()

COMMITS_MATCH_SPAN = 10


def _build_git_repo_readme(output_repo_path: str):
    with open(f"{output_repo_path}/README.md", "w") as f:
        f.write(
            f"""
# Legifrance Github Clone
Hi! The goal of this projects is to provide a secondary mirror of [Legifrance](https://piste.gouv.fr/index.php?option=com_apiportal&view=apitester&usage=api&apitab=tests&apiName=L%C3%A9gifrance&apiId=7daab368-e9f3-4511-989d-aba63907eef7&managerId=2&type=rest&apiVersion=2.0.0&Itemid=402&swaggerVersion=2.0&lang=fr)
inside of Git. This proof of concept is made available without any guarantees for
data quality. Please double-check anything on official websites.

# Legifrance License & Reuse
The data is reused under [Open License V2](https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf)
from Legifrance. This was last updated at {DATE_DUMP_GENERATED}.

```
« Ministère de ??? / Legifrance - Données originales téléchargées sur
https://piste.gouv.fr/, mise à jour à {DATE_DUMP_GENERATED} »
```
""".strip()
        )


def _init_repo(output_repo_path: str):
    subprocess.run(["rm", "-rf", output_repo_path])

    os.makedirs(output_repo_path, exist_ok=True)
    subprocess.run(["git", "init", output_repo_path, "--quiet"])

    _build_git_repo_readme(output_repo_path)
    subprocess.call(["git", "add", "README.md"], cwd=output_repo_path)


def _resolve_links(html: str | None, article_cid_to_uri: dict[Cid, Uri]):
    if html is None:
        return None

    look_for = r"/affichCodeArticle\.do\?cidTexte=(LEGI[A-Z0-9]+)&idArticle=(LEGI[A-Z0-9]+)&dateTexte=&categorieLien=cid"
    matches = re.finditer(look_for, html)
    for match in matches:
        # TODO is this information we really need?
        # text_cid = match.group(1)
        article_cid = match.group(2)
        try:
            html = html.replace(match.group(0), "/" + article_cid_to_uri[article_cid])
        except KeyError:
            pass

    return html


def _find_list_max_overlap_end_index(arr: list[str], seq: list[str]) -> int | None:
    assert len(seq) > 0
    for i in range(len(arr), len(seq) - 1, -1):
        if arr[i - len(seq) : i] == seq:
            return i - 1
    return None


def _clean_msg(m: str) -> str:
    return re.sub("['\\s]", "", m)


def _commit_messages(output_repo_path: str) -> list[str]:
    git_log = subprocess.run(
        ["git", "log", "--pretty=format:'%s'"],
        cwd=output_repo_path,
        capture_output=True,
        text=True,
    )

    return list(reversed(git_log.stdout.split("\n")))


def _play_commits(
    commits: list[Commit], init: bool, output_repo_path: str
) -> Generator[Commit, None, None]:
    if init:
        _init_repo(output_repo_path)
        repo_commit_messages = []
        commits_match_index = -1
    else:
        repo_commit_messages = _commit_messages(output_repo_path)
        if len(repo_commit_messages) >= COMMITS_MATCH_SPAN:
            commits_match_index = _find_list_max_overlap_end_index(
                [_clean_msg(c.title) for c in commits],
                [_clean_msg(t) for t in repo_commit_messages[-COMMITS_MATCH_SPAN:]],
            )
        else:
            commits_match_index = -1

    tz = pytz.timezone("UTC")

    assert len(commits) >= len(
        repo_commit_messages
    ), f"len(commits)={len(commits)} len(repo_commits)={len(repo_commit_messages)}"

    article_cid_to_uri: dict[Cid, Uri] = {}

    for i, commit in enumerate(
        tqdm.tqdm(
            commits,
            desc=f"Replaying commits ({len(commits)-commits_match_index-1} new commits)",
        )
    ):
        yield commit

        should_replay = (commits_match_index is None) or i > commits_match_index

        for cid, (uri, html) in commit.article_changes.items():
            if html is None:
                assert cid in article_cid_to_uri, (cid, article_cid_to_uri)
                del article_cid_to_uri[cid]

                if should_replay:
                    subprocess.run(["git", "rm", uri, "--quiet"], cwd=output_repo_path)
            else:
                old_uri = article_cid_to_uri.get(cid, None)
                article_cid_to_uri[cid] = uri

                if should_replay:
                    html = _resolve_links(html, article_cid_to_uri)

                    abs_path = os.path.abspath(os.path.join(output_repo_path, uri))
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

                    if old_uri is not None and uri != old_uri:
                        subprocess.run(
                            ["git", "mv", "-f", old_uri, uri],
                            cwd=output_repo_path,
                        )

                    with open(abs_path, "w") as f:
                        f.write(html)
                    subprocess.run(
                        ["git", "add", uri],
                        cwd=output_repo_path,
                    )

        if should_replay:
            # TODO ms vs s
            date_dt = datetime.fromtimestamp(math.floor(commit.timestamp / 1000), tz)

            # TODO
            if date_dt.year >= 2038:
                date_dt = datetime(2038, 1, 1)
            if date_dt.year <= 1969:
                date_dt = datetime(1970, 1, 2)  # GitHub doesn't like Jan 1

            date_str = date_dt.isoformat()
            date_with_format_str = "format:iso8601:" + date_str

            env = os.environ.copy()
            env["GIT_COMMITTER_DATE"] = date_with_format_str

            subprocess.run(
                [
                    "git",
                    "commit",
                    "--date",
                    date_with_format_str,
                    "-m",
                    commit.title,
                    "--quiet",
                    "--allow-empty",
                ],
                env=env,
                cwd=output_repo_path,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="legifrance-bot")

    parser.add_argument(
        "-t",
        "--test-code",
        help="Select CODE_DU_TRAVAIL_MARITIME to process instead of all of them",
        action="store_true",
    )
    parser.add_argument(
        "-c",
        "--only-from-cache",
        help="Take everything from cache, don't query server",
        action="store_true",
    )
    parser.add_argument(
        "-n",
        help="Number of codes to use",
    )
    parser.add_argument(
        "--init",
        help="Start from a fresh output repo",
        action="store_true",
    )

    args = parser.parse_args()
    client = CachedLegifranceClient(args.only_from_cache)
    code_list = client.fetch_code_list()

    assert CID_CODE_DU_TRAVAIL_MARITIME in {c["cid"] for c in code_list}

    if args.test_code:
        code_list = [
            c for c in code_list if c["cid"] == CID_CODE_DU_TRAVAIL_MARITIME
        ]  # "LEGITEXT000006071190"]

    if args.n:
        code_list = code_list[: int(args.n)]

    articles = client.fetch_articles_from_codes(code_list)
    commits = get_commits(articles)

    # Play all commits, we used a generator to make testing easier
    for _ in _play_commits(commits, args.init, OUTPUT_REPO_PATH):
        pass

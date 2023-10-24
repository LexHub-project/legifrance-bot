import argparse
import math
import os
import subprocess
from datetime import datetime
from typing import Callable, Generator

import pytz

from commit_state_to_md import to_one_file_per_article, to_one_file_per_code
from commits import ArticleJSON, CodeJSON, get_commits
from constants import CID_CODE_DU_TRAVAIL_MARITIME
from fetch_data import CachedLegifranceClient
from to_commit_state import StateAtCommit, generate_commit_states

OUTPUT_REPO_PATH = "./output"
DEFAULT_COMMIT_MESSAGE = "Modifié par un texte d'une portée générale"


def _process(
    code_tms: list[CodeJSON], articles_by_code: dict[str, ArticleJSON]
) -> Generator[StateAtCommit, None, None]:
    articles = [a for v in articles_by_code.values() for a in v]
    commits = get_commits(articles)
    yield from generate_commit_states(code_tms, commits, articles_by_code)


def _yield_entries_from_flatten_dict(d: dict | str, paths=[]):
    if isinstance(d, dict):
        for path, content in d.items():
            yield from _yield_entries_from_flatten_dict(content, paths + [path])
    else:
        yield os.path.join(*paths), d


DATE_DUMP_GENERATED = datetime.now().isoformat()


def _build_git_repo_readme():
    with open(f"{OUTPUT_REPO_PATH}/README.md", "w") as f:
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


def _build_git_repo(
    states: list[StateAtCommit],
    to_files: Callable[[StateAtCommit], dict],
):
    subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
    os.makedirs(OUTPUT_REPO_PATH, exist_ok=True)
    subprocess.run(["git", "init", OUTPUT_REPO_PATH])

    tz = pytz.timezone("UTC")

    for s in states:
        subprocess.run(["git", "rm", "-r", "."], cwd=OUTPUT_REPO_PATH)
        _build_git_repo_readme()

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
        "-c",
        "--only-from-cache",
        help="Take everything from cache, don't query server",
        action="store_true",
    )

    args = parser.parse_args()
    client = CachedLegifranceClient(args.only_from_cache)
    code_list = client.fetch_code_list()

    assert CID_CODE_DU_TRAVAIL_MARITIME in {c["cid"] for c in code_list}

    if args.test_code:
        code_list = [c for c in code_list if c["cid"] == CID_CODE_DU_TRAVAIL_MARITIME]

    code_tms = list(client.fetch_tms(code_list))

    articles_by_code: dict[str, ArticleJSON] = {
        tm["cid"]: client.fetch_articles(tm) for tm in code_tms
    }

    states = list(_process(code_tms, articles_by_code))

    _build_git_repo(states, args.to_files)

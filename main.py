import argparse
import math
import os
import subprocess
from datetime import datetime

import pytz

from commits import ArticleJSON, get_commits, Commit
from constants import CID_CODE_DU_TRAVAIL_MARITIME
from fetch_data import CachedLegifranceClient

OUTPUT_REPO_PATH = "./output"
DEFAULT_COMMIT_MESSAGE = "Modifié par un texte d'une portée générale"


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


def _ensure_dir_exists(uri: str):
    parent_path = os.path.dirname(uri)
    if not os.path.isdir(parent_path):
        dirs = parent_path.split(os.sep)
        for i in range(len(dirs)):
            p = os.path.join(*dirs[: i + 1])
            if not os.path.isdir(p):
                os.mkdir(p)


def _build_git_repo(commits: list[Commit]):
    subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
    os.makedirs(OUTPUT_REPO_PATH, exist_ok=True)
    subprocess.run(["git", "init", OUTPUT_REPO_PATH])

    tz = pytz.timezone("UTC")

    for i, c in enumerate(commits):
        # print(c)
        # input("Press Enter to continue...")
        if i == 0:
            _build_git_repo_readme()
            subprocess.call(["git", "add", "README.md"], cwd=OUTPUT_REPO_PATH)
        for uri, text in c.article_changes.items():
            if uri.endswith("/34.md"):
                print("\n\n", f"== {34} ==")
                print(text)
                print(c.article_moves)
                input("Press Enter to continue...")
            # update
            if text is not None:
                # ensure dir exists or create it
                full_uri = f"{OUTPUT_REPO_PATH}/{uri}"
                _ensure_dir_exists(full_uri)
                # write file
                with open(full_uri, "w") as f:
                    f.write(text)
                subprocess.run(["git", "add", uri], cwd=OUTPUT_REPO_PATH)
            else:
                try:
                    subprocess.check_output(["git", "rm", uri], cwd=OUTPUT_REPO_PATH)
                except subprocess.CalledProcessError as e:
                    print(f"@delete {uri}")
                    print(e.output)
                    input("Press Enter to continue...")
            if uri in c.article_moves:
                assert uri != c.article_moves[uri]
                try:
                    full_uri = os.path.join(OUTPUT_REPO_PATH, c.article_moves[uri])
                    _ensure_dir_exists(full_uri)
                    subprocess.check_output(
                        ["git", "mv", "-f", uri, c.article_moves[uri]],
                        cwd=OUTPUT_REPO_PATH,
                    )
                except subprocess.CalledProcessError as e:
                    print("@from", uri)
                    print("@to", c.article_moves[uri])
                    print("error", e.output)
                    input("Press Enter to continue...")

        # TODO ms vs s
        date_dt = datetime.fromtimestamp(math.floor(c.timestamp / 1000), tz)

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
                c.title or DEFAULT_COMMIT_MESSAGE,
            ],
            env=env,
            cwd=OUTPUT_REPO_PATH,
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

    code_tms = list(client.fetch_tms(code_list))

    articles_by_code: dict[str, list[ArticleJSON]] = {
        tm["cid"]: client.fetch_articles(tm) for tm in code_tms
    }

    articles = [a for v in articles_by_code.values() for a in v]
    commits = get_commits(articles)

    _build_git_repo(commits)

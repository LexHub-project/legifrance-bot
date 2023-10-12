import io
import itertools
import json
import math
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Tuple

import pytz
from clean_article_html import clean_article_html
from client import LegifranceClient
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

CACHE_DIR = "./cache"

CLIENT_ID = os.environ.get("CLIENT_ID", None)
assert CLIENT_ID

CLIENT_SECRET = os.environ.get("CLIENT_SECRET", None)
assert CLIENT_SECRET

client = LegifranceClient(CLIENT_ID, CLIENT_SECRET)

OUTPUT_REPO_PATH = "../legifrance"


codes = client.get_codes_list()

for i, c in enumerate(codes):
    if c["etat"] == "VIGUEUR":
        print(f"{i}: {c['cid']} - {c['titre']}")

code_cids = ["LEGITEXT000044595989", "LEGITEXT000006072051"]


ArticleJSON = dict
CodeJSON = dict


@dataclass
class Commit:
    title: str
    timestamp: int
    article_changes: dict[str, str]


@dataclass
class StateAtCommit:
    title: str
    timestamp: int
    full_code_texts: list[Tuple[str, str]]


def _yield_article_ids(tm: CodeJSON) -> Generator[Tuple[str, str], None, None]:
    if len(tm["articles"]) > 0:
        for article in tm["articles"]:
            yield (article["cid"], article["id"])

    if len(tm["sections"]) > 0:
        for section in tm["sections"]:
            yield from _yield_article_ids(section)


def _fetch_and_cache_article_with_history(path: str, cid: str) -> ArticleJSON:
    article = client.get_article(cid)

    with open(path, "w") as f:
        json.dump(article, f, indent=4)

    return article


def fetch_article_with_history(cid: str, ids: set[str]) -> ArticleJSON:
    path = f"{CACHE_DIR}/articles/{cid}.json"

    try:
        with open(path, "r") as f:
            article = json.load(f)

            existing_ids = {a["id"] for a in article["listArticle"]}

            if len(ids.difference(existing_ids)) > 0:
                print(f"Outdated {cid}, refetching")
                return _fetch_and_cache_article_with_history(path, cid)

            return article

    except (IOError, ValueError):
        return _fetch_and_cache_article_with_history(path, cid)


def fetch_articles(tm: CodeJSON) -> list[ArticleJSON]:
    print(f"{tm['cid']} - {tm['title']}")

    ids = sorted(list(_yield_article_ids(tm)), key=lambda x: x[0])
    grouped_by_cid = [
        (cid, {i[1] for i in with_same_cid})
        for (cid, with_same_cid) in itertools.groupby(ids, key=lambda x: x[0])
    ]

    return [fetch_article_with_history(cid, ids) for (cid, ids) in tqdm(grouped_by_cid)]


def get_commits(article: ArticleJSON) -> dict[str, Commit]:
    commits = {}
    for version in article["listArticle"]:
        modifs = version["lienModifications"]
        timestamp: int = version["dateDebut"]
        textCids: list[str] = sorted({m["textCid"] for m in modifs})

        if len(textCids) == 0:
            textCids = ["???"]
            # TODO

        commitId = f"{timestamp}-{'-'.join(textCids)}"

        # TODO
        # TODO add nota?
        commitTitle = "Modifications par " + " & ".join(
            {m["textTitle"] if m["textTitle"] is not None else "?TODO?" for m in modifs}
        )
        text = version["texteHtml"]

        assert commitId not in commits
        commits[commitId] = Commit(
            title=commitTitle,
            timestamp=timestamp,
            article_changes={version["cid"]: text},
        )

    return commits


def merge_commits(all_commits: list[dict[str, Commit]]) -> dict[str, Commit]:
    merged: dict[str, Commit] = {}
    for partial in all_commits:
        for commit_id, c in partial.items():
            if commit_id in merged:
                assert merged[commit_id].timestamp == c.timestamp
                # TODO: humans ...
                # assert merged[commit_id].title == c.title, merged[commit_id].title  + " !== " + c.title

                for article_cid, text in c.article_changes.items():
                    assert article_cid not in merged[commit_id].article_changes, (
                        commit_id,
                        article_cid,
                        text,
                    )
                    merged[commit_id].article_changes[article_cid] = text

            else:
                merged[commit_id] = c

    return merged


def last_text(commits: list[Commit], cid: str) -> str:
    for c in reversed(commits):
        if cid in c.article_changes:
            return c.article_changes[cid]

    # BUG / TODO
    # https://github.com/LexHub-project/legifrance-bot/issues/22
    # raise KeyError(cid)
    return "<TODO>"


def header(level: int, text: str) -> str:
    # TODO, for now limited to level 6
    return ("#" * min(level, 6)) + " " + text


def article_to_header_text(article: ArticleJSON) -> str:
    return f"Article {article['num']}"


def header_to_anchor(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


def print_tm(
    tm: CodeJSON,
    commits: list[Commit],
    text_to_cid_to_anchor: dict[str, dict[str, str]],
    file,
    level=1,
) -> None:
    if tm["etat"] == "ABROGE":
        return

    print(header(level, tm["title"]), file=file)

    for article in tm["articles"]:
        if article["etat"] != "ABROGE":
            print(header(level + 1, article_to_header_text(article)), file=file)
            print(
                clean_article_html(
                    last_text(commits, article["cid"]), text_to_cid_to_anchor
                ),
                file=file,
            )
            print("\n", file=file)

    for section in tm["sections"]:
        print_tm(section, commits, text_to_cid_to_anchor, file=file, level=level + 1)

    if "commentaire" in tm and tm["commentaire"] is not None:
        print(tm["commentaire"], file=file)
    # assert False, tm
    # TODO


def process(
    code_tms: list[CodeJSON], articles: list[ArticleJSON]
) -> Generator[StateAtCommit, None, None]:
    all_commits = [get_commits(a) for a in articles]
    merged = merge_commits(all_commits)
    sorted_commits = sorted(merged.values(), key=lambda c: c.timestamp)

    text_to_cid_to_anchor = {
        tm["cid"]: {
            article["listArticle"][0]["cid"]: header_to_anchor(
                article_to_header_text(article["listArticle"][0])
            )
            for article in articles
        }
        for tm in code_tms
    }

    for i in tqdm(range(0, len(sorted_commits) - 1), desc="Processing"):
        full_code_texts = []
        for tm in code_tms:
            f = io.StringIO()
            print_tm(tm, sorted_commits[: (i + 1)], text_to_cid_to_anchor, file=f)
            full_code_texts.append((tm["title"], f.getvalue()))

        yield StateAtCommit(
            title=sorted_commits[i].title,
            timestamp=sorted_commits[i].timestamp,
            full_code_texts=full_code_texts,
        )


code_tms = [client.get_tm(c) for c in code_cids]
articles = [a for tm in code_tms for a in fetch_articles(tm)]
commits = list(process(code_tms, articles))


subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
subprocess.run(["mkdir", OUTPUT_REPO_PATH])
subprocess.run(["git", "init", OUTPUT_REPO_PATH])

tz = pytz.timezone("UTC")

for c in commits:
    for title, full_text in c.full_code_texts:
        with open(f"{OUTPUT_REPO_PATH}/{title}.md", "w") as f:
            f.write(full_text)

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

    subprocess.run(["git", "add", "."], cwd=OUTPUT_REPO_PATH)
    subprocess.run(
        [
            "git",
            "commit",
            "--date",
            date_with_format_str,
            "-m",
            c.title,
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

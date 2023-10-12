import requests
import json
from tqdm import tqdm
from datetime import datetime
from typing import Generator
import os
import io
from dotenv import load_dotenv
import subprocess
import pytz
from client import LegifranceClient


load_dotenv()

CACHE_DIR = "./cache"

CLIENT_ID = os.environ.get("CLIENT_ID", None)
assert CLIENT_ID

CLIENT_SECRET = os.environ.get("CLIENT_SECRET", None)
assert CLIENT_SECRET

client = LegifranceClient(CLIENT_ID, CLIENT_SECRET)

OUTPUT_REPO_PATH = "../legifrance"

URL_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"


l = client.get_codes_list()

for i, c in enumerate(l["results"]):
    if c["etat"] == "VIGUEUR":
        print(f"{i}: {c['titre']} - {c['cid']}")

code = "LEGITEXT000044595989"


def _yield_article_ids(tm):
    if len(tm["articles"]) > 0:
        for article in tm["articles"]:
            yield (article["cid"], article["id"])

    if len(tm["sections"]) > 0:
        for section in tm["sections"]:
            yield from _yield_article_ids(section)


def _fetch_and_cache_article_with_history(path: str, cid: str):
    article = client.get_article(cid)

    with open(path, "w") as f:
        json.dump(article, f, indent=4)

    return article


def fetch_article_with_history(cid: str, id: str):
    path = f"{CACHE_DIR}/articles/{cid}.json"

    try:
        with open(path, "r") as f:
            article = json.load(f)

            ids = {a["id"] for a in article["listArticle"]}
            if id not in ids:
                print(f"Outdated {cid}, refetching")
                return _fetch_and_cache_article_with_history(path, cid)

            return article

    except (IOError, ValueError):
        return _fetch_and_cache_article_with_history(path, cid)


def fetch_articles(tm):
    return [
        fetch_article_with_history(cid, i)
        for (cid, i) in tqdm(list(_yield_article_ids(tm)))
    ]


def get_commits(article):
    commits = {}
    for version in article["listArticle"]:
        modifs = version["lienModifications"]
        date = version["dateDebut"]
        textCids = sorted({m["textCid"] for m in modifs})

        if len(textCids) == 0:
            textCids = {"???"}
            # TODO

        commitId = f"{date}-{'-'.join(textCids)}"
        # TODO
        # TODO add nota?
        commitTitle = "Modifications par " + " & ".join(
            {m["textTitle"] if m["textTitle"] is not None else "?TODO?" for m in modifs}
        )
        text = version["texteHtml"]  # TODO html?

        assert commitId not in commits
        commits[commitId] = {
            "commitTitle": commitTitle,
            "articles": {version["cid"]: text},
            "date": date,
        }

    return commits


def merge_commits(all_commits):
    merged = {}
    for partial in all_commits:
        for commitId, c in partial.items():
            if commitId in merged:
                assert merged[commitId]["date"] == c["date"]
                # TODO: humans ...
                # assert merged[commitId]['commitTitle'] == c['commitTitle'], merged[commitId]['commitTitle']  + " !== " + c['commitTitle']

                for articleCid, text in c["articles"].items():
                    assert articleCid not in merged[commitId]["articles"]
                    merged[commitId]["articles"][articleCid] = text

            else:
                merged[commitId] = c

    return merged


def last_text(commits: list[dict], cid):
    for c in reversed(commits):
        if cid in c["articles"]:
            return c["articles"][cid]

    return "<TODO>"


from clean_article_html import clean_article_html


def header(level, text):
    # TODO, for now limited to level 6
    return ("#" * min(level, 6)) + " " + text


def article_to_header_text(article):
    return f"Article {article['num']}"


def header_to_anchor(s: str):
    return s.strip().lower().replace(" ", "-")


def print_tm(
    tm, commits, text_to_cid_to_anchor: dict[str, dict[str, str]], file, level=1
):
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


def process(tm: dict, articles: list[dict]) -> Generator[str, None, None]:
    all_commits = [get_commits(a) for a in articles]
    merged = merge_commits(all_commits)
    sorted_commits = sorted(merged.values(), key=lambda c: c["date"])

    text_to_cid_to_anchor = {
        tm["cid"]: {
            article["listArticle"][0]["cid"]: header_to_anchor(
                article_to_header_text(article["listArticle"][0])
            )
            for article in articles
        }
    }

    for i in range(0, len(sorted_commits) - 1):
        f = io.StringIO()
        print_tm(tm, sorted_commits[: (i + 1)], text_to_cid_to_anchor, file=f)

        date = sorted_commits[i]["date"] / 1000  # TODO ms vs s
        title = sorted_commits[i]["commitTitle"]

        yield (f.getvalue(), date, title)


tm = client.get_tm(code)
# for debugging
with open("code.json", "w") as f:
    f.write(json.dumps(tm, indent=4))

articles = fetch_articles(tm)
commits = process(tm, articles)




subprocess.run(["rm", "-rf", OUTPUT_REPO_PATH])
subprocess.run(["mkdir", OUTPUT_REPO_PATH])
subprocess.run(["git", "init", OUTPUT_REPO_PATH])

tz = pytz.timezone("UTC")

for (full_code_text, date, title) in commits:
    with open(f"{OUTPUT_REPO_PATH}/{tm['title']}.md", "w") as f:
        f.write(full_code_text)

    date_dt = datetime.fromtimestamp(date, tz)

    # TODO
    if date_dt.year >= 2038:
        date_dt = datetime(2038, 1, 1)

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
            title,
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

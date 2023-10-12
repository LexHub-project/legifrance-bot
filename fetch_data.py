import itertools
import json
import os
from typing import Generator, Tuple

from dotenv import load_dotenv
from tqdm import tqdm

from commits import ArticleJSON, CodeJSON
from legifrance_client import LegifranceClient

CACHE_DIR = "./cache"

load_dotenv()


CLIENT_ID = os.environ.get("CLIENT_ID", None)
assert CLIENT_ID

CLIENT_SECRET = os.environ.get("CLIENT_SECRET", None)
assert CLIENT_SECRET

client = LegifranceClient(CLIENT_ID, CLIENT_SECRET)


def _yield_article_ids(tm: CodeJSON) -> Generator[Tuple[str, str], None, None]:
    if len(tm["articles"]) > 0:
        for article in tm["articles"]:
            yield (article["cid"], article["id"])

    if len(tm["sections"]) > 0:
        for section in tm["sections"]:
            yield from _yield_article_ids(section)


def _fetch_and_cache_article_with_history(path: str, cid: str) -> ArticleJSON:
    article = client.fetch_article(cid)

    with open(path, "w") as f:
        json.dump(article, f, indent=4)

    return article


def _fetch_article_with_history(cid: str, ids: set[str]) -> ArticleJSON:
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

    return [
        _fetch_article_with_history(cid, ids) for (cid, ids) in tqdm(grouped_by_cid)
    ]


def fetch_and_print_codes_list() -> None:
    codes = client.fetch_codes_list()
    for i, c in enumerate(codes):
        if c["etat"] == "VIGUEUR":
            print(f"{i}: {c['cid']} - {c['titre']}")


def fetch_tms(cids: [str]) -> Generator[CodeJSON, None, None]:
    for cid in tqdm(cids, "Getting TM"):
        tm = client.fetch_tm(cid)

        del tm["executionTime"]

        with open(f"{CACHE_DIR}/codes/{cid}.json", "w") as f:
            f.write(json.dumps(tm, indent=4))

        yield tm

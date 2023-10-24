import itertools
import json
import os
from functools import cached_property
from typing import Generator, Tuple

from dotenv import load_dotenv
from tqdm import tqdm

from commits import ArticleJSON, CodeJSON
from legifrance_client import LegifranceClient

CACHE_DIR = "./cache"

load_dotenv()


class CachedLegifranceClient:
    def __init__(self, only_from_disk=False):
        self._only_from_disk = only_from_disk

    @cached_property
    def _client(self):
        assert not self._only_from_disk

        CLIENT_ID = os.environ.get("CLIENT_ID", None)
        CLIENT_SECRET = os.environ.get("CLIENT_SECRET", None)

        return LegifranceClient(CLIENT_ID, CLIENT_SECRET)

    def _yield_article_ids(
        self, tm: CodeJSON
    ) -> Generator[Tuple[str, str], None, None]:
        if len(tm["articles"]) > 0:
            for article in tm["articles"]:
                yield (article["cid"], article["id"])

        if len(tm["sections"]) > 0:
            for section in tm["sections"]:
                yield from self._yield_article_ids(section)

    def _article_path(self, cid: str) -> str:
        return f"{CACHE_DIR}/articles/{cid}.json"

    def _fetch_and_cache_article_with_history(self, cid: str) -> ArticleJSON:
        article = self._client.fetch_article(cid)

        with open(self._article_path(cid), "w") as f:
            json.dump(article, f, indent=4)

        return article

    def _fetch_article_from_disk(self, cid: str) -> ArticleJSON:
        with open(self._article_path(cid), "r") as f:
            return json.load(f)

    def _fetch_article_with_history(self, cid: str, ids: set[str]) -> ArticleJSON:
        try:
            article = self._fetch_article_from_disk(cid)

            existing_ids = {a["id"] for a in article["listArticle"]}

            if len(ids.difference(existing_ids)) > 0:
                print(f"Outdated {cid}, refetching")
                return self._fetch_and_cache_article_with_history(cid)

            return article

        except (IOError, ValueError):
            return self._fetch_and_cache_article_with_history(cid)

    def fetch_articles(self, tm: CodeJSON) -> list[ArticleJSON]:
        ids = sorted(list(self._yield_article_ids(tm)), key=lambda x: x[0])
        grouped_by_cid = [
            (cid, {i[1] for i in with_same_cid})
            for (cid, with_same_cid) in itertools.groupby(ids, key=lambda x: x[0])
        ]

        return [
            self._fetch_article_with_history(cid, ids)
            for (cid, ids) in tqdm(grouped_by_cid, desc=f"{tm['cid']} - {tm['title']}")
        ]

    def _tm_path(self, cid: str) -> str:
        return f"{CACHE_DIR}/codes/{cid}.json"

    def _fetch_tms_from_network(
        self, cids: list[str]
    ) -> Generator[CodeJSON, None, None]:
        assert not self._only_from_disk

        for cid in tqdm(cids, "Getting TM"):
            tm = self._client.fetch_tm(cid)

            del tm["executionTime"]
            del tm["fileSize"]

            with open(self._tm_path(cid), "w") as f:
                f.write(json.dumps(tm, indent=4))

            yield tm

    def _fetch_tms_from_disk(self, cids: list[str]) -> Generator[CodeJSON, None, None]:
        assert self._only_from_disk

        for cid in tqdm(cids, "Getting TM"):
            with open(self._tm_path(cid), "r") as f:
                yield json.load(f)

    def fetch_tms(self, cids: list[str]) -> Generator[CodeJSON, None, None]:
        if self._only_from_disk:
            yield from self._fetch_tms_from_disk(cids)
        else:
            yield from self._fetch_tms_from_network(cids)

    def _fetch_code_list(self) -> dict:
        cache_path = f"{CACHE_DIR}/codelist.json"

        if self._only_from_disk:
            with open(cache_path, "r") as f:
                return json.load(f)
        else:
            list = self._client.fetch_codes_list()
            with open(cache_path, "w") as f:
                f.write(json.dumps(list, indent=4))

            return list

    def fetch_code_cids(self) -> list[str]:
        list = self._fetch_code_list()
        return [c["cid"] for c in list]

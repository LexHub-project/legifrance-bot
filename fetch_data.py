import datetime
import itertools
import json
import os
from functools import cached_property
from typing import Generator, Tuple

from dotenv import load_dotenv
from tqdm import tqdm

from commits import ArticleJSON, CodeJSON, CodeListJSON
from constants import DATE_STR_FMT
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
    ) -> Generator[Tuple[str, str, str], None, None]:
        if len(tm["articles"]) > 0:
            for article in tm["articles"]:
                yield (article["cid"], article["id"], article["etat"])

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

    def _fetch_article_with_history(
        self, cid: str, ids_with_state: set[Tuple[str, str]]
    ) -> ArticleJSON:
        try:
            article = self._fetch_article_from_disk(cid)
            if self._only_from_disk:
                return article
            existing_ids_with_state = {
                (a["id"], a["etat"]) for a in article["listArticle"]
            }

            if len(ids_with_state.difference(existing_ids_with_state)) > 0:
                print(f"Outdated {cid}, refetching")
                return self._fetch_and_cache_article_with_history(cid)

            return article

        except (IOError, ValueError):
            return self._fetch_and_cache_article_with_history(cid)

    def fetch_articles(self, tm: CodeJSON) -> list[ArticleJSON]:
        ids = sorted(list(self._yield_article_ids(tm)), key=lambda x: x[0])

        grouped_by_cid = [
            (cid, {(i[1], i[2]) for i in with_same_cid})
            for (cid, with_same_cid) in itertools.groupby(ids, key=lambda x: x[0])
        ]

        return [
            self._fetch_article_with_history(cid, ids_with_state)
            for (cid, ids_with_state) in tqdm(
                grouped_by_cid, desc=f"{tm['cid']} - {tm['title']}"
            )
        ]

    def _tm_path(self, cid: str) -> str:
        return f"{CACHE_DIR}/codes/{cid}.json"

    def _fetch_tm_from_network_and_cache(self, cid: str) -> CodeJSON:
        print(f"Outdated TM, fetching: {cid}")

        tm = self._client.fetch_tm(cid)

        del tm["executionTime"]
        del tm["fileSize"]

        with open(self._tm_path(cid), "w") as f:
            f.write(json.dumps(tm, indent=4))

        return tm

    def _fetch_tm_from_disk(self, cid: str) -> CodeJSON | None:
        try:
            with open(self._tm_path(cid), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def fetch_tms(self, code_list: CodeListJSON) -> Generator[CodeJSON, None, None]:
        for c in tqdm(code_list, "Getting TM"):
            value = self._fetch_tm_from_disk(c["cid"])

            if not self._only_from_disk:
                cached_date = (
                    datetime.datetime.strptime(
                        value["modifDate"], DATE_STR_FMT
                    ).replace(tzinfo=datetime.timezone.utc)
                    if value is not None
                    else None
                )
                list_date = datetime.datetime.fromisoformat(c["lastUpdate"])
                if cached_date != list_date:
                    value = self._fetch_tm_from_network_and_cache(c["cid"])

            assert value is not None
            yield value

    def fetch_code_list(self) -> CodeListJSON:
        cache_path = f"{CACHE_DIR}/codelist.json"

        if self._only_from_disk:
            with open(cache_path, "r") as f:
                return json.load(f)
        else:
            list = sorted(self._client.fetch_codes_list(), key=lambda c: c["cid"])

            with open(cache_path, "w") as f:
                f.write(json.dumps(list, indent=4))

            return list

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

    def _yield_entries_from_tm(
        self, tm: CodeJSON
    ) -> Generator[Tuple[str, str, str], None, None]:
        if len(tm["articles"]) > 0:
            for entry in tm["articles"]:
                yield entry

        if len(tm["sections"]) > 0:
            for section in tm["sections"]:
                yield from self._yield_entries_from_tm(section)

    def _entries_grouped_by_cid(self, tm: CodeJSON):
        entries = sorted(self._yield_entries_from_tm(tm), key=lambda e: e["cid"])

        return {
            cid: list(entries)
            for cid, entries in itertools.groupby(entries, key=lambda e: e["cid"])
        }

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
        self, cid: str, ids: set[str], force_refetch: bool
    ) -> ArticleJSON:
        try:
            article = self._fetch_article_from_disk(cid)
            if self._only_from_disk:
                return article

            existing_ids = {a["id"] for a in article["listArticle"]}

            if force_refetch or len(ids.difference(existing_ids)) > 0:
                print(f"Outdated {cid}, refetching")
                return self._fetch_and_cache_article_with_history(cid)

            return article

        except (IOError, ValueError):
            return self._fetch_and_cache_article_with_history(cid)

    def _fetch_articles(
        self, new_tm: CodeJSON, cached_tm: CodeJSON
    ) -> list[ArticleJSON]:
        new_entries = self._entries_grouped_by_cid(new_tm)
        old_entries = self._entries_grouped_by_cid(cached_tm)

        for cid in tqdm(new_entries, desc=f"{new_tm['cid']} - {new_tm['title']}"):
            new_article_entries = new_entries[cid]
            old_article_entries = old_entries[cid]

            ids = {e["id"] for e in new_article_entries}
            force_refetch = new_article_entries != old_article_entries

            yield self._fetch_article_with_history(cid, ids, force_refetch)

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

    def _fetch_tm(self, code_list_entry: dict) -> Tuple[CodeJSON, CodeJSON]:
        disk_value = self._fetch_tm_from_disk(code_list_entry["cid"])

        if self._only_from_disk:
            assert disk_value is not None
            return (disk_value, disk_value)

        else:
            cached_date = (
                datetime.datetime.strptime(
                    disk_value["modifDate"], DATE_STR_FMT
                ).replace(tzinfo=datetime.timezone.utc)
                if disk_value is not None
                else None
            )
            list_date = datetime.datetime.fromisoformat(code_list_entry["lastUpdate"])
            if cached_date == list_date:
                assert disk_value is not None
                return (disk_value, disk_value)
            else:
                network_value = self._fetch_tm_from_network_and_cache(
                    code_list_entry["cid"]
                )
                assert network_value is not None
                return (network_value, disk_value)

    def _fetch_tms(
        self, code_list: CodeListJSON
    ) -> Generator[Tuple[CodeJSON, list[str]], None, None]:
        for c in tqdm(code_list, "Getting TM"):
            yield self._fetch_tm(c)

    def fetch_articles_from_codes(self, code_list: CodeListJSON):
        tms = list(self._fetch_tms(code_list))

        for new_tm, cached_tm in tms:
            yield from self._fetch_articles(new_tm, cached_tm)

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

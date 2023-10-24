from commits import ArticleJSON, CodeJSON
import json
import pytest
from tm import (
    _patch_tm_missing_sections,
    _patch_tm_multiple_paths,
    _is_path_valid,
    _article_exists_at_path,
)


@pytest.fixture(scope="module")
def tm() -> CodeJSON:
    with open("cache/codes/LEGITEXT000006072051.json", "r") as f:
        return json.load(f)


def read_article(cid: str) -> ArticleJSON:
    with open(f"fixtures/{cid}.json", "r") as f:
        return json.load(f)


PATH_ERROR_CID = "LEGIARTI000006652601_new_path"
MISSING_PATH = ["LEGISCTA000006101384", "TEST_ID"]


def test_patch_tm_missing_sections(tm):
    assert not _is_path_valid(tm, MISSING_PATH)
    path_error_article = read_article(PATH_ERROR_CID)
    patched_tm = _patch_tm_missing_sections(tm, [path_error_article])
    assert _is_path_valid(patched_tm, MISSING_PATH)


MULTIPLE_PATH_CID = "LEGIARTI000006652601"
ARTICLE_OK_PATH = ["LEGISCTA000006101385", "LEGISCTA000006123928"]
MISSING_ARTICLE_PATH = ["LEGISCTA000006101384", "LEGISCTA000006123925"]
TIMESTAMP = 879897600000


def test_path_tm_multiple_paths(tm):
    article = read_article(MULTIPLE_PATH_CID)
    assert _article_exists_at_path(tm, ARTICLE_OK_PATH, MULTIPLE_PATH_CID)
    assert not _article_exists_at_path(tm, MISSING_ARTICLE_PATH, MULTIPLE_PATH_CID)
    patched_tm = _patch_tm_multiple_paths(tm, [article], TIMESTAMP)
    assert _article_exists_at_path(patched_tm, ARTICLE_OK_PATH, MULTIPLE_PATH_CID)
    assert _article_exists_at_path(patched_tm, MISSING_ARTICLE_PATH, MULTIPLE_PATH_CID)


OK_ARTICLE_CIDS = ["LEGIARTI000006652410", "LEGIARTI000023181567"]
TIMESTAMP_2 = 1698076959000


def test_tm_unchanged_if_no_error(tm):
    articles = [read_article(cid) for cid in OK_ARTICLE_CIDS]
    sections_patched_tm = _patch_tm_missing_sections(tm, articles)
    assert sections_patched_tm == tm
    multiple_paths_patched_tm = _patch_tm_multiple_paths(tm, articles, TIMESTAMP_2)
    assert multiple_paths_patched_tm == tm

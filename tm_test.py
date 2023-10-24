from commits import ArticleJSON, CodeJSON
import json
import pytest
from tm import (
    _patch_tm_missing_sections,
    _patch_tm_multiple_paths,
    _is_path_valid,
    _article_exists_at_path,
)


def read_tm(cid: str) -> CodeJSON:
    with open(f"cache/codes/{cid}.json", "r") as f:
        return json.load(f)


def read_article(cid: str) -> ArticleJSON:
    with open(f"fixtures/{cid}.json", "r") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "tm_cid,article_cid,missing_path",
    [
        (  # home-made example
            "LEGITEXT000006072051",
            "LEGIARTI000006652601_new_path",
            ["LEGISCTA000006101384", "TEST_ID"],
        ),
        (  # R621-92 code du patrimoine, has duplicates in titresTM
            "LEGITEXT000006074236",
            "LEGIARTI000024242164",
            [
                "LEGISCTA000024239714",
                "LEGISCTA000024241830",
                "LEGISCTA000024241921",
                "LEGISCTA000024241923",
                "LEGISCTA000024242160",
                "LEGISCTA000024242162",
            ],
        ),
    ],
)
def test_patch_tm_missing_sections(tm_cid, article_cid, missing_path):
    tm = read_tm(tm_cid)
    articles = [read_article(article_cid)]
    assert not _is_path_valid(tm, missing_path)
    patched_tm = _patch_tm_missing_sections(tm, articles)
    assert _is_path_valid(patched_tm, missing_path)


@pytest.fixture(scope="module")
def tm():
    return read_tm("LEGITEXT000006072051")


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


@pytest.mark.parametrize(
    "tm_cid,articles_cids,timestamp",
    [
        ("LEGITEXT000006072051", OK_ARTICLE_CIDS, 1698076959000),
        (
            "LEGITEXT000006071366",
            ["LEGIARTI000006579186"],  # article with empty path / titresTM
            605094400000,
        ),
    ],
)
def test_tm_unchanged_if_no_error(tm_cid, articles_cids, timestamp):
    tm = read_tm(tm_cid)
    articles = [read_article(cid) for cid in articles_cids]
    sections_patched_tm = _patch_tm_missing_sections(tm, articles)
    assert sections_patched_tm == tm
    multiple_paths_patched_tm = _patch_tm_multiple_paths(tm, articles, timestamp)
    assert multiple_paths_patched_tm == tm

import lxml.etree
import os
import pytest
import requests
import time

API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")


def test_api():
    """Test pulling from the FCS API."""

    URL = "http://localhost:9090/api"

    def wait_search(cid, qhash, rid):
        TIMEOUT = 30  # 30s for timeout
        search_start = time.time()
        ret = {}
        while 1:
            async_check = requests.get(f"{URL}/corpora/{cid}/search/{qhash}/{rid}")
            if async_check.status_code == 200:
                ret = async_check.json()
                break
            assert async_check.status_code == 202, AssertionError(
                "Invalid response to check of async search (runtime error)"
            )
            assert time.time() - search_start < TIMEOUT, AssertionError(
                f"Asynchronous request timed out (over {TIMEOUT} seconds)"
            )
            time.sleep(0.1)
        return ret

    # 1. check list of public corpora
    corpora = requests.get(f"{URL}/corpora").json()
    assert len(corpora) > 0, AssertionError("No public corpus found")
    MANDATORY_CONFIG_FIELDS = (
        "meta",
        "layer",
        "firstClass",
        "current_version",
        "schema_path",
        "token_counts",
        "mapping",
        "segment",
        "token",
        "document",
        "column_names",
    )
    assert all(
        c.get(k) for c in corpora.values() for k in MANDATORY_CONFIG_FIELDS
    ), AssertionError(
        "Found at least one public corpus missing a mandatory config field"
    )

    # 2. check details of single corpus
    first_corpus_id = next(k for k in corpora)
    first_corpus_details = requests.get(f"{URL}/corpora/{first_corpus_id}").json()
    assert all(
        first_corpus_details.get(k) for k in MANDATORY_CONFIG_FIELDS
    ), AssertionError(f"Invalid response for {URL}/corpora/{first_corpus_id}")

    # 3. test synchronous DQD query
    seg = first_corpus_details["segment"]
    unspecified_dqd = (
        f"{seg} s\n\nres => plain\n    context\n        s\n    entities\n        *"
    )
    unspecified_body = {"query": unspecified_dqd, "kind": "dqd", "synchronous": True}
    unspecified_search = requests.post(
        f"{URL}/corpora/{first_corpus_id}/search", json=unspecified_body
    ).json()
    # 0: meta
    # 1: hits
    # -1: prepared segments
    # -2: layer annotations
    unspecified_results_keys = ("1", "0", "-1", "-2")
    assert all(
        unspecified_search.get(k) for k in unspecified_results_keys
    ), AssertionError(
        f"Invalid response to synchronous unspecified search on first corpus"
    )

    # 4. test asynchronous DQD query
    async_body = {
        "query": "a sequence unlikely to appear in the corpus",
        "kind": "text",
        "synchronous": False,
    }
    async_search = requests.post(
        f"{URL}/corpora/{first_corpus_id}/search", json=async_body
    )
    assert async_search.status_code in (200, 202), AssertionError(
        "Error when running asynchronous search"
    )
    async_results = async_search.json()
    query_hash = async_results["query_hash"]
    assert query_hash, AssertionError(
        "Did not get a query hash in response to async search"
    )
    request_id = async_results["request_id"]
    assert request_id, AssertionError(
        "Did not get a request ID in response to async search"
    )
    if async_search.status_code == 202:
        wait_search(first_corpus_id, query_hash, request_id)

    # 5. check private corpora
    headers = {"X-API-Key": API_KEY, "X-API-Secret": API_SECRET}
    private_corpora = requests.get(f"{URL}/corpora", headers=headers).json()
    assert len(private_corpora) > len(corpora), AssertionError(
        "Did not find any private corpus"
    )

    # 6. search and export from private corpus
    private_corpus_id = next(k for k in private_corpora if k not in corpora)
    private_corpus_details = requests.get(
        f"{URL}/corpora/{private_corpus_id}", headers=headers
    ).json()
    private_seg = private_corpus_details["segment"]
    private_dqd = f"{private_seg} s\n\nres => plain\n    context\n        s\n    entities\n        *"
    private_body = {
        "query": private_dqd,
        "kind": "dqd",
        "synchronous": False,
        "to_export": {"format": "xml"},
        "offset": 0,
        "requested": 200,
    }
    private_search = requests.post(
        f"{URL}/corpora/{private_corpus_id}/search",
        json=private_body,
        headers=headers,
    )
    assert private_search.status_code in (200, 202), AssertionError(
        "Error when running asynchronous search"
    )
    private_results = private_search.json()
    query_hash = private_results["query_hash"]
    assert query_hash, AssertionError(
        "Did not get a query hash in response to async export search"
    )
    request_id = private_results["request_id"]
    assert request_id, AssertionError(
        "Did not get a request ID in response to async export search"
    )
    if private_search.status_code == 202:
        wait_search(private_corpus_id, query_hash, request_id)

    download_url = f"{URL.removesuffix('/api')}/download_export?hash={query_hash}&format=xml&offset=0&requested=200"
    download_no_headers = requests.get(download_url)
    assert download_no_headers.status_code == 403, AssertionError(
        "Header-less export check should be forbidden"
    )
    download_with_headers = requests.get(download_url, headers=headers)
    try:
        lxml.etree.fromstring(download_with_headers.text.encode("utf-8"))
    except:
        raise AssertionError("Could not parse download results")

import time
import requests
import pytest


def test_api():
    """Test pulling from the FCS API."""

    URL = "http://localhost:9090/api"

    # check list of public corpora
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

    first_corpus_id = next(k for k in corpora)
    first_corpus_details = requests.get(f"{URL}/corpora/{first_corpus_id}").json()
    assert all(
        first_corpus_details.get(k) for k in MANDATORY_CONFIG_FIELDS
    ), AssertionError(f"Invalid response for {URL}/corpora/{first_corpus_id}")

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
    async_body = {
        "query": "a sequence unlikely to appear in the corpus",
        "kind": "text",
        "synchronous": False,
    }
    async_search = requests.post(
        f"{URL}/corpora/{first_corpus_id}/search", json=async_body
    ).json()
    query_hash = async_search["query_hash"]
    assert query_hash, AssertionError(
        "Did not get a query hash in response to async search"
    )
    request_id = async_search["request_id"]
    assert request_id, AssertionError(
        "Did not get a request ID in response to async search"
    )
    TIMEOUT = 30  # 30s for timeout
    search_start = time.time()
    while 1:
        async_check = requests.get(
            f"{URL}/corpora/{first_corpus_id}/search/{query_hash}/{request_id}"
        ).json()
        assert not async_check.get("code") == 500, AssertionError(
            "Invalid response to check of async search (runtime error)"
        )
        if "0" in async_check:
            break
        assert "status" in async_check, AssertionError(
            "Invalid response to check of async search (could not get a valid status)"
        )
        assert time.time() - search_start < TIMEOUT, AssertionError(
            f"Asynchronous request timed out (over {TIMEOUT} seconds)"
        )
        time.sleep(0.1)

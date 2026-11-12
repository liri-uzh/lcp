import lxml.etree
import os
import pytest
import requests
import time

API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")


def test_sample_queries():
    """Test the sample queries from the public corpora."""

    URL = "http://localhost:9090/api"
    params = {}
    if API_KEY and API_SECRET:
        params["headers"] = {"X-API-Key": API_KEY, "X-API-Secret": API_SECRET}

    # 1. check list of public corpora
    corpora = requests.get(f"{URL}/corpora").json()
    assert len(corpora) > 0, AssertionError("No public corpus found")

    public_corpora = [
        f"{cid}: {conf.get('shortname','')}" for cid, conf in corpora.items()
    ]
    print("Public corpora:\n" + "\n".join(public_corpora))

    for cid, conf in corpora.items():
        if conf.get("authRequired") and (not API_SECRET or not API_KEY):
            print(
                f"Corpus {conf.get('shortname','')} ({cid}) requires authentication but no valid credentials were found; skipping."
            )
            continue
        meta = conf.get("meta") or {}
        sample = ""
        # sample_query could live at the meta or main level (inconsistent, needs to be fixed)
        for sq in (meta.get("sample_query"), conf.get("sample_query")):
            # sample could be {'en': "query", 'de': "query", ...}
            if isinstance(sq, dict):
                sq = next(x for x in sq.values())
            if not sq:
                continue
            sample = sq
            break
        if not sample:
            print(f"No sample query on {conf.get('shortname','')} ({cid})")
            continue
        sample_body = {
            "query": sample,
            "kind": "dqd",
            "offset": 0,
            "requested": 200,
            "synchronous": True,
        }
        sample_response = requests.post(
            f"{URL}/corpora/{cid}/search", json=sample_body, **params
        )
        assert sample_response.status_code == 200, AssertionError(
            f"Got a non-200 response for corpus {conf.get('shortname','')} ({cid}) for DQD query: {sample_response.reason}\n{sample}"
        )
        sample_search = sample_response.json()
        assert "0" in sample_search, AssertionError(
            f"Did not get a key '0' in response to the sample query on {conf.get('shortname','')} ({cid})\n{sample}"
        )
        assert "result_sets" in sample_search["0"], AssertionError(
            f"Ill-formed response-meta field (key '0') in response to the sample query on {conf.get('shortname','')} ({cid})\n{sample}"
        )
        has_plain = False
        for n, r in enumerate(sample_search["0"]["result_sets"]):
            assert str(n + 1) in sample_search, AssertionError(
                f"Couldn't find key {n+1} in reponse to the sample query on {conf.get('shortname','')} ({cid})\n{sample}"
            )
            has_plain = has_plain or r.get("type") == "plain"
        assert not has_plain or (
            "-1" in sample_search and "-2" in sample_search
        ), AssertionError(
            f"Couldn't find segments and/or layer meta in reponse to the sample query on {conf.get('shortname','')} ({cid})\n{sample}"
        )
        print(f"Validated sample query on {conf.get('shortname','')} ({cid})")

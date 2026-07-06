import requests
import pytest
import xml.etree.ElementTree as ET


def test_fcs():
    """Test pulling from the FCS API."""

    URL = "http://localhost:9090/fcs-endpoint"
    ZR = "{http://explain.z3950.org/dtd/2.0/}"
    ED = "{http://clarin.eu/fcs/endpoint-description}"
    HITS = "{http://clarin.eu/fcs/dataview/hits}"
    FCS = "{http://clarin.eu/fcs/resource}"

    # check description of endpoint (no list of corpora)
    response = requests.get(URL).text
    parsed_response = ET.fromstring(response)
    server_info = parsed_response.find(f".//{ZR}serverInfo")
    database_info = parsed_response.find(f".//{ZR}databaseInfo")
    assert server_info, AssertionError("Could not find serverInfo in FCS response")
    assert database_info, AssertionError("Could not find databaseInfo in FCS response")
    assert (
        server_info.find(f"{ZR}database[.='LCP public corpora']") is not None
    ), AssertionError("serverInfo lacks the database 'LCP public corpora'")
    assert (
        database_info.find(f"{ZR}title[.='LCP public corpora']") is not None
    ), AssertionError("databaseInfo lacks the title 'LCP public corpora'")

    # check list of corpora
    response = requests.get(f"{URL}?x-fcs-endpoint-description=true").text
    parsed_response = ET.fromstring(response)
    corpora = parsed_response.findall(f".//{ED}Resource")
    assert len(corpora) > 30, AssertionError(
        "FCS lists fewer than 30 public corpora, which is unexpected"
    )

    # check simple query (no context)
    response = requests.get(f"{URL}?operation=searchRetrieve&query=Elephant").text
    parsed_response = ET.fromstring(response)
    resources = parsed_response.findall(f".//{FCS}Resource")
    hits = parsed_response.findall(f".//{HITS}Result")
    assert len(hits) > 10, AssertionError(
        "Found fewer than 10 hits for FCS query 'Elephant', which is unexpected"
    )
    pid_elephant = resources[0].get("pid", "")

    # check CQL query (no context)
    cql = '"the elephant" OR dirt'  # rare enough second disjunct so as to have matches for both
    response = requests.get(
        f"{URL}?operation=searchRetrieve&query={cql}&queryType=cql"
    ).text
    parsed_response = ET.fromstring(response)
    resources = parsed_response.findall(f".//{FCS}Resource")
    hits = parsed_response.findall(f".//{HITS}Hit")
    assert any(x.text == "dirt" for x in hits), AssertionError(
        f"No FCS match for 'dirt' for CQL query {cql}"
    )
    assert any(x.text == "the elephant" for x in hits), AssertionError(
        f"No FCS match for 'the elephant' for CQL query {cql}"
    )
    pid_cql = resources[0].get("pid", "")

    # check simple query with context
    response = requests.get(
        f"{URL}?operation=searchRetrieve&query=Elephant&x-fcs-context={pid_elephant}"
    ).text
    parsed_response = ET.fromstring(response)
    hits = parsed_response.findall(f".//{HITS}Result")
    assert len(hits) > 0, AssertionError(
        f"Found no hits for FCS query 'Elephant' in context ({pid_elephant})"
    )

    # check CQL query with context
    cql = '"the elephant" OR dirt'  # rare enough second disjunct so as to have matches for both
    response = requests.get(
        f"{URL}?operation=searchRetrieve&query={cql}&queryType=cql&x-fcs-context={pid_cql}"
    ).text
    parsed_response = ET.fromstring(response)
    hits = parsed_response.findall(f".//{HITS}Result")
    assert len(hits) > 0, AssertionError(
        f"Found no FCS hits for CQL query {cql} in context ({pid_cql})"
    )

import asyncio
import json
import os

from aiohttp import web
from typing import cast
from xml.sax.saxutils import escape

from .authenticate import Authentication
from .cql_to_json import CqlToJson
from .textsearch_to_json import textsearch_to_json
from .query_classes import QueryInfo, Request
from .query import process_query
from .typed import JSONObject
from .utils import _get_iso639_3, LCPApplication

FCS_HOST = "catchphrase.linguistik.uzh.ch"
FCS_PORT = "443"
FCS_DB = "LCP public corpora"
PID_PREFIX = f"https://{FCS_HOST}/"
DEFAULT_MAX_KWIC_LINES = os.getenv("DEFAULT_MAX_KWIC_LINES", 9999)
SRU = {"1.2": "sru", "2.0": "sruResponse"}
SRU_URL = {
    "1.2": "http://www.loc.gov/zing/srw/",
    "2.0": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
}


def _get_cid_from_pid(pid: str) -> str:
    prefix_less = pid[len(PID_PREFIX) :]
    return "".join(
        x for n, x in enumerate(prefix_less, start=1) if "/" not in prefix_less[:n]
    )


def _get_lg_from_pid(pid: str) -> str:
    rpid = [x for x in reversed(pid)]
    lg = (
        "".join(
            y
            for y in reversed(
                [x for n, x in enumerate(rpid, start=1) if "/" not in rpid[:n]]
            )
        )
        or "en"
    )
    return lg


def _get_languages(partitions: dict, main_language: str = "") -> str:
    lg_template = """          <ed:Languages>
            {languages}
          </ed:Languages>"""
    languages = "<ed:Language>und</ed:Language>"
    if values := partitions.get("values", []):
        languages = "\n            ".join(
            f"<ed:Language>{_get_iso639_3(lg)}</ed:Language>"
            for lg in values
            if _get_iso639_3(lg)
        )
    elif main_language:
        languages = f"<ed:Language>{_get_iso639_3(main_language)}</ed:Language>"
    return lg_template.format(languages=languages)


def _get_descriptions(conf: dict) -> str:
    ret: str = ""
    descriptions: str | dict = (
        conf["meta"].get("corpusDescription") or conf["description"]
    )
    if isinstance(descriptions, str):
        ret = f"""<ed:Description xml:lang="en">{escape(descriptions)}</ed:Description>\n          """
    elif isinstance(descriptions, dict):
        ret = (
            "\n          ".join(
                f"""<ed:Description xml:lang="{lg}">{escape(desc)}</ed:Description>"""
                for lg, desc in descriptions.items()
            )
            + "\n          "
        )
    return ret


async def _check_request_complete(
    qi: QueryInfo,
    request: Request,
    app: web.Application,
    request_ids: dict[str, dict],
    requested: int,
):
    while 1:
        await asyncio.sleep(0.5)
        if not qi.has_request(request):
            request_ids[request.id]["done"] = True
            break
        n_results = sum(
            len(app["query_buffers"].get(rid, {}).get("1", []))
            for rid, rprops in request_ids.items()
            if rprops.get("done")
        )
        if n_results >= requested:
            qi.stop_request(request)
            break
    return


def _get_record_headers(version: str = "1.2", operation: str = "explain") -> str:
    record_schema: str = (
        "http://explain.z3950.org/dtd/2.0/"
        if operation == "explain"
        else "http://clarin.eu/fcs/resource"
    )
    first_line = (
        f"<{SRU[version]}:recordSchema>{record_schema}</{SRU[version]}:recordSchema>"
    )
    second_line = (
        f"<{SRU[version]}:recordPacking>xml</{SRU[version]}:recordPacking>"
        if version == "1.2"
        else f"<{SRU[version]}:recordXMLEscaping>xml</{SRU[version]}:recordXMLEscaping>"
    )
    return first_line + second_line


def _make_search_response(
    buffers,
    request_ids: dict[str, dict],
    startRecord: int = 0,
    requested: int = 50,
    version: str = "2.0",
) -> str:
    resp = """<?xml version='1.0' encoding='utf-8'?>
<{sru}:searchRetrieveResponse xmlns:{sru}="{sru_url}">
  <{sru}:version>{version}</{sru}:version>""".format(
        version=version, sru=SRU[version], sru_url=SRU_URL[version]
    )
    records: list[str] = []
    for rid, corpus in request_ids.items():
        if not corpus.get("done"):
            continue
        if len(records) >= requested:
            break
        payload = buffers[rid]
        cid = corpus["cid"]
        lg = corpus["lg"]
        shortname = corpus["conf"]["shortname"]
        column_names: list[str] = (
            corpus["conf"]["mapping"]["layer"]
            .get(corpus["conf"]["segment"])
            .get("prepared", {})
            .get("columnHeaders", corpus["conf"]["column_names"])
        )
        space_after_id = (
            column_names.index("spaceAfter") if "spaceAfter" in column_names else -1
        )
        form_id = column_names.index("form")
        if "1" not in payload or "-1" not in payload:
            continue
        for rp, (sid, hits, *_) in enumerate(payload["1"], start=1):
            offset, tokens, *annotations = payload["-1"][sid]
            prep_seg = ""
            in_hit = False
            for n, token in enumerate(tokens):
                token_str = escape(token[form_id]) if token[form_id] else ""
                is_hit = offset + n in hits or offset + n in [
                    y for x in hits if isinstance(x, list) for y in x
                ]
                if in_hit and not is_hit:
                    after_space = prep_seg and prep_seg[-1] == " "
                    prep_seg = (
                        prep_seg.rstrip() + "</hits:Hit>" + (" " if after_space else "")
                    )
                if not in_hit and is_hit:
                    token_str = f"<hits:Hit>{token_str}"
                in_hit = is_hit
                if space_after_id < 0 or token[space_after_id] == "1":
                    token_str += " "
                prep_seg += token_str
            prep_seg = prep_seg.strip()
            if in_hit:
                prep_seg += "</hits:Hit>"
            ref = f"{PID_PREFIX}query/{cid}/{shortname}"
            records.append(f"""
    <{SRU[version]}:record>
      {_get_record_headers(version, 'searchRetrieve')}
      <{SRU[version]}:recordData>
        <fcs:Resource xmlns:fcs="http://clarin.eu/fcs/resource" pid="{PID_PREFIX}{cid}/{lg}" ref="{ref}">
          <fcs:ResourceFragment ref="{ref}">
            <fcs:DataView type="application/x-clarin-fcs-hits+xml" ref="{ref}">
              <hits:Result xmlns:hits="http://clarin.eu/fcs/dataview/hits">
                {prep_seg}
              </hits:Result>
            </fcs:DataView>
          </fcs:ResourceFragment>
        </fcs:Resource>
      </{SRU[version]}:recordData>
      <{SRU[version]}:recordPosition>{startRecord+rp}</{SRU[version]}:recordPosition>
    </{SRU[version]}:record>""")
            if len(records) >= requested:
                break
    if len(records) == 0:
        resp += f"""
  <{SRU[version]}:numberOfRecords>0</{SRU[version]}:numberOfRecords>
"""
    else:
        resp += f"""
  <{SRU[version]}:numberOfRecords>{len(records)}</{SRU[version]}:numberOfRecords>
  <{SRU[version]}:records>{''.join(records)}
  </{SRU[version]}:records>
"""
    return resp + f"</{SRU[version]}:searchRetrieveResponse>"


async def search_retrieve(
    app: LCPApplication,
    request: web.Request,
    operation: str = "searchRetrieve",
    version: str = "2.0",
    query: str = "",
    queryType: str = "cql",
    maximumRecords: str | int = "",
    startRecord: str | int = 0,
    **extra_params,
) -> str:
    authenticator = cast(Authentication, app["auth_class"](app))
    user = await authenticator.user_details(request)

    resources = [
        (_get_cid_from_pid(pid), _get_lg_from_pid(pid))
        for pid in extra_params.get("x-fcs-context", "").split(",")
        if pid
    ]
    corpora: list[tuple[str, dict, str]] = [
        (cid, conf, lg)
        for cid, conf in app["config"].items()
        for lg in conf.get("partitions", {}).get(
            "values", [conf.get("meta", {}).get("language", "en")]
        )
        if (not resources or ((cid, lg) in resources))
        and authenticator.check_corpus_searchable(cid, user, "lcp", get_all=False)
        and conf.get("enabled")
    ]
    try:
        requested: int = int(maximumRecords)
        requested = min(requested, 50)
    except:
        requested = 50
    try:
        startRecord = int(startRecord)
        startRecord = max(0, startRecord)
    except:
        startRecord = 0

    request_ids: dict[str, dict] = {}
    async with asyncio.TaskGroup() as tg:
        for cid, conf, lg in corpora:
            langs = [lg if "partitions" in conf else "en"]
            json_query: str = json.dumps(
                CqlToJson(
                    segment=conf["firstClass"]["segment"],
                    token=conf["firstClass"]["token"],
                    query=query,
                ).convert()
                if queryType == "cql"
                else textsearch_to_json(query, conf)
            )
            req, qi, job = process_query(
                app,
                {
                    "appType": "lcp",
                    "corpus": cid,
                    "query": json_query,
                    "languages": langs,
                    "offset": startRecord,
                    "requested": requested,
                    "synchronous": True,
                },
            )
            request_ids[req.id] = {
                "cid": cid,
                "conf": conf,
                "lg": lg,
                "n_results": 0,
                "done": False,
            }
            # No job means no request is running: delete it
            if job is None and qi.has_request(req):
                qi.delete_request(req)
            tg.create_task(
                _check_request_complete(qi, req, app, request_ids, requested)
            )
    return _make_search_response(
        app["query_buffers"],
        request_ids,
        startRecord=startRecord,
        requested=requested,
        version=version,
    )


async def explain(app: LCPApplication, request: web.Request, **extra_params) -> str:
    version = extra_params.get("version", "2.0")
    first_half: str = f"""<?xml version='1.0' encoding='utf-8'?>
<{SRU[version]}:explainResponse xmlns:{SRU[version]}="{SRU_URL[version]}">
  <{SRU[version]}:version>{version}</{SRU[version]}:version>
  <{SRU[version]}:record>
    {_get_record_headers(version, 'explain')}
    <{SRU[version]}:recordData>
      <zr:explain xmlns:zr="http://explain.z3950.org/dtd/2.0/">
        <zr:serverInfo protocol="SRU" version="{version}" transport="http">
          <zr:host>{FCS_HOST}</zr:host>
          <zr:port>{FCS_PORT}</zr:port>
          <zr:database>{FCS_DB}</zr:database>
        </zr:serverInfo>
        <zr:databaseInfo>
          <zr:title lang="en" primary="true">{FCS_DB}</zr:title>
          <zr:description lang="en" primary="true">The corpora publicly available at the LCP.</zr:description>
        </zr:databaseInfo>
        <zr:schemaInfo>
          <zr:schema identifier="http://clarin.eu/fcs/resource" name="fcs">
            <zr:title lang="en" primary="true">CLARIN-CH Federated Content Search</zr:title>
          </zr:schema>
        </zr:schemaInfo>
        <zr:configInfo>
          <zr:default type="numberOfRecords">50</zr:default>
          <zr:setting type="maximumRecords">{DEFAULT_MAX_KWIC_LINES}</zr:setting>
        </zr:configInfo>
      </zr:explain>
    </{SRU[version]}:recordData>
  </{SRU[version]}:record>"""
    second_half = f"</{SRU[version]}:explainResponse>"
    if extra_params.get("x-fcs-endpoint-description") in (True, "true", "True", 1):
        authenticator = cast(Authentication, app["auth_class"](app))
        user = await authenticator.user_details(request)
        resources_list: list[str] = [
            f"""      <ed:Resource pid="{PID_PREFIX}{cid}/{lg}">
          <ed:Title xml:lang="en">{conf['shortname']}{ ' ('+lg+')' if 'partitions' in conf else ''}</ed:Title>
          {_get_descriptions(conf)}<ed:LandingPageURI>{PID_PREFIX}query/{cid}/{conf['shortname']}</ed:LandingPageURI>
          {_get_languages({}, lg)}
          <ed:AvailableDataViews ref="hits"/>
        </ed:Resource>"""
            for cid, conf in app["config"].items()
            for lg in conf.get("partitions", {}).get(
                "values", [conf.get("meta", {}).get("language", "")]
            )
            if authenticator.check_corpus_searchable(cid, user, "lcp", get_all=False)
            and conf.get("enabled")
        ]
        resources_str = "\n        ".join(resources_list)
        second_half = f"""  <{SRU[version]}:echoedExplainRequest>
    <{SRU[version]}:version>{version}</{SRU[version]}:version>
    <{SRU[version]}:baseUrl>http://repos.example.org/fcs-endpoint</{SRU[version]}:baseUrl>
  </{SRU[version]}:echoedExplainRequest>
  <{SRU[version]}:extraResponseData>
    <ed:EndpointDescription xmlns:ed="http://clarin.eu/fcs/endpoint-description" version="2">
      <ed:Capabilities>
        <ed:Capability>http://clarin.eu/fcs/capability/basic-search</ed:Capability>
      </ed:Capabilities>
      <ed:SupportedDataViews>
        <ed:SupportedDataView id="hits" delivery-policy="send-by-default">application/x-clarin-fcs-hits+xml</ed:SupportedDataView>
      </ed:SupportedDataViews>
      <ed:Resources>
        {resources_str}
      </ed:Resources>
    </ed:EndpointDescription>
  </{SRU[version]}:extraResponseData>
</{SRU[version]}:explainResponse>"""
    return first_half + "\n" + second_half


async def get_fcs(request: web.Request) -> web.Response:
    resp: str = ""
    app = cast(LCPApplication, request.app)
    q = request.rel_url.query
    query_content = (q.get("query") or "").strip()
    operation = q.get("operation") or "explain"
    if query_content:
        operation = "searchRetrieve"
    if "x-fcs-endpoint-description" in q:
        operation = "explain"
    version = q.get("version") or "2.0"
    if version not in SRU:
        resp = """<diagnostics>
        <diagnostic xmlns="info:srw/xmlns/1/sru-1-2-diagnostic">
            <uri>http://clarin.eu/fcs/diagnostic/10</uri>
            <details>10</details>
            <message>Version {version} not supported.</message>
        </diagnostic>
    </diagnostics>""".format(version=version)
    elif operation == "explain":
        resp = await explain(app, request, **q)
    elif operation == "searchRetrieve":
        resp = await search_retrieve(app, request, **q)
    else:
        # http://clarin.eu/fcs/diagnostic/10
        resp = """<diagnostics>
        <diagnostic xmlns="info:srw/xmlns/1/sru-1-2-diagnostic">
            <uri>http://clarin.eu/fcs/diagnostic/10</uri>
            <details>10</details>
            <message>No valid query found in the request.</message>
        </diagnostic>
    </diagnostics>"""
    return web.Response(body=resp, content_type="application/xml")

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
from .utils import LCPApplication

FCS_HOST = "catchphrase.linguistik.uzh.ch"
FCS_PORT = "443"
FCS_DB = "LCP public corpora"
PID_PREFIX = f"https://{FCS_HOST}/query/"
DEFAULT_MAX_KWIC_LINES = os.getenv("DEFAULT_MAX_KWIC_LINES", 9999)


def _get_cid_from_pid(pid: str) -> str:
    prefix_less = pid[len(PID_PREFIX) :]
    return "".join(
        x for n, x in enumerate(prefix_less, start=1) if "/" not in prefix_less[:n]
    )


def _get_iso639_3(lang: str) -> str:
    if lang == "en":
        return "eng"
    if lang == "de":
        return "deu"
    if lang == "fr":
        return "fra"
    if lang == "it":
        return "ita"
    if lang == "rm":
        return "roh"
    if lang == "ro":
        return "ron"
    return ""


def _get_languages_from_partitions(partitions: dict) -> str:
    lg_template = """          <ed:Languages>
            {languages}
          </ed:Languages>"""
    languages = "<ed:Language>eng</ed:Language>"
    if values := partitions.get("values", []):
        languages = "\n            ".join(
            f"<ed:Language>{_get_iso639_3(lg)}</ed:Language>"
            for lg in values
            if _get_iso639_3(lg)
        )
    return lg_template.format(languages=languages)


async def _check_request_complete(qi: QueryInfo, request: Request):
    while 1:
        await asyncio.sleep(0.5)
        if not qi.has_request(request):
            break
    return


def _make_search_response(
    buffers, request_ids: dict[str, dict], startRecord: int = 0
) -> str:
    resp = """<?xml version='1.0' encoding='utf-8'?>
<sru:searchRetrieveResponse xmlns:sru="http://www.loc.gov/zing/srw/">
  <sru:version>2.0</sru:version>"""
    records: list[str] = []
    for rid, corpus in request_ids.items():
        payload = buffers[rid]
        cid = corpus["cid"]
        shortname = corpus["conf"]["shortname"]
        column_names: list[str] = corpus["conf"]["column_names"]
        space_after_id = (
            column_names.index("spaceAfter") if "spaceAfter" in column_names else -1
        )
        form_id = column_names.index("form")
        if "1" not in payload or "-1" not in payload:
            continue
        for rp, (sid, hits) in enumerate(payload["1"], start=1):
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
            records.append(
                f"""
    <sru:record>
      <sru:recordSchema>http://clarin.eu/fcs/resource</sru:recordSchema>
      <sru:recordPacking>xml</sru:recordPacking>
      <sru:recordData>
        <fcs:Resource xmlns:fcs="http://clarin.eu/fcs/resource" pid="{PID_PREFIX}{cid}/{shortname}">
          <fcs:ResourceFragment>
            <fcs:DataView type="application/x-clarin-fcs-hits+xml">
              <hits:Result xmlns:hits="http://clarin.eu/fcs/dataview/hits">
                {prep_seg}
              </hits:Result>
            </fcs:DataView>
          </fcs:ResourceFragment>
        </fcs:Resource>
      </sru:recordData>
      <sru:recordPosition>{startRecord+rp}</sru:recordPosition>
    </sru:record>"""
            )
    resp += f"""
  <sru:numberOfRecords>{len(records)}</sru:numberOfRecords>
  <sru:records>{''.join(records)}
  </sru:records>
</sru:searchRetrieveResponse>"""
    return resp


async def search_retrieve(
    app: LCPApplication,
    operation: str = "searchRetrieve",
    version: str = "2.0",
    query: str = "",
    queryType: str = "cql",
    maximumRecords: str | int = "",
    startRecord: str | int = 0,
    **extra_params,
) -> str:
    authenticator = cast(Authentication, app["auth_class"](app))

    resources = [
        _get_cid_from_pid(pid)
        for pid in extra_params.get("x-fcs-context", "").split(",")
        if pid
    ]
    corpora: dict[str, dict] = {
        cid: conf
        for cid, conf in app["config"].items()
        if (not resources or cid in resources)
        and authenticator.check_corpus_allowed(cid, conf, {}, "lcp", get_all=False)
    }
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

    try:
        query_buffers = app["query_buffers"]
    except:
        query_buffers = {}
        app.addkey("query_buffers", dict[str, dict], query_buffers)

    request_ids: dict[str, dict] = {}
    async with asyncio.TaskGroup() as tg:
        for cid, conf in corpora.items():
            langs = ["en"]
            partitions = conf.get("partitions", {})
            if (
                partitions
                and partitions.get("values")
                and "en" not in partitions["values"]
            ):
                continue  # only do English for now
                # langs = [next(x for x in partitions["values"])]
            json_query: str = json.dumps(
                CqlToJson(
                    segment=conf["firstClass"]["segment"],
                    token=conf["firstClass"]["token"],
                    query=query,
                ).convert()
                if queryType == "cql"
                else textsearch_to_json(query, conf)
            )
            (req, qi, job) = process_query(
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
            query_buffers[req.id] = {}
            request_ids[req.id] = {"cid": cid, "conf": conf}
            tg.create_task(_check_request_complete(qi, req))
    return _make_search_response(query_buffers, request_ids, startRecord=startRecord)


async def explain(app: LCPApplication, **extra_params) -> str:
    first_half: str = f"""<?xml version='1.0' encoding='utf-8'?>
<sru:explainResponse xmlns:sru="http://www.loc.gov/zing/srw/">
  <sru:version>2.0</sru:version>
  <sru:record>
    <sru:recordSchema>http://explain.z3950.org/dtd/2.0/</sru:recordSchema>
    <sru:recordPacking>xml</sru:recordPacking>
    <sru:recordData>
      <zr:explain xmlns:zr="http://explain.z3950.org/dtd/2.0/">
        <zr:serverInfo protocol="SRU" version="2.0" transport="http">
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
    </sru:recordData>
  </sru:record>"""
    second_half = "</sru:explainResponse>"
    if "x-fcs-endpoint-description" in extra_params:
        authenticator = cast(Authentication, app["auth_class"](app))
        resources_list: list[str] = [
            f"""      <ed:Resource pid="{PID_PREFIX}{cid}/{conf['shortname']}">
          <ed:Title xml:lang="en">{conf['shortname']}</ed:Title>
          <ed:Description xml:lang="en">{conf['description']}</ed:Description>
          <ed:LandingPageURI>{PID_PREFIX}{cid}/{conf['shortname']}</ed:LandingPageURI>
          {_get_languages_from_partitions(conf.get('partitions', {}))}
          <ed:AvailableDataViews ref="hits"/>
        </ed:Resource>"""
            for cid, conf in app["config"].items()
            if authenticator.check_corpus_allowed(cid, conf, {}, "lcp", get_all=False)
        ]
        resources_str = "\n        ".join(resources_list)
        second_half = f"""  <sru:echoedExplainRequest>
    <sru:version>2.0</sru:version>
    <sru:baseUrl>http://repos.example.org/fcs-endpoint</sru:baseUrl>
  </sru:echoedExplainRequest>
  <sru:extraResponseData>
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
  </sru:extraResponseData>
</sru:explainResponse>"""
    return first_half + "\n" + second_half


async def get_fcs(request: web.Request) -> web.Response:
    resp: str = ""
    app = cast(LCPApplication, request.app)
    q = request.rel_url.query
    operation = q["operation"]
    if operation == "explain":
        resp = await explain(app, **q)
    elif operation == "searchRetrieve":
        if not q.get("query", "").strip():
            # http://clarin.eu/fcs/diagnostic/10
            resp = """<diagnostics>
        <diagnostic xmlns="info:srw/xmlns/1/sru-1-2-diagnostic">
            <uri>http://clarin.eu/fcs/diagnostic/10</uri>
            <details>10</details>
            <message>No query found in the request.</message>
        </diagnostic>
    </diagnostics>"""
        else:
            resp = await search_retrieve(app, **q)
    return web.Response(body=resp, content_type="application/xml")

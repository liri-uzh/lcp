"""
api.py: API access to LCP
"""

import asyncio
import json

from aiohttp import web
from typing import cast, Any

from .query import process_query
from .query_classes import QueryInfo
from .utils import LCPApplication
from .validate import validate


async def _get_user(request: web.Request, authenticator) -> dict:
    user_data = await authenticator.user_details(request)
    return user_data


async def list_corprora(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    corpora = {
        cid: conf
        for cid, conf in request.app["config"].items()
        if authenticator.check_corpus_allowed(cid, user_data, "lcp", get_all=False)
        and conf.get("enabled")
    }
    return web.json_response(corpora)


async def get_corpus(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    cid: str = request.match_info["corpus_id"]
    if not authenticator.check_corpus_allowed(cid, user_data, "lcp", get_all=False):
        return web.HTTPForbidden(text="Not allowed to access this corpus")
    return web.json_response(request.app["config"].get(cid, {}))


async def get_search(request: web.Request) -> web.Response:
    qhash = request.match_info["query_hash"]
    request_id = request.match_info["request_id"]
    try:
        qi = QueryInfo(qhash, connection=request.app["redis"])
    except:
        error = f"Could not find a query for the provided hash ({qhash})"
        return web.json_response(text=error, reason=error, status=500)

    if any(r.id == request_id for r in qi.requests):
        return web.json_response(data={"status": "running"}, status=202)

    if (
        "query_buffers" not in request.app
        or request_id not in request.app["query_buffers"]
    ):
        error = f"Could not find a request for the provided ID ({request_id})"
        return web.json_response(text=error, reason=error, status=500)

    payload = request.app["query_buffers"].pop(request_id, {})
    return web.json_response(payload)


async def search(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    cid: str = request.match_info["corpus_id"]
    if not authenticator.check_corpus_searchable(cid, user_data, "lcp", get_all=False):
        return web.HTTPForbidden(text="Not allowed to access this corpus")
    request_data: dict[str, str] = await request.json()
    query = request_data.get("query", "")
    kind = request_data.get("kind", "json")
    corpus_conf = request.app["config"].get(cid, {})
    lg = request_data.get("partition", "")
    offset = int(request_data.get("offset", 0))
    requested = int(request_data.get("requested", 200))
    full = bool(request_data.get("full", False))
    synchronous = bool(request_data.get("synchronous", True))
    raw_hits = bool(request_data.get("raw_hits", False))
    if partitions := corpus_conf.get("partitions", {}):
        lg = partitions.get("values", [""])[0]
    kwargs: dict[str, Any] = {"config": {cid: corpus_conf}, "corpus": cid}

    val = validate(query, kind, **kwargs)
    if val.get("status") != 200:
        return web.HTTPBadRequest(text=cast(dict, val).get("error", "Error"))

    json_query = val["json"]

    data_to_process = {
        "appType": "lcp",
        "corpus": cid,
        "query": json.dumps(json_query),
        "languages": [lg],
        "offset": offset,
        "requested": requested,
        "synchronous": synchronous,
        "to_buffer": True,
        "full": full,
        "raw_hits": raw_hits,
    }
    if "to_export" in request_data:
        data_to_process["to_export"] = request_data["to_export"]
    app = cast(LCPApplication, request.app)
    req, qi, job = process_query(app, data_to_process)

    # No job means no query is being run: delete the request
    if job is None and qi.has_request(req):
        qi.delete_request(req)

    if not synchronous:
        return web.json_response({"query_hash": qi.hash, "request_id": req.id})

    while 1:
        if not qi.has_request(req):
            break
        await asyncio.sleep(0.5)

    payload = app["query_buffers"].pop(req.id, {})

    return web.json_response(payload)

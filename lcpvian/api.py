"""
api.py: API access to LCP
"""

import asyncio
import json

from aiohttp import web
from typing import cast, Any

from .query import process_query
from .utils import LCPApplication
from .validate import validate


async def _get_user(request: web.Request, authenticator) -> dict:
    user_data = {}
    if "X-API-Key" in request.headers and "X-API-Secret" in request.headers:
        user_data = await authenticator.check_api_key(request)
    else:
        user_data = await authenticator.user_details(request)
    return user_data


async def list_coprora(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    corpora = {
        cid: conf
        for cid, conf in request.app["config"].items()
        if authenticator.check_corpus_allowed(cid, user_data, "lcp", get_all=False)
    }
    return web.json_response(corpora)


async def get_corpus(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    cid: str = request.match_info["corpus_id"]
    if not authenticator.check_corpus_allowed(cid, user_data, "lcp", get_all=False):
        return web.HTTPForbidden(text="Not allowed to access this corpus")
    return web.json_response(request.app["config"].get(cid, {}))


async def search(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data = await _get_user(request, authenticator)
    cid: str = request.match_info["corpus_id"]
    if not authenticator.check_corpus_allowed(cid, user_data, "lcp", get_all=False):
        return web.HTTPForbidden(text="Not allowed to access this corpus")

    request_data: dict[str, str] = await request.json()
    query = request_data.get("query", "")
    kind = request_data.get("kind", "json")
    corpus_conf = request.app["config"].get(cid, {})
    lg = request_data.get("partition", "")
    offset = int(request_data.get("offset", 0))
    requested = int(request_data.get("requested", 200))
    if partitions := corpus_conf.get("partitions", {}):
        lg = partitions.get("values", [""])[0]
    kwargs: dict[str, Any] = {"config": {cid: corpus_conf}, "corpus": cid}

    val = await validate(query, kind, **kwargs)
    if val.get("status") != 200:
        return web.HTTPForbidden(text=cast(dict, val).get("error", "Error"))

    json_query = val["json"]

    (req, qi, job) = process_query(
        cast(LCPApplication, request.app),
        {
            "appType": "lcp",
            "corpus": cid,
            "query": json.dumps(json_query),
            "languages": [lg],
            "offset": offset,
            "requested": requested,
            "synchronous": True,
        },
    )

    while 1:
        await asyncio.sleep(0.5)
        if not qi.has_request(req):
            break

    payload = request.app["query_buffers"][req.id]

    return web.json_response(payload)

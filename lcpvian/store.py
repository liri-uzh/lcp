from uuid import uuid4

from typing import cast

from aiohttp import web
from rq.job import Job

from .typed import JSONObject
from .utils import ensure_authorised


@ensure_authorised
async def fetch_queries(request: web.Request) -> web.Response:
    """
    User wants to retrieve their stored queries from the DB

    Currently these buttons are not shown in the frontend, so these are unused
    """
    request_data: dict[str, str] = await request.json()
    user = request_data["user"]
    room = request_data.get("room")
    job: Job = request.app["query_service"].fetch_queries(user, room)
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)


@ensure_authorised
async def store_query(request: web.Request) -> web.Response:
    """
    User wants to store one or more queries in the DB

    Currently these buttons are not shown in the frontend, so these are unused
    """
    request_data: JSONObject = await request.json()
    user = cast(str, request_data["user"])
    room = cast(str | None, request_data["room"])
    query = cast(JSONObject, request_data["query"])
    to_store = dict(
        corpora=request_data["corpora"],
        query=query,
        page_size=request_data["page_size"],
        languages=request_data["languages"],
        total_results_requested=request_data["total_results_requested"],
        query_name=request_data["query_name"],
    )
    idx = uuid4()
    args = (to_store, idx, user, room)
    job: Job = request.app["query_service"].store_query(*args)
    info: dict[str, str] = {"status": "started", "job": job.id, "query_id": str(idx)}
    return web.json_response(info)

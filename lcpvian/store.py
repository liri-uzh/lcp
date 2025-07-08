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
    """
    request_data: dict[str, str] = await request.json()
    user = request_data.get("user")
    room = request_data.get("room")
    query_type = request_data.get("query_type")
    if not user or not room or not query_type:
        return web.json_response({})
    job: Job = request.app["query_service"].fetch_queries(user, room, query_type)
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)


@ensure_authorised
async def store_query(request: web.Request) -> web.Response:
    """
    User wants to store one or more queries in the DB
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
        query_type=request_data["query_type"],
    )
    idx = uuid4()
    args = (to_store, idx, user, room)
    job: Job = request.app["query_service"].store_query(*args)
    info: dict[str, str] = {"status": "started", "job": job.id, "query_id": str(idx)}
    return web.json_response(info)


@ensure_authorised
async def delete_query(request: web.Request) -> web.Response:
    """
    User wants to delete their stored query from the DB.
    Expects URL parameters: /user/{user_id}/room/{room_id}/query/{query_id}
    """
    user_id: str = request.match_info["user_id"]
    room_id: str = request.match_info["room_id"]
    query_id: str = request.match_info["query_id"]

    job: Job = request.app["query_service"].delete_query(user_id, room_id, query_id)
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)

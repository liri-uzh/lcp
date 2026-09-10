import json
import uuid

from aiohttp import web
from arq.jobs import Job
from typing import Any, cast
from uuid import uuid4

from .jobfuncs import _db_query
from .typed import JSONObject, DBQueryParams
from .utils import _publish_msg
from .worker import arq_task, ctx


async def fetch_queries(request: web.Request) -> web.Response:
    """
    User wants to retrieve their stored queries from the DB
    """
    request_data: dict[str, str] = await request.json()
    user = request_data.get("user")
    room = request_data.get("room")

    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)
    if not user_data.get("user", {}).get("id") == user:
        raise PermissionError("Could not verify the identity of the user")

    query_type = request_data.get("query_type", "")
    if not user or not room:
        return web.json_response({})
    job: Job | None = await _fetch_queries(ctx, user, room, query_type)
    info: dict[str, str] = {
        "status": "started",
        "job": "" if job is None else job.job_id,
    }
    return web.json_response(info)


async def store_query(request: web.Request) -> web.Response:
    """
    User wants to store one or more queries in the DB
    """
    request_data: JSONObject = await request.json()
    user = cast(str, request_data["user"])
    room = cast(str | None, request_data["room"])

    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)
    if not user_data.get("user", {}).get("id") == user:
        raise PermissionError("Could not verify the identity of the user")

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
    job: Job | None = await _store_query(ctx, *args)
    info: dict[str, str] = {
        "status": "started",
        "job": "" if job is None else job.job_id,
        "query_id": str(idx),
    }
    return web.json_response(info)


async def delete_query(request: web.Request) -> web.Response:
    """
    User wants to delete their stored query from the DB.
    Expects URL parameters: /user/{user_id}/room/{room_id}/query/{query_id}
    """
    user_id: str = request.match_info["user_id"]
    room_id: str = request.match_info["room_id"]
    query_id: str = request.match_info["query_id"]

    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)
    if not user_data.get("user", {}).get("id") == user_id:
        raise PermissionError("Could not verify the identity of the user")

    job: Job | None = await _delete_query(ctx, user_id, room_id, query_id)
    info: dict[str, str] = {
        "status": "started",
        "job": "" if job is None else job.job_id,
    }
    return web.json_response(info)


@arq_task("internal")
async def _fetch_queries(
    ctx,
    user: str,
    room: str,
    query_type: str,
    limit: int = 10,
):
    """
    Get previous saved queries for this user/room
    """
    params: DBQueryParams = {"user": user}

    if query_type:
        params["query_type"] = query_type

        query = ("""SELECT * FROM lcp_user.queries q
            WHERE q."user" = :user AND q.query_type = :query_type
            ORDER BY created_at DESC LIMIT {limit};""").format(limit=limit)
    else:
        query = ("""SELECT * FROM lcp_user.queries q
            WHERE q."user" = :user
            ORDER BY created_at DESC LIMIT {limit};""").format(limit=limit)

    result = await _db_query(
        ctx,
        query.strip(),
        params,
        user=user,
        room=room,
        config=True,
        query_type=query_type,
        is_main=True,
    )

    action = "fetch_queries"
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": user,
        "room": room,
        "status": "success",
        "action": action,
        "queries": [],
        "msg_id": msg_id,
    }
    if result:
        cols = ["idx", "query", "username", "room", "created_at"]
        queries: list[dict[str, Any]] = []
        for x in result:
            dct: dict[str, Any] = dict(zip(cols, x))
            queries.append(dct)
        jso["queries"] = json.dumps(queries, default=str)

    await _publish_msg(ctx["redis"], jso, msg_id)


@arq_task("internal")
async def _store_query(
    ctx,
    query_data: JSONObject,
    idx: int,
    user: str,
    room: str,
):
    """
    Add a saved query to the db
    """
    query = (
        'INSERT INTO lcp_user.queries (idx, query, "user", room, query_name, query_type) '
        "VALUES (:idx, :query, :user, :room, :query_name, :query_type);"
    )
    params: dict[str, Any] = {
        "idx": idx,
        "query": json.dumps(query_data, default=str),
        "user": user,
        "room": room,
        "query_name": query_data["query_name"],
        "query_type": query_data["query_type"],
    }
    await _db_query(
        ctx, query, params, user=user, room=room, store=True, is_main=True, query_id=idx
    )

    action = "store_query"

    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": user,
        "room": room,
        "status": "success",
        "action": action,
        "queries": [],
        "msg_id": msg_id,
    }
    jso["query_id"] = str(idx)
    jso.pop("queries")

    await _publish_msg(ctx["redis"], jso, msg_id)


@arq_task("internal")
async def _delete_query(ctx, user_id: str, room_id: str, query_id: str):
    """
    Delete a query using a background job.
    """
    # Convert the query_id string to a UUID object for proper binding.
    try:
        query_uuid = uuid.UUID(query_id)
    except ValueError:
        raise ValueError("Invalid query id provided")

    # Build parameters with the UUID object.
    params: dict[str, Any] = {"user": user_id, "room": room_id, "idx": query_uuid}

    # DELETE query without a RETURNING clause.
    query = """DELETE FROM lcp_user.queries
        WHERE "user" = :user
        AND idx = :idx"""

    await _db_query(
        ctx,
        query.strip(),
        params,
        user=user_id,
        room=room_id,
        idx=query_id,
        delete=True,
        config=True,
    )

    action = "delete_query"
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": str(user_id),
        "room": room_id,
        "idx": query_id,
        "status": "success",
        "action": action,
        "msg_id": msg_id,
        "queries": "[]",
    }

    return _publish_msg(ctx["redis"], jso, msg_id)

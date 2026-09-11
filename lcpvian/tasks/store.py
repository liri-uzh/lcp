"""
Async tasks called from store.py
"""

import json
import uuid

from typing import Any
from uuid import uuid4

from ..jobfuncs import _db_query
from ..typed import JSONObject
from ..utils import _publish_msg


async def fetch_queries(
    ctx,
    user: str,
    room: str,
    query_type: str,
    limit: int = 10,
):
    """
    Get previous saved queries for this user/room
    """
    params: dict = {"user": user}

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


async def store_query(
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


async def delete_query(ctx, user_id: str, room_id: str, query_id: str):
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

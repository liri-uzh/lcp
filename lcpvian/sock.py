"""
sock.py: websocket utilities, both sending and receiving

Each message should have `action`, which is how we know how to handle the
message, plus `user` and `room`, which tell us where the message should be sent.

Message sending is always ultimately done by utils.push_msg, which can send a
message to all users in a room, a specific user, all users, etc. as required
for a given `action`.

The /ws endpoint is connected to sock().

`listen_to_redis()` is running on a loop as a background job in the main process.
When the worker process finishes processing DB data, it publishes the data to
the Redis channel we are listening to. The main thread gets the message and
broadcasts it to the correct user/room via websocket.
"""

import asyncio
import json
import logging
import os
import traceback

from collections.abc import Coroutine
from typing import Any, Sized, cast

try:
    from aiohttp import WSCloseCode, WSMsgType, web
except ImportError:
    from aiohttp import web
    from aiohttp.http import WSCloseCode, WSMsgType

from aiohttp.http_websocket import WSMessage
from rq.job import Job

from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError


from .configure import _get_batches, CorpusConfig
from .query_service import QueryService
from .query_classes import QueryInfo, Request
from .utils import push_msg
from .validate import validate

from .typed import JSON, JSONObject, RedisMessage, Websockets
from .utils import (
    PUBSUB_CHANNEL,
    _filter_corpora,
    _set_config,
    _sign_payload,
)


MESSAGE_TTL = os.getenv("REDIS_WS_MESSSAGE_TTL", 5000)
QUERY_TTL = os.getenv("QUERY_TTL", 5000)


async def _process_message(
    message: RedisMessage, channel: PubSub, app: web.Application
) -> None:
    """
    Check that a WS message contains data, and is not a subscribe message,
    then handle it if so.
    """
    await asyncio.sleep(0.1)
    if not message or not isinstance(message, dict):
        return
    if message.get("type", "") == "subscribe":
        return
    if not message.get("data"):
        return
    data = json.loads(cast(bytes, message["data"]))
    if "msg_id" in data:
        raw: bytes = app["redis"].get(data["msg_id"])
        if not raw and "shared_redis" in app:
            raw = app["shared_redis"].get(data["msg_id"])
        if not raw:
            return None
        payload: JSONObject = json.loads(raw)
        if "callback_query" in payload:
            qi_hash: str = str(payload["hash"])
            qi = QueryInfo(qi_hash, app["redis"])
            async with asyncio.TaskGroup() as group:
                for req in qi.requests:
                    group.create_task(req.respond(app, payload))
        if "user" in data or "room" in data:
            # If the incoming data contains fresher information than from redis memory,
            # (as determined by the presence of a user/room in data)
            # then sign the payload with the information contained in data
            _sign_payload(payload, data)
        payload["status"] = data.get("status", payload.get("status", ""))
        if not payload or not isinstance(payload, dict):
            return
    else:
        payload = data
    await _handle_message(payload, channel, app)
    return None


async def handle_redis_response(
    channel: PubSub, app: web.Application, test: bool = False, retries: int = 5
) -> None:
    """
    If redis publishes a message, it gets picked up here in an async loop
    and broadcast to the correct websockets.

    We need to know if we're running c-compiled code or not, because
    channel.get_message() fails when compiled to c for some reason
    """
    message: RedisMessage = None

    try:
        while True:
            await asyncio.sleep(0.1)
            try:
                if app.get("mypy", False) is True:
                    async for message in channel.listen():
                        if message is None:
                            continue
                        await _process_message(message, channel, app)
                        if message and test is True:
                            return None
                else:
                    while True:
                        await asyncio.sleep(0.1)
                        message = await channel.get_message(
                            ignore_subscribe_messages=True, timeout=10.0
                        )
                        if message is None:
                            continue
                        await _process_message(message, channel, app)
                        if message and test is True:
                            return None
            except ConnectionError as err:
                print("Possibly too much data for redis pubsub?", err)
                await asyncio.sleep(app["redis_pubsub_limit_sleep"])

    except asyncio.TimeoutError as err:
        print(f"Warning: timeout in websocket listener ({err})")
    except asyncio.CancelledError as err:
        tb = traceback.format_exc()
        print(f"Canceled redis handler: {err}\n\n{tb}")
    except Exception as err:
        formed = traceback.format_exc()
        print(f"Error: {str(err)}\n{formed}")
        extra = {"error": str(err), "status": "failed", "traceback": formed}
        logging.error(str(err), extra=extra)


async def listen_to_redis(
    app: web.Application, instance: str, test: bool = False
) -> None:
    """
    Using our async redis connection instance, listen for events coming from redis
    and delegate to the sender, All the try/except logic is shutdown logic only
    """
    ainstance = f"a{instance}"
    if instance not in app or ainstance not in app:
        return
    while True:
        try:
            async with app[ainstance].pubsub() as channel:
                await channel.subscribe(PUBSUB_CHANNEL)
                await handle_redis_response(channel, app, test=test)
        except ConnectionError as err:
            print("Connection error in listen_to_redis", err)
        except KeyboardInterrupt:
            pass
        except Exception as err:
            raise err
        try:
            print("Attempt unsubscribe")
            await channel.unsubscribe(PUBSUB_CHANNEL)
            print("unsubscribe success")
        except:
            pass
        try:
            await app["aredis"].quit()
        except Exception:
            pass
        try:
            app["redis"].quit()
        except Exception:
            pass
        await asyncio.sleep(0.1)
    return None


async def _handle_error(
    app: web.Application, user: str, room: str, payload: JSONObject
) -> None:
    """
    Sanitise errors send to FE if not in debug mode
    """
    payload["debug"] = app["_debug"]
    bad_keys = {"traceback", "original_query", "sentences_query", "sql", "consoleSQL"}
    if not app["_debug"]:
        for key in bad_keys:
            payload.pop(key, None)
    await push_msg(app["websockets"], room, payload, skip=None, just=(room, user))
    return None


async def _handle_message(
    payload: JSONObject, channel: PubSub, app: web.Application
) -> None:
    """
    Build a message, do any extra needed actions and send on to the right websocket(s)
    """
    user = cast(str, payload.get("user", ""))
    room = cast(str, payload.get("room", ""))
    action = payload.get("action", "")
    simples = (
        "fetch_queries",
        "store_query",
        "delete_query",
        "background_job_progress",
        "document",
        "document_ids",
        "image_annotations",
        "started_export",
        "export_complete",
    )
    errors = (
        "failed",
        "upload_fail",
        "unregistered",
        "timeout",
        "interrupted",  # not currently used, maybe when rooms have multiple users
    )

    # for non-errors, we attach a msg_id to all messages, and store the message with
    # this key in redis so that the FE can retrieve it by /get_message endpoint anytime
    if (
        action not in errors
        and "msg_id" in payload
        and "no_restart" not in payload
        and app["_use_cache"]
        # and False
    ):
        uu = payload["msg_id"]
        if not app["redis"].get(uu):
            app["redis"].set(uu, json.dumps(payload))
        app["redis"].expire(uu, MESSAGE_TTL)

    if action == "export_complete":
        await app["query_service"].get_export_notifs(hash=payload.get("hash", ""))
        return

    # for document ids request, we also add this information to config
    # so that on subsequent requests we can just fetch it from there
    if action == "document_ids":
        app["config"][str(payload["corpus_id"])]["doc_ids"] = [
            payload["job"],
            payload["document_ids"],
        ]

    to_submit: None | Coroutine[None, None, web.Response] = None

    if action in simples:
        await push_msg(
            app["websockets"],
            room,
            payload,
            skip=None,
            just=(room, user),
        )
        return None

    if action in errors:
        await _handle_error(app, user, room, payload)
        return None

    # handle configuration message
    if action == "set_config":
        return await _set_config(payload, app)

    if action == "export_notifs":
        room = ""
        for rid, users in app["websockets"].items():
            for _, uid in users:
                if uid != user:
                    continue
                room = rid
                break
        if room:
            await push_msg(
                app["websockets"],
                room,
                payload,
                skip=None,
                just=(room, user),
            )
        return

    # handle the final stage of a corpus being uploaded.
    # - add the corpus to config
    # - if corpus was uploaded via gui mode, send a ws message
    #   to all users with the latest config so the FE can show it
    if action == "uploaded":
        # TODO: Should be chnaged to accept all app types (catchphrase, soundscript, videoscope)
        app_type = "lcp"
        user_data = cast(JSONObject | None, payload["user_data"])
        conf: CorpusConfig = cast(CorpusConfig, payload["entry"])
        conf["_batches"] = _get_batches(conf)
        ids_to_names: list[tuple[str, str]] = [
            (sid, c.get("shortname", "")) for sid, c in app["config"].items()
        ]
        id_str = str(payload["id"])
        for sid, name in ids_to_names:
            if name != conf.get("shortname", "") or int(sid) >= int(id_str):
                continue
            app["config"].pop(sid, {})
        app["config"][id_str] = conf
        if payload.get("gui"):
            authenticator = app["auth_class"](app)
            filt = _filter_corpora(authenticator, app["config"], app_type, user_data)
            payload["config"] = cast(JSONObject, filt)
            await push_msg(app["websockets"], "", payload)

    if to_submit is not None:
        await to_submit

    return None


async def sock(request: web.Request) -> web.WebSocketResponse:
    """
    Socket has to handle incoming messages, but also send a message when
    queries have finished processing
    """
    ws = web.WebSocketResponse(autoping=True, heartbeat=17)

    await ws.prepare(request)

    sockets = request.app["websockets"]

    msg: WSMessage | None = None
    if request.app["mypy"]:
        while True:
            msg = await ws.receive()
            await _handle_sock(ws, msg, sockets, request.app)
    else:
        # mypyc bug?
        async for msg in ws:
            await _handle_sock(ws, msg, sockets, request.app)

    # connection closed
    # await ws.close(code=WSCloseCode.GOING_AWAY, message=b"Server shutdown")

    return ws


async def _handle_sock(
    ws: web.WebSocketResponse, msg: WSMessage, sockets: Websockets, app: web.Application
) -> None:
    """
    Handle an incoming message based on its `action`

    * validate queries
    * query has enough results, so stop it (in simultaneous mode only)
    * user joins/leaves room
    """
    qs: QueryService = app["query_service"]
    conf: dict[str, Any] = app["config"]
    if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
        try:
            await ws.close(code=WSCloseCode.GOING_AWAY, message=b"User left")
        except Exception:
            pass
        return None
    if msg.type != WSMsgType.TEXT:
        return None

    payload = msg.json()
    action = payload["action"]
    possible_session: str | None = payload["room"]
    if possible_session is None:
        print("No room: something wrong")
        return None
    session_id: str = possible_session
    possible_user: str | None = payload.get("user", None)
    if possible_user is None:
        print("User not logged in! Nothing to do")
        return None
    user_id: str = possible_user
    ident: tuple[str, str] = (session_id, user_id)
    response: JSONObject

    # user opens the query page/joins a room
    if action == "joined":
        originally = len(sockets[session_id])
        sockets[session_id].add((ws, user_id))
        currently = len(sockets[session_id])
        if session_id and originally != currently:
            response = {"joined": user_id, "room": session_id, "n_users": currently}
            await push_msg(sockets, session_id, response, skip=ident)

    # user closes page or leaves a room
    elif action == "left":
        await ws.close(code=WSCloseCode.GOING_AWAY, message=b"User left")
        try:
            sockets[session_id].remove((ws, user_id))
        except KeyError:
            return None
        currently = len(sockets[session_id])
        if not currently:
            qs.cancel_running_jobs(user_id, session_id)
            if session_id:
                sockets.pop(session_id)
        elif session_id:
            response = {"left": user_id, "room": session_id, "n_users": currently}
            await push_msg(sockets, session_id, response, skip=ident)

    # query is stopped, automatically or manually
    elif action == "stop":
        request_id = payload.get("request", "")
        if not request_id:
            return
        req: None | Request
        try:
            req = Request(app["redis"], {"id": request_id})
        except:
            req = None
        if not req:
            return
        qi: QueryInfo = QueryInfo(req.hash, app["redis"])
        qi.stop_request(req)
        # jobs = qs.cancel_running_jobs(user_id, session_id)
        # jobs = list(set(jobs))
        # if jobs:
        response = {
            "request": request_id,
            "status": "stopped",
            # "n": len(jobs),
            "action": "stopped",
            # "jobs": jobs,
        }
        await push_msg(sockets, session_id, response, just=ident)

    # user edited a query, triggering auto-validation of the DQD/JSON
    elif action == "validate":
        payload["config"] = conf
        resp = validate(**payload)
        await push_msg(sockets, session_id, resp, just=ident)

    # used in simultaneous mode only: once FE sees enough results, cancel
    # any other ongoing jobs
    elif action == "enough_results":
        job = payload["job"]
        jobs = qs.cancel_running_jobs(user_id, session_id, base=job)
        jobs = list(set(jobs))
        response = {
            "status": "stopped",
            "n": len(jobs),
            "action": "stopped",
            # "jobs": jobs,
        }
        if jobs:
            await push_msg(sockets, session_id, response, just=ident)


async def ws_cleanup(sockets: Websockets) -> None:
    """
    Periodically remove any closed websocket connections to ensure that app size
    doesn't irreversibly increase over time

    Send a message to other users about it, too
    """
    interval = 3600 * 48
    while True:
        for room, conns in sockets.items():
            to_close = set()
            for ws, user in conns:
                if ws.closed:
                    to_close.add((ws, user))
            for conn in to_close:
                msg = f"Removing stale WS connection: {room}/{user}"
                print(msg)
                logging.info(msg)
                conns.remove(conn)
            n_users = len(conns)
            if not n_users or not to_close:
                continue
            for _, user in to_close:
                response: JSONObject = {
                    "left": user,
                    "room": room,
                    "n_users": n_users,
                }
                await push_msg(sockets, room, response)
        await asyncio.sleep(interval)
    return None

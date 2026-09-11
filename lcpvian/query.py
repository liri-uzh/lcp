import asyncio
import json
import logging
import traceback

from aiohttp import web

from arq.jobs import Job
from typing import cast, Any

from .abstract_query.create import json_to_sql
from .abstract_query.typed import QueryJSON
from .authenticate import Authentication
from .dqd_parser import convert
from .query_classes import QueryInfo, Request
from .utils import (
    _get_query_batches,
    hasher,
    push_msg,
    CustomEncoder,
    LCPApplication,
)

from .tasks.query import schedule_next_batch


async def process_query(
    app: LCPApplication, request_data: dict
) -> tuple[Request, QueryInfo, Any]:
    """
    Determine whether it is necessary to send queries to the DB
    and return the corresponding Request + QueryInfo + job
    """
    request: Request = Request(app["redis"], request_data)
    if request.to_buffer:
        try:
            query_buffers = app["query_buffers"]
        except:
            query_buffers = {}
            app.addkey("query_buffers", dict[str, dict], query_buffers)
        if request.id not in query_buffers:
            query_buffers[request.id] = {}
    print(
        f"Received new POST request: {request.id} ; {request.offset} -- {request.requested}"
    )
    config = app["config"][request.corpus]
    assert config.get("enabled"), RuntimeError(
        "Tried to query a corpus that has been disabled."
    )
    try:
        json_query = json.loads(request.query)
    except json.JSONDecodeError:
        json_query = convert(request.query, config)
    json_query_str = json.dumps(json_query)
    languages = [str(l) for l in request.languages.to_list()]
    lang = cast(str | None, languages[0] if languages else None)
    all_batches = _get_query_batches(config, languages)
    first_batch = all_batches[0]
    sql_query, meta_json, post_processes = json_to_sql(
        cast(QueryJSON, json_query),
        schema=config.get("schema_path", ""),
        batch=cast(str, first_batch[0]),  # batch_name
        config=config,
        lang=lang,
    )
    print("SQL query:", sql_query)
    shash = hasher(sql_query)
    local_kind = request_data.get("kind")
    local_query = request_data.get("localQuery")
    local_queries: dict = {k: v for k, v in [(local_kind, local_query)] if k and v}
    qi = QueryInfo(
        shash,
        app["redis"],
        json.loads(json_query_str),  # roll back any modifications made to json_query
        meta_json,
        post_processes,
        languages,
        config,
        local_queries,
    )
    job: Job | None = None
    should_run: bool = True
    if request.to_export and request.user:
        xp_format: str = request.to_export.get("format", "xml") or "xml"
        should_run = await app["exporters"][xp_format].initiate_db(
            app, shash, config, request
        )
    if should_run:
        qi.add_request(request)
        # pass QueryInfo to schedule_next_batch, defined in ./tasks/ (no import of query_classes)
        job = await schedule_next_batch(
            shash, connection=app["redis"], ctx={"_queryInfo": QueryInfo}
        )
        if job and qi.full:
            job_info = await job.info()
            # Schedule all batches in parallel if this is a full query
            scheduled_batch, _ = ("", "") if not job_info else job_info.args[1]
            print(
                f"Full query: batch {scheduled_batch} already scheduled -- adding the remaining ones now"
            )
            for remaining_batch in all_batches:
                batch_name, _ = remaining_batch
                if batch_name == scheduled_batch:
                    continue
                extra_job = await qi.enqueue(
                    "query.do_batch", shash, list(remaining_batch)
                )
                extra_job_info = await cast(Job, extra_job).info()
                newly_scheduled_batch, _ = (
                    extra_job_info.args[1] if extra_job_info else ["", None]
                )
                print(f"Full query: scheduled {newly_scheduled_batch}")
    return (request, qi, job)


async def post_query(request: web.Request) -> web.Response:
    """
    Main query endpoint: generate and queue up corpus queries
    """
    app = cast(LCPApplication, request.app)
    request_data = await request.json()

    user = request_data.get("user", "")
    room = request_data.get("room", "")
    corpus = request_data.get("corpus", "")
    if request_data.get("api"):
        room = "api"
        request_data["room"] = room
    # Check permission
    authenticator = cast(Authentication, app["auth_class"](app))
    user_data: dict = await authenticator.user_details(request)
    app_type = str(request_data.get("appType", "lcp"))
    app_type = (
        "lcp"
        if app_type not in {"lcp", "videoscope", "soundscript", "catchphrase"}
        else app_type
    )
    allowed = authenticator.check_corpus_searchable(
        str(corpus), user_data, app_type, get_all=False
    )
    if not allowed:
        fail: dict[str, str] = {
            "status": "403",
            "error": "Forbidden",
            "action": "query_error",
            "user": user,
            "room": room,
            "info": "Attempted access to an unauthorized corpus",
        }
        msg = "Attempted access to an unauthorized corpus"
        # # alert everyone possible about this problem:
        print(msg)
        logging.error(msg, extra=fail)
        just: tuple[str, str] = (room, user or "")
        await push_msg(app["websockets"], room, cast(dict, fail), just=just)
        raise web.HTTPForbidden(text=msg)

    try:
        req, qi, job = await process_query(app, request_data)
    except Exception as e:
        print("Could not process query", e)
        traceback.print_exc()
        raise web.HTTPBadRequest(reason=str(e))

    if req.to_export and req.user:
        xpformat = req.to_export.get("format", "xml") or "xml"
        if xpformat == "swissdox":
            user_account = cast(dict, user_data.get("user", user_data.get("account")))
            email = (user_account or {}).get("email", "")
            req.to_export["email"] = email or ""
        await push_msg(
            app["websockets"],
            req.room,
            {
                "action": "started_export",
                "format": xpformat,
                "request": req.id,
                "filename": req.to_export.get("filename", ""),
            },
            skip=None,
            just=(req.room, req.user),
        )

    if req.synchronous:
        while 1:
            await asyncio.sleep(0.5)
            if not qi.has_request(req):
                break
        res = app["query_buffers"].pop(req.id, None)
        print(f"[{req.id}] Done with synchronous request")
        serializer = CustomEncoder()
        return web.json_response(serializer.default(res))
    else:
        job_info = (
            {"status": "started", "job": req.hash, "request": req.id} if job else {}
        )
        return web.json_response(job_info)

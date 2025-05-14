# TODO: add export, call exporter in send_query and send_segment

import asyncio
import json
import os
import shutil

from aiohttp import web
from datetime import datetime
from redis import Redis as RedisConnection
from rq import Callback
from rq.job import get_current_job, Job
from typing import cast, Any

from .abstract_query.create import json_to_sql
from .abstract_query.typed import QueryJSON
from .authenticate import Authentication
from .callbacks import _general_failure
from .dqd_parser import convert
from .jobfuncs import _handle_export
from .query_classes import QueryInfo, Request
from .utils import (
    sanitize_filename,
    _get_query_batches,
    get_segment_meta_script,
    hasher,
    push_msg,
    CustomEncoder,
    LCPApplication,
)

EXPORT_TTL = 5000
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


def batch_callback(job: Job, connection: RedisConnection, batch_name: str):
    """
    Publish a message that we got some results (to be captured by the requests)
    then schedule the query on the next batch
    and run the appropriate segment/meta queries now (if applicable)
    """

    if not batch_name:
        return

    qhash: str = job.args[0]
    qi: QueryInfo = QueryInfo(qhash, connection)

    # do next batch (if needed)
    schedule_next_batch(qhash, connection, batch_name)

    # run needed segment+meta queries
    lines_before, lines_now = qi.get_lines_batch(batch_name)
    lines_so_far = lines_before + lines_now
    # send sentences if needed
    if not qi.kwic_keys:
        return

    min_offset = min(r.offset for r in qi.requests)
    # Send only if this batch exceeds the offset and this batch starts before what's required
    need_segments_this_batch = (
        lines_now > 0 and lines_so_far >= min_offset and qi.required > lines_before
    )
    print(
        f"need segments for {batch_name}?",
        min_offset,
        lines_so_far,
        need_segments_this_batch,
    )
    if not need_segments_this_batch:
        return

    offset_this_batch = max(0, min_offset - lines_so_far)
    lines_this_batch = (
        lines_now if qi.full else min(lines_now, qi.required - lines_before)
    )
    qi.enqueue(
        do_segment_and_meta,
        qi.hash,
        batch_name,
        offset_this_batch,
        lines_this_batch,
    )


async def do_segment_and_meta(
    qhash: str,
    batch_name: str,
    offset_this_batch: int,
    lines_this_batch: int,
):
    """
    Fetch from cache or run a segment+meta query on the given batch
    """
    current_job: Job | None = get_current_job()
    assert current_job, RuntimeError(
        f"No current jbo found for do_segment_and_meta {batch_name}"
    )
    connection = current_job.connection
    qi = QueryInfo(qhash, connection=connection)
    batch_hash, _ = qi.query_batches[batch_name]
    batch_results: list = qi.get_from_cache(batch_hash)

    all_segment_ids: dict[str, int] = qi.segment_ids_in_results(
        batch_results,
        qi.kwic_keys,
        offset_this_batch,
        offset_this_batch + lines_this_batch,
    )
    seg_hashes = qi.segment_hashes_for_batch.setdefault(batch_name, [])
    existing_seg_ids: dict[str, int] = {}
    for sgh in seg_hashes:
        try:
            # Retrieve any associated segment job query from cache
            res_prep = [line for rtype, line in qi.get_from_cache(sgh) if rtype == -1]
            seg_sids = {str(sid): 1 for sid, *_ in res_prep}
            existing_seg_ids.update(seg_sids)
        except:
            pass
    if existing_seg_ids:
        print(
            f"Found {len(existing_seg_ids)}/{len(all_segment_ids)} segments in cache for {batch_name}"
        )
    segment_ids: list[str] = [
        sid for sid in all_segment_ids if sid not in existing_seg_ids
    ]
    if not segment_ids:
        print(f"No new segment query needed for {batch_name}")
    else:
        script, meta_labels = get_segment_meta_script(
            qi.config, qi.languages, batch_name, segment_ids
        )
        qi.meta_labels = meta_labels
        qi.update({"meta_labels": meta_labels})
        shash = hasher(script)
        print(f"Running new segment query for {batch_name} -- {shash}")
        res = await qi.query(shash, script)
        seg_hashes.append(shash)
    # Calculate which lines from res should be sent to each request
    reqs_offsets = {r.id: r.lines_for_batch(qi, batch_name) for r in qi.requests}
    reqs_sids: dict[str, dict[str, int]] = {
        req_id: qi.segment_ids_in_results(batch_results, qi.kwic_keys, o, o + l)
        for req_id, (o, l) in reqs_offsets.items()
    }
    for sgh in seg_hashes:
        reqs_nlines: dict[str, dict[int, int]] = {req_id: {} for req_id in reqs_sids}
        for nline, (_, (sid, *_)) in enumerate(qi.get_from_cache(sgh)):
            for req_id, sids in reqs_sids.items():
                if sid not in sids:
                    continue
                reqs_nlines[req_id][nline] = 1
        for r in qi.requests:
            if sgh in r.segment_lines_for_hash:
                continue
            r.update_dict("segment_lines_for_hash", {sgh: reqs_nlines[r.id]})
    qi.publish(batch_name, "segments")


async def do_batch(qhash: str, batch: list):
    """
    Fetch from cache or run a main query on a batch from within a worker
    and aggregate the results for stats if needed
    """
    current_job: Job | None = get_current_job()
    assert current_job, RuntimeError(f"No current job found for do_batch {batch}")
    connection = current_job.connection
    qi = QueryInfo(qhash, connection=connection)
    batch_name = cast(str, batch[0])
    if batch_name == qi.running_batch:
        # This batch is already running: stop here
        return
    # Now this is the running batch
    qi.running_batch = batch_name
    try:
        batch_hash, _ = qi.query_batches[batch_name]
        qi.get_from_cache(batch_hash)
        print(f"Retrieved query from cache: {batch_name} -- {batch_hash}")
    except:
        print(f"No job in cache for {batch_name}, running it now")
        await qi.run_query_on_batch(batch)
        batch_hash, _ = qi.query_batches.get(batch_name, ("", 0))
    min_offset = min(r.offset for r in qi.requests)
    await qi.run_aggregate(min_offset, batch)
    qi.publish(batch_name, "main")
    return batch_name


def schedule_next_batch(
    qhash: str,
    connection: RedisConnection,
    previous_batch_name: str | None = None,
) -> Job | None:
    """
    Find the next batch to run based on the previous one
    and return the corresponding job (None if no next batch)
    """
    qi = QueryInfo(qhash, connection=connection)
    if previous_batch_name:
        lines_before, lines_batch = qi.get_lines_batch(previous_batch_name)
        if lines_before + lines_batch >= qi.required:
            qi.running_batch = ""
            return None
    next_batch = qi.decide_next_batch(previous_batch_name)
    if not next_batch:
        qi.running_batch = ""
        return None
    min_offset = min(r.offset for r in qi.requests)
    while min_offset > 0 and list(next_batch) in qi.done_batches:
        lines_before_batch, lines_next_batch = qi.get_lines_batch(next_batch[0])
        if min_offset <= lines_before_batch + lines_next_batch:
            break
        next_batch = qi.decide_next_batch(next_batch[0])
    return qi.enqueue(do_batch, qhash, list(next_batch), callback=batch_callback)


def process_query(
    app: LCPApplication, request_data: dict
) -> tuple[Request, QueryInfo, Any]:
    """
    Determine whether it is necessary to send queries to the DB
    and return the job info + the asyncio task + QueryInfo instance
    """
    request: Request = Request(app["redis"], request_data)
    print(
        f"Received new POST request: {request.id} ; {request.offset} -- {request.requested}"
    )
    config = app["config"][request.corpus]
    try:
        json_query = json.loads(request.query)
        json_query = json.loads(json.dumps(json_query, sort_keys=True))
    except json.JSONDecodeError:
        json_query = convert(request.query, config)
    all_batches = _get_query_batches(config, request.languages)
    sql_query, meta_json, post_processes = json_to_sql(
        cast(QueryJSON, json_query),
        schema=config.get("schema_path", ""),
        batch=cast(str, all_batches[0][0]),
        config=config,
        lang=request.languages[0] if request.languages else None,
    )
    print("SQL query:", sql_query)
    shash = hasher(sql_query)
    qi = QueryInfo(
        shash,
        app["redis"],
        json_query,
        meta_json,
        post_processes,
        request.languages,
        config,
    )
    qi.add_request(request)
    if request.to_export and request.user:
        # TODO: move this into the exporter script instead?
        epath = app["exporters"]["xml"].get_dl_path_from_hash(
            shash, request.offset, request.requested, request.full
        )
        if os.path.exists(epath):
            shutil.rmtree(epath)
        xp_format: str = request.to_export.get("format", "xml") or "xml"
        ext: str = ".db" if xp_format == "swissdox" else ".xml"
        filename: str = cast(str, request.to_export.get("filename", ""))
        cshortname = config.get("shortname")
        if not filename:
            filename = (
                f"{cshortname} {datetime.now().strftime('%Y-%m-%d %I:%M%p')}{ext}"
            )
        filename = sanitize_filename(filename)
        corpus_folder = sanitize_filename(cshortname or config.get("project_id", ""))
        userpath: str = os.path.join(corpus_folder, filename)
        suffix: int = 0
        while os.path.exists(os.path.join(RESULTS_USERS, request.user, userpath)):
            suffix += 1
            userpath = os.path.join(
                corpus_folder, f"{os.path.splitext(filename)[0]} ({suffix}){ext}"
            )
        app["internal"].enqueue(
            _handle_export,  # init_export
            on_failure=Callback(
                _general_failure,
            ),
            result_ttl=EXPORT_TTL,
            job_timeout=EXPORT_TTL,
            args=(shash, xp_format, True, request.offset, request.requested),
            kwargs={
                "user_id": request.user,
                "userpath": userpath,
                "corpus_id": request.corpus,
            },
        )
    job: Job | None = schedule_next_batch(shash, connection=app["redis"])
    return (request, qi, job)


async def post_query(request: web.Request) -> web.Response:
    """
    Main query endpoint: generate and queue up corpus queries
    """
    app = cast(LCPApplication, request.app)
    request_data = await request.json()
    # user = request_data.get("user", "")
    # room = request_data.get("room", "")
    # corpus = request_data.get("corpus", "")
    # if request_data.get("api"):
    #     room = "api"
    #     request_data["room"] = room
    #     request_data["to_export"] = request_data.get("to_export") or {"format": "xml"}
    # # Check permission
    # authenticator = cast(Authentication, app["auth_class"](app))
    # user_data: dict = {}
    # if "X-API-Key" in request.headers and "X-API-Secret" in request.headers:
    #     user_data = await authenticator.check_api_key(request)
    # else:
    #     user_data = await authenticator.user_details(request)
    # app_type = str(request_data.get("appType", "lcp"))
    # app_type = (
    #     "lcp"
    #     if app_type not in {"lcp", "videoscope", "soundscript", "catchphrase"}
    #     else app_type
    # )
    # allowed = authenticator.check_corpus_allowed(
    #     str(corpus), app["config"][str(corpus)], user_data, app_type, get_all=False
    # )
    # if not allowed:
    #     fail: dict[str, str] = {
    #         "status": "403",
    #         "error": "Forbidden",
    #         "action": "query_error",
    #         "user": user,
    #         "room": room,
    #         "info": "Attempted access to an unauthorized corpus",
    #     }
    #     msg = "Attempted access to an unauthorized corpus"
    #     # # alert everyone possible about this problem:
    #     print(msg)
    #     logging.error(msg, extra=fail)
    #     payload = cast(JSONObject, fail)
    #     just: tuple[str, str] = (room, user or "")
    #     await push_msg(app["websockets"], room, payload, just=just)
    #     print("pushed message")
    #     raise web.HTTPForbidden(text=msg)

    (req, qi, job) = process_query(app, request_data)
    if req.to_export and req.user:
        xpformat = req.to_export.get("format", "xml") or "xml"
        await push_msg(
            app["websockets"],
            req.room,
            {"action": "started_export", "format": xpformat},
            skip=None,
            just=(req.room, req.user),
        )

    if req.synchronous:
        try:
            query_buffers = app["query_buffers"]
        except:
            query_buffers = {}
            app.addkey("query_buffers", dict[str, dict], query_buffers)
        query_buffers[req.id] = {}
        while 1:
            await asyncio.sleep(0.5)
            if not qi.has_request(req):
                break
        res = query_buffers[req.id]
        query_buffers.pop(req.id, None)
        print(f"[{req.id}] Done with synchronous request")
        serializer = CustomEncoder()
        return web.json_response(serializer.default(res))
    else:
        job_info = {
            "status": "started",
            "job": req.hash,
        }
        return web.json_response(job_info)

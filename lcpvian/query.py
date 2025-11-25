import asyncio
import json
import logging
import re
import traceback

from aiohttp import web
from intervaltree import IntervalTree
from redis import Redis as RedisConnection
from rq.job import get_current_job, Job
from typing import cast, Any
from uuid import uuid4

from .abstract_query.create import json_to_sql
from .abstract_query.typed import QueryJSON
from .authenticate import Authentication
from .dqd_parser import convert
from .query_classes import QueryInfo, Request
from .redis_proxies import RedisDict
from .utils import (
    _get_query_batches,
    get_segment_meta_script,
    hasher,
    push_msg,
    range_from_str,
    CustomEncoder,
    LCPApplication,
)


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

    min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
    # Send only if this batch exceeds the offset and this batch starts before what's required
    need_segments_this_batch = (
        lines_now > 0
        and lines_so_far >= min_offset
        and (qi.full or qi.required > lines_before)
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
    if not qi.requests:
        return
    batch_hash, _ = qi.query_batches[batch_name]
    batch_results: list = qi.get_from_cache(batch_hash)

    segment: str = qi.config["firstClass"]["segment"]
    export_to_xml = any(
        r.to_export and r.to_export.get("format") == "xml" for r in qi.requests
    )

    kwics = [x for x in qi.result_sets if x.get("type") == "plain"]
    kwics_ids = [
        next(y for y in x.get("attributes", []) if y.get("name") == "identifier")
        for x in kwics
    ]
    context: None | str = kwics_ids[0].get("layer", segment)
    assert all(x.get("layer") == context for x in kwics_ids), ReferenceError(
        f"All contexts in the plain results must refer to the same annotation layer"
    )
    if not export_to_xml:
        context = None

    script, meta_labels = get_segment_meta_script(
        qi.config, qi.languages, batch_name, context=context
    )

    all_segment_ids: dict[str, int | list[int]] = qi.segment_ids_in_results(
        batch_results,
        offset_this_batch,
        offset_this_batch + lines_this_batch,
    )
    segments_this_batch = qi.segments_for_batch.get(batch_name, {})
    if isinstance(segments_this_batch, RedisDict):
        segments_this_batch = segments_this_batch.to_dict()
    existing_sids: dict[str, int] = {
        sid: 1 for _, sids in segments_this_batch.items() for sid in sids
    }
    needed_sids: dict[str, int] = {
        sid: 1 for sid in all_segment_ids if sid not in existing_sids
    }
    if existing_sids:
        print(
            f"Found {len(existing_sids)}/{len(all_segment_ids)} segments in cache for {batch_name}"
        )
    if export_to_xml and context != segment:
        # Force re-querying the segments and their meta for wide contexts when exporting to XML
        needed_sids = {sid: 1 for sid in all_segment_ids}
        print(
            f"Running the segment query (again?) for export purposes -- it might take a while"
        )
    if not needed_sids:
        print(f"No new segment query needed for {batch_name}")
    else:
        qi.qi["meta_labels"] = meta_labels
        squery_id = str(uuid4())
        print(f"Running new segment query for {batch_name} -- {squery_id}")
        await qi.query(squery_id, script, params={"sids": [sid for sid in needed_sids]})
        if batch_name not in qi.segments_for_batch:
            qi.segments_for_batch[batch_name] = {}
        qi.segments_for_batch[batch_name][squery_id] = needed_sids
    # Calculate which lines from res should be sent to each request
    reqs_offsets = {r.id: r.lines_for_batch(qi, batch_name) for r in qi.requests}
    reqs_sids: dict[str, dict[str, int | list[int]]] = {
        req_id: qi.segment_ids_in_results(batch_results, o, o + l)
        for req_id, (o, l) in reqs_offsets.items()
    }
    reqs_itvls: dict[str, IntervalTree] = {}
    for req_id, sids_to_crs in reqs_sids.items():
        reqs_itvls[req_id] = IntervalTree()
        for char_range in sids_to_crs.values():
            reqs_itvls[req_id][range(*cast(list[int], char_range))] = 1
    segments_this_batch = cast(RedisDict, qi.segments_for_batch[batch_name]).to_dict()
    for sqid in segments_this_batch:
        reqs_nlines: dict[str, dict[str, int]] = {req_id: {} for req_id in reqs_sids}
        lines: list
        try:
            lines = qi.get_from_cache(sqid)
        except:
            sids = [si for si in segments_this_batch[sqid]]
            lines = await qi.query(sqid, script, params={"sids": sids})
        # Be smart about which lines to include
        for nline, (rtype, content) in enumerate(lines):
            for req_id, sids_in_req in reqs_sids.items():
                # No longer using sids_in_req here since we're using char_range
                cr: str | dict = content[-1]
                if isinstance(cr, dict):
                    cr = cr.get("char_range", "")
                if not isinstance(cr, str) or not re.match(r"\[\d+,\d+\)", cr):
                    continue
                if not reqs_itvls[req_id][range_from_str(cast(str, cr))]:
                    continue
                reqs_nlines[req_id][str(nline)] = 1
        for r in qi.requests:
            if sqid in r.segment_lines_for_hash:
                continue
            r.segment_lines_for_hash[sqid] = reqs_nlines[r.id]
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
    if not qi.requests:
        return
    batch_name = cast(str, batch[0])
    if batch_name == qi.running_batch:
        # This batch is already running: stop here
        return
    # Now this is the running batch
    qi.running_batch = batch_name
    try:
        assert batch_name in qi.query_batches
        batch_hash, _ = qi.query_batches[batch_name]
        qi.get_from_cache(batch_hash)
        print(f"Retrieved query from cache: {batch_name} -- {batch_hash}")
    except:
        print(f"No job in cache for {batch_name}, running it now")
        await qi.run_query_on_batch(batch)
        batch_hash, _ = qi.query_batches.get(batch_name, ("", 0))
    min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
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
    if not qi.requests:
        return None
    if previous_batch_name and not qi.full:
        lines_before, lines_batch = qi.get_lines_batch(previous_batch_name)
        if lines_before + lines_batch >= qi.required:
            qi.running_batch = ""
            return None
    next_batch = qi.decide_next_batch(previous_batch_name)
    if not next_batch:
        qi.running_batch = ""
        return None
    min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
    while min_offset > 0 and next_batch[0] in qi.done_batches:
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
    and return the corresponding Request + QueryInfo + job
    """
    request: Request = Request(app["redis"], request_data)
    if request.synchronous:
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
    try:
        json_query = json.loads(request.query)
    except json.JSONDecodeError:
        json_query = convert(request.query, config)
    json_query_str = json.dumps(json_query)
    lang = cast(str | None, request.languages[0] if request.languages else None)
    all_batches = _get_query_batches(config, request.languages)
    sql_query, meta_json, post_processes = json_to_sql(
        cast(QueryJSON, json_query),
        schema=config.get("schema_path", ""),
        batch=cast(str, all_batches[0][0]),
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
        json.loads(json_query_str),  # discard any modifications made to json_query
        meta_json,
        post_processes,
        request.languages,
        config,
        local_queries,
    )
    # if local_kind and local_kind not in qi.local_queries:
    #     qi.update({"local_queries": {**qi.local_queries, local_kind: local_query}})
    job: Job | None = None
    should_run: bool = True
    if request.to_export and request.user:
        xp_format: str = request.to_export.get("format", "xml") or "xml"
        should_run = app["exporters"][xp_format].initiate_db(
            app, shash, config, request
        )
    if should_run:
        qi.add_request(request)
        job = schedule_next_batch(shash, connection=app["redis"])
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
    user_data: dict = {}
    if "X-API-Key" in request.headers and "X-API-Secret" in request.headers:
        user_data = await authenticator.check_api_key(request)
    else:
        user_data = await authenticator.user_details(request)
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
        (req, qi, job) = process_query(app, request_data)
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

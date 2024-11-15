"""
query.py: The /query POST endpoint

When user submits a new query or resumes an existing one, the /query endpoint
calls the `query()` async function.

The logic is basically:

    1. Create a QueryIteration object from the POST data (qi.py)
    2. Submit a query and/or sentences query
    3. The callbacks for these queries publish the result as JSON (callbacks.py)
    4. Listener hears these messages, sends them to relevant users (sock.py)
    5. If query is not finished, the query() function is called again, but with
       data passed in manually rather than through HTTP request.
    6. Process repeats until query is satisfied/finished

"""

import json
import logging
import os
import traceback

from typing import cast

from aiohttp import web
from rq.job import Job

from .export import export
from .log import logged
from .qi import QueryIteration
from .typed import Batch, Iteration, JSONObject
from .utils import ensure_authorised, push_msg


async def _do_resume(qi: QueryIteration) -> QueryIteration:
    """
    Resume a query, or decide that we need to query the next batch

    When resuming, there are two or three possible situations we could be in:

    1. we have already got enough results via previous sql queries to fill
       the request, we just haven't sent them yet
    2. we have not got enough results, so we need to query this batch and the next one
    3? we had exactly the right number of results ... edge case

    """
    prev_job = Job.fetch(qi.previous, connection=qi.app["redis"])
    pjkwargs = cast(dict, prev_job.kwargs)
    dones = cast(list[tuple[int, str, str, int]], pjkwargs["done_batches"])
    done_batches: list[Batch] = [(a, b, c, d) for a, b, c, d in dones]
    so_far = cast(int, prev_job.meta["total_results_so_far"])
    tot_req = qi.total_results_requested
    prev_total = qi.current_kwic_lines

    prev_batch_results = cast(int, prev_job.meta["results_this_batch"])
    need_now = tot_req - prev_total

    next_offset = cast(int, prev_job.meta["offset_for_next_time"])
    latest_offset = cast(int, prev_job.meta.get("latest_offset", 0))
    qi.offset = max(latest_offset, next_offset)

    left_in_batch = prev_batch_results - qi.offset
    not_enough = left_in_batch < need_now

    prev = cast(Batch, tuple(pjkwargs["current_batch"]))
    previous_batch: Batch = (prev[0], prev[1], prev[2], prev[3])
    if previous_batch not in done_batches:
        done_batches.append(previous_batch)
    qi.done_batches = done_batches

    max_kwic = int(os.getenv("DEFAULT_MAX_KWIC_LINES", 9999))

    all_batches_queried = len(done_batches) >= len(qi.all_batches)

    is_last = prev_total + left_in_batch > max_kwic

    if prev_total >= max_kwic and not qi.full:
        qi.needed = 0
        qi.no_more_data = True
        return qi
    if qi.total_results_so_far >= tot_req:
        qi.needed = tot_req - prev_total
    elif not_enough and not all_batches_queried and not is_last:
        qi.needed = left_in_batch
        qi.start_query_from_sents = True
    elif not_enough and (all_batches_queried or is_last):
        qi.needed = left_in_batch
        qi.no_more_data = True
        return qi
    else:
        raise ValueError("Backend error. Please debug")

    if qi.full:
        qi.start_query_from_sents = True

    qi.total_results_so_far = so_far

    return qi


async def _query_iteration(
    qi: QueryIteration, it: int
) -> QueryIteration | web.Response:
    """
    Oversee the querying of a single batch:

        * Set up data needed for resumed queries
        * Decide batch to query this time
        * Submit actual query
        * Optionally, submit sentences query
        * Prepare for next iteration if need be
    """
    max_jobs = int(os.getenv("MAX_SIMULTANEOUS_JOBS_PER_USER", -1))

    # handle resumed queries -- figure out if we need to query new batch
    if qi.resume:
        qi = await _do_resume(qi)
        if qi.needed <= 0 and qi.no_more_data:
            return await qi.no_batch()
    else:
        qi.offset = 0

    jobs: dict[str, str | list[str] | bool] = {}

    qi.current_batch = qi.decide_batch()

    if not qi.current_batch and qi.no_more_data:
        return await qi.no_batch()

    # Handle cases where the query was canceled or stopped prematurely
    if qi.first_job:
        first_job: Job = Job.fetch(qi.first_job, connection=qi.app["redis"])
        first_job_status = first_job.get_status(refresh=True)
        if (
            first_job_status in ("stopped", "canceled")
            or qi.first_job in qi.app["canceled"]
        ):
            if qi.first_job not in qi.app["canceled"]:
                qi.app["canceled"].append(qi.first_job)
            qi.app["query_service"].cancel_running_jobs(qi.user, qi.room)
            print(f"Query was stopped: {qi.first_job} -- preventing update")
            return await qi.no_batch()

    qi.make_query()

    # print query info to terminal for first batch only
    if not it and not qi.job and not qi.resume:
        query_type = "DQD" if qi.dqd else "JSON"
        form = json.dumps(qi.jso, indent=4)
        print(f"Detected query type: {query_type}")
        print(f"DQD:\n\n{qi.dqd}\n\nJSON:\n\n{form}\n\nSQL:\n\n{qi.sql}")

    # organise and submit query to rq via query service
    query_job, do_sents = await qi.submit_query()

    # simultaneous query setup for next iteration -- plz improve
    divv = (it + 1) % max_jobs if max_jobs > 0 else -1
    if qi.job and qi.simultaneous and it and max_jobs > 0 and not divv:
        if query_job.id not in qi.dep_chain:
            qi.dep_chain.append(query_job.id)

    assert qi.current_batch is not None
    schema_table = ".".join(qi.current_batch[1:3])

    if (
        qi.current_batch is not None
        and qi.job is not None
        and do_sents is not None
        and not qi.resume
    ):
        print(f"\nNow querying: {schema_table} ... {query_job.id}")

    # prepare and submit sentences query
    if do_sents and (qi.sentences or qi.resume):
        sents_jobs = qi.submit_sents(do_sents)

    jobs = {
        "status": "started",
        "job": qi.job_id if qi.job else qi.previous,
    }

    if qi.sentences and do_sents:
        jobs.update({"sentences": True, "sentences_jobs": sents_jobs})

    qi.job_info = jobs

    if qi.simultaneous and qi.current_batch is not None:
        qi.done_batches.append(qi.current_batch)
        qi.current_batch = None

    return qi


@ensure_authorised
@logged
async def query(
    request: web.Request,
    manual: JSONObject | None = None,
    app: web.Application | None = None,
) -> web.Response:
    """
    Main query endpoint: generate and queue up corpus queries

    Actual DB queries are done in the worker process, managed by RQ/Redis. Once
    these jobs are submitted, we return an HTTP response with the job id,
    so that the frontend knows the query has started and its job id.

    This endpoint can be manually triggered for queries over multiple batches. When
    that happpens, `manual` is a dict with the needed data and the app is passed in
    as a kwarg.

    Because data can come in either through a request or through a dict, we normalise
    by creating a utils.QueryIteration dataclass. Use this to keep the namespace of this
    function from growing any larger...

    On any serious error, we send a failure message to the user and log the
    error to sentry if configured.

    Simultaneous mode is currently not used, but can be enabled in .env . In
    this mode, multiple query requests can be sent simultaneously, rather than
    one at a time. This is experimental, it will probably remain unused.
    """
    qi: QueryIteration | web.Response
    # Turn request or manual dict into a QueryIteration object
    if manual is not None and isinstance(app, web.Application):
        # 'request' comes from sock.py, it is a non-first iteration
        qi = await QueryIteration.from_manual(manual, app)
    else:
        # request is from the frontend, most likely a new query...
        qi = await QueryIteration.from_request(request)

    # prepare for query iterations (just one if not simultaneous mode)
    iterations = len(qi.all_batches) if qi.simultaneous else 1
    http_response: list[dict[str, str | bool | list[str]]] = []
    out: Iteration

    try:
        for it in range(iterations):
            qi = await _query_iteration(qi, it)
            if not isinstance(qi, QueryIteration):
                return qi
            elif qi.to_export:
                ready_to_export = len(qi.done_batches) == len(
                    qi.all_batches
                ) or qi.to_export.get("preview")
                if ready_to_export:
                    await export(qi.app, qi.to_export, qi.first_job)
                # elif qi.job and len(qi.done_batches)+1 == len(qi.all_batches):
                else:
                    qi_job = cast(Job, qi.job)
                    qi_job.meta["to_export"] = qi.to_export
                    qi_job.save_meta()
            http_response.append(qi.job_info)
    except Exception as err:
        qi = cast(QueryIteration, qi)
        tb = traceback.format_exc()
        fail: dict[str, str] = {
            "status": "error",
            "action": "query_error",
            "type": str(type(err)),
            "traceback": tb,
            "user": qi.user,
            "room": qi.room or "",
            "info": f"Could not create query: {str(err)}",
        }
        msg = f"Error: {err} ({qi.user}/{qi.room})"
        # alert everyone possible about this problem:
        print(f"{msg}:\n\n{tb}")
        logging.error(msg, extra=fail)
        payload = cast(JSONObject, fail)
        room: str = qi.room or ""
        just: tuple[str, str] = (room, qi.user)
        await push_msg(qi.app["websockets"], room, payload, just=just)
        return web.json_response(fail)

    if qi.simultaneous:
        return web.json_response(http_response)
    else:
        return web.json_response(http_response[0])


@ensure_authorised
async def refresh_config(request: web.Request) -> web.Response:
    """
    Force a refresh of the config via the /config endpoint
    """
    qs = request.app["query_service"]
    job: Job = await qs.get_config(force_refresh=True)
    return web.json_response({"job": str(job.id)})

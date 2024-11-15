"""
callbacks.py: post-process the result of an SQL query and broadcast
it to the relevant websockets

These jobs are usually run in the worker process, but in exceptional
circumstances, they are run in the main thread, like when fetching
jobs that were run earlier

These callbacks are hooked up as on_success and on_failure kwargs in
calls to Queue.enqueue in query_service.py
"""

import json
import os
import shutil
import traceback

from datetime import datetime
from types import TracebackType
from typing import Any, Unpack, cast
from uuid import uuid4

from redis import Redis as RedisConnection
from rq.job import Job

from .configure import _get_batches
from .convert import (
    _aggregate_results,
    _format_kwics,
    _apply_filters,
    _get_all_sents,
)
from .typed import (
    BaseArgs,
    Batch,
    Config,
    DocIDArgs,
    JSONObject,
    MainCorpus,
    QueryArgs,
    QueryMeta,
    RawSent,
    Results,
    SentJob,
    UserQuery,
)
from .utils import (
    CustomEncoder,
    Interrupted,
    _get_status,
    _row_to_value,
    _get_associated_query_job,
    _get_first_job,
    _get_total_requested,
    _decide_can_send,
    _time_remaining,
    _publish_msg,
    _sharepublish_msg,
    format_meta_lines,
    TRUES,
)


PUBSUB_LIMIT = int(os.getenv("PUBSUB_LIMIT", 31999999))
MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))


def _query(
    job: Job,
    connection: RedisConnection,
    result: list[Any],
    **kwargs: Unpack[QueryArgs],
) -> None:
    """
    Job callback, publishes a redis message containing the results

    This is where we need to aggregate statistics over all jobs in the group

    This callback can be run either in the worker or the main thread, and needs
    to handle normal queries, as well as queries fetched from redis memory

    When a new query is submitted, the QueryIteration object and the RQ Job
    object have an empty string as the `first_job` attribute/key. For subsequent
    batches, `first_job` is the initial job id. On this job's `meta`, we store
    the aggregated results that are calculated during this callback. Then we
    apply post_processes filters and send the result as a WS message.
    """
    job_kwargs = cast(dict, job.kwargs)
    table = f"{job_kwargs['current_batch'][1]}.{job_kwargs['current_batch'][2]}"
    allowed_time = float(os.getenv("QUERY_ALLOWED_JOB_TIME", 0.0))
    ended_at = cast(datetime, job.ended_at)
    started_at = cast(datetime, job.started_at)
    duration: float = round((ended_at - started_at).total_seconds(), 3)
    total_duration = round(job_kwargs.get("total_duration", 0.0) + duration, 3)
    duration_string = f"Duration ({table}): {duration} :: {total_duration}"

    from_memory = kwargs.get("from_memory", False)
    meta_json: QueryMeta = cast(QueryMeta, job_kwargs.get("meta_json"))
    existing_results: Results = {0: meta_json}
    post_processes = kwargs.get("post_processes", job_kwargs.get("post_processes", {}))
    is_base = not bool(job_kwargs.get("first_job"))
    total_before_now = job_kwargs["total_results_so_far"]
    done_part = job_kwargs["done_batches"]
    is_full = kwargs.get("full", job_kwargs["full"])
    first_job = _get_first_job(job, connection)
    stored = first_job.meta.get("progress_info", {})
    existing_results = first_job.meta.get("all_non_kwic_results", existing_results)
    total_requested = cast(
        int,
        kwargs.get("total_results_requested", job_kwargs["total_results_requested"]),
    )
    just_finished = tuple(job_kwargs["current_batch"])

    # if from memory, we had this result cached, we just need to apply filters
    if from_memory:
        all_res = existing_results
        to_send = _apply_filters(all_res, post_processes)
        n_res = stored["total_results_so_far"]
        search_all = stored["search_all"]
        show_total = stored["show_total"]
    # if not cached, we do all the aggregation and filtering of previous+current result
    else:
        all_res, to_send, n_res, search_all, show_total = _aggregate_results(
            result,
            existing_results,
            meta_json,
            post_processes,
            just_finished,
            done_part,
        )
        first_job.meta["all_non_kwic_results"] = all_res

    # right now, when a job has no kwic element, we query all batches and only stop
    # if a time limit is reached. so the progress bar can reflect the amount of time used
    time_perc = 0.0
    if allowed_time > 0.0 and search_all:
        time_perc = total_duration * 100.0 / allowed_time

    total_found = total_before_now + n_res if show_total else -1

    offset_for_next_time = 0
    if total_before_now + n_res > total_requested:
        offset_for_next_time = total_requested - total_before_now

    job.meta["offset_for_next_time"] = offset_for_next_time

    done_part.append(just_finished)
    status = _get_status(
        total_found,
        done_batches=done_part,
        all_batches=job_kwargs["all_batches"],
        total_results_requested=total_requested,
        search_all=search_all,
        full=job_kwargs.get("full", False),
        time_so_far=total_duration,
    )
    job.meta["_status"] = status
    job.meta["results_this_batch"] = n_res
    job.meta["total_results_requested"] = total_requested  # todo: can't this change!?
    job.meta["_search_all"] = search_all
    job.meta["_total_duration"] = total_duration
    job.meta["total_results_so_far"] = total_found

    batches_done_string = f"{len(done_part)}/{len(job_kwargs['all_batches'])}"

    # in these next conditions we basically build the progress information
    # for a query, based on its status and batch metadata.
    if status == "finished":
        projected_results = total_found if show_total else -1
        perc_words = 100.0
        perc_matches = 100.0
        if search_all:
            perc_matches = time_perc
        job.meta["percentage_done"] = 100.0
    elif status in {"partial", "satisfied", "overtime"}:
        done_batches = job_kwargs["done_batches"]
        total_words_processed_so_far = sum([x[-1] for x in done_batches]) or 1
        proportion_that_matches = total_found / total_words_processed_so_far
        projected_results = int(job_kwargs["word_count"] * proportion_that_matches)
        if not show_total:
            projected_results = -1
        perc_words = total_words_processed_so_far * 100.0 / job_kwargs["word_count"]
        perc_matches = min(total_found, total_requested) * 100.0 / total_requested
        if search_all:
            perc_matches = time_perc
        job.meta["percentage_done"] = round(perc_matches, 3)
    if from_memory:
        projected_results = stored["projected_results"]
        perc_matches = stored["percentage_done"]
        perc_words = stored["percentage_words_done"]
        total_found = stored["total_results_so_far"]
        n_res = stored["batch_matches"]
        batches_done_string = stored["batches_done_string"]
        status = stored["status"]
        total_duration = stored["total_duration"]

    progress_info = {
        "projected_results": projected_results,
        "percentage_done": round(perc_matches, 3),
        "percentage_words_done": round(perc_words, 3),
        "total_results_so_far": total_found,
        "batch_matches": n_res,
        "show_total": show_total,
        "search_all": search_all,
        "batches_done_string": batches_done_string,
        "total_duration": total_duration,
        "status": status,
    }

    # so we do not override newer data with older data?
    info: dict[str, str | bool | int | float] = first_job.meta.get("progress_info", {})
    latest_total = cast(int, info.get("total_results_so_far", -1))
    is_latest = not info or total_found > latest_total
    if is_latest:
        first_job.meta["progress_info"] = progress_info

    # can_send controls whether or not the FE gets a message with the stats...
    can_send = _decide_can_send(status, is_full, is_base, from_memory)

    msg_id = str(uuid4())  # todo: hash instead?

    use_cache = os.getenv("USE_CACHE", "true").lower() in TRUES

    # todo: this should no longer happen, as we send a progress update message instead?
    do_full = is_full and status != "finished"
    if do_full:
        can_send = False

    if "latest_stats_message" not in first_job.meta:
        first_job.meta["latest_stats_message"] = msg_id
    if job.meta["total_results_so_far"] >= first_job.meta["total_results_so_far"]:
        first_job.meta["latest_stats_message"] = msg_id

    if "_sent_jobs" not in first_job.meta:
        first_job.meta["_sent_jobs"] = {}
    if "_meta_jobs" not in first_job.meta:
        first_job.meta["_meta_jobs"] = {}

    first_job.save_meta()  # type: ignore

    use = perc_words if search_all or is_full else perc_matches
    time_remaining = _time_remaining(status, total_duration, use)

    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))

    max_kwic = int(os.getenv("DEFAULT_MAX_KWIC_LINES", 9999))
    current_kwic_lines = min(max_kwic, total_found)

    action = "query_result"

    jso = dict(**job_kwargs)
    jso.update(
        {
            "result": to_send,
            "full_result": all_res,
            "user": user,
            "room": room,
            "status": status,
            "job": job.id,
            "action": action,
            "projected_results": projected_results,
            "percentage_done": round(perc_matches, 3),
            "percentage_words_done": round(perc_words, 3),
            "from_memory": from_memory,
            "duration_string": duration_string,
            "total_results_so_far": total_found,
            "table": table,
            "first_job": first_job.id,
            "post_processes": post_processes,
            "search_all": search_all,
            "batches_done": batches_done_string,
            "batch_matches": n_res,
            "full": is_full,
            "can_send": can_send,
            "done_batches": done_part,
            "current_kwic_lines": current_kwic_lines,
            "msg_id": msg_id,
            "resume": False,
            "duration": duration,
            "offset": offset_for_next_time,
            "total_duration": total_duration,
            "remaining": time_remaining,
            "total_results_requested": total_requested,
        }
    )

    if job_kwargs["debug"] and job_kwargs["sql"]:
        jso["sql"] = job_kwargs["sql"]
    if job_kwargs["sql"]:
        jso["consoleSQL"] = job_kwargs["sql"]

    if is_full and status != "finished":
        jso["progress"] = {
            "remaining": time_remaining,
            "first_job": first_job.id,
            "job": job.id,
            "user": user,
            "room": room,
            "duration": duration,
            "batches_done": batches_done_string,
            "total_duration": total_duration,
            "projected_results": projected_results,
            "percentage_done": round(perc_matches, 3),
            "percentage_words_done": round(perc_words, 3),
            "total_results_so_far": total_found,
            "action": "background_job_progress",
        }

    job.meta["payload"] = jso
    job.save_meta()  # type: ignore

    dumped = json.dumps(jso, cls=CustomEncoder)

    # todo: just update progress here, but do not send the rest
    if use_cache and not can_send and False:
        if not connection.get(msg_id):
            connection.set(msg_id, dumped)
        connection.expire(msg_id, MESSAGE_TTL)
        return None

    return _publish_msg(connection, dumped, msg_id)


def _meta(
    job: Job,
    connection: RedisConnection,
    result: list[Any] | None,
    **kwargs: Unpack[SentJob],  # type: ignore
) -> None:
    """
    Process meta data and send via websocket
    """
    if not result:
        return None
    job_kwargs = cast(dict[str, Any], job.kwargs)
    base = Job.fetch(job_kwargs["first_job"], connection=connection)
    depended = _get_associated_query_job(job_kwargs["depends_on"], connection)
    cb: Batch = cast(dict, depended.kwargs)["current_batch"]
    table = f"{cb[1]}.{cb[2]}"

    full = cast(
        bool, kwargs.get("full", job_kwargs.get("full", base.kwargs.get("full", False)))  # type: ignore
    )
    status = depended.meta["_status"]

    to_send = {"-2": format_meta_lines(job_kwargs.get("meta_query", ""), result)}
    if not to_send["-2"]:
        return None

    msg_id = str(uuid4())  # todo: hash instead!
    if "meta_job_ws_messages" not in base.meta:
        base.meta["meta_job_ws_messages"] = {}
    base.meta["meta_job_ws_messages"][msg_id] = None
    base.meta["_meta_jobs"][job.id] = None
    base.save_meta()  # type: ignore

    can_send = not base.meta.get("to_export", False) and (
        not full or status == "finished"
    )

    action = "meta"

    jso = {
        "result": to_send,
        "status": status,
        "action": action,
        "user": kwargs.get("user", job_kwargs["user"]),
        "room": kwargs.get("room", job_kwargs["room"]),
        "query": depended.id,
        "can_send": can_send,
        "full": full,
        "table": table,
        "first_job": base.id,
        "msg_id": msg_id,
    }

    # # todo: just update progress here, but do not send the rest
    dumped = json.dumps(jso, cls=CustomEncoder)

    return _publish_msg(connection, dumped, msg_id)


def _sentences(
    job: Job,
    connection: RedisConnection,
    result: list[RawSent] | None,
    **kwargs: int | bool | str | None,
) -> None:
    """
    Create KWIC data and send via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    total_requested = _get_total_requested(kwargs, job)
    base = Job.fetch(job_kwargs["first_job"], connection=connection)
    depended = _get_associated_query_job(job_kwargs["depends_on"], connection)
    depended_kwargs: dict = cast(dict, depended.kwargs)
    full = cast(bool, kwargs.get("full", job_kwargs.get("full", False)))
    meta_json = depended_kwargs["meta_json"]
    resume = cast(bool, job_kwargs.get("resume", False))
    offset = cast(int, job_kwargs.get("offset", 0) if resume else -1)
    prev_offset = cast(int, depended.meta.get("latest_offset", -1))
    max_kwic = int(os.getenv("DEFAULT_MAX_KWIC_LINES", 9999))
    current_lines = cast(
        int, kwargs.get("current_kwic_lines", job_kwargs["current_kwic_lines"])
    )

    if prev_offset > offset:  # and not kwargs.get("from_memory"):
        offset = prev_offset if resume else -1
    total_to_get = job_kwargs.get("needed", total_requested)

    cb: Batch = depended_kwargs["current_batch"]
    table = f"{cb[1]}.{cb[2]}"

    status = depended.meta["_status"]
    latest_offset = max(offset, 0) + total_to_get
    depended.meta["latest_offset"] = latest_offset
    # base.save_meta, which is called later, overwrites depended.save_meta when pointing to the same job
    if base.id == depended.id:
        base.meta["latest_offset"] = latest_offset

    depended.save_meta()  # type: ignore

    # in full mode, we need to combine all the sentences into one message when finished
    get_all_sents = full and status == "finished"
    to_send: Results

    if full:
        current_lines = 0

    if get_all_sents:
        to_send = _get_all_sents(
            job, base, meta_json, max_kwic, current_lines, full, connection
        )
    else:
        to_send = _format_kwics(
            depended.result,
            meta_json,
            result,
            total_to_get,
            True,
            offset,
            max_kwic,
            current_lines,
            full,
        )

    more_data = not job_kwargs["no_more_data"]
    submit_query = job_kwargs["start_query_from_sents"]
    if submit_query and more_data:
        status = "partial"

    if status == "finished" and more_data:
        more_data = base.meta["total_results_so_far"] >= total_requested

    # if to_send contains only {0: meta, -1: sentences} or less
    if len(to_send) < 3 and not submit_query:
        print(f"No results found for {table} kwic -- skipping WS message")
        return None

    # if we previously sent a warning about there being too much data, stop here
    if base.meta.get("been_warned"):
        print("Processed too much data -- skipping WS message")
        return None

    use_cache = os.getenv("USE_CACHE", "true").lower() in TRUES

    if not use_cache:
        perc_done = depended.meta["payload"]["percentage_done"]
        words_done = depended.meta["payload"]["percentage_words_done"]
    else:
        perc_done = base.meta["progress_info"]["percentage_done"]
        words_done = base.meta["progress_info"]["percentage_words_done"]

    submit_payload = depended.meta["payload"]
    submit_payload["full"] = full
    submit_payload["total_results_requested"] = total_requested
    submit_payload["to_export"] = depended.meta.get("to_export", {})

    # Do not send if this is an "export" query
    can_send = not base.meta.get("to_export", False) and (
        not full or status == "finished"
    )

    msg_id = str(uuid4())  # todo: hash instead!
    if "sent_job_ws_messages" not in base.meta:
        base.meta["sent_job_ws_messages"] = {}
    base.meta["sent_job_ws_messages"][msg_id] = None
    base.meta["_sent_jobs"][job.id] = None
    base.save_meta()  # type: ignore

    action = "sentences"

    jso = {
        "result": to_send,
        "status": status,
        "action": action,
        "full": full,
        "more_data_available": more_data,
        "submit_query": submit_payload if submit_query else False,
        "user": kwargs.get("user", cast(dict, job.kwargs)["user"]),
        "room": kwargs.get("room", cast(dict, job.kwargs)["room"]),
        "query": depended.id,
        "table": table,
        "first_job": base.id,
        "msg_id": msg_id,
        "can_send": can_send,
        "percentage_done": perc_done,
        "percentage_words_done": words_done,
    }

    # todo: just update progress here, but do not send the rest
    dumped = json.dumps(jso, cls=CustomEncoder)

    # if use_cache and not can_send:
    #     if not connection.get(msg_id):
    #         connection.set(msg_id, dumped)
    #     connection.expire(msg_id, MESSAGE_TTL)
    #     print("not returning sentences because searching whole corpus")
    #     return

    job.save_meta()  # type: ignore

    return _publish_msg(connection, dumped, msg_id)


def _document(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[BaseArgs],
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    action = "document"
    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))
    if not room:
        return
    if isinstance(result, list) and len(result) == 1:
        result = result[0]

    tmp_result: dict[str, dict] = {
        "structure": {},
        "layers": {},
        "global_attributes": {},
    }
    for row in result:
        typ, key, props = cast(list, row)
        if typ == "layer":
            if key not in tmp_result["structure"]:
                tmp_result["structure"][key] = [*props.keys()]
            if key not in tmp_result["layers"]:
                tmp_result["layers"][key] = []
            keys = tmp_result["structure"][key]
            line = [props[k] for k in keys]
            tmp_result["layers"][key].append(line)
        elif typ == "glob":
            if key not in tmp_result["global_attributes"]:
                tmp_result["global_attributes"][key] = []
            tmp_result["global_attributes"][key].append(props)
        elif typ == "doc":
            tmp_result["doc"] = props
    result = cast(JSONObject, tmp_result)

    msg_id = str(uuid4())
    jso = {
        "document": result,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
        "corpus": job_kwargs["corpus"],
        "doc_id": job_kwargs["doc"],
    }
    return _publish_msg(connection, jso, msg_id)


def _document_ids(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[DocIDArgs],
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))
    if not room:
        return None
    msg_id = str(uuid4())
    formatted = {
        str(idx): {
            "name": name,
            "media": media,
            "frame_range": (
                [frame_range.lower, frame_range.upper] if frame_range else [0, 0]
            ),
        }
        for idx, name, media, frame_range in cast(
            list[tuple[int, str, dict, Any]], result
        )
    }
    action = "document_ids"
    jso = {
        "document_ids": formatted,
        "action": action,
        "user": user,
        "msg_id": msg_id,
        "room": room,
        "job": job.id,
        "corpus_id": job_kwargs["corpus_id"],
    }
    return _publish_msg(connection, jso, msg_id)


def _schema(
    job: Job,
    connection: RedisConnection,
    result: bool | None = None,
) -> None:
    """
    This callback is executed after successful creation of schema.
    We might want to notify some WS user?
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    user = job_kwargs.get("user")
    room = job_kwargs.get("room")
    if not room:
        return None
    msg_id = str(uuid4())
    action = "uploaded"
    jso = {
        "user": user,
        "status": "success" if not result else "error",
        "project": job_kwargs["project"],
        "project_name": job_kwargs["project_name"],
        "corpus_name": job_kwargs["corpus_name"],
        "action": action,
        "gui": job_kwargs.get("gui", False),
        "room": room,
        "msg_id": msg_id,
    }
    if result:
        jso["error"] = result

    return _publish_msg(connection, jso, msg_id)


def _upload(
    job: Job,
    connection: RedisConnection,
    result: MainCorpus | None,
) -> None:
    """
    Success callback when user has uploaded a dataset
    """
    if result is None:
        print("Result was none. Skipping callback.")
        return None
    project: str = job.args[0]
    user: str = job.args[1]
    room: str | None = job.args[2]
    job_kwargs: dict = cast(dict, job.kwargs)
    user_data: JSONObject = job_kwargs["user_data"]
    gui: bool = job_kwargs["gui"]
    msg_id = str(uuid4())
    action = "uploaded"

    # if not room or not result:
    #     return None
    jso = {
        "user": user,
        "room": room,
        "id": result[0],
        "user_data": user_data,
        "entry": _row_to_value(result, project=project),
        "status": "success" if not result else "error",
        "project": project,
        "action": action,
        "gui": gui,
        "msg_id": msg_id,
    }

    # We want to notify *all* the instances of the new corpus
    return _sharepublish_msg(cast(JSONObject, jso), msg_id)
    # return _publish_msg(connection, cast(JSONObject, jso), msg_id)


def _upload_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    """
    Cleanup on upload fail, and maybe send ws message
    """
    print(f"Upload failure: {typ} : {value}: {traceback}")
    msg_id = str(uuid4())

    project: str
    user: str
    room: str | None

    job_kwargs: dict = cast(dict, job.kwargs)

    if "project_name" in job_kwargs:  # it came from create schema job
        project = job_kwargs["project"]
        user = job_kwargs["user"]
        room = job_kwargs["room"]
    else:  # it came from upload job
        project = job.args[0]
        user = job.args[1]
        room = job.args[2]

    uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
    path = os.path.join(uploads_path, project)
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")

    form_error = str(trace)

    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    action = "upload_fail"

    if user and room:
        jso = {
            "user": user,
            "room": room,
            "project": project,
            "action": action,
            "status": "failed",
            "job": job.id,
            "msg_id": msg_id,
            "traceback": form_error,
            "kind": str(typ),
            "value": str(value),
        }
        return _publish_msg(connection, jso, msg_id)


def _general_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    """
    On job failure, return some info ... probably hide some of this from prod eventually!
    """
    msg_id = str(uuid4())
    form_error = str(trace)
    action = "failed"
    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    print("Failure of some kind:", job, trace, typ, value)
    if isinstance(typ, Interrupted) or typ == Interrupted:
        # no need to send a message to the user for interrupts
        # jso = {"status": "interrupted", "action": "interrupted", "job": job.id}
        return None
    else:
        jso = {
            "status": "failed",
            "kind": str(typ),
            "value": str(value),
            "action": action,
            "msg_id": msg_id,
            "traceback": form_error,
            "job": job.id,
            **cast(dict, job.kwargs),
        }
    # this is just for consistency with the other timeout messages
    if "No such job" in jso["value"]:
        jso["status"] = "timeout"
        jso["action"] = "timeout"

    return _publish_msg(connection, jso, msg_id)


def _queries(
    job: Job,
    connection: RedisConnection,
    result: list[UserQuery] | None,
) -> None:
    """
    Fetch or store queries
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    is_store: bool = job_kwargs.get("store", False)
    action = "store_query" if is_store else "fetch_queries"
    room: str | None = job_kwargs.get("room")
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": str(job_kwargs["user"]),
        "room": room,
        "status": "success",
        "action": action,
        "queries": [],
        "msg_id": msg_id,
    }
    if is_store:
        jso["query_id"] = str(job_kwargs["query_id"])
        jso.pop("queries")
    elif result:
        cols = ["idx", "query", "username", "room", "created_at"]
        queries: list[dict[str, Any]] = []
        for x in result:
            dct: dict[str, Any] = dict(zip(cols, x))
            queries.append(dct)
        jso["queries"] = queries
    return _publish_msg(connection, jso, msg_id)


def _export_complete(
    job: Job,
    connection: RedisConnection,
    result: list[UserQuery] | None,
) -> None:
    print("export complete!")
    if job.args and isinstance(job.args[0], str) and os.path.exists(job.args[0]):
        j_kwargs: dict = cast(dict, job.kwargs)
        dep_kwargs: dict = cast(dict, job.dependency.kwargs) if job.dependency else {}
        user = j_kwargs.get("user", dep_kwargs.get("user", ""))
        room = j_kwargs.get("room", dep_kwargs.get("room", ""))
        if user and room and cast(dict, job.kwargs).get("download", False):
            msg_id = str(uuid4())
            jso: dict[str, Any] = {
                "user": user,
                "room": room,
                "action": "export_link",
                "msg_id": msg_id,
                "fn": os.path.basename(job.args[0]),
            }
            _publish_msg(connection, jso, msg_id)
    return None


def _config(
    job: Job,
    connection: RedisConnection,
    result: list[MainCorpus],
    publish: bool = True,
) -> dict[str, str | bool | Config]:
    """
    Run by worker: make config data
    """
    action = "set_config"
    fixed: Config = {}
    msg_id = str(uuid4())
    for tup in result:
        made = _row_to_value(tup)
        if not made.get("enabled"):
            continue
        fixed[str(made["corpus_id"])] = made

    for conf in fixed.values():
        if "_batches" not in conf:
            conf["_batches"] = _get_batches(conf)

    jso: dict[str, str | bool | Config] = {
        "config": fixed,
        "_is_config": True,
        "action": action,
        "msg_id": msg_id,
    }
    if publish:
        _publish_msg(connection, cast(JSONObject, jso), msg_id)
    return jso

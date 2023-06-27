from __future__ import annotations

import json
import os
import shutil
import traceback

from types import TracebackType
from typing import Any, Unpack, cast

from redis import Redis as RedisConnection
from rq.job import Job

from .configure import _get_batches
from .typed import (
    MainCorpus,
    JSONObject,
    UserQuery,
    RawSent,
    Config,
    QueryArgs,
    Results,
    Batch,
    QueryMeta,
)
from .utils import (
    CustomEncoder,
    Interrupted,
    _get_status,
    # _union_results,
    _row_to_value,
    # _apply_filters,
    # _trim_bundle,
    _aggregate_results,
    _format_kwics,
    # _get_kwics,
    PUBSUB_CHANNEL,
)
from .worker import SQLJob


def _query(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: list[tuple],
    **kwargs: Unpack[QueryArgs],  # type: ignore
) -> None:
    """
    Job callback, publishes a redis message containing the results

    This is where we need to aggregate statistics over all jobs in the group
    """
    meta_json: QueryMeta = job.kwargs.get("meta_json")
    existing_results: Results = {0: meta_json}
    # if this job is non-first, we need to store its id on the original
    if job.kwargs.get("first_job"):
        first_job = Job.fetch(job.kwargs["first_job"], connection=connection)
        # group = set(first_job.meta.get("group", set()))
        # group.add(job.id)
        # first_job.meta["group"] = group
        existing_results = first_job.meta["all_non_kwic_results"]
    else:
        first_job = job

    total_requested = kwargs.get(
        "total_results_requested", job.kwargs["total_results_requested"]
    )

    post_processes = job.kwargs.get("post_processes", {})

    all_results, results_to_send, n_results = _aggregate_results(
        result, existing_results, meta_json, post_processes, total_requested
    )

    first_job.meta["all_non_kwic_results"] = all_results
    first_job.save_meta()
    from_memory = kwargs.get("from_memory", False)
    total_before_now = job.kwargs.get("total_results_so_far")
    done_part = job.kwargs["done_batches"]
    total_found = total_before_now + n_results
    just_finished = tuple(job.kwargs["current_batch"])
    done_part.append(just_finished)
    status = _get_status(total_found, tot_req=total_requested, **job.kwargs)
    job.meta["_status"] = status
    job.meta["total_results_so_far"] = total_found
    table = f"{job.kwargs['current_batch'][1]}.{job.kwargs['current_batch'][2]}"
    first_job = job.kwargs["first_job"] or job.id

    if status == "finished":
        projected_results = total_found
        perc_words = 100.0
        perc_matches = 100.0
        job.meta["percentage_done"] = 100.0
    elif status in {"partial", "satisfied"}:
        done_batches = job.kwargs["done_batches"]
        total_words_processed_so_far = sum([x[-1] for x in done_batches])
        proportion_that_matches = total_found / total_words_processed_so_far
        projected_results = int(job.kwargs["word_count"] * proportion_that_matches)
        perc_words = total_words_processed_so_far * 100.0 / job.kwargs["word_count"]
        perc_matches = min(total_found, total_requested) * 100.0 / total_requested
        job.meta["percentage_done"] = round(perc_matches, 3)

    job.save_meta()  # type: ignore
    jso = dict(**job.kwargs)
    jso.update(
        {
            "result": results_to_send,
            "full_result": all_results,
            "status": status,
            "job": job.id,
            "action": "query_result",
            "projected_results": projected_results,
            "percentage_done": round(perc_matches, 3),
            "percentage_words_done": round(perc_words, 3),
            "from_memory": from_memory,
            "total_results_so_far": total_found,
            "table": table,
            "first_job": first_job,
            "batch_matches": n_results,
            "done_batches": done_part,
            "sentences": job.kwargs["sentences"],
            "total_results_requested": total_requested,
        }
    )
    jso["user"] = kwargs.get("user", jso["user"])
    jso["room"] = kwargs.get("room", jso["room"])

    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))


def _sentences(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: list[RawSent],
    **kwargs: int | bool | str | None,
) -> None:
    """
    Create KWIC data and send via websocket
    """
    total_requested = cast(int | None, kwargs.get("total_results_requested"))

    base = Job.fetch(job.kwargs["first_job"], connection=connection)

    depends_on = job.kwargs["depends_on"]
    if isinstance(depends_on, list):
        depends_on = depends_on[-1]

    depended = Job.fetch(depends_on, connection=connection)
    meta_json = depended.kwargs["meta_json"]
    to_send = _format_kwics(depended.result, meta_json, result, total_requested)
    cb: Batch = depended.kwargs["current_batch"]
    table = f"{cb[1]}.{cb[2]}"

    jso = {
        "result": to_send,
        "status": depended.meta["_status"],
        "action": "sentences",
        "user": kwargs.get("user", job.kwargs["user"]),
        "room": kwargs.get("room", job.kwargs["room"]),
        "query": depended.id,
        "table": table,
        "first_job": base.id,
        "percentage_done": round(depended.meta["percentage_done"], 3),
    }

    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))


def _document(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: list[JSONObject] | JSONObject,
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    user = job.kwargs["user"]
    room = job.kwargs["room"]
    if not room:
        return
    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    jso = {
        "document": result,
        "action": "document",
        "user": user,
        "room": room,
        "corpus": job.kwargs["corpus"],
        "doc_id": job.kwargs["doc"],
    }
    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))
    return None


def _document_ids(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: list[JSONObject] | JSONObject,
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    user = job.kwargs["user"]
    room = job.kwargs["room"]
    if not room:
        return
    formatted = {str(idx): name for idx, name in cast(list[tuple], result)}
    jso = {
        "document_ids": formatted,
        "action": "document_ids",
        "user": user,
        "room": room,
        "job": job.id,
        "corpus_id": job.kwargs["corpus_id"],
    }
    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))
    return None


def _schema(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: bool | None = None,
) -> None:
    """
    This callback is executed after successful creation of schema.
    We might want to notify some WS user?
    """
    user = job.kwargs.get("user")
    room = job.kwargs.get("room")
    if not room:
        return
    jso = {
        "user": user,
        "status": "success" if not result else "error",
        "project": job.kwargs["project"],
        "project_name": job.kwargs["project_name"],
        "action": "uploaded",
        "gui": job.kwargs.get("gui", False),
        "room": room,
    }
    if result:
        jso["error"] = result

    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))


def _upload(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
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
    user_data: JSONObject = job.kwargs["user_data"]
    is_vian: bool = job.kwargs["is_vian"]
    gui: bool = job.kwargs["gui"]

    if not room or not result:
        return
    jso = {
        "user": user,
        "room": room,
        "id": result[0],
        "user_data": user_data,
        "is_vian": is_vian,
        "entry": _row_to_value(result, project=project),
        "status": "success" if not result else "error",
        "project": project,
        "action": "uploaded",
        "gui": gui,
    }
    if result:
        jso["error"] = result

    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))


def _upload_failure(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    typ: type,
    value: BaseException,
    trace: Any,
) -> None:
    """
    Cleanup on upload fail, and maybe send ws message
    """
    print(f"Upload failure: {typ} : {value}: {traceback}")

    project: str
    user: str
    room: str | None

    if "project_name" in job.kwargs:  # it came from create schema job
        project = job.kwargs["project"]
        user = job.kwargs["user"]
        room = job.kwargs["room"]
    else:  # it came from upload job
        project = job.args[0]
        user = job.args[1]
        room = job.args[2]

    path = os.path.join("uploads", project)
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")

    form_error: str = str(trace)

    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    if user and room:
        jso = {
            "user": user,
            "room": room,
            "project": project,
            "action": "upload_fail",
            "status": "failed",
            "job": job.id,
            "traceback": form_error,
            "kind": str(typ),
            "value": str(value),
        }
        red = job._redis if hasattr(job, "_redis") else connection
        red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))
    return None


def _general_failure(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    """
    On job failure, return some info ... probably hide some of this from prod eventually!
    """
    form_error: str = str(trace)
    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    print("Failure of some kind:", job, trace, typ, value)
    if isinstance(typ, Interrupted) or typ == Interrupted:
        # no need to send a message to the user for interrupts
        # jso = {"status": "interrupted", "action": "interrupted", "job": job.id}
        return
    else:
        jso = {
            "status": "failed",
            "kind": str(typ),
            "value": str(value),
            "action": "failed",
            "traceback": form_error,
            "job": job.id,
            **job.kwargs,
        }
    # this is just for consistency with the other timeout messages
    if "No such job" in jso["value"]:
        jso["status"] = "timeout"
        jso["action"] = "timeout"

    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))


def _queries(
    job: SQLJob | Job,
    connection: RedisConnection[bytes],
    result: list[UserQuery] | None,
) -> None:
    """
    Fetch or store queries
    """
    is_store: bool = job.kwargs.get("store", False)
    action = "store_query" if is_store else "fetch_queries"
    room: str | None = job.kwargs.get("room")
    jso: dict[str, Any] = {
        "user": str(job.kwargs["user"]),
        "room": room,
        "status": "success",
        "action": action,
        "queries": [],
    }
    if is_store:
        jso["query_id"] = str(job.kwargs["query_id"])
        jso.pop("queries")
    elif result:
        cols = ["idx", "query", "username", "room", "created_at"]
        queries: list[dict[str, Any]] = []
        for x in result:
            dct: dict[str, Any] = dict(zip(cols, x))
            queries.append(dct)
        jso["queries"] = queries
    made = json.dumps(jso, cls=CustomEncoder)
    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, made)


def _config(
    job: SQLJob | Job, connection: RedisConnection[bytes], result: list[MainCorpus]
) -> None:
    """
    Run by worker: make config data
    """
    fixed: Config = {}
    for tup in result:
        made = _row_to_value(tup)
        if not made["enabled"]:
            continue
        fixed[str(made["corpus_id"])] = made

    for name, conf in fixed.items():
        if "_batches" not in conf:
            conf["_batches"] = _get_batches(conf)

    jso: dict[str, str | bool | Config] = {
        "config": fixed,
        "_is_config": True,
        "action": "set_config",
    }
    red = job._redis if hasattr(job, "_redis") else connection
    red.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))
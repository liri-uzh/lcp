"""
callbacks.py: post-process the result of an SQL query and broadcast
it to the relevant websockets

These jobs are usually run in the worker process, but in exceptional
circumstances, they are run in the main thread, like when fetching
jobs that were run earlier

These callbacks are hooked up as on_success and on_failure kwargs in
calls to Queue.enqueue in query_service.py
"""

import duckdb
import json
import os
import pandas
import shutil
import tempfile
import traceback


from datetime import datetime
from types import TracebackType
from typing import Any, Unpack, cast
from uuid import uuid4


from redis.asyncio import Redis as RedisConnection

# TODO(ARQ_MIGRATION): Replace rq.job.Job with Arq equivalent
from arq.jobs import Job

from .configure import _get_batches
from .typed import (
    BaseArgs,
    Config,
    DocIDArgs,
    JSONObject,
    MainCorpus,
    UserQuery,
)
from .utils import (
    Interrupted,
    _row_to_value,
    _publish_msg,
    _sharepublish_msg,
)

PUBSUB_LIMIT = int(os.getenv("PUBSUB_LIMIT", 31999999))
MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


def _schema(
    job: Job,
    connection: RedisConnection,
    result: bool | None = None,
) -> None:
    """
    This callback is executed after successful creation of schema.
    We might want to notify some WS user?
    """
    # TODO(ARQ_MIGRATION): job.kwargs may need to be accessed differently in Arq
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


def _inserted(
    job: Job,
    connection: RedisConnection,
    result: MainCorpus | None,
) -> None:
    """
    Success callback when user has inserted a dataset into the database
    """
    if result is None:
        print("Result was none. Skipping callback.")
        return None
    # TODO(ARQ_MIGRATION): job.args may need to be accessed differently in Arq
    project: str = job.args[0]
    user: str = job.args[1]
    room: str | None = job.args[2]
    # TODO(ARQ_MIGRATION): job.kwargs may need to be accessed differently in Arq
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

    # TODO(ARQ_MIGRATION): job.kwargs may need to be accessed differently in Arq
    job_kwargs: dict = cast(dict, job.kwargs)

    if "project_name" in job_kwargs:  # it came from create schema job
        project = job_kwargs["project"]
        user = job_kwargs["user"]
        room = job_kwargs["room"]
    else:  # it came from upload job
        # TODO(ARQ_MIGRATION): job.args may need to be accessed differently in Arq
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


async def _general_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType | None,
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
        # jso = {"status": "interrupted", "action": "interrupted", "job": job.job_id}
        return None
    else:
        # TODO(ARQ_MIGRATION): job.id and job.kwargs may need to be accessed differently in Arq
        jso = {
            "status": "failed",
            "kind": str(typ),
            "value": str(value),
            "action": action,
            "msg_id": msg_id,
            "traceback": form_error,
            "job": job.job_id,
            **cast(dict, job.kwargs),
        }
    # this is just for consistency with the other timeout messages
    if "No such job" in jso["value"]:
        jso["status"] = "timeout"
        jso["action"] = "timeout"

    await _publish_msg(connection, jso, msg_id)


def _queries(
    job: Job,
    connection: RedisConnection,
    result: list[UserQuery] | None,
) -> None:
    """
    Fetch or store queries
    """
    # TODO(ARQ_MIGRATION): job.kwargs may need to be accessed differently in Arq
    job_kwargs: dict = cast(dict, job.kwargs)
    is_store: bool = job_kwargs.get("store", False)
    is_delete: bool = job_kwargs.get("delete", False)

    action = "fetch_queries"

    if is_store:
        action = "store_query"
    elif is_delete:
        action = "delete_query"

    # action = "store_query" if is_store else "fetch_queries"

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
    elif is_delete:
        jso.pop("queries")
    elif result:
        cols = ["idx", "query", "username", "room", "created_at"]
        queries: list[dict[str, Any]] = []
        for x in result:
            dct: dict[str, Any] = dict(zip(cols, x))
            queries.append(dct)
        jso["queries"] = json.dumps(queries, default=str)

    return _publish_msg(connection, jso, msg_id)


def _deleted(job: Job, connection: RedisConnection, result: Any) -> None:
    """
    Callback for successful deletion.
    """
    # TODO(ARQ_MIGRATION): job.kwargs may need to be accessed differently in Arq
    job_kwargs: dict = cast(dict, job.kwargs)
    action = "delete_query"
    room: str = job_kwargs.get("room") or ""
    # Since DELETE without RETURNING doesn't provide row data, we use the original query_id.
    deleted_idx = job_kwargs.get("idx")
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": str(job_kwargs["user"]),
        "room": room,
        "idx": deleted_idx,
        "status": "success",
        "action": action,
        "msg_id": msg_id,
        "queries": "[]",
    }

    return _publish_msg(connection, jso, msg_id)


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
    # TODO(ARQ_MIGRATION): job.result may need to be accessed differently in Arq
    for tup in result:
        made = _row_to_value(tup)
        # if not made.get("enabled"):
        #     continue
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
    if publish:  # refresh the config for all instances
        _sharepublish_msg(cast(JSONObject, jso), msg_id)
        # _publish_msg(connection, cast(JSONObject, jso), msg_id)
    return jso

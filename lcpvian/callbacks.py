"""
callbacks.py: post-process the result of an SQL query and broadcast
it to the relevant websockets

These jobs are usually run in the worker process, but in exceptional
circumstances, they are run in the main thread, like when fetching
jobs that were run earlier

These callbacks are hooked up as on_success and on_failure kwargs in
calls to Queue.enqueue in query_service.py
"""

import os
import traceback


from types import TracebackType
from typing import cast
from uuid import uuid4


from redis.asyncio import Redis as RedisConnection

# TODO(ARQ_MIGRATION): Replace rq.job.Job with Arq equivalent
from arq.jobs import Job

from .utils import (
    Interrupted,
    _publish_msg,
)
from .redis import get_job_kwargs

PUBSUB_LIMIT = int(os.getenv("PUBSUB_LIMIT", 31999999))
MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


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
        job_kwargs = await get_job_kwargs(job)
        jso = {
            "status": "failed",
            "kind": str(typ),
            "value": str(value),
            "action": action,
            "msg_id": msg_id,
            "traceback": form_error,
            "job": job.job_id,
            **job_kwargs,
        }
    # this is just for consistency with the other timeout messages
    if "No such job" in jso["value"]:
        jso["status"] = "timeout"
        jso["action"] = "timeout"

    await _publish_msg(connection, jso, msg_id)

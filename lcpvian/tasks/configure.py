"""
Async tasks called from configure.py
"""

from arq.jobs import Job, ResultNotFound
from typing import cast
from uuid import uuid4

from ..jobfuncs import _db_query
from ..typed import JSONObject
from ..utils import (
    Config,
    _format_config_query,
    _row_to_value,
    _sharepublish_msg,
    _get_batches,
)


async def get_config(ctx, force_refresh: bool = False, publish: bool = True):
    """
    Get initial app configuration JSON
    """
    job_id = "app_config"

    query = _format_config_query(
        "SELECT {selects} FROM main.corpus mc {join}"  # WHERE mc.enabled = true;"
    )

    redis = ctx["redis"]
    try:
        assert not force_refresh, ResultNotFound()
        job = Job(job_id, redis=redis)
        result = await job.result()
        print("Loading config from redis (flush redis if new corpora added)")
    except ResultNotFound:
        result = await _db_query(ctx, query, {}, is_main=True)

    action = "set_config"
    fixed: Config = {}
    msg_id = str(uuid4())
    # TODO(ARQ_MIGRATION): job.result may need to be accessed differently in Arq
    for tup in cast(list, result):
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
        await _sharepublish_msg(cast(JSONObject, jso), msg_id)
        # _publish_msg(connection, cast(JSONObject, jso), msg_id)

    return jso

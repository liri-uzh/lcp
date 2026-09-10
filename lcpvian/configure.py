"""
Model the various parts of the corpus template/corpus config

Code for generating batches is also in here
"""

from aiohttp import web
from arq.jobs import Job, ResultNotFound
from typing import cast
from uuid import uuid4

from .jobfuncs import _db_query
from .typed import CorpusConfig, JSONObject
from .utils import (
    Config,
    _format_config_query,
    _row_to_value,
    _sharepublish_msg,
    ensure_authorised,
)

from .worker import arq_task, ctx


def _generate_batches(n_batches: int, basename: str, size: int) -> dict[str, int]:
    """
    We can create batchnames if we know three things:

    total number of batches
    the prefix of the table name
    the total size of the corpus
    """
    batches: dict[str, int] = {}
    if n_batches < 2:
        named = basename.replace("<batch>", "") + "0"
        return {named: size}
    for i in range(1, n_batches):
        if i + 1 == n_batches and n_batches > 1:
            name = "rest"
        else:
            name = str(i)
        batch = basename.replace("<batch>", name)
        size = int(size / 2 if name != "rest" else size)
        batches[batch] = int(size)
    return batches


def _get_batches(config: CorpusConfig) -> dict[str, int]:
    """
    Get a dict of batch_name: size for a given corpus
    """
    batches: dict[str, int] = {}
    counts: dict[str, int] = config.get("token_counts", {})
    try:
        mapping = (
            config.get("mapping", {}).get("layer", {}).get(config.get("token", ""))
        )
    except (KeyError, TypeError):
        return counts
    if not mapping:
        return counts
    if "partitions" in mapping:
        for lang, details in mapping["partitions"].items():
            basename = details["relation"]
            if "<language>" in basename:
                basename = basename.replace("<language>", lang)
            count_key = basename.replace("<batch>", "0").lower()
            size = next(v for k, v in counts.items() if k.lower() == count_key)
            n_batches = details["batches"]
            more = _generate_batches(n_batches, basename, size)
            batches.update(more)
    else:
        n_batches = mapping["batches"]
        name = mapping["relation"]
        count_key = name.replace("<batch>", "0").lower()
        try:
            size = next(v for k, v in counts.items() if k.lower() == count_key)
        except:
            size = sum(v for v in counts.values())
        more = _generate_batches(n_batches, name, size)
        batches.update(more)
    if not batches:
        return counts
    return batches


@arq_task("internal")
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


@ensure_authorised
async def refresh_config(request: web.Request) -> web.Response:
    """
    Force a refresh of the config via the /config endpoint
    """
    job: Job | None = await get_config(ctx, force_refresh=True)
    return web.json_response({"job": str("" if job is None else job.job_id)})

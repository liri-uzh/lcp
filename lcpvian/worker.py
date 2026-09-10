#!/usr/bin/env python3

"""
custom Arq worker for lcpvian: initialise db connection pools
and store them on the custom job class.

This allows us to submit queries to the db pool without
restarting/recreating the pools each time.

This worker should be started with `python -m lcpvian worker`.

If app is compiled to C, this will use the C code. Otherwise
it will use straight Python.

`python lcpvian/worker.py` forces the use of the Python version.

We can start as many workers as we want, depending on available
resources on the deployment server.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import urllib.parse

from types import CoroutineType
from typing import Any, Callable

import uvloop

from arq import create_pool, Worker
from arq.jobs import Job
from arq.connections import RedisSettings
from redis import Redis
from redis.backoff import ConstantBackoff
from redis.exceptions import ConnectionError
from redis.retry import Retry

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from sshtunnel import SSHTunnelForwarder

from .utils import load_env, get_redis_sleep_time

load_env()


SENTRY_DSN = os.getenv("SENTRY_DSN", None)

if SENTRY_DSN:
    import sentry_sdk

    # TODO(ARQ_MIGRATION): Replace sentry_sdk.integrations.rq.RqIntegration with Arq equivalent
    # from sentry_sdk.integrations.rq import RqIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.WARNING,
    )

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # TODO(ARQ_MIGRATION): Replace RqIntegration with Arq equivalent
        integrations=[
            sentry_logging
        ],  # TODO(ARQ_MIGRATION): Add Arq integration if available
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 1.0)),
        environment=os.getenv("SENTRY_ENVIRONMENT", "lcp"),
    )


UPLOAD_USER = urllib.parse.quote(os.environ["SQL_UPLOAD_USERNAME"])
QUERY_USER = urllib.parse.quote(os.environ["SQL_QUERY_USERNAME"])
WEB_USER = urllib.parse.quote(os.environ["SQL_WEB_USERNAME"])
UPLOAD_PASSWORD = urllib.parse.quote(os.environ["SQL_UPLOAD_PASSWORD"])
QUERY_PASSWORD = urllib.parse.quote(os.environ["SQL_QUERY_PASSWORD"])
WEB_PASSWORD = urllib.parse.quote(os.environ["SQL_WEB_PASSWORD"])
HOST = os.environ["SQL_HOST"]
DBNAME = os.environ["SQL_DATABASE"]
_UPLOAD_POOL = os.getenv("UPLOAD_USE_POOL", "false")
UPLOAD_POOL = _UPLOAD_POOL.strip().lower() not in ("false", "no", "0", "")
MAX_CONCURRENT = int(os.getenv("IMPORT_MAX_CONCURRENT", 1))

QUERY_MIN_NUM_CONNS = int(os.getenv("QUERY_MIN_NUM_CONNECTIONS", 8))
UPLOAD_MIN_NUM_CONNS = int(os.getenv("UPLOAD_MIN_NUM_CONNECTIONS", 8))
UPLOAD_MIN_NUM_CONNS = max(UPLOAD_MIN_NUM_CONNS, MAX_CONCURRENT) if UPLOAD_POOL else 0
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", 1000))

QUERY_MAX_NUM_CONNS = int(os.getenv("QUERY_MAX_NUM_CONNECTIONS", 8))
UPLOAD_MAX_NUM_CONNS = int(os.getenv("UPLOAD_MAX_NUM_CONNECTIONS", 8))
UPLOAD_MAX_NUM_CONNS = max(UPLOAD_MAX_NUM_CONNS, MAX_CONCURRENT) if UPLOAD_POOL else 0
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", 43200))

PORT = int(os.getenv("SQL_PORT", 25432))

REDIS_DB_INDEX = int(os.getenv("REDIS_DB_INDEX", 0))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_url: str = f"{REDIS_URL}/{REDIS_DB_INDEX}" if REDIS_DB_INDEX > -1 else REDIS_URL
redis_conn = RedisSettings.from_dsn(redis_url)
sync_redis: None | Redis = None

tunnel: SSHTunnelForwarder
if os.getenv("SSH_HOST"):
    tunnel = SSHTunnelForwarder(
        os.environ["SSH_HOST"],
        ssh_username=os.environ["SSH_USER"],
        ssh_password=None,
        ssh_pkey=os.environ["SSH_PKEY"],
        remote_bind_address=(HOST, PORT),
    )
    tunnel.start()
    HOST = "localhost"
    PORT = tunnel.local_bind_port


upload_connstr = (
    f"postgresql+asyncpg://{UPLOAD_USER}:{UPLOAD_PASSWORD}@{HOST}:{PORT}/{DBNAME}"
)
query_connstr = (
    f"postgresql+asyncpg://{QUERY_USER}:{QUERY_PASSWORD}@{HOST}:{PORT}/{DBNAME}"
)
web_connstr = f"postgresql+asyncpg://{WEB_USER}:{WEB_PASSWORD}@{HOST}:{PORT}/{DBNAME}"


query_kwargs = dict(
    pool_size=QUERY_MAX_NUM_CONNS,
    connect_args={
        "timeout": QUERY_TIMEOUT,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {"jit": "off"},
    },
    echo_pool=True,
    pool_recycle=3600,
    pool_timeout=3600,
    pool_pre_ping=True,
)
upload_kwargs = dict(
    pool_size=UPLOAD_MAX_NUM_CONNS,
    connect_args={
        "timeout": UPLOAD_TIMEOUT,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "server_settings": {"jit": "off"},
    },
    echo_pool=True,
    pool_recycle=3600,
    pool_timeout=3600,
    pool_pre_ping=True,
    isolation_level="READ COMMITTED",
)
if not UPLOAD_POOL:
    upload_kwargs["pool_class"] = NullPool  # type: ignore


# Arq requires registering callables, so we use a decorator to store them in _functions
_functions = []
ctx = None  # placeholder for calling decorated tasks


def get_sync_redis():
    global redis_url
    sleep_time = get_redis_sleep_time(redis_url)
    retry_policy: Retry = Retry(ConstantBackoff(sleep_time), 3)
    return Redis.from_url(
        redis_url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=retry_policy,
    )


async def get_redis():
    global redis_conn
    return await create_pool(redis_conn)


async def get_job_kwargs(job: Job) -> dict:
    return {}


async def set_job_kwargs(job: Job, kwargs: dict):
    return {}


async def get_job_meta(job: Job) -> dict:
    return {}


async def set_job_meta(job: Job, meta: dict):
    return {}


def arq_task(queue: str = "query"):
    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., CoroutineType[Any, Any, Job | None]]:
        func_name = f"{func.__module__}.{func.__qualname__}"
        _functions.append(func)

        # wrap so as to keep the function's name all the way through
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Job | None:
            redis = await get_redis()
            job_id = kwargs.pop("job_id", None) or None
            arq_queue = kwargs.pop("arq_queue", queue) or queue
            job = await redis.enqueue_job(
                func_name, *args, **kwargs, _queue_name=arq_queue, _job_id=job_id
            )
            return job

        return wrapper

    return decorator


async def on_startup(ctx: dict) -> None:
    ctx["_pool"] = create_async_engine(query_connstr, **query_kwargs)
    ctx["_upool"] = create_async_engine(upload_connstr, **upload_kwargs)
    ctx["_wpool"] = create_async_engine(web_connstr, **upload_kwargs)


async def on_shutdown(ctx: dict) -> None:
    ctx["_pool"].dispose()
    ctx["_upool"].dispose()
    ctx["_wpool"].dispose()


async def work(queue: str = "internal"):
    global _functions, redis_conn

    valid_queues = ("internal", "query", "background")
    assert queue in valid_queues, TypeError(
        f"Tried to run a worker with an invalid queue name ({queue}). The queue should be one of: {', '.join(q for q in valid_queues)}"
    )
    w = Worker(
        functions=_functions,
        queue_name=queue,
        max_jobs=QUERY_MAX_NUM_CONNS if queue == "query" else UPLOAD_MAX_NUM_CONNS,
        redis_settings=redis_conn,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
    print(f"Running worker on queue {queue}")

    await w.async_run()


def start_worker(queue: str = "internal") -> None:
    try:
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(work(queue))
    except KeyboardInterrupt:
        print("Worker stopped.")


if __name__ == "__main__":
    start_worker()

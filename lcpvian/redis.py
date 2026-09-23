"""
Definitions for redis clients
"""

import json
import os

from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from redis import Redis
from redis import asyncio as aioredis
from redis.asyncio.retry import Retry as AsyncRetry
from redis.backoff import ConstantBackoff
from redis.exceptions import ConnectionError
from redis.retry import Retry

_redis_url = ""
_shared_redis_url = ""
_redis_conn = None

_redis_sleep_time: int = -1


def get_redis_conf() -> tuple[str, str, RedisSettings]:
    REDIS_DB_INDEX = int(os.getenv("REDIS_DB_INDEX", 0))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_SHARED_DB_INDEX = int(os.getenv("REDIS_SHARED_DB_INDEX", -1))
    REDIS_SHARED_URL = os.getenv("REDIS_SHARED_URL", REDIS_URL)

    global _redis_url, _shared_redis_url, _redis_conn
    if _redis_url and _shared_redis_url and _redis_conn:
        return _redis_url, _shared_redis_url, _redis_conn
    _redis_url = f"{REDIS_URL}/{REDIS_DB_INDEX}" if REDIS_DB_INDEX > -1 else REDIS_URL
    _shared_redis_url = f"{REDIS_SHARED_URL}/{REDIS_SHARED_DB_INDEX}"
    _redis_conn = RedisSettings.from_dsn(_redis_url)
    return _redis_url, _shared_redis_url, _redis_conn


def get_redis_sleep_time() -> int:
    global _redis_sleep_time
    redis_url, _, _ = get_redis_conf()
    if _redis_sleep_time < 0:
        redis_settings = Redis.from_url(redis_url)
        limit = "client-output-buffer-limit"
        pubsub_limit = redis_settings.config_get(limit)[limit]
        redis_settings.quit()
        _pieces = pubsub_limit.split()
        return int(_pieces[-1]) + 2
    return _redis_sleep_time


def get_shared_redis():
    redis_url, shared_redis_url, _ = get_redis_conf()
    sleep_time = get_redis_sleep_time()
    retry_policy = Retry(ConstantBackoff(sleep_time), 3)
    REDIS_SHARED_DB_INDEX = int(os.getenv("REDIS_SHARED_DB_INDEX", -1))
    url = redis_url if REDIS_SHARED_DB_INDEX < 0 else shared_redis_url
    return Redis.from_url(
        url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=retry_policy,
    )


def get_sync_redis():
    redis_url, _, _ = get_redis_conf()
    sleep_time = get_redis_sleep_time()
    retry_policy = Retry(ConstantBackoff(sleep_time), 3)
    return Redis.from_url(
        redis_url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=retry_policy,
    )


def get_async_redis():
    redis_url, _, _ = get_redis_conf()
    sleep_time = get_redis_sleep_time()
    async_retry_policy = AsyncRetry(ConstantBackoff(sleep_time), 3)
    return aioredis.Redis.from_url(
        redis_url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=async_retry_policy,
    )


async def get_redis():
    _, _, redis_conn = get_redis_conf()
    return await create_pool(redis_conn)


async def get_job_kwargs(job: Job) -> dict:
    payload = await job._redis.get(f"kwargs::{job.job_id}")
    kwargs = json.loads(payload or "null")
    return kwargs or {}


async def set_job_kwargs(job: Job, kwargs: dict):
    await job._redis.set(f"kwargs::{job.job_id}", json.dumps(kwargs))
    return kwargs


async def get_job_meta(job: Job) -> dict:
    payload = await job._redis.get(f"meta::{job.job_id}")
    meta = json.loads(payload or "null")
    return meta or {}


async def set_job_meta(job: Job, meta: dict):
    await job._redis.set(f"meta::{job.job_id}", json.dumps(meta))
    return meta

"""
Definitions for redis clients
"""

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

REDIS_DB_INDEX = int(os.getenv("REDIS_DB_INDEX", 0))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_SHARED_DB_INDEX = int(os.getenv("REDIS_SHARED_DB_INDEX", -1))
REDIS_SHARED_URL = os.getenv("REDIS_SHARED_URL", REDIS_URL)

redis_url: str = f"{REDIS_URL}/{REDIS_DB_INDEX}" if REDIS_DB_INDEX > -1 else REDIS_URL
shared_redis_url: str = f"{REDIS_SHARED_URL}/{REDIS_SHARED_DB_INDEX}"
redis_conn = RedisSettings.from_dsn(redis_url)


_redis_sleep_time: int = -1


def get_redis_sleep_time() -> int:
    global _redis_sleep_time, redis_url
    if _redis_sleep_time < 0:
        redis_settings = Redis.from_url(redis_url)
        limit = "client-output-buffer-limit"
        pubsub_limit = redis_settings.config_get(limit)[limit]
        redis_settings.quit()
        _pieces = pubsub_limit.split()
        return int(_pieces[-1]) + 2
    return _redis_sleep_time


def get_shared_redis():
    global redis_url
    sleep_time = get_redis_sleep_time()
    retry_policy: Retry = Retry(ConstantBackoff(sleep_time), 3)
    url = redis_url if REDIS_SHARED_DB_INDEX < 0 else shared_redis_url
    return Redis.from_url(
        url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=retry_policy,
    )


def get_sync_redis():
    global redis_url
    sleep_time = get_redis_sleep_time()
    retry_policy: Retry = Retry(ConstantBackoff(sleep_time), 3)
    return Redis.from_url(
        redis_url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=retry_policy,
    )


def get_async_redis():
    global redis_url
    sleep_time = get_redis_sleep_time()
    async_retry_policy: AsyncRetry = AsyncRetry(ConstantBackoff(sleep_time), 3)
    return aioredis.Redis.from_url(
        redis_url,
        health_check_interval=10,
        retry_on_error=[ConnectionError],
        retry=async_retry_policy,
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

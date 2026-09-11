"""
Method to enqueue arq tasks
"""

from arq.jobs import Job

from .redis import get_redis
from .tasks import _registered_tasks

TRIM_ARGS = 80  # number of characters to trim down the string representation of (keyword) arguments


async def enqueue(
    func_name: str, *args, queue: str | None = None, job_id: str | None = None, **kwargs
) -> Job | None:
    redis = await get_redis()
    full_func_name = f"lcpvian.tasks.{func_name}"
    job = await redis.enqueue_job(
        full_func_name, *args, **kwargs, _queue_name=queue, _job_id=job_id
    )
    str_args = str(args)
    str_kwargs = str(kwargs)
    if len(str_args) > TRIM_ARGS:
        str_args = str_args[:TRIM_ARGS] + "..."
    if len(str_kwargs) > TRIM_ARGS:
        str_kwargs = str_kwargs[:TRIM_ARGS] + "..."
    print(
        f"Enqueued '{queue or ''}' job '{full_func_name}' (job id: {'null' if job is None else job.job_id}) with parameters",
        str_args,
        str_kwargs,
    )
    return job

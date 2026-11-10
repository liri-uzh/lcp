"""
Utils methods specific to arq jobs' definitions
"""

from arq.worker import func


def timeout(timeout: int = 3000):
    def decorator(task_method):
        async def task_wrapper(ctx, *args, **kwargs):
            r = await task_method(ctx, *args, **kwargs)
            return r

        fname = f"{task_method.__module__}.{task_method.__qualname__}"
        job_func = func(
            task_wrapper,
            name=fname,
            keep_result=True,
            timeout=timeout,  # parameterize this
        )
        return job_func

    return decorator

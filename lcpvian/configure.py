"""
Endpoint for refreshing the config
"""

from aiohttp import web
from arq.jobs import Job

from .utils import (
    ensure_authorised,
)
from .tasker import enqueue


@ensure_authorised
async def refresh_config(request: web.Request) -> web.Response:
    """
    Force a refresh of the config via the /config endpoint
    """
    job: Job | None = await enqueue(
        "configure.get_config", force_refresh=True, queue="internal"
    )
    return web.json_response({"job": str("" if job is None else job.job_id)})

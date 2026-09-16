import os

from arq.jobs import Job
from aiohttp import web
from typing import cast

from .authenticate import Authentication
from .tasker import enqueue
from .utils import LCPApplication


async def download_export(request: web.Request) -> web.FileResponse:
    """
    Endpoint to download a file that was previously generated
    """
    app = cast(LCPApplication, request.app)
    authenticator = cast(Authentication, app["auth_class"](app))
    user_data: dict = await authenticator.user_details(request)
    if not user_data.get("user", {}).get("id"):
        raise PermissionError("Unauthenticated users cannot export results")

    filepath = ""
    qhash = request.rel_url.query["hash"]
    format = request.rel_url.query["format"]
    offset = request.rel_url.query.get("offset", "0")
    requested = request.rel_url.query.get("requested", "0")
    full = cast(bool, request.rel_url.query.get("full", False))

    db_job: Job | None = await enqueue(
        "export.get_exports", ehash=qhash, queue="internal"
    )
    db_results = await cast(Job, db_job).result()
    corpus_id = str(db_results[0][1])
    if not authenticator.check_corpus_searchable(corpus_id, user_data):
        raise PermissionError("User does not have export access to this corpus")

    if format == "swissdox":
        results_path = str(os.environ.get("RESULTS_PATH", "results"))
        filepath = os.path.join(results_path, qhash, offset, "swissdox.db")
    else:
        exporter_class = request.app["exporters"][format]
        filepath = exporter_class.get_dl_path_from_hash(
            qhash, cast(int, offset), cast(int, requested), full, filename=True
        )
    if not os.path.exists(filepath):
        raise FileNotFoundError("Could not find the export file")

    content_disposition = f'attachment; filename="{os.path.basename(filepath)}"'
    headers = {
        "content-disposition": content_disposition,
        "content-length": f"{os.stat(filepath).st_size}",
    }
    return web.FileResponse(filepath, headers=headers)

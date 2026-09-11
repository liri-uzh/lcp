import os

from aiohttp import web
from typing import cast


async def download_export(request: web.Request) -> web.FileResponse:
    """
    Endpoint to download a file that was previously generated
    """
    filepath = ""
    qhash = request.rel_url.query["hash"]
    format = request.rel_url.query["format"]
    offset = request.rel_url.query.get("offset", "0")
    requested = request.rel_url.query.get("requested", "0")
    full = cast(bool, request.rel_url.query.get("full", False))
    if format == "swissdox":
        results_path = str(os.environ.get("RESULTS_PATH", "results"))
        filepath = os.path.join(results_path, qhash, offset, "swissdox.db")
    else:
        exporter_class = request.app["exporters"][format]
        filepath = exporter_class.get_dl_path_from_hash(
            qhash, cast(int, offset), cast(int, requested), full, filename=True
        )
    assert os.path.exists(filepath), FileNotFoundError("Could not find the export file")
    # TODO: check user access to file
    content_disposition = f'attachment; filename="{os.path.basename(filepath)}"'
    headers = {
        "content-disposition": content_disposition,
        "content-length": f"{os.stat(filepath).st_size}",
    }
    return web.FileResponse(filepath, headers=headers)

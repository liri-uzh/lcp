import os

from aiohttp import web
from redis.asyncio import Redis as RedisConnection
from rq.job import Job
from typing import Any, cast
from uuid import uuid4

from .exporter import Exporter as ExporterXml
from .exporter_swissdox import Exporter as ExporterSwissdox
from .utils import _publish_msg

EXPORT_TTL = 5000
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")


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


def _export_notifs(
    job: Job,
    connection: RedisConnection,
    result: list | None,
) -> None:
    """
    Callback when getting the export rows from the DB
    """
    if not result:
        return None
    RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
    j_kwargs: dict = cast(dict, job.kwargs)
    user = j_kwargs.get("user", "")
    hash = j_kwargs.get("hash", "")
    jso: dict[str, Any]
    if user:
        msg_id = str(uuid4())
        jso = {
            "user": user,
            "action": "export_notifs",
            "msg_id": msg_id,
            "exports": result,
        }
        _publish_msg(connection, jso, msg_id)
    elif hash:
        for res in result:
            _, _, _, _, user_id, format, offset, requested, _, fn, _, _ = res
            full = requested <= 0
            exp_class = ExporterSwissdox if format == "swissdox" else ExporterXml
            user_folder = os.path.join(RESULTS_USERS, user_id)
            srcfn = exp_class.get_dl_path_from_hash(hash, offset, requested, full)  # type: ignore
            # TODO: maybe create an ExporterSwissdox class?
            if format == "swissdox":
                srcfn = os.path.join(
                    RESULTS_SWISSDOX,
                    "exports",
                    f"{hash}.db",
                )
            normfn = os.path.normpath(fn)
            destfn = os.path.join(user_folder, normfn)
            if not os.path.exists(os.path.dirname(destfn)):
                os.makedirs(os.path.dirname(destfn))
            if not os.path.exists(destfn) and not os.path.islink(destfn):
                try:
                    os.symlink(os.path.abspath(srcfn), destfn)
                except Exception as e:
                    print(f"Problem with creating symlink {srcfn}->{destfn}", e)
            user_id = res[4]
            msg_id = str(uuid4())
            jso = {
                "user": user_id,
                "action": "export_notifs",
                "msg_id": msg_id,
                "exports": [res],
            }
            _publish_msg(connection, jso, msg_id)
            continue
    return None

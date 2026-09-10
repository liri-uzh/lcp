import os

from aiohttp import web
from redis.asyncio import Redis as RedisConnection
from rq.job import Job
from typing import Any, cast
from uuid import uuid4

from .exporter import Exporter as ExporterXml
from .exporter_swissdox import Exporter as ExporterSwissdox
from .jobfuncs import _db_query
from .utils import _publish_msg
from .worker import arq_task, ctx

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


@arq_task("internal")
async def _export_notifs(ctx, user_id: str = "", ehash: str = "") -> None:
    """
    Callback when getting the export rows from the DB
    """
    query: str
    if user_id:
        assert ";" not in user_id and "'" not in user_id
        query = f"SELECT * FROM main.exports WHERE user_id = '{user_id}';"
    elif ehash:
        assert ";" not in ehash and "'" not in ehash
        query = f"SELECT * FROM main.exports WHERE query_hash = '{ehash}';"

    result = await _db_query(ctx, query, {}, user=user_id, hash=ehash, is_main=True)

    if not result:
        return None

    RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
    user = user_id
    jso: dict[str, Any]
    if user:
        msg_id = str(uuid4())
        jso = {
            "user": user,
            "action": "export_notifs",
            "msg_id": msg_id,
            "exports": result,
        }
        await _publish_msg(ctx["redis"], jso, msg_id)
    elif ehash:
        for res in result:
            res = cast(list, res)
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
            await _publish_msg(ctx["redis"], jso, msg_id)

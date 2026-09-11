"""
Async tasks called from exporter_swissdox.py
"""

import importlib
import os
import shutil

from typing import cast

from ..redis import get_sync_redis

EXPORT_TTL = 5000
RESULTS_DIR = os.getenv("RESULTS", "results")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")


async def export(ctx, class_name: str, request_id: str, qhash: str, payload: dict):
    """
    The core of the export pipeline, run in a worker
    """
    mod, clas = class_name.split(".", 1)
    cls = importlib.import_module(mod).__dict__[clas]
    connection = get_sync_redis()
    request = ctx["_request"](connection, {"id": request_id})
    qi = ctx["_queryInfo"](qhash, connection)
    offset = request.offset
    requested = request.requested
    full = request.full
    try:
        exporter = cls(request, qi)
        wpath = exporter.get_working_path()
        await exporter.process_lines(payload)
        if not request.is_done(qi):
            return
        # each payload needs corresponding *_query/*_segments subfolders
        qb_hashes = [bh for bh, _ in qi.query_batches.values()]
        for h, nlines in request.sent_hashes.items():
            if h not in qb_hashes or cast(int, nlines) <= 0:
                continue
            if not os.path.exists(os.path.join(wpath, f"{h}_segments")):
                return
        delivered = request.lines_sent_so_far
        await exporter.finalize(ctx)
        shutil.rmtree(exporter.get_working_path())
        for h in request.sent_hashes:
            hpath = os.path.join(wpath, f"{h}_segments")
            if os.path.exists(hpath):
                shutil.rmtree(hpath)
        print(
            f"SWISSDOX Exporting complete for request {request.id} (hash: {request.hash}) ; DELETED REQUEST"
        )
        qi.delete_request(request)
        cls.finish_export_db(
            connection,
            qhash,
            offset,
            requested,
            cast(int, delivered),
            full,
            "swissdox",
        )
    except Exception as e:
        shutil.rmtree(cls.get_dl_path_from_hash(qhash, offset, requested, full))
        print("ERROR", e)
        raise e

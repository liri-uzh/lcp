"""
Async tasks called from exporter.py
"""

import asyncio
import importlib
import os
import shutil

from typing import cast

from ..redis import get_sync_redis

EXPORT_TTL = 5000
RESULTS_DIR = os.getenv("RESULTS", "results")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


async def export_db(
    ctx,
    query_hash: str,
    xp_format: str,
    operation: str = "create",
    offset: int = 0,
    requested: int = 0,
    **kwargs: int | str | None,
) -> None:
    """
    Run on an "internal" arq worker, create/update entry in main.exports table
    """
    wpool = ctx["_wpool"]
    try:
        export_query: str
        export_params = {
            "query_hash": query_hash,
            "format": xp_format,
            "offset": offset,
            "requested": requested,
        }
        should_run: bool = cast(dict, kwargs).get("should_run", False)
        if operation == "create":
            export_params["user_id"] = kwargs.get("user_id", "")
            export_params["userpath"] = kwargs.get("userpath", "export")
            export_params["corpus_id"] = kwargs.get("corpus_id", 0)
            export_params["need_querying"] = "TRUE" if should_run else "FALSE"
            export_query = "CALL main.init_export('{query_hash}', '{format}', {offset}, {requested}, '{user_id}', {need_querying}, '{userpath}', {corpus_id});"
        elif operation == "update":
            export_query = "CALL main.update_export('{query_hash}', '{format}', {offset}, {requested}, '{status}', '{message}');"
            export_params.pop("user_id", "")
            export_params["status"] = (
                "export"
                if "export" in kwargs
                else ("query" if "query" in kwargs else "failure")
            )
            export_params["message"] = kwargs.get("message", "")
        elif operation == "finish":
            # if path := kwargs.get("path"):
            #     RESULTS_DIR = os.getenv("RESULTS_USERS", os.path.join("results","users/"))
            export_query = "CALL main.finish_export('{query_hash}', '{format}', {offset}, {requested}, {delivered});"
            export_params.pop("user_id", "")
            export_params["delivered"] = kwargs.get("delivered", 0)

        query = export_query.format(**export_params)

        async with wpool.begin() as conn:
            raw = await conn.get_raw_connection()
            con = raw._connection
            async with con.transaction():
                print("Handling export...\n", query)
                await con.execute(query)

        if should_run:
            return

        exporter = importlib.import_module("lcpvian/exporter.py").__dict__["Exporter"]
        full: bool = cast(dict, kwargs).get("full", False)
        await exporter.finish_export_db(
            ctx["redis"],
            query_hash,
            offset,
            requested,
            requested,
            full,
            xp_format,
        )

    except asyncio.TimeoutError as e:
        # job-specific timeout handling
        msg = str("Export timed out")

        export_query = "CALL main.update_export('{query_hash}', '{format}', {offset}, {requested}, '{status}', '{message}');"
        export_params.pop("user_id", "")
        export_params["status"] = "failure"
        export_params["message"] = msg

        query = export_query.format(**export_params)

        async with wpool.begin() as conn:
            raw = await conn.get_raw_connection()
            con = raw._connection
            async with con.transaction():
                await con.execute(query)

        # await _general_failure(
        #     ctx["job"], ctx["redis"], asyncio.TimeoutError, e, e.__traceback__
        # )
        # Optionally re-raise so Arq retries or fails according to max_tries
        raise
    except Exception as e:
        # on_failure for other errors
        print("Error when handling export", e)
        raise e
    return None


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
        upd_exp_args = (qhash, cls.xp_format, "update", offset, requested)
        await export_db(
            ctx,
            *upd_exp_args,
            export=True,
            message=f"{payload.get('percentage_done', 'NA')}%",
        )
        exporter = cls(request, qi)
        wpath = exporter.get_working_path()
        await exporter.process_lines(payload)
        if not request.is_done(qi):
            return
        await export_db(
            ctx,
            *upd_exp_args,
            export=True,
            message=f"100% - finalizing...",
        )  # each payload needs corresponding *_query/*_segments subfolders
        qb_hashes = [bh for bh, _ in qi.query_batches.values()]
        for h, nlines in request.sent_hashes.items():
            if h not in qb_hashes or cast(int, nlines) <= 0:
                continue
            hpath = os.path.join(wpath, h)
            if not os.path.exists(f"{hpath}_query"):
                return
            seg_exists = os.path.exists(f"{hpath}_segments")
            if qi.kwic_keys and not seg_exists:
                return
        delivered: int = cast(int, request.lines_sent_so_far)
        await exporter.finalize(ctx)
        shutil.rmtree(exporter.get_working_path())
        for h in request.sent_hashes:
            hpath = os.path.join(wpath, h)
            if os.path.exists(f"{hpath}_query"):
                shutil.rmtree(f"{hpath}_query")
            if os.path.exists(f"{hpath}_segments"):
                shutil.rmtree(f"{hpath}_segments")
        print(
            f"Exporting complete for request {request.id} (hash: {request.hash}) ; DELETED REQUEST"
        )
        qi.delete_request(request)
        await cls.finish_export_db(
            qi._connection, qi.hash, offset, requested, delivered, full
        )
    except Exception as e:
        shutil.rmtree(cls.get_dl_path_from_hash(qhash, offset, requested, full))
        await export_db(
            ctx,
            qhash,
            cls.xp_format,
            "update",
            offset,
            requested,
            failure=True,
            message=str(e),
        )
        raise e

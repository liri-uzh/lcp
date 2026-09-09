import asyncio
import json
import logging
import os
import shutil
import traceback

from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

# TODO(ARQ_MIGRATION): Replace rq imports with Arq equivalents
# from rq.connections import get_current_connection
# from rq.job import get_current_job, Job
from arq.jobs import Job

from lcpvian.upload import _move_media_files

from .callbacks import _general_failure
from .impo import Importer
from .project import refresh_config
from .typed import DBQueryParams, JSONObject, MainCorpus, Sentence, UserQuery
from .utils import _get_sent_ids, _row_to_value
from .worker import arq_task


@arq_task("background")
async def _insert_data(
    ctx,
    project: str,
    user: str,
    room: str | None,
    debug: bool,
    **kwargs: dict[str, JSONObject | bool],
) -> MainCorpus | None:
    """
    Script to be run by arq worker, convert data and upload to postgres
    """
    uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
    corpus = os.path.join(uploads_path, project)
    data_path = os.path.join(corpus, "_data.json")

    with open(data_path, "r") as fo:
        data: JSONObject = json.load(fo)

    importer = Importer(ctx["_upool"], data, corpus, debug, **kwargs)
    extra = {"user": user, "room": room, "project": project}
    row: MainCorpus | None = None
    try:
        msg = f"Starting corpus import for {user}: {project}"
        logging.info(msg, extra=extra)
        row = await importer.pipeline()
        config = _row_to_value(row, project=project)
        media_path = os.path.join(corpus, "media")
        has_media = config.get("meta", {}).get("mediaSlots", {})
        if has_media and os.path.isdir(media_path):
            msg = f"Moving media files for {user}: {project}"
            logging.info(msg, extra=extra)
            _move_media_files(
                os.path.join(project, "media"), config.get("schema_path", "")
            )
    except Exception as err:
        tb = traceback.format_exc()
        msg = f"Error during import/upload: {err}"
        print(msg, tb)
        extra["traceback"] = tb
        logging.error(msg, extra=extra)
        await importer.cleanup()
    finally:
        shutil.rmtree(corpus)  # todo: should we do this?
    if not row:
        raise RuntimeError(msg)
    return row


@arq_task("background")
async def _create_schema(
    ctx,
    create: str,
    schema_name: str,
    # drops: list[str] | None,
    user: str = "",
    room: str | None = None,
    **kwargs: str | None,
) -> None:
    """
    To be run by arq worker, create schema in DB for a new corpus
    """
    # extra = {"user": user, "room": room, "drops": drops, "schema": schema_name}
    extra = {"user": user, "room": room, "schema": schema_name}

    # todo: figure out how to make this block a little nicer :P
    async with ctx["_upool"].begin() as conn:
        raw = await conn.get_raw_connection()
        con = raw._connection
        async with con.transaction():
            try:
                print("Creating schema...\n", create)
                await con.execute(create)
            except Exception as err:
                print("Error when creating the schema", err)
    return None


async def _db_query(
    ctx,
    query: str,
    params: DBQueryParams = {},
    config: bool = False,
    store: bool = False,
    delete: bool = False,
    is_main: bool = False,  # is the query related to the schame 'main'?
    is_import: bool = False,  # is the query related to the import pipeline?
    has_return: bool = True,
    **kwargs: str | None | int | float | bool | list[str],
) -> (
    list[tuple[Any, ...]]
    | tuple[Any, ...]
    | list[JSONObject]
    | JSONObject
    | list[MainCorpus]
    | list[UserQuery]
    | list[Sentence]
    | None
):
    """
    The function queued by Arq, which executes our DB query
    """
    # this can only be done after the previous job finished...
    if "depends_on" in kwargs and "sentences_query" in kwargs:
        dep = cast(list[str] | str, kwargs["depends_on"])
        total = cast(int, kwargs.get("total_results_requested"))
        offset = cast(int, kwargs.get("offset", -1))
        needed = cast(int, kwargs.get("needed", total))
        needed = max(-1, needed)  # todo: fix this earlier?
        ids: list[str] | list[int] | None = await _get_sent_ids(
            ctx["redis"], dep, needed, offset=offset
        )
        if not ids:
            return None
        params = {"ids": ids}

    name = (
        "_upool"
        if (store or delete or is_import)
        else ("_wpool" if (config or is_main) else "_pool")
    )
    pool = ctx[name]
    method = "begin" if (store or delete or is_import) else "connect"

    first_job_id = cast(str, kwargs.get("first_job", ""))
    if first_job_id:
        first_job_result = await ctx["redis"].job(first_job_id)
        if first_job_result and first_job_result.status in ("stopped", "canceled"):
            print("First job was stopped or canceled - not executing the query")
            raise SQLAlchemyError("Job canceled")

    params = params or {}

    if kwargs.get("refresh_config"):
        await refresh_config()

    async with getattr(pool, method)() as conn:
        try:
            res = await conn.execute(text(query), params)

            if store or delete:
                # For DELETE queries, simply return None (or log res.rowcount if needed)
                if delete:
                    # For non-SELECT queries (store/delete), do not attempt to fetch rows.
                    return res.rowcount
                else:
                    return None

            if is_import or not has_return:
                return None

            out: list[tuple[Any, ...]] = [tuple(i) for i in res.fetchall()]

            return out
        except SQLAlchemyError as err:
            print(f"SQL error: {err}")
            raise err

import json
import logging
import os
import shutil
import traceback

from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from rq.connections import get_current_connection
from rq.job import get_current_job, Job

from .impo import Importer
from .project import refresh_config
from .typed import DBQueryParams, JSONObject, MainCorpus, Sentence, UserQuery
from .utils import _get_sent_ids


async def _upload_data(
    project: str,
    user: str,
    room: str | None,
    debug: bool,
    **kwargs: dict[str, JSONObject | bool],
) -> MainCorpus | None:
    """
    Script to be run by rq worker, convert data and upload to postgres
    """
    uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
    corpus = os.path.join(uploads_path, project)
    data_path = os.path.join(corpus, "_data.json")

    with open(data_path, "r") as fo:
        data: JSONObject = json.load(fo)

    # constraints = cast(list[str], data["constraints"])
    # perms = cast(str, data["perms"])
    # constraints.append(perms)

    # template = cast(CorpusTemplate, data["template"])

    # if not template.get("project"):
    #     template["project"] = project

    upool = get_current_job()._upool  # type: ignore
    importer = Importer(upool, data, corpus, debug, **kwargs)
    extra = {"user": user, "room": room, "project": project}
    row: MainCorpus | None = None
    try:
        msg = f"Starting corpus import for {user}: {project}"
        logging.info(msg, extra=extra)
        row = await importer.pipeline()
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


async def _export_db(
    query_hash: str,
    format: str,
    operation: str = "create",
    offset: int = 0,
    requested: int = 0,
    **kwargs: int | str | None,
) -> None:
    """
    To be run by rq worker, create/update entry in main.exports table
    """
    export_query: str
    export_params = {
        "query_hash": query_hash,
        "format": format,
        "offset": offset,
        "requested": requested,
    }
    if operation == "create":
        export_params["user_id"] = kwargs.get("user_id", "")
        export_params["userpath"] = kwargs.get("userpath", "export")
        export_params["corpus_id"] = kwargs.get("corpus_id", 0)
        export_params["need_querying"] = "TRUE" if kwargs.get("should_run") else "FALSE"
        export_query = "CALL main.init_export('{query_hash}', '{format}', {offset}, {requested}, '{user_id}', {need_querying}, '{userpath}', {corpus_id});"
    elif operation == "update":
        export_query = "CALL main.update_export('{query_hash}', '{format}', {offset}, {requested}, {delivered});"
    elif operation == "finish":
        # if path := kwargs.get("path"):
        #     RESULTS_DIR = os.getenv("RESULTS_USERS", os.path.join("results","users/"))
        export_query = "CALL main.finish_export('{query_hash}', '{format}', {offset}, {requested}, {delivered});"
        export_params.pop("user_id", "")
        export_params["delivered"] = kwargs.get("delivered", 0)

    query = export_query.format(**export_params)

    async with get_current_job()._wpool.begin() as conn:  # type: ignore
        raw = await conn.get_raw_connection()
        con = raw._connection
        async with con.transaction():
            try:
                print("Handling export...\n", query)
                await con.execute(query)
            except Exception as err:
                print("Error when handling export", err)
    return None


async def _create_schema(
    create: str,
    schema_name: str,
    # drops: list[str] | None,
    user: str = "",
    room: str | None = None,
    **kwargs: str | None,
) -> None:
    """
    To be run by rq worker, create schema in DB for a new corpus
    """
    # extra = {"user": user, "room": room, "drops": drops, "schema": schema_name}
    extra = {"user": user, "room": room, "schema": schema_name}

    # todo: figure out how to make this block a little nicer :P
    async with get_current_job()._upool.begin() as conn:  # type: ignore
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
    query: str,
    params: DBQueryParams = {},
    config: bool = False,
    store: bool = False,
    delete: bool = False,
    is_main: bool = False,  # is the query related to the schame 'main'?
    is_import: bool = False,  # is the query related to the import pipeline?
    has_return: bool = True,
    document: bool = False,
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
    The function queued by RQ, which executes our DB query
    """
    # this can only be done after the previous job finished...
    if "depends_on" in kwargs and "sentences_query" in kwargs:
        dep = cast(list[str] | str, kwargs["depends_on"])
        total = cast(int, kwargs.get("total_results_requested"))
        offset = cast(int, kwargs.get("offset", -1))
        needed = cast(int, kwargs.get("needed", total))
        needed = max(-1, needed)  # todo: fix this earlier?
        ids: list[str] | list[int] | None = _get_sent_ids(dep, needed, offset=offset)
        if not ids:
            return None
        params = {"ids": ids}

    name = (
        "_upool"
        if (store or delete or is_import)
        else ("_wpool" if (config or is_main) else "_pool")
    )
    job = get_current_job()
    pool = getattr(job, name)
    method = "begin" if (store or delete or is_import) else "connect"

    first_job_id = cast(str, kwargs.get("first_job", ""))
    if first_job_id:
        first_job: Job = Job.fetch(first_job_id, connection=get_current_connection())
        if first_job:
            first_job_status = first_job.get_status(refresh=True)
            if first_job_status in ("stopped", "canceled"):
                print("First job was stopped or canceled - not executing the query")
                raise SQLAlchemyError("Job canceled")

    params = params or {}

    if job and cast(dict, job.kwargs).get("refresh_config", None):
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

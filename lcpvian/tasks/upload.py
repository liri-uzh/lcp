"""
Async tasks called from upload.py
"""

import json
import logging
import os
import shutil
import traceback

from typing import cast
from uuid import uuid4

from .configure import get_config
from ..impo import Importer
from ..jobfuncs import _db_query
from ..typed import DBQueryParams, JSONObject, MainCorpus
from ..utils import (
    _row_to_value,
    _load_top_module_file,
    _publish_msg,
    _sharepublish_msg,
    move_media_files,
)

lcpcli = _load_top_module_file(
    "lcpcli", os.path.join("lcpcli", "lcpcli", "__init__.py")
)

MEDIA_EXTENSIONS = ("mp3", "mp4", "wav", "ogg", "png", "jpg", "jpeg", "bmp")
UPLOADS_PATH = os.getenv("TEMP_UPLOADS_PATH", "uploads")


async def overwrite_corpus(
    ctx, corpus_id: int, to_be_overwritten: int, queue: str = "internal"
):
    """
    Overwrite corpus id to_be_overwritten with corpus id corpus_id in the DB
    """
    kwargs = {
        "store": True,
        "is_main": True,  # query on main.*
        "has_return": False,
    }
    args = {"corpus_id": corpus_id, "overwrite": to_be_overwritten}
    query = f"""CALL main.update_corpus(:overwrite, :corpus_id);"""
    await _db_query(ctx, query, cast(DBQueryParams, args), **kwargs)
    await get_config(ctx)


async def insert_data(
    ctx,
    user: str,
    project: str,
    room: str | None = None,
    gui: bool = False,
    user_data: JSONObject | None = None,
    **kwargs,
):
    """
    Insert a new corpus into the database
    """
    try:
        kwargs = {"gui": gui, "user_data": user_data, **kwargs}
        uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
        corpus = os.path.join(uploads_path, project)
        data_path = os.path.join(corpus, "_data.json")

        with open(data_path, "r") as fo:
            data: JSONObject = json.load(fo)

        debug = False
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
                move_media_files(
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

        msg_id = str(uuid4())
        action = "uploaded"

        # if not room or not result:
        #     return None
        jso = {
            "user": user,
            "room": room,
            "id": row[0],
            "user_data": user_data,
            "entry": _row_to_value(row, project=project),
            "status": "success" if not row else "error",
            "project": project,
            "action": action,
            "gui": gui,
            "msg_id": msg_id,
        }

        await _sharepublish_msg(cast(JSONObject, jso), msg_id)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Upload failure: {e.__class__} : {e}; {tb}")
        msg_id = str(uuid4())
        uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
        path = os.path.join(uploads_path, project)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"Deleted: {path}")

        action = "upload_fail"

        if user and room:
            jso = {
                "user": user,
                "room": room,
                "project": project,
                "action": action,
                "status": "failed",
                "job": ctx["job_id"],
                "msg_id": msg_id,
                "traceback": tb,
                "kind": str(e.__class__),
                "value": str(e),
            }
            await _publish_msg(ctx["redis"], jso, msg_id)


async def create(
    ctx,
    create: str,
    user: str = "",
    room: str = "",
    project: str = "",
    project_name: str = "",
    corpus_name: str = "",
):
    status = "success"
    error = ""
    tb = ""
    async with ctx["_upool"].begin() as conn:
        raw = await conn.get_raw_connection()
        con = raw._connection
        async with con.transaction():
            try:
                print("Creating schema...\n", create)
                await con.execute(create)
            except Exception as err:
                print("Error when creating the schema", err)
                status = "error"
                error = str(err)
                tb = traceback.format_exc()
    if not room:
        return None
    msg_id = str(uuid4())
    action = "uploaded"
    jso = {
        "user": user,
        "status": status,
        "project": project,
        "project_name": project_name,
        "corpus_name": corpus_name,
        "action": action,
        "gui": False,
        "room": room,
        "msg_id": msg_id,
    }
    if status == "error":
        jso["error"] = error
        uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
        path = os.path.join(uploads_path, project)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"Deleted: {path}")

        action = "upload_fail"
        if user and room:
            jso = {
                "user": user,
                "room": room,
                "project": project,
                "action": action,
                "status": "failed",
                "job": ctx["job_id"],
                "msg_id": msg_id,
                "traceback": tb,
                "kind": "unknown",
                "value": error,
            }
            await _publish_msg(ctx["redis"], jso, msg_id)

    await _publish_msg(ctx["redis"], jso, msg_id)

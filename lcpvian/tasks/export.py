"""
Async tasks called from export.py
"""

import asyncio
import os

from typing import Any, cast
from uuid import uuid4

from ..callbacks import handle_general_failure
from ..jobfuncs import _db_query
from ..utils import _publish_msg

from ..abstract_query.utils import literal_sql, sql_str

RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")


@handle_general_failure  # or maybe not?
async def export_notifs(
    ctx, user_id: str = "", ehash: str = "", delay: float = 0.0
) -> None:
    """
    Callback when getting the export rows from the DB
    """
    if delay > 0.0:
        await asyncio.sleep(delay)

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
            _, _, _, _, user_id_from_res, xp_format, offset, requested, _, fn, _, _ = (
                res
            )
            user_id = str(user_id_from_res)
            full = cast(int, requested) <= 0
            xp_class = ctx["_exporters"][xp_format]
            user_folder = os.path.join(RESULTS_USERS, user_id)
            srcfn = xp_class.get_dl_path_from_hash(ehash, offset, requested, full)  # type: ignore
            # TODO: maybe create an ExporterSwissdox class?
            if xp_format == "swissdox":
                srcfn = os.path.join(
                    RESULTS_SWISSDOX,
                    "exports",
                    f"{ehash}.db",
                )
            normfn = os.path.normpath(str(fn))
            destfn = os.path.join(user_folder, normfn)
            if not os.path.exists(os.path.dirname(destfn)):
                os.makedirs(os.path.dirname(destfn))
            if not os.path.exists(destfn) and not os.path.islink(destfn):
                try:
                    os.symlink(os.path.abspath(srcfn), destfn)
                except Exception as e:
                    await xp_class.error(
                        f"Problem with creating symlink",
                        ehash,
                        offset=cast(int, offset),
                        requested=cast(int, requested),
                    )
                    raise RuntimeError(
                        f"Problem with creating symlink {srcfn}->{destfn}", e
                    )
            msg_id = str(uuid4())
            jso = {
                "user": user_id,
                "action": "export_notifs",
                "msg_id": msg_id,
                "exports": [res],
            }
            await _publish_msg(ctx["redis"], jso, msg_id)


@handle_general_failure
async def get_exports(ctx, user_id: str = "", ehash: str = "", **kwargs):
    """
    Fetch all applicable entries from main.exports
    """
    query: str = ""
    if user_id:
        assert ";" not in user_id and "'" not in user_id
        query = f"SELECT * FROM main.exports WHERE user_id = '{user_id}'"
    elif ehash:
        assert ";" not in ehash and "'" not in ehash
        query = f"SELECT * FROM main.exports WHERE query_hash = '{ehash}'"

    for k, v in kwargs.items():
        query = query + sql_str(" AND {} = {}", k, literal_sql(v))

    query = query + ";"
    print("query", query)
    result = await _db_query(ctx, query, {}, is_main=True)

    return result

from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from .typed import DBQueryParams, JSONObject, MainCorpus, Sentence, UserQuery
from .utils import _get_sent_ids


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

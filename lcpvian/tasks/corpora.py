"""
Async tasks called from corpora.py
"""

import json

from .configure import get_config
from ..jobfuncs import _db_query
from ..typed import JSONObject


async def update_descriptions(
    ctx,
    corpus_id: int,
    layer_descs: JSONObject,
    global_descs: JSONObject,
    lg: str = "en",
):
    """
    Update the descriptions of the layers and attributes in a corpus
    """
    # TODO: check localizableString in corpus_template schema instead?
    MONOLINGUAL = {"name", "revision", "license", "language"}

    query = f"""CALL main.update_corpus_descriptions(:corpus_id, :descriptions ::jsonb, :globals ::jsonb);"""
    params: dict = {
        "corpus_id": corpus_id,
        "descriptions": json.dumps(layer_descs),
        "globals": json.dumps(global_descs),
    }
    await _db_query(
        ctx,
        query,
        params,
        store=True,
        is_main=True,
        has_return=False,
    )
    await get_config(ctx)


async def update_metadata(
    ctx,
    corpus_id: int,
    query_data: JSONObject,
    existing_meta: dict = {},
    lg: str = "en",
):
    """
    Update metadata for a corpus
    """
    # TODO: check localizableString in corpus_template schema instead?
    MONOLINGUAL = {"name", "revision", "license", "language", "swissubase"}

    query = f"""CALL main.update_corpus_meta(:corpus_id, :metadata_json ::jsonb);"""
    for k, v in query_data.items():
        if k in MONOLINGUAL:
            continue
        is_str = isinstance(existing_meta.get(k), str)
        if is_str:
            if lg == "en" or existing_meta[k] == v:
                continue
            query_data[k] = {"en": existing_meta[k]}
        if not isinstance(query_data[k], dict):
            query_data[k] = (
                {**existing_meta[k]} if isinstance(existing_meta.get(k), dict) else {}
            )
        query_data[k][lg] = v  # type: ignore
        if "en" not in query_data[k]:  # type: ignore
            query_data[k]["en"] = v  # type: ignore
    params: dict = {
        "corpus_id": corpus_id,
        "metadata_json": json.dumps(query_data),
    }
    await _db_query(
        ctx,
        query,
        params,
        store=True,
        is_main=True,
        has_return=False,
    )
    await get_config(ctx)


async def update_projects(
    ctx,
    corpus_id: int,
    project_ids: list,
):
    """
    Update which project(s) a corpus belongs to
    """
    args = {
        "corpus_id": corpus_id,
        "pid": str(project_ids[0]),
        "pids": "[" + ",".join(f'"{str(pid)}"' for pid in project_ids) + "]",
    }
    query = (
        f"""CALL main.update_corpus_projects(:corpus_id, :pid ::uuid, :pids ::text);"""
    )
    await _db_query(
        ctx,
        query,
        args,
        store=True,
        is_main=True,
        has_return=False,
    )
    await get_config(ctx)

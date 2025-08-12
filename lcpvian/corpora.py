"""
corpora.py: /corpora endpoint, returns a dict of corpora available for a given
user and app, and return it as a JSON HTTP response

We use the complete version of this dict as app["config"], so no DB requests
are needed for this request.
"""

import copy
import logging

from json.decoder import JSONDecodeError

from .utils import _filter_corpora
from .utils import _remove_sensitive_fields_from_corpora
from .typed import JSONObject

from aiohttp import web
from aiohttp.client_exceptions import ClientOSError
from rq.job import Job
from typing import cast


async def corpora(request: web.Request) -> web.Response:
    """
    Return config to frontend (as HTTP response, not WS message!)
    """
    request_data: dict[str, str | bool] = {}
    try:
        request_data = await request.json()
    except JSONDecodeError:  # no data was sent ... eventually this should not happpen
        pass
    app_type = str(request_data.get("appType", "lcp"))
    app_type = (
        "lcp"
        if app_type not in {"lcp", "videoscope", "soundscript", "catchphrase"}
        else app_type
    )

    authenticator = request.app["auth_class"](request.app)
    if not request_data.get("all", False):
        try:
            user_data = await authenticator.user_details(request)
        except ClientOSError as err:
            jso = {
                "details": str(err),
                "type": err.__class__.__name__,
                "status": "warning",
            }
            logging.warning(f"Failed to login: {err}", extra=jso)
            return web.json_response({"error": "no login possible", "status": 401})
        corpora = _filter_corpora(
            authenticator, request.app["config"], app_type, user_data
        )
    else:
        corpora = request.app["config"]

    # Create a copy of the corpora before removing any sensitive data
    corpora = copy.deepcopy(corpora)
    corpora = _remove_sensitive_fields_from_corpora(corpora)
    return web.json_response({"config": corpora})


async def corpora_meta_update(request: web.Request) -> web.Response:
    """
    Updates metadata for a given corpus
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    corpora_id: int = int(request.match_info["corpora_id"])
    request_data: JSONObject = await request.json()
    metadata: dict = cast(dict, request_data.get("metadata", {}))
    descriptions: dict = cast(dict, request_data.get("descriptions", {}))

    if not authenticator.check_corpus_allowed(
        str(corpora_id),
        user_data,
        "lcp",
    ):
        raise PermissionError("This user is not authorized to modify this corpus")

    # When apiAccessToken is hidden (less then 20 chars), get the original one from the config
    swissubase = metadata.get("swissubase", {})
    if len(swissubase.get("apiAccessToken") or "") < 20:
        corpora = request.app["config"]
        corpus = corpora.get(str(corpora_id))
        access_token = (
            corpus.get("meta", {}).get("swissubase", {}).get("apiAccessToken")
            if corpus
            else None
        )
        swissubase["apiAccessToken"] = access_token

    to_store_meta = dict(
        name=metadata["name"],
        source=metadata.get("source", ""),
        authors=metadata.get("authors", ""),
        institution=metadata.get("institution", ""),
        revision=metadata.get("revision", ""),
        corpusDescription=metadata["corpusDescription"],
        language=metadata.get("language", ""),
        license=metadata.get("license", ""),
        userLicense=metadata.get("userLicense", ""),
        dataType=metadata.get("dataType", ""),
        sample_query=metadata.get("sample_query", ""),
        swissubase=swissubase,
    )
    args_meta = (corpora_id, to_store_meta, request_data.get("lg") or "en")
    job_meta: Job = request.app["query_service"].update_metadata(*args_meta)
    to_store_desc = {
        k: {
            vk: (
                vv
                if vk == "description"
                else {
                    vvk: (
                        {
                            vvvk: vvvv["description"]
                            for vvvk, vvvv in vvv.items()
                            if "description" in vvvv
                        }
                        if vvk == "meta" and isinstance(vvv, dict)
                        else vvv["description"]
                    )
                    for vvk, vvv in vv.items()
                    if "description" in vvv or vvk == "meta"
                }
            )
            for vk, vv in v.items()
            if vk in ("description", "attributes")
        }
        for k, v in descriptions.items()
    }
    args_desc = (corpora_id, to_store_desc, request_data.get("lg") or "en")
    job_desc: Job = request.app["query_service"].update_descriptions(*args_desc)

    jobs_payload = [str(job_meta.id), str(job_desc.id)]
    if "projects" in request_data:
        user: dict = user_data.get("user") or {}
        if not user.get("superAdmin"):
            raise PermissionError(
                "User is not authorized to update the project of this corpus"
            )
        pids = request_data["projects"] or ["00000000-0000-0000-0000-000000000000"]
        job_update_projects: Job = request.app["query_service"].update_projects(
            corpora_id, pids
        )
        jobs_payload.append(str(job_update_projects.id))
    info: dict[str, str | list[str]] = {
        "status": "1",
        "jobs": [str(job_meta.id), str(job_desc.id)],
    }
    return web.json_response(info)

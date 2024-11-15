"""
corpora.py: /corpora endpoint, returns a dict of corpora available for a given
user and app, and return it as a JSON HTTP response

We use the complete version of this dict as app["config"], so no DB requests
are needed for this request.
"""

import logging

from json.decoder import JSONDecodeError

from .utils import _filter_corpora, ensure_authorised
from .typed import JSONObject

from aiohttp import web
from aiohttp.client_exceptions import ClientOSError
from rq.job import Job


@ensure_authorised
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
    return web.json_response({"config": corpora})


@ensure_authorised
async def corpora_meta_update(request: web.Request) -> web.Response:
    """
    Updates metadata for a given corpus
    """
    corpora_id: int = int(request.match_info["corpora_id"])
    request_data: JSONObject = await request.json()
    to_store = dict(
        name=request_data["name"],
        source=request_data.get("source", ""),
        authors=request_data.get("authors", ""),
        institution=request_data.get("institution", ""),
        revision=request_data.get("revision", ""),
        corpusDescription=request_data["corpusDescription"],
        license=request_data.get("license", ""),
        userLicense=request_data.get("userLicense", ""),
        dataType=request_data.get("dataType", ""),
    )
    args = (corpora_id, to_store)
    job: Job = request.app["query_service"].update_metadata(*args)
    info: dict[str, str] = {"status": "1", "job": str(job.id)}
    return web.json_response(info)

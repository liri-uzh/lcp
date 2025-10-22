"""
Endpoints for multimodal document/document ids fetching
"""

import os

from aiohttp import web
from typing import Sequence, Any, cast

from .typed import Config, JSONObject
from .utils import push_msg

RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


async def document(request: web.Request) -> web.Response:
    """
    Start a job fetching a corpus document via the doc_export functionality.

    The job's callback will send the document to the user/room via websocket
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    doc_id: int = int(request.match_info["doc_id"])
    request_data: dict[str, str] = await request.json()
    room: str | None = request_data.get("room")
    user: str = request_data.get("user", "")
    c: int | str | list[int] | list[str] = request_data["corpora"]
    corpora: list[int] = [int(c)] if not isinstance(c, list) else [int(i) for i in c]
    corpus = corpora[0]

    if not authenticator.check_corpus_allowed(
        str(corpus),
        user_data,
        "lcp",
    ):
        raise PermissionError("This user is not authorized to access this corpus")

    corpus_conf = request.app["config"][str(corpus)]
    schema = corpus_conf["schema_path"]
    job = request.app["query_service"].document(
        schema, corpus, doc_id, user, room, corpus_conf
    )
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)


async def image_annotations(request: web.Request) -> web.Response:
    """
    Start a job fetching image annotations.

    The job's callback will send the document to the user/room via websocket
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    request_data: dict[str, str] = await request.json()
    assert "corpus" in request_data, KeyError(
        f"Corpus is missing from the request for image annotations"
    )
    assert "layer" in request_data, KeyError(
        f"Layer is missing from the request for image annotations"
    )
    assert "ids" in request_data, KeyError(
        f"IDs are missing from the request for image annotations"
    )
    corpus = request_data["corpus"]
    layer = request_data["layer"]
    ids: list = cast(list, request_data.get("ids", []))
    xy_box: list = cast(list, request_data.get("xy_box", []))
    assert all(isinstance(id, int) for id in ids), ValueError(
        "All the IDs should be integers in an image annotation request"
    )
    assert all(isinstance(xy, int) for xy in xy_box), ValueError(
        "All the values of xy_box must be integers in an image annotation request"
    )

    room: str | None = request_data.get("room")
    user: str = request_data.get("user", "")

    if not authenticator.check_corpus_allowed(
        str(corpus),
        user_data,
        "lcp",
    ):
        raise PermissionError("This user is not authorized to access this corpus")

    corpus_conf = request.app["config"][str(corpus)]
    assert layer in corpus_conf["layer"] and any(
        a.get("type") == "image"
        for a in corpus_conf["layer"][layer].get("attributes", {}).values()
    ), ValueError(
        f"Could not find a layer named {layer} with an image attribute in this corpus."
    )
    job = request.app["query_service"].image_annotations(
        corpus_conf, layer, ids, xy_box, user, room
    )
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)


async def clip_media(request: web.Request) -> web.Response:
    """
    Start a job fetching image annotations.

    The job's callback will send the document to the user/room via websocket
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    if not user_data:
        raise PermissionError("Unauthenticated users cannot clip media")

    request_data: dict[str, str] = await request.json()
    assert "corpus" in request_data, KeyError(
        f"Corpus is missing from the request for image annotations"
    )
    corpus = request_data["corpus"]
    span = request_data["span"]
    assert isinstance(span, list) and len(span) == 2, TypeError(
        "Span should be a list of 2 numbers"
    )
    doc_id: int = int(request.match_info["doc_id"])
    assert doc_id, ReferenceError("Need a document id to export a media clip")

    room: str | None = request_data.get("room")
    user: str = request_data.get("user", "")

    if not authenticator.check_corpus_allowed(
        str(corpus),
        user_data,
        "lcp",
    ):
        raise PermissionError("This user is not authorized to access this corpus")

    corpus_conf = request.app["config"][str(corpus)]

    job = request.app["query_service"].clip_media(corpus_conf, span, doc_id, user, room)
    info: dict[str, str] = {"status": "started", "job": job.id}
    return web.json_response(info)


async def get_clip_media(request: web.Request) -> web.FileResponse:
    """
    Start a job fetching image annotations.

    The job's callback will send the document to the user/room via websocket
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)
    user_id = (user_data or {}).get("user", user_data.get("account", {})).get("id")

    if not user_id:
        raise PermissionError("Unauthenticated users cannot clip media")

    file: str = str(request.match_info["file"])
    assert "/" not in file, ValueError("The filename cannot contain the character '/'")
    file = os.path.basename(file)

    filepath = os.path.join(RESULTS_USERS, user_id, file)

    # TODO: schedule deletion of the file after serving it
    # see https://stackoverflow.com/a/73313042

    content_disposition = f'attachment; filename="{file}"'
    headers = {
        "content-disposition": content_disposition,
        "content-length": f"{os.stat(filepath).st_size}",
    }
    if file.endswith(".zip"):
        headers["content-type"] = "application/zip"
    return web.FileResponse(filepath, headers=headers)


async def document_ids(request: web.Request) -> web.Response:
    """
    Get a dict of doc_id: doc_name

    As usual, it comes back via WS message. Only the first call will
    trigger a new job; subsequent calls get the stored result from config.
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    request_data: dict[str, str] = await request.json()
    room: str = request_data.get("room", "")
    user: str = request_data.get("user", "")
    corpus_id = str(request.match_info["corpus_id"])
    config: Config = request.app["config"]
    schema = config[corpus_id]["schema_path"]
    kind: str = request_data.get("kind", "audio")

    if not authenticator.check_corpus_allowed(
        corpus_id,
        user_data,
        "lcp",
    ):
        raise PermissionError("This user is not authorized to access this corpus")

    if "doc_ids" not in config[corpus_id]:
        job = request.app["query_service"].document_ids(
            schema, int(corpus_id), user, room, config[corpus_id], kind=kind
        )
        info: dict[str, str] = {"status": "started", "job": job.id}
        return web.json_response(info)

    job_id: str
    doc_ids: JSONObject
    ids: Sequence[Any] = config[corpus_id]["doc_ids"]  # type: ignore
    job_id, doc_ids = ids
    payload: JSONObject = {
        "document_ids": doc_ids,
        "action": "document_ids",
        "user": user,
        "room": room,
        "job": job_id,
        "corpus_id": int(corpus_id),
        "kind": kind,
    }
    await push_msg(
        request.app["websockets"],
        room,
        payload,
        skip=None,
        just=(room, user),
    )
    early: JSONObject = {
        "status": "finished",
        "job": job_id,
        "document_ids": doc_ids,
    }
    return web.json_response(early)

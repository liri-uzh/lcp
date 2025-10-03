"""
corpora.py: /corpora endpoint, returns a dict of corpora available for a given
user and app, and return it as a JSON HTTP response

We use the complete version of this dict as app["config"], so no DB requests
are needed for this request.
"""

import copy
import json
import logging
import os

import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from json.decoder import JSONDecodeError

from .utils import (
    _filter_corpora,
    _remove_sensitive_fields_from_corpora,
    _structure_descriptions,
    get_pending_invites,
)
from .typed import JSONObject

from aiohttp import web
from aiohttp.client_exceptions import ClientOSError
from rq.job import Job
from typing import cast

MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))
MAIL_SERVER = os.getenv("MAIL_SERVER", "")
MAIL_PORT = os.getenv("MAIL_PORT", "50")
MAIL_SUBJECT_PREFIX = os.getenv("MAIL_SUBJECT_PREFIX", "")
MAIL_FROM_EMAIL = os.getenv("MMAIL_FROM_EMAIL", "")


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


async def check_corpus(request: web.Request) -> web.Response:
    """
    Return whether the corpus exists
    """
    authenticator = request.app["auth_class"](request.app)
    try:
        await authenticator.user_details(request)
    except ClientOSError as err:
        return web.json_response({"error": "Failed to log in.", "status": 401})
    corpus_id = request.match_info["corpus_id"]
    ret = {"status": 404, "error": "Corpus not found."}
    if str(corpus_id) in request.app["config"]:
        ret = {"status": 200, "message": "Corpus found."}
    return web.json_response(ret)


async def discard_invites(request: web.Request) -> web.Response:
    """
    Remove the redis key for the invite to this corpus
    """
    authenticator = request.app["auth_class"](request.app)
    try:
        user_data = await authenticator.user_details(request)
    except ClientOSError as err:
        return web.json_response({"error": "Failed to log in.", "status": 401})
    subscriptions = user_data.get("subscription", {}).get("subscriptions", {})
    pending_invites = get_pending_invites(request, subscriptions)
    no_pending_res = {"error": "No pending invites for this user.", "status": 401}
    if not pending_invites:
        return web.json_response(no_pending_res)
    corpus_id = request.match_info["corpus_id"]
    if corpus_id not in pending_invites:
        return web.json_response(no_pending_res)
    request_id = f"request_invite::{corpus_id}"
    request.app["redis"].delete(request_id)
    return web.json_response({"status": 200, "message": "Invitation discarded."})


async def request_invite(request: web.Request) -> web.Response:
    """
    Send an email to the owner of the project of the corpus to request an invite
    """
    authenticator = request.app["auth_class"](request.app)
    try:
        user_data = await authenticator.user_details(request)
    except ClientOSError as err:
        return web.json_response({"error": "Failed to log in.", "status": 401})
    user = cast(dict, user_data.get("user", user_data.get("account", {})))
    user_id = user.get("id")
    user_name = user.get("name", "")
    user_email = user.get("email", "")
    if not user_id:
        return web.json_response(
            {"error": "Could not identify the user.", "status": 401}
        )
    corpus_id = request.match_info["corpus_id"]
    if str(corpus_id) not in request.app["config"]:
        return web.json_response({"status": 401, "message": "Corpus not found."})

    request_id = f"request_invite::{corpus_id}"
    existing_invites = json.loads(request.app["redis"].get(request_id) or "null")
    # if existing_invites and user_email in existing_invites:
    #     return web.json_response(
    #         {"error": "Access to this corpus has already been requested", "status": 401}
    #     )
    corpus = request.app["config"][corpus_id]
    project_id = corpus.get("project_id", "")
    corpus_name = corpus.get(
        "name", corpus.get("shortname", corpus.get("meta", {}).get("name", ""))
    )

    project_users = await authenticator.project_users(request, project_id)

    admin_users = [u for u in project_users.get("registred", []) if u.get("isAdmin")]
    admin_user = admin_users[0]
    if len(admin_users) == 0:
        return web.json_response(
            {"status": 401, "message": "No admin found for the project."}
        )
    elif len(admin_users) > 1:
        non_invited_admins = [u for u in admin_users if not u.get("invitedFromEmail")]
        admin_user = non_invited_admins[0] if non_invited_admins else admin_users[0]

    admin_name = admin_user.get("displayName", "")
    admin_email = admin_user.get("email", "")

    message_html = f"""Hello {admin_name},<br><br>
        The LCP user named "{user_name}" ({user_email}) wants to access the corpus named "{corpus_name}" (ID: {corpus_id}).
        This corpus belongs to a group of corpora of which you are an administrator.
        You can decide to invite {user_name} to the group: they would then have access to all the corpora in this group.
        Should you decide to grant {user_name} access to the group that contains the corpus {corpus_name},
        you can visit LCP and paste the email address {user_email} in the "Permissions" tab of the group's settings,
        and click "Invite".<br><br>

        Kind Regards<br><br>
        LCP"""
    message_plain = f"""Hello {admin_name},\nThe LCP user named "{user_name}" ({user_email}) wants to access the corpus named "{corpus_name}" (ID: {corpus_id}). This corpus belongs to a group of corpora of which you are an administrator. You can decide to invite {user_name} to the group: they would then have access to all the corpora in this group. Should you decide to grant {user_name} access to the group that contains the corpus {corpus_name}, you can visit LCP and paste the email address {user_email} in the "Permissions" tab of the group's settings, and click "Invite".\nKind Regards\nLCP"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"{MAIL_SUBJECT_PREFIX}Invitation request for corpus {corpus_name} [LCP]"
        )
        msg["From"] = MAIL_FROM_EMAIL
        msg["To"] = admin_email
        msg.attach(MIMEText(message_html, "html", "utf-8"))
        msg.attach(MIMEText(message_plain, "plain"))

        s = smtplib.SMTP(MAIL_SERVER, int(MAIL_PORT))
        s.sendmail(MAIL_FROM_EMAIL, [admin_email], msg.as_string())
        s.quit()
    except Exception as e:
        print("Could not send an email.", e)
        print(f"HTML email: {message_html}")

    existing_invites = json.loads(request.app["redis"].get(request_id) or "[]")
    if user_email not in existing_invites:
        existing_invites.append(user_email)
        request.app["redis"].set(request_id, json.dumps(existing_invites))
        # request.app["redis"].expire(request_id, MESSAGE_TTL)
    return web.json_response({"status": 200, "message": "Invitation request sent."})


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
    global_descs: dict = cast(dict, request_data.get("globals", {}))

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
        url=metadata.get("url", ""),
        date=metadata.get("date", ""),
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
    to_store_desc = _structure_descriptions(descriptions)
    to_store_globals = {
        glob_name: {
            k: v["description"]
            for k, v in glob_props.get("keys", {}).items()
            if "description" in v
        }
        for glob_name, glob_props in global_descs.items()
    }
    args_desc = (
        corpora_id,
        to_store_desc,
        to_store_globals,
        request_data.get("lg") or "en",
    )
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


async def corpora_overwrite(request: web.Request) -> web.Response:
    """
    Updates metadata for a given corpus
    """
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)

    corpora_id: int = int(request.match_info["corpora_id"])
    request_data: JSONObject = await request.json()
    overwrite_id: int = int(cast(int, request_data.get("overwrite", -1)) or -1)

    if any(
        not authenticator.check_corpus_allowed(
            str(cid),
            user_data,
            "lcp",
        )
        for cid in (corpora_id, overwrite_id)
    ):
        raise PermissionError(
            f"This user is not authorized to modify this pair of corpora ({corpora_id}, {overwrite_id})"
        )

    corpora = request.app["config"]
    corpus = corpora.get(str(corpora_id))
    assert corpus, ReferenceError(f"Could not find corpus id {corpora_id}")
    to_be_overwritten = corpora.get(str(overwrite_id))
    assert to_be_overwritten, ReferenceError(f"Could not find corpus id {overwrite_id}")

    args_overwrite = (corpora_id, overwrite_id)
    job_overwrite: Job = request.app["query_service"].overwrite_corpus(*args_overwrite)

    info: dict[str, str | list[str]] = {"status": "1", "job": str(job_overwrite.id)}
    return web.json_response(info)

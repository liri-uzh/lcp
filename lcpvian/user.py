import json

from aiohttp import web


def get_pending_invites(request: web.Request, subscriptions: list) -> dict:
    ret = {}
    config = request.app["config"]
    subscriptions_map = {y["id"]: y for x in subscriptions for y in x["profiles"]}
    for cid, corpus in config.items():
        project_id = corpus.get("project_id", "")
        if project_id not in subscriptions_map:
            continue
        if not subscriptions_map[project_id].get("isAdmin"):
            continue
        request_id = f"request_invite::{cid}"
        existing_invites = json.loads(request.app["redis"].get(request_id) or "[]")
        if not existing_invites:
            continue
        corpus_name = corpus.get(
            "name", corpus.get("shortname", corpus.get("meta", {}).get("name", ""))
        )
        ret[cid] = {
            "title": subscriptions_map[project_id].get("title", ""),
            "corpus": {"name": corpus_name, "id": cid},
            "emails": existing_invites,
        }
    return ret


async def user_data(request: web.Request) -> web.Response:
    """
    Returns user data and app settings
    """
    authenticator = request.app["auth_class"](request.app)
    res = await authenticator.user_details(request)
    res["debug"] = request.app["_debug"]
    user_id = res.get("user", {}).get("id")
    if user_id:
        await request.app["query_service"].get_export_notifs(user_id=user_id)
    subscriptions = res.get("subscription", {}).get("subscriptions", {})
    pending_invites = get_pending_invites(request, subscriptions)
    if pending_invites:
        res["pending_invites"] = pending_invites
    return web.json_response(data=res)

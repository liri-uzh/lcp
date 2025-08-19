from aiohttp import web

from .utils import get_pending_invites


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

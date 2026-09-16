from aiohttp import web

from .utils import get_pending_invites
from .tasker import enqueue


async def user_data(request: web.Request) -> web.Response:
    """
    Returns user data and app settings
    """
    authenticator = request.app["auth_class"](request.app)
    res = await authenticator.user_details(request)
    res["debug"] = request.app["_debug"]
    user_id = res.get("user", {}).get("id")
    if user_id:
        # Add a 1s delay because websockets communication can take some time to set up
        await enqueue(
            "export.export_notifs", user_id=user_id, delay=1.0, queue="internal"
        )
    subscriptions = res.get("subscription", {}).get("subscriptions", {})
    pending_invites = get_pending_invites(request, subscriptions)
    if pending_invites:
        res["pending_invites"] = pending_invites
    return web.json_response(data=res)

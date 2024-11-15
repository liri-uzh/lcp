from aiohttp import web


async def user_data(request: web.Request) -> web.Response:
    """
    Returns user data and app settings
    """
    authenticator = request.app["auth_class"](request.app)
    res = await authenticator.user_details(request)
    res["debug"] = request.app["_debug"]
    return web.json_response(data=res)

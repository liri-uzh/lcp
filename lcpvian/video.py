from aiohttp import web


async def video(request: web.Request) -> web.Response:
    authenticator = request.app["auth_class"](request.app)
    user_data: dict = await authenticator.user_details(request)
    corpora = [i.strip() for i in request.rel_url.query["corpora"].split(",")]
    if not all(
        authenticator.check_corpus_allowed(c, user_data, "videoscope") for c in corpora
    ):
        raise PermissionError("User is not allowed to access corpus videos")
    out = {}
    for corpus in corpora:
        try:
            paths = request.app["corpora"][corpus]["videos"]
        except (AttributeError, KeyError):
            paths = [f"{corpus}.mp4"]
        out[corpus] = paths
    return web.json_response(out)

"""
project.py: endpoints for project management
"""

from aiohttp import web

from .authenticate import Authentication


async def project_create(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    request_data: dict[str, str] = await request.json()
    keys = ["title", "startDate", "finishDate", "description", "additionalData"]
    project_data = {k: request_data[k] for k in keys}
    project_data["unit"] = "----"  # leave it for now, need to be changed in LAMa
    res = await authenticator.project_create(request, project_data)
    return web.json_response(res)


async def project_update(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    request_data: dict[str, str] = await request.json()
    keys = ["title", "startDate", "finishDate", "description", "additionalData"]
    project_data = {k: request_data[k] for k in keys}
    project_data["unit"] = "----"  # leave it for now, need to be changed in LAMa
    res = await authenticator.project_update(request, request_data, project_data)
    return web.json_response(res)


async def project_user_update(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    request_data: dict[str, str] = await request.json()
    project_id: str = request.match_info["project"]
    user_id: str = request.match_info["user"]
    keys = ["projectId", "userId", "active", "admin"]
    user_data = {k: request_data[k] for k in keys if k in request_data}
    res = await authenticator.project_user_update(
        request, project_id, user_id, user_data
    )
    return web.json_response(res)


async def project_api_create(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    project_id: str = request.match_info["project"]
    res = await authenticator.project_api_create(request, project_id)
    return web.json_response(res)


async def project_api_revoke(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    apikey_id: str = request.match_info["key"]
    project_id: str = request.match_info["project"]
    res = await authenticator.project_api_revoke(request, project_id, apikey_id)
    return web.json_response(res)


async def project_users(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    project_id: str = request.match_info["project"]
    res = await authenticator.project_users(request, project_id)
    return web.json_response(res)


async def project_users_invite(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    request_data: dict[str, str] = await request.json()
    project_id: str = request.match_info["project"]
    res = await authenticator.project_users_invite(
        request, project_id, request_data["emails"]
    )
    return web.json_response(res)


async def project_users_invitation_remove(request: web.Request) -> web.Response:
    authenticator: Authentication = request.app["auth_class"](request.app)
    invitation_id: str = request.match_info["invitation"]
    res = await authenticator.project_users_invitation_remove(request, invitation_id)
    return web.json_response(res)

"""
check-file-permissions.py: endpoint for telling FE whether user has permission
for a given resource
"""

from typing import Any, cast

from aiohttp import web
from yarl import URL

from .utils import _lama_user_details


async def check_file_permissions(request: web.Request) -> web.Response:
    """
    Returns if user has access to file
    """
    msg, status = ("Error", 460)
    profiles_id: set[str] = set()
    uri: str = request.headers.get("X-Request-Uri", "")

    user_details_lama = await _lama_user_details(request.headers)
    sub = cast(dict[str, Any], user_details_lama["subscription"])
    subs = cast(list[dict[str, Any]], sub["subscriptions"])
    for subscription in subs:
        for profile in subscription["profiles"]:
            profiles_id.add(profile["id"])

    profiles = cast(list[dict[str, Any]], user_details_lama.get("publicProfiles", []))
    for public_profile in profiles:
        profiles_id.add(public_profile["id"])

    profile_id: str = ""
    if uri and user_details_lama:
        profile_id = URL(uri).parts[-2]
        if profile_id in profiles_id:
            msg, status = ("OK", 200)
        elif not profile_id:
            msg, status = ("Invalid query", 464)
        elif profile_id not in profiles_id:
            msg, status = ("No permission", 465)
    elif not user_details_lama:
        msg, status = ("Invalid user", 461)

    return web.Response(body=msg, status=status)

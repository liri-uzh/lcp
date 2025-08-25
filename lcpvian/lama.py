"""
utils.py: all miscellaneous helpers and tools used by backend
"""

import os

from collections.abc import Mapping
from typing import Any

try:
    from aiohttp import web, ClientSession
except ImportError:
    from aiohttp import web
    from aiohttp.client import ClientSession

from .typed import (
    Headers,
    JSONObject,
)
from .utils import _general_error_handler


def _extract_lama_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """
    Create needed headers from existing headers
    """
    retval = {
        "X-API-Key": os.environ["LAMA_API_KEY"],
        "X-Remote-User": headers.get("X-Remote-User"),
        "X-Display-Name": (
            headers["X-Display-Name"] if headers.get("X-Display-Name") else ""
        ),
        "X-Edu-Person-Unique-Id": headers.get("X-Edu-Person-Unique-Id"),
        "X-Home-Organization": headers.get("X-Home-Organization"),
        "X-Schac-Home-Organization": headers.get("X-Schac-Home-Organization"),
        "X-Persistent-Id": headers.get("X-Persistent-Id"),
        "X-Given-Name": headers["X-Given-Name"] if headers.get("X-Given-Name") else "",
        "X-Surname": headers["X-Surname"] if headers.get("X-Surname") else "",
        "X-Principal-Name": headers.get("X-Principal-Name"),
        "X-Mail": headers.get("X-Mail"),
        "X-Shib-Identity-Provider": headers.get("X-Shib-Identity-Provider"),
    }
    return {k: v for k, v in retval.items() if v}


async def _lama_user_details(headers: Headers) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """
    url = f"{os.environ['LAMA_API_URL']}/user/details/v2"
    async with ClientSession() as session:
        async with session.post(url, data=_extract_lama_headers(headers)) as resp:
            jso: JSONObject = await resp.json()
            jso["max_kwic"] = int(os.getenv("DEFAULT_MAX_KWIC_LINES", 9999))
            return jso


async def _lama_project_user_update(
    headers: Headers, project_id: str, user_id: str, data: dict
) -> JSONObject:
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}/account/{user_id}/modify"
    async with ClientSession() as session:
        async with session.post(
            url, json=data, headers=_extract_lama_headers(headers)
        ) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_invitation_remove(headers: Headers, invitation_id: str) -> JSONObject:
    url = f"{os.environ['LAMA_API_URL']}/invitation/{invitation_id}/remove"
    async with ClientSession() as session:
        async with session.post(url, headers=_extract_lama_headers(headers)) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_invitation_add(
    headers: Headers, project_id: str, invitation_data: dict
) -> JSONObject:
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}/invitation/add"
    async with ClientSession() as session:
        async with session.post(
            url, json=invitation_data, headers=_extract_lama_headers(headers)
        ) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_project_check_title(headers: Headers, title_json: dict) -> JSONObject:
    url = f"{os.environ['LAMA_API_URL']}/profile/check-title"
    async with ClientSession() as session:
        async with session.post(
                url, json=title_json, headers=_extract_lama_headers(headers)
            ) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_project_users(headers: Headers, project_id: str) -> JSONObject:
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}/accounts"
    async with ClientSession() as session:
        async with session.get(url, headers=_extract_lama_headers(headers)) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_project_create(
    headers: Headers, project_data: dict[str, str]
) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """
    url = f"{os.environ['LAMA_API_URL']}/profile"
    async with ClientSession() as session:
        async with session.post(
            url, json=project_data, headers=_extract_lama_headers(headers)
        ) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def _lama_project_update(
    headers: Headers, project_id: str, project_data: dict[str, str]
) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}"
    async with ClientSession() as session:
        async with session.post(
            url, headers=_extract_lama_headers(headers), json=project_data
        ) as resp:
            jso: JSONObject = await resp.json(content_type=None)
            return jso


async def _lama_api_create(headers: Headers, project_id: str) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}/api/create"
    async with ClientSession() as session:
        async with session.post(url, headers=_extract_lama_headers(headers)) as resp:
            jso: JSONObject = await resp.json(content_type=None)
            return jso


async def _lama_api_revoke(
    headers: Headers, project_id: str, apikey_id: str
) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """
    url = f"{os.environ['LAMA_API_URL']}/profile/{project_id}/api/{apikey_id}/revoke"
    data = {"comment": "Revoked by user"}
    async with ClientSession() as session:
        async with session.post(
            url, headers=_extract_lama_headers(headers), json=data
        ) as resp:
            jso: JSONObject = await resp.json(content_type=None)
            return jso


async def _lama_check_api_key(headers: Headers) -> JSONObject:
    """
    Get details about a user via their API key
    """
    url = f"{os.environ['LAMA_API_URL']}/profile/api/check"
    key = headers["X-API-Key"]
    secret = headers["X-API-Secret"]
    api_headers = {"X-API-Key": key, "X-API-Secret": secret}
    async with ClientSession() as session:
        async with session.post(url, headers=api_headers) as resp:
            jso: JSONObject = await resp.json()
            return jso


async def handle_lama_error(exc: Exception, request: web.Request) -> None:
    """
    If we get a connectionerror when trying to reach lama...
    """
    await _general_error_handler("unregistered", exc, request)

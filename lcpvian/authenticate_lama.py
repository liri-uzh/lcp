from aiohttp import web
from os import getenv
from typing import Any, cast
from yarl import URL

from .authenticate import Authentication
from .configure import CorpusConfig
from .lama import (
    _lama_user_details,
    _lama_project_user_update,
    _lama_invitation_remove,
    _lama_invitation_add,
    _lama_project_users,
    _lama_project_create,
    _lama_project_update,
    _lama_api_create,
    _lama_api_revoke,
    _lama_check_api_key,
)
from .typed import JSONObject, TypeAlias

subtype: TypeAlias = list[dict[str, str]]

SUPER_ADMINS = getenv("SUPER_ADMINS", "").split(" ")


# Authentication class used at LiRI with the Lama system
class Lama(Authentication):

    def __init__(self, app: web.Application) -> None:
        super().__init__(app)

    ## Check methods

    async def check_file_permissions(self, request: web.Request) -> tuple[str, int]:
        msg, status = ("Error", 460)
        profiles_id: set[str] = set()
        uri: str = request.headers.get("X-Request-Uri", "")

        user_details_lama = await _lama_user_details(request.headers)
        sub = cast(dict[str, Any], user_details_lama["subscription"])
        subs = cast(list[dict[str, Any]], sub["subscriptions"])
        for subscription in subs:
            for profile in subscription["profiles"]:
                profiles_id.add(profile["id"])

        profiles = cast(
            list[dict[str, Any]], user_details_lama.get("publicProfiles", [])
        )
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

        return (msg, status)

    def check_corpus_allowed(
        self,
        corpus_id: str,
        user_data: JSONObject | None,
        app_type: str = "",
        get_all: bool = False,
    ) -> bool:

        corpus: CorpusConfig = self.app["config"][corpus_id]

        ids: set[str] = set()
        if isinstance(user_data, dict):
            user_id = cast(dict, user_data.get("user", {})).get("id", "")
            if user_id in SUPER_ADMINS:
                return True

            subs = cast(dict[str, subtype], user_data.get("subscription", {}))
            sub = subs.get("subscriptions", [])
            for s in sub:
                ids.add(s["id"])
                # Hack to support responses from both user_details and check_api_key
                for p in s.get("profiles", []):
                    if "id" not in p:
                        continue
                    ids.add(cast(dict, p)["id"])

            for proj in cast(list[dict[str, Any]], user_data.get("publicProfiles", [])):
                ids.add(proj["id"])

        ids.add("all")

        if get_all is False and not [
            project_id for project_id in corpus.get("projects", {}) if project_id in ids
        ]:
            return False
        idx = str(corpus_id)
        if idx == "-1":
            return True
        data_type: str = ""
        for slot in cast(dict, corpus).get("meta", {}).get("mediaSlots", {}).values():
            if data_type == "video":
                continue
            data_type = slot.get("mediaType", "")
        if get_all or app_type in ("lcp", "catchphrase"):
            return True
        if app_type == "videoscope" and data_type in ["video"]:
            return True
        if app_type == "soundscript" and data_type in ["audio", "video"]:
            return True

        return False

    ## JSON responses to GET requests

    async def user_details(self, request: web.Request) -> JSONObject:
        user_details_lama = await _lama_user_details(request.headers)
        # TODO: move this to LAMA directly
        user_id = cast(dict, user_details_lama.get("user", {})).get("id", "")
        if user_id in SUPER_ADMINS:
            cast(dict, user_details_lama["user"])["superAdmin"] = True
        else:
            cast(dict, user_details_lama["user"]).pop("superAdmin", "")
        return user_details_lama

    async def project_users(self, request: web.Request, project_id: str) -> JSONObject:
        res = await _lama_project_users(request.headers, project_id)
        return res

    async def check_api_key(self, request) -> JSONObject:
        ret = await _lama_check_api_key(request.headers)
        return ret

    ## Handle creation, update and removal of projects and users

    async def project_create(
        self, request: web.Request, project_data: dict[str, str]
    ) -> JSONObject:
        res = await _lama_project_create(request.headers, project_data)
        return res

    async def project_update(
        self,
        request: web.Request,
        request_data: dict[str, str],
        project_data: dict[str, str],
    ) -> JSONObject:
        res = await _lama_project_update(
            request.headers, request_data["id"], project_data
        )
        return res

    async def project_user_update(
        self,
        request: web.Request,
        project_id: str,
        user_id: str,
        user_data: dict[str, str],
    ) -> JSONObject:
        res = await _lama_project_user_update(
            request.headers, project_id, user_id, user_data
        )
        return res

    async def project_api_create(
        self, request: web.Request, project_id: str
    ) -> JSONObject:
        res = await _lama_api_create(request.headers, project_id)
        return res

    async def project_api_revoke(
        self, request: web.Request, project_id: str, apikey_id: str
    ) -> JSONObject:
        res = await _lama_api_revoke(request.headers, project_id, apikey_id)
        return res

    async def project_users_invite(
        self, request: web.Request, project_id: str, emails: Any
    ) -> JSONObject:
        res = await _lama_invitation_add(
            request.headers, project_id, {"emails": emails}
        )
        return res

    async def project_users_invitation_remove(
        self, request: web.Request, invitation_id: str
    ) -> JSONObject:
        res = await _lama_invitation_remove(request.headers, invitation_id)
        return res

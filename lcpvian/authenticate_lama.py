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
    _lama_project_check_title,
    _lama_project_users,
    _lama_project_create,
    _lama_project_update,
    _lama_api_create,
    _lama_api_revoke,
    _lama_check_api_key,
)
from .typed import JSONObject, TypeAlias
from .utils import _filter_corpora

subtype: TypeAlias = list[dict[str, str]]

SUPER_ADMINS = getenv("SUPER_ADMINS", "").split(" ")


# Authentication class used at LiRI with the Lama system
class Lama(Authentication):

    def __init__(self, app: web.Application) -> None:
        super().__init__(app)

    ## Check methods

    async def check_file_permissions(self, request: web.Request) -> tuple[str, int]:
        uri: str = request.headers.get("X-Request-Uri", "") or ""
        user_details_lama = await _lama_user_details(request.headers)

        if not user_details_lama:
            return ("Invalid user", 461)

        user_data = await self.user_details(request)
        corpora = _filter_corpora(self, request.app["config"], "lcp", user_data)
        allowed_schema_paths = {
            corpus.get("schema_path")
            for corpus_id, corpus in corpora.items()
            if corpus and corpus.get("schema_path")
        }

        if not uri:
            return ("Invalid query", 464)

        try:
            parts = URL(uri).parts
            if len(parts) < 2 or not parts[-2]:
                return ("Invalid query", 464)
            profile_id = parts[-2]
        except Exception:
            return ("Invalid query", 464)

        if profile_id in allowed_schema_paths:
            return ("OK", 200)

        return ("No permission", 465)

    def check_corpus_allowed(
        self,
        corpus_id: str,
        user_data: JSONObject | None,
        app_type: str = "lcp",
        get_all: bool = False,
    ) -> bool:

        corpus: CorpusConfig = self.app["config"][corpus_id]

        ids: set[str] = set()
        if isinstance(user_data, dict):
            user_id = cast(dict, user_data.get("user", {})).get("id", "")
            if user_id and SUPER_ADMINS and user_id in SUPER_ADMINS:
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

    def check_corpus_searchable(
        self,
        corpus_id: str,
        user_data: JSONObject | None,
        app_type: str = "lcp",
        get_all: bool = False,
    ) -> bool:
        allowed = self.check_corpus_allowed(
            corpus_id, user_data, app_type=app_type, get_all=get_all
        )
        if not allowed:
            return False
        corpus: CorpusConfig = self.app["config"][corpus_id]
        auth_required = corpus.get("authRequired")
        if not auth_required:
            return True
        user_data_d: dict = cast(dict, user_data or {})
        user: dict = user_data_d.get("user") or user_data_d.get("account", {})
        if not user.get("id"):
            return False
        is_swissdox = corpus.get("isSwissdox")
        if not is_swissdox:
            return True
        if user.get("swissdoxUser") or user["id"] in SUPER_ADMINS:
            return True
        return False

    ## JSON responses to GET requests

    async def user_details(self, request: web.Request) -> JSONObject:
        user_details_lama: JSONObject
        if "X-API-Key" in request.headers and "X-API-Secret" in request.headers:
            user_details_lama = await _lama_check_api_key(request.headers)
            user_details_lama["user"] = user_details_lama.get("account", {})
        else:
            user_details_lama = await _lama_user_details(request.headers)
        # TODO: move this to LAMA directly
        user_id = cast(dict, user_details_lama.get("user", {})).get("id", "")
        if user_id and SUPER_ADMINS and user_id in SUPER_ADMINS:
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

    async def project_check_title(self, request: web.Request, title: str) -> JSONObject:
        res = await _lama_project_check_title(request.headers, {"title": title})
        return res

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
        self, request: web.Request, project_id: str, emails: Any, byLink: bool = False
    ) -> JSONObject:
        res = await _lama_invitation_add(
            request.headers, project_id, {"emails": emails, "byLink": byLink}
        )
        return res

    async def project_users_invitation_remove(
        self, request: web.Request, invitation_id: str
    ) -> JSONObject:
        res = await _lama_invitation_remove(request.headers, invitation_id)
        return res

from aiohttp import web
from typing import cast

from .configure import CorpusConfig
from .typed import JSONObject, TypeAlias

subtype: TypeAlias = list[dict[str, str]]

# This is just a placeholder -- a proper authentication system needs to take care of this
USER = {
    "id": "00000000-0000-0000-0000-000000000000",
    "displayName": "Foo Bar",
    "name": "Foo Bar",
    "email": "foo@bar.xyz",
    "homeOrganization": "FooBar",
}
PROFILE = {
    "id": "848c1f0f-a1e3-4f6b-93da-4a7b26c6c6d9",
    "project_id": "9d925a5b-f198-49c4-a577-4cddc1cbb78b",
    "title": "Public",
    "institution": "uzh.ch",
    "additionalData": {"public": True},
}
USERS_AND_PROFILES = {
    "user": USER,
    "subscription": {"subscriptions": []},
    "publicProfiles": [PROFILE],
}


# Default authentication class
# see authenticate_lama.py for an effective implementation
class Authentication:

    def __init__(self, app: web.Application) -> None:
        self.app = app
        # self.all_corpora = app.all_corpora

    def basic(self):
        pass

    ## Check methods

    # Return (status_string, status_code) given a web request [async]
    async def check_file_permissions(self, request: web.Request) -> tuple[str, int]:
        return ("OK", 200)

    def check_user_ok(self, user):
        return True

    # Return True/False given a corpus_id, CorpusConfig, user_data and app_type
    def check_corpus_allowed(
        self,
        corpus_id: str,
        user_data: JSONObject | None,
        app_type: str = "",
        get_all: bool = False,
    ) -> bool:
        return True

    def check_corpus_searchable(
        self,
        corpus_id: str,
        user_data: JSONObject | None,
        app_type: str = "lcp",
        get_all: bool = False,
    ) -> bool:
        return self.check_corpus_allowed(
            corpus_id, user_data, app_type=app_type, get_all=get_all
        )

    ## JSON responses to GET requests

    async def user_details(self, request: web.Request) -> JSONObject:
        return cast(JSONObject, USERS_AND_PROFILES)

    async def project_users(self, request: web.Request, project_id: str) -> JSONObject:
        return {"registered": [], "invited": []}

    async def check_api_key(self, request) -> JSONObject:
        ret = cast(
            JSONObject,
            {
                "account": USER,
                "profile": PROFILE,
            },
        )
        return ret

    ## Handle creation, update and removal of projects and users

    async def project_create(
        self, request: web.Request, project_data: dict[str, str]
    ) -> JSONObject:
        ret: JSONObject = cast(
            JSONObject, {"status": True, "id": PROFILE["id"], "title": PROFILE["title"]}
        )
        return ret

    async def project_update(
        self,
        request: web.Request,
        request_data: dict[str, str],
        project_data: dict[str, str],
    ) -> JSONObject:
        return {}

    async def project_user_update(
        self,
        request: web.Request,
        project_id: str,
        user_id: str,
        user_data: dict[str, str],
    ) -> JSONObject:
        return {}

    async def project_api_create(
        self, request: web.Request, project_id: str
    ) -> JSONObject:
        return {}

    async def project_api_revoke(
        self, request: web.Request, project_id: str, apikey_id: str
    ) -> JSONObject:
        return {}

    async def project_users_invite(
        self, request: web.Request, project_id: str, emails, byLink: bool = False
    ) -> JSONObject:
        return {}

    async def project_users_invitation_remove(
        self, request: web.Request, invitation_id: str
    ) -> JSONObject:
        return {}

    def query(self, corpora):
        # self.check_user_ok()
        # for c in self.all_corpora:
        #     pass
        # assert c in user.projects
        pass

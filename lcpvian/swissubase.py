import os
from .typed import JSONObject

try:
    from aiohttp import web, ClientSession
except ImportError:
    from aiohttp import web
    from aiohttp.client import ClientSession

# from .callbacks import _general_failure

SWISSUBASE_BASE_URL = os.environ.get("SWISSUBASE_API_URL", "https://demo.swissubase.ch/api")


async def swissubase_check_api(request: web.Request) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """

    request_data = await request.json()
    access_token = request_data.get("accessToken")

    # When accessToken is hidden (less then 20 chars), get the original one from the config
    if len(access_token or "") < 20:
        corpus_id = str(request_data.get("corpusId"))
        corpora = request.app["config"]
        corpus = corpora.get(corpus_id)
        access_token = (
            corpus.get("meta", {})
            .get("swissubase", {})
            .get("apiAccessToken")
            if corpus else None
        )

    if not access_token:
        return web.json_response(
            {"error": "No valid access token provided", "status": 400}
        )

    url = f"{SWISSUBASE_BASE_URL}/v2/datasets/?requestedListScope=owner"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            jso: JSONObject = await resp.json()
            valid_project = False
            if resp.status == 200:
                for item in jso.get("items"):
                    if str(item.get("studyReferenceNumber")) == request_data.get("projectId"):
                        valid_project = True
                        break
            return web.json_response(data={
                "data": jso,
                "hasProject": valid_project,
                "status": resp.status
            })


async def swissubase_submit(request: web.Request) -> JSONObject:
    """
    todo: not tested yet, but the syntax is something like this
    """

    request_data = await request.json()
    # print("REQUEST DATA", request_data)

    corpus_id = str(request_data.get("corpusId"))
    corpora = request.app["config"]
    corpus = corpora.get(corpus_id)
    swissubase_json = corpus.get("meta", {}).get("swissubase", {}) if corpus else None
    access_token = (
        swissubase_json.get("apiAccessToken")
        if swissubase_json else None
    )

    url = f"{SWISSUBASE_BASE_URL}/v2/datasets/"
    headers = {"Authorization": f"Bearer {access_token}"}

    jso = {
        "parentIdentifier": swissubase_json.get("projectId"),
        "languageCode": swissubase_json.get("datasetLanguage"),
        # We need to clean up the empty titles
        "title": {k: v for k, v in swissubase_json.get("datasetTitle").items() if v != ""},
        "requestDOI": True if swissubase_json.get("requestDoi") is True or swissubase_json.get("requestDoi") == "true" else False,
        "description": swissubase_json.get("datasetDescription"),
        # "dataUrl": f"https://catchphrase.linguistik.uzh.ch/query/{corpus_id}/x",
        "documentationRemarks": swissubase_json.get("documentationRemarks"),
        "versionNotes": swissubase_json.get("versionNote"),
        "domainSpecificMetadata": [{
            "configBlockId": 1,
            "jsonBlock": {
                "keywords": swissubase_json.get("keywords"),
                "resourceDescription": swissubase_json.get("resourceDescription"),
                "resourceType": swissubase_json.get("resourceType"),
                "validationInfo": swissubase_json.get("validationInformation")
                }
            }
        ]
    }

    async with ClientSession() as session:
        async with session.post(url, headers=headers, json=jso) as resp:
            jso: JSONObject = await resp.json()
            return web.json_response(data={"data": jso, "status": resp.status})

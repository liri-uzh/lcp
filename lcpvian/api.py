import json
import os

try:
    from aiohttp import ClientSession
except ImportError:
    from aiohttp.client import ClientSession

from .typed import JSONObject


async def corpora(app_type: str = "all") -> JSONObject:
    """
    Helper to quickly show corpora in app
    """
    from dotenv import load_dotenv

    load_dotenv(override=True)

    headers: JSONObject = {}
    jso = {"appType": app_type, "all": True}

    url = f"http://localhost:{os.environ['AIO_PORT']}/corpora"
    async with ClientSession() as session:
        async with session.post(url, headers=headers, json=jso) as resp:
            result: JSONObject = await resp.json()
            return result


async def query(corpus: int, query: str) -> None:
    """
    Run a query and get results from websocket
    """
    sock_url = f"http://localhost:{os.getenv('AIO_PORT', 9090)}/ws"
    query_url = f"http://localhost:{os.getenv('AIO_PORT', 9090)}/query"
    async with ClientSession() as session:
        async with session.ws_connect(sock_url) as ws:
            msg = {"user": "api", "room": "api", "action": "joined"}
            await ws.send_json(msg)

            from textwrap import dedent

            headers: JSONObject = {}

            jso = {
                "user": "api",
                "room": "api",
                "appType": "lcp",
                "languages": ["en"],
                "total_results_requested": 100,
                "corpora": [corpus],
                "query": dedent(query),
            }

            async with session.post(query_url, headers=headers, json=jso) as resp:
                result: JSONObject = await resp.json()
                print(f"Query submission:\n{json.dumps(result, indent=4)}\n\n")

            async for message in ws:
                payload = message.json()
                print(f"Query data:\n{json.dumps(payload, indent=4)}\n")
                if payload["status"] != "partial":
                    msg = {"user": "api", "room": "api", "action": "left"}
                    await ws.send_json(msg)
                    return None
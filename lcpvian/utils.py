"""
utils.py: all miscellaneous helpers and tools used by backend
"""

import asyncio
import json
import logging
import numpy as np
import os
import re
import shutil
import traceback
import uuid

from dotenv import load_dotenv
from asyncpg import Connection, Range, Box
from collections import Counter
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from datetime import date, datetime
from hashlib import md5
from io import BytesIO
from typing import Any, cast, TypeAlias
from rq.registry import FinishedJobRegistry

from aiohttp import web

# here we remove __slots__ from these superclasses because mypy can't handle them...
from redis import Redis as RedisConnection

from redis._parsers import _AsyncHiredisParser, _AsyncRESP3Parser  # type: ignore

from redis.utils import HIREDIS_AVAILABLE

DefaultParser: Any

if HIREDIS_AVAILABLE:
    DefaultParser = _AsyncHiredisParser
else:
    DefaultParser = _AsyncRESP3Parser

ParserClass = DefaultParser

from rq.command import PUBSUB_CHANNEL_TEMPLATE
from rq.connections import get_current_connection
from rq.job import Job

from .authenticate import Authentication

# from .callbacks import _general_failure
from .configure import CorpusConfig, CorpusTemplate
from .typed import (
    Config,
    JSON,
    JSONObject,
    MainCorpus,
    ObservableDict,
    ObservableList,
    _serialize_observable,
    SentJob,
    Websockets,
)
from .abstract_query.utils import SQLCorpus, sql_str

CSV_DELIMITERS = [",", "\t"]
CSV_QUOTES = ['"', "\b"]

QUERY_TTL = int(os.getenv("QUERY_TTL", 5000))

RESULTS_DIR = os.getenv("RESULTS", "results")

PUBSUB_CHANNEL = PUBSUB_CHANNEL_TEMPLATE % "lcpvian"

PSQL_NAMEDATALEN = int(os.getenv("PSQL_NAMEDATALEN", 64))

TRUES = {"true", "1", "y", "yes"}
FALSES = {"", "0", "null", "none"}

MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))

# The query in get_config is complex because we inject the possible values of the global attributes in corpus_template
CONFIG_SELECT = """
mc.corpus_id,
mc.name,
mc.current_version,
mc.version_history,
mc.description,
mc.corpus_template::jsonb || a.glob_attr::jsonb AS corpus_template,
mc.schema_path,
mc.token_counts,
mc.mapping,
mc.enabled,
mc.sample_query,
mc.project_id::text
"""
CONFIG_JOIN = """CROSS JOIN
(SELECT
    json_build_object('glob_attr', jsonb_object_agg(
        t4.typ,
        case
            when array_length(t4.labels,1)=1 then to_json(t4.labels[1])
            else to_json(t4.labels)
        end
    )) AS glob_attr
    FROM
        (SELECT
            pg_type.typname AS typ,
            array_agg(pg_enum.enumlabel) AS labels
            FROM pg_enum
            JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
            JOIN
                (SELECT
                    DISTINCT t2each.key AS typname
                    FROM
                        (SELECT
                            t1each.key AS layer,
                            t1each.value->>'attributes' AS attributes
                            FROM
                                (SELECT corpus_template->>'layer' AS lay FROM main.corpus) t1,
                                json_each(t1.lay::json) t1each
                        ) t2,
                        json_each(t2.attributes::json) t2each
                    WHERE
                        t2each.value->>'isGlobal' = 'true'
                ) t3 ON t3.typname = pg_type.typname
            GROUP BY typ
        ) t4
) a
"""

META_QUERY = """SELECT
    {selects_formed}
FROM
    preps
    {joins_formed}
GROUP BY
    {group_by_formed}"""
slb = r"[\s\n]+"
META_QUERY_REGEXP = rf"""SELECT
    -2::int2 AS rstype,{slb}((.+ AS .+)+?)
FROM(.|{slb})+
"""

LR = "{}"


def _futurecb(
    job: Job,
    connection: RedisConnection,
    result: dict | None = None,
) -> None:
    """
    Fetch msg_id from the job's meta and sends it publish_msg
    Will be picked up in socks.py, which will resolve the future
    """
    msg_id = cast(dict, job.get_meta(refresh=True)).get("msg_id", "")
    jso = json.dumps(result, cls=CustomEncoder)
    return _publish_msg(connection, jso, msg_id)


# Custom class to add a `job` attribute
class CustomFuture(asyncio.Future):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job: Job  # type: ignore


class LCPApplication(web.Application):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._keys: dict[str, web.AppKey] = {}
        return None

    def addkey(self, name: str, kind: Any, value: Any) -> None:
        key: web.AppKey = web.AppKey(name, kind)
        self[key] = value
        self._keys[name] = key
        return None

    def __getitem__(self, a: str | web.AppKey) -> Any:
        if a in self._keys:
            assert isinstance(a, str)
            return self[self._keys[a]]
        return super().__getitem__(a)


class Interrupted(Exception):
    """
    Used when a user interrupts a query from frontend
    """

    pass


class CustomEncoder(json.JSONEncoder):
    """
    Fix numpy objects and dates, otherwise normal serialisation
    Also handle ranges from postgres
    """

    def default(self, obj: Any) -> JSON:
        if isinstance(obj, bytes):
            return obj.decode("utf-8")
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Range):
            return [obj.lower, obj.upper]
        if isinstance(obj, Box):
            return [obj.low.x, obj.low.y, obj.high.x, obj.high.y]
        if isinstance(obj, (ObservableDict, ObservableList)):
            return obj._serialize()
        if isinstance(obj, (tuple, list)):
            return [_serialize_observable(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _serialize_observable(v) for k, v in obj.items()}
        try:
            default: JSON = json.JSONEncoder.default(self, obj)
        except:
            default = obj
        return default


class Timer:
    def __init__(self, duration):
        self._start = datetime.now()
        self._duration = duration

    def elapsed(self):
        diff = datetime.now() - self._start
        return diff.total_seconds() > self._duration


def load_env() -> None:
    """
    Load .env from ~/lcp/.env if present, otherwise from current dir/dotenv defaults
    """
    ENVFILE = ".env.docker" if os.getenv("IS_DOCKER") else ".env"
    current = os.path.join(os.getcwd(), ".env")
    installed_path = os.path.expanduser("~/lcp/.env")
    loaded = False
    if os.path.isfile(installed_path):
        try:
            load_dotenv(installed_path, override=True)
            print(f"Loaded .env from {installed_path}")
            return None
        except:
            print(f"Could not load {installed_path}...")
    if not loaded:
        load_dotenv(ENVFILE, override=True)
        print(f"Loaded .env from {current}")
    return None


def setup() -> None:
    """
    Command user can run as `lcp-setup` -- right now it just makes a .env

    We could add argparsing, input() based formatting of the .env, etc etc.
    """
    home = os.path.expanduser("~/lcp")
    os.makedirs(home, exist_ok=True)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_ex = os.path.join(root, ".env.example")
    out = os.path.join(home, ".env")
    if not os.path.isfile(out):
        shutil.copyfile(env_ex, out)
        print(
            f"""
            Created: {out} ...
            Edit this file with needed values for the app to run,
            then run `lcp` and `lcp-worker` commands to start app
            """.strip()
        )


def sanitize_filename(filename: str) -> str:
    return re.sub(r"^[ .]|[/<>:\"\\|?*]+|[ .]$", "_", filename)


def sanitize_xml_attribute_name(name: str) -> str:
    # Replace invalid characters with an underscore
    # Invalid characters include anything that is not a valid XML character
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)

    # Ensure name starts with a letter or underscore
    if name and not name[0].isalpha() and name[0] != "_":
        name = "_" + name  # Prepend an underscore if it starts with a digit

    # Additional rule: XML names cannot be a vs reserved name ('xml' in any case)
    if name.lower() == "xml":
        name = "xml_attr"  # Change if it conflicts with reserved name

    return name


def ensure_authorised(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    auth decorator, still wip
    """
    return func


def _check_email(email: str) -> bool:
    """
    Is an email address valid?
    """
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return bool(re.fullmatch(regex, email))


async def _general_error_handler(
    kind: str, exc: Exception, request: web.Request
) -> None:
    """
    Catch exception, log it, try to send ws message
    """
    try:
        request_data = await request.json()
    except json.decoder.JSONDecodeError:
        return None
    tb = ""
    if hasattr(exc, "__traceback__"):
        tb = "".join(traceback.format_tb(exc.__traceback__))
    user = cast(str, request_data.get("user", ""))
    room = cast(str | None, request_data.get("room", None))
    job = str(exc).split("rq:job:")[-1] if kind == "timeout" else ""
    jso = {
        "user": user,
        "room": room,
        "error": str(exc),
        "status": kind,
        "action": kind,
        "traceback": tb,
    }
    msg = f"Warning: {kind}"
    if job:
        msg += f" -- {job}"
        jso["job"] = job
    logging.warning(msg, extra=jso)
    if user:
        connection = request.app["redis"]
        connection.publish(PUBSUB_CHANNEL, json.dumps(jso, cls=CustomEncoder))
    return None


async def handle_timeout(exc: Exception, request: web.Request) -> None:
    """
    If a job dies due to TTL, we send this...
    """
    await _general_error_handler("timeout", exc, request)


async def handle_bad_request(exc: Exception, request: web.Request) -> None:
    """
    If BE raises an HTTPBadRequest error
    """
    await _general_error_handler(str(exc), exc, request)


def _get_redis_obj(connection: RedisConnection, key: str) -> dict[str, Any]:
    obj = json.loads(connection.get(key) or "{}")
    return obj


def _update_redis_obj(
    connection: RedisConnection,
    key: str,
    info: dict[str, Any] = {},
) -> dict[str, Any]:
    obj = json.loads(connection.get(key) or "{}")
    for k, v in info.items():
        obj[k] = v
    connection.set(key, json.dumps(obj, cls=CustomEncoder))
    connection.expire(key, MESSAGE_TTL)
    return obj


def _get_query_info(
    connection: RedisConnection, hash: str = "", job: Job | None = None
) -> dict[str, Any]:
    qi_key = f"query_info::{hash}"
    return _get_redis_obj(connection, qi_key)


def _update_query_info(
    connection: RedisConnection,
    hash: str = "",
    job: Job | None = None,
    info: dict[str, Any] = {},
) -> dict[str, Any]:
    qi_key = f"query_info::{hash}"
    return _update_redis_obj(connection, qi_key, info)


def _get_request(
    connection: RedisConnection, hash: str = "", job: Job | None = None
) -> dict[str, Any]:
    qi_key = f"request::{hash}"
    return _get_redis_obj(connection, qi_key)


def _update_request(
    connection: RedisConnection,
    hash: str = "",
    job: Job | None = None,
    info: dict[str, Any] = {},
) -> dict[str, Any]:
    qi_key = f"request::{hash}"
    return _update_redis_obj(connection, qi_key, info)


async def sem_coro(
    semaphore: asyncio.Semaphore, coro: Awaitable[list[tuple[int | str | bool]]]
) -> list[tuple[int | str | bool]]:
    """
    Stop too many tasks from running at once
    """
    async with semaphore:
        return await coro


async def gather(
    n: int, tasks: list[Coroutine[None, None, Any]], name: str | None = None
) -> list[list[tuple[int | str | bool]]]:
    """
    A replacement for asyncio.gather that runs a maximum of n tasks at once.
    If any task errors, we cancel all tasks in the group that share the same name

    Used exclusively during upload/import right now

    Like asyncio.gather, it returns a list containing the results from the
    coroutine `tasks`,

    If there is an error, we try to cancel all jobs of the same type (name)
    """
    if n > 0:
        semaphore = asyncio.Semaphore(n)
        tsks = [asyncio.create_task(sem_coro(semaphore, c), name=name) for c in tasks]
    else:
        tsks = [asyncio.create_task(c, name=name) for c in tasks]
    try:
        gathered: list[list[tuple[int | str | bool]]] = await asyncio.gather(*tsks)
        return gathered
    except BaseException as err:
        print(f"Error while gathering tasks: {str(err)[:1000]}. Cancelling others...")
        running_tasks = asyncio.all_tasks()
        # Commenting this out for now, otherwise importer.cleanup won't run from the exception catcher
        # current = asyncio.current_task()
        # if current is not None:
        #     try:
        #         current.cancel()
        #     except Exception:
        #         pass
        #     name = current.get_name()
        #     running_tasks.remove(current)
        for task in running_tasks:
            if name is not None and task.get_name() == name:
                task.cancel()
        raise err


async def push_msg(
    sockets: Websockets,
    session_id: str,
    msg: JSONObject | bytes,
    skip: tuple[str | None, str] | None = None,
    just: tuple[str | None, str] | None = None,
) -> None:
    """
    Send JSON websocket message to one or more users/rooms

    A message can be sent to all users by passing an empty string as session_id
    """
    sent_to: set[tuple[str | None, str]] = set()
    for room, users in sockets.items():
        if session_id and room != session_id:
            continue
        for conn, user_id in users:
            if (room, user_id) in sent_to:
                continue
            if skip and (room, user_id) == skip:
                continue
            if just and (room, user_id) != just:
                continue
            try:
                if isinstance(msg, bytes):
                    await conn.send_bytes(msg)
                else:
                    await conn.send_json(msg)
            except ConnectionResetError:
                print(f"Connection reset: {room}/{user_id}")
                pass
            sent_to.add((room, user_id))


def _format_config_query(template: str) -> str:
    """
    Select the appropriate fields from main.corpus
    and inject the possible values of the global attributes in corpus_template
    """
    return template.format(selects=CONFIG_SELECT, join=CONFIG_JOIN)


async def _set_config(payload: JSONObject, app: web.Application) -> None:
    """
    Helper to set the configuration on the app
    """
    # assert needed for mypy
    assert isinstance(payload["config"], dict)
    print(f"Config loaded: {len(payload['config'])} corpora")
    cast(LCPApplication, app).addkey("config", Config, payload["config"])
    payload["action"] = "update_config"
    await push_msg(app["websockets"], "", payload)
    app["redis"].set("app_config", json.dumps(payload["config"]))
    app["redis"].expire("app_config", MESSAGE_TTL)

    return None


@ensure_authorised
async def refresh_config(request: web.Request) -> web.Response:
    """
    Force a refresh of the config via the /config endpoint
    """
    qs = request.app["query_service"]
    job: Job = await qs.get_config(force_refresh=True)
    return web.json_response({"job": str(job.id)})


subtype: TypeAlias = list[dict[str, str]]


def _filter_corpora(
    authenticator: Authentication,
    config: Config,
    app_type: str,
    user_data: JSONObject | None,
    get_all: bool = False,
) -> Config:
    """
    Filter corpora based on app type and user projects
    """
    corpora: dict[str, CorpusConfig] = {
        idx: corpus
        for idx, corpus in config.items()
        if authenticator.check_corpus_allowed(idx, user_data, app_type, get_all)
    }
    return corpora


def _remove_sensitive_fields_from_corpora(corpora: dict) -> dict:
    """
    Remove or obfuscate sensitive fields from corpora configuration, such as SWISSUbase tokens.
    """
    filtered = {}
    for name, config in corpora.items():
        config_copy = config.copy()
        swissubase = config_copy.get("meta", {}).get("swissubase", {})

        token = swissubase.get("apiAccessToken")
        if token:
            swissubase["apiAccessToken"] = f"{token[:3]}...{token[-3:]}"

        filtered[name] = config_copy
    return filtered


def _row_to_value(
    tup: MainCorpus,
    project: str | None = None,
) -> CorpusConfig:
    """
    Take a row of the main.corpus table and make a CorpusConfig dict
    """
    (
        corpus_id,
        name,
        current_version,
        version_history,
        description,
        template,
        schema_path,
        token_counts,
        mapping,
        enabled,
        sample_query,
        project_id,
    ) = tup
    ver = str(current_version)
    corpus_template = cast(CorpusTemplate, template)
    if not enabled:
        print(f"Corpus disabled: {name}={corpus_id}")

    schema_path = schema_path.replace("<version>", ver)
    if not schema_path.endswith(ver):
        schema_path = f"{schema_path}{ver}"
    layer = corpus_template.get("layer", {})
    fc = corpus_template.get("firstClass", {})
    tok = fc.get("token", "")
    cols = [str(k) for k in layer.get(tok, {}).get("attributes", {}).keys()]

    projects: list[str] = corpus_template.get("projects", [])
    if not projects:
        projects = ["all"]
    if project and project not in projects:
        projects.append(project)
    corpus_template["projects"] = projects

    rest = {
        "shortname": name,
        "corpus_id": int(corpus_id),
        "current_version": int(ver) if ver.isnumeric() else ver,
        "version_history": version_history,
        "description": description,
        "schema_path": schema_path,
        "token_counts": token_counts,
        "mapping": mapping,
        "enabled": enabled,
        "segment": fc.get("segment"),
        "token": fc.get("token"),
        "document": fc.get("document"),
        "column_names": cols,
        "sample_query": sample_query,
        "project_id": project_id,
    }

    together = {**corpus_template, **rest}
    return cast(CorpusConfig, together)


def _get_sent_ids(
    associated: str | list[str], total: int, offset: int = 0
) -> list[int] | list[str]:
    """
    Helper to format the query to retrieve sentences: get a list of unique sent
    ids needed in order to create KWIC results
    """
    out: list[int] = []
    conn = get_current_connection()
    job = _get_associated_query_job(associated, conn)
    if job.get_status(refresh=True) in ("stopped", "canceled"):
        raise Interrupted()
    if job.result is None:
        raise Interrupted()
    if not job.result:
        return out
    prev_results = job.result
    seg_ids: set[str | int] = set()
    query_info = _get_query_info(conn, job=job)
    rs = query_info.get("meta_json", {}).get("result_sets", [])
    kwics = set([i for i, r in enumerate(rs, start=1) if r.get("type") == "plain"])
    counts: Counter[int] = Counter()
    to_use: int = next((int(i[0]) for i in prev_results if int(i[0]) in kwics), -2)
    added: Counter[int] = Counter()

    if to_use == -2:
        return out

    for res in prev_results:
        key = int(res[0])
        rest = res[1]
        if key != to_use:
            continue
        counts[key] += 1
        if offset > 0 and counts[key] - 1 < offset:
            continue
        if total >= 0 and added[key] >= total:
            continue
        seg_ids.add(rest[0])
        added[key] += 1

    return cast(list[str] | list[int], list(sorted(seg_ids)))


def _get_associated_query_job(
    depends_on: str | list[str],
    connection: "RedisConnection[bytes]",
) -> Job:
    """
    Helper to find the query job associated with sent job
    """
    if isinstance(depends_on, list):
        depends_on = depends_on[-1]
    depended = Job.fetch(depends_on, connection=connection)
    return depended


def _get_all_jobs_from_hash(
    hash: str,
    connection: "RedisConnection[bytes]",
) -> tuple[list[Job], list[Job], list[Job]]:
    """
    Helper to get all the query, sent and meta jobs from a hash
    """
    query_jobs: list[Job] = []
    sent_jobs: list[Job] = []
    meta_jobs: list[Job] = []

    main_job = Job.fetch(hash, connection=connection)
    finished_jobs = [
        Job.fetch(jid, connection=connection)
        for registry in [
            FinishedJobRegistry(name=x, connection=connection)
            for x in ("query", "background")
        ]
        + [main_job.finished_job_registry]
        for jid in registry.get_job_ids()
    ]
    for j in finished_jobs:
        j_kwargs = cast(dict, j.kwargs)
        if j_kwargs.get("first_job") != hash and j.id != hash:
            continue
        if j_kwargs.get("meta_query"):
            meta_jobs.append(j)
        elif j_kwargs.get("sentences_query"):
            sent_jobs.append(j)
        else:
            query_jobs.append(j)
    query_jobs_sorted = sorted(
        query_jobs, key=lambda j: len(cast(dict, j.kwargs).get("done_batches", []))
    )
    return (query_jobs_sorted, sent_jobs, meta_jobs)


def _get_prep_segment(
    segment_id: str, sentence_jobs: list[Job], first_job: Job
) -> tuple[str, int, list]:
    try:
        sid, s_offset, s_tokens = next(
            r for sj in sentence_jobs for r in sj.result if str(r[0]) == segment_id
        )
    except:
        sid, s_offset, s_tokens = next(
            (si, so, st)
            for msg_id in first_job.meta.get("sent_job_ws_messages", {})
            for si, (so, st) in cast(
                dict,
                json.loads(first_job.connection.get(msg_id) or b"{}"),
            )
            .get("result", {})
            .get("-1", {})
            .items()
            if str(si) == segment_id
        )
    return (sid, s_offset, s_tokens)


def _sanitize_corpus_name(corpus_name: str) -> str:
    cn = re.sub(r"\W", "_", corpus_name)
    cn = re.sub(r"_+", "_", cn)
    return cn.lower()


def _schema_from_corpus_name(corpus_name: str, project_id: str) -> str:
    tmp_name = _sanitize_corpus_name(corpus_name)
    while (
        len(tmp_name) > 1
        and len(
            str.encode(
                schema_name := re.sub(
                    "-", "", re.sub(r"_+", "_", tmp_name + "_" + project_id)
                )
            )
        )
        > PSQL_NAMEDATALEN - 5  # Leave some room for the version suffix
    ):
        tmp_name = tmp_name[0:-1]
    return schema_name


def format_query_params(
    query: str, params: dict[str, int | str]
) -> tuple[str, tuple[int | str, ...]]:
    """
    Helper to allow for sqlalchemy format query with asyncpg
    """
    if isinstance(params, tuple):
        return query, params
    out = []
    n = 1
    if not isinstance(params, dict):
        return query, params
    for k, v in params.items():
        in_query = f":{k}"
        if in_query in query:
            query = query.replace(in_query, f"${n}")
            n += 1
            out.append(v)
    return query, tuple(out)


def range_to_array(sql_ref: str) -> str:
    return f"jsonb_build_array(lower({sql_ref}), upper({sql_ref}))"


def _layer_contains(config: CorpusConfig, parent: str, child: str) -> bool:
    conf_layers: dict = config.get("layer", {})
    child_layer = conf_layers.get(child)
    parent_layer = conf_layers.get(parent)
    if not child_layer or not parent_layer:
        return False
    while parent_layer and (parents_child := parent_layer.get("contains")):
        if parents_child == child:
            return True
        parent_layer = conf_layers.get(parents_child)
    return False


def _get_iso639_3(lang: str) -> str:
    if lang == "en":
        return "eng"
    if lang == "de":
        return "deu"
    if lang == "fr":
        return "fra"
    if lang == "it":
        return "ita"
    if lang == "rm":
        return "roh"
    if lang == "ro":
        return "ron"
    if lang == "gs":
        return "gsw"
    return ""


def _determine_language(batch: str) -> str | None:
    """
    Helper to find language from batch
    """
    batch = batch.rstrip("0123456789")
    if batch.endswith("rest"):
        batch = batch[:-4]
    for lan in ["de", "en", "fr", "ca", "it"]:
        if batch.endswith(f"_{lan}"):
            return lan
    return None


def _get_batch_suffix(batch: str, n_batches: int = 2) -> str:
    if batch and n_batches > 1:
        batchsuffix = re.match(r".+?(\d+|rest)$", batch)
        if batchsuffix:
            return batchsuffix.group(1)
    return "0"


def _get_mapping(layer: str, config: Any, batch: str, lang: str) -> dict[str, Any]:
    if layer.lower() == batch.lower():
        layer = config["firstClass"]["token"]
    mapping: dict = config["mapping"]["layer"].get(layer, {})
    if "partitions" in mapping and lang:
        mapping = mapping["partitions"].get(lang, {})
    return mapping


def _get_table(layer: str, config: Any, batch: str, lang: str) -> str:
    table = _get_mapping(layer, config, batch, lang).get("relation", layer)
    # Use batch suffixes if layer == batch (token) or if we're working with segments
    if layer.lower() == batch.lower() or layer.lower() in (
        config["segment"].lower(),
        config["token"].lower(),
    ):
        token_mapping = _get_mapping(config["token"], config, batch, lang)
        n_batches = token_mapping.get("batches", 1)
        batch_suffix: str = _get_batch_suffix(batch, n_batches=n_batches)
        if table.endswith("<batch>"):
            table = table[:-7]
        table += batch_suffix
    return table


def _get_all_attributes(layer: str, config: Any, lang: str = "") -> dict:
    """
    Look up the config to get all the attributes of a given layer (name + props)
    including those of the passed language partition or all partitions
    """
    if layer not in config["layer"]:
        return {}
    main_attrs: dict = config["layer"][layer].get("attributes", {})
    ret = {
        k: v for k, v in main_attrs.items() if k != "meta" or not isinstance(v, dict)
    }
    if isinstance(main_attrs.get("meta", ""), dict):
        ret.update({k: v for k, v in main_attrs["meta"].items()})
    if config["layer"][layer].get("layerType") == "relation":
        for k, v in main_attrs.items():
            if not v.get("entity", "") in config["layer"]:
                continue
            ret.pop(k, None)
            ret[v.get("name", "")] = v
    partitions = config["mapping"]["layer"].get(layer, {}).get("partitions", {})
    if partitions:
        if lang and lang not in partitions:
            return ret
        lkey = f"{layer}@{lang}"
        if lang and lkey in config["layer"]:
            ret.update({k: v for k, v in _get_all_attributes(lkey, config).items()})
        if not lang:
            ret.update(
                {
                    k: v
                    for lg in partitions
                    for k, v in _get_all_attributes(f"{layer}@{lg}", config).items()
                }
            )
    return ret


def _get_all_labels(json_query: dict | list) -> dict[str, str]:
    """
    Recursively scan the JSON query and return all the label to layer mappings
    """
    ret = {}
    is_list = isinstance(json_query, list)
    for k in json_query:
        v = k if is_list else json_query[k]
        if isinstance(v, dict) and "label" in v:
            ret[v["label"]] = v.get("layer", "")
        if isinstance(v, (dict, list)):
            ret.update(_get_all_labels(v))
    return ret


def _time_remaining(status: str, total_duration: float, use: float) -> float:
    """
    Helper to estimate remaining time for a job
    """
    if status == "finished":
        return 0.0
    if use <= 0.0:
        return 0.0
    timed = (total_duration * (100.0 / use)) - total_duration
    return max(0.0, round(timed, 3))


def _sign_payload(
    payload: dict[str, Any] | JSONObject | SentJob,
    kwargs: dict[str, Any] | SentJob,
) -> None:
    to_export = kwargs.get("to_export")
    kwargs_to_payload_keys = (
        "user",
        "room",
        "total_results_requested",
        "offset",
        "full",
    )
    for k in kwargs_to_payload_keys:
        if k not in kwargs:
            continue
        payload[k] = kwargs[k]  # type: ignore
    if to_export:
        payload["to_export"] = to_export
    else:
        payload.pop("to_export", None)


def _sharepublish_msg(message: JSONObject | str | bytes, msg_id: str) -> None:
    """
    Connect to the shared redis instance (if it exists) and call _publish_msg on it
    """
    redis_shared_db_index = int(os.getenv("REDIS_SHARED_DB_INDEX", -1))
    redis_shared_url = os.getenv(
        "REDIS_SHARED_URL", os.getenv("REDIS_URL", "redis://localhost:6379")
    )

    full_url = (
        redis_shared_url
        if redis_shared_db_index < 0
        else f"{redis_shared_url}/{redis_shared_db_index}"
    )
    shared_connection = RedisConnection.from_url(full_url)
    _publish_msg(shared_connection, message, msg_id)


def _publish_msg(
    connection: "RedisConnection[bytes]", message: JSONObject | str | bytes, msg_id: str
) -> None:
    """
    Store a message with msg_id as key, and notify listener
    """
    if not isinstance(message, (str, bytes)):
        message = json.dumps(message, cls=CustomEncoder)
    connection.set(msg_id, message)
    connection.expire(msg_id, MESSAGE_TTL)
    connection.publish(PUBSUB_CHANNEL, json.dumps({"msg_id": msg_id}))
    return None


def hasher(arg):
    str_arg = json.dumps(arg)
    return md5(str_arg.encode("utf-8")).digest().hex()


def _parent_of(config: CorpusConfig, child: str, parent: str) -> bool:
    return _layer_contains(config, parent, child)


def _is_anchored(entity: dict, config: dict, anchor: str) -> bool:
    if "anchoring" in entity:
        return entity["anchoring"].get(anchor, False)
    if entity.get("contains", "") in config.get("layer", {}):
        return _is_anchored(config["layer"][entity["contains"]], config, anchor)
    return False


def _is_char_anchored(entity: dict, config: dict) -> bool:
    return _is_anchored(entity, config, "stream")


def _is_time_anchored(entity: dict, config: dict) -> bool:
    return _is_anchored(entity, config, "time")


def _is_xy_anchored(entity: dict, config: dict) -> bool:
    return _is_anchored(entity, config, "location")


def _default_tracks(config: CorpusConfig) -> dict:
    ret: dict = {}
    segment: str = config["firstClass"]["segment"]
    ret["layers"] = {segment: {}}
    return ret


def _get_query_batches(
    config: dict,
    languages: list[str],
) -> list[list[str | int]]:
    """
    Get a list of tuples in the format of (batch_suffix, size) to be queried
    """
    out: list[list[str | int]] = []
    all_languages = ["en", "de", "fr", "ca", "it", "rm"]
    all_langs = tuple([f"_{la}" for la in all_languages])
    langs = tuple([f"_{la}" for la in languages])
    batches = config["_batches"]
    for name, size in batches.items():
        stripped = name.rstrip("0123456789")
        if stripped.endswith("rest"):
            stripped = stripped[:-4]
        if not stripped.endswith(langs) and stripped.endswith(all_langs):
            continue
        out.append([name, size])
    return sorted(out, key=lambda x: x[-1])


def get_segment_meta_script(
    config: dict, languages: list[str], batch_name: str
) -> tuple[str, list[str]]:
    # TODO: use sql_str here
    schema = config["schema_path"]
    layers: dict = config["layer"]
    doc: str = config["document"]
    seg: str = config["segment"]
    tok: str = config["token"]
    lang = languages[0] if languages else ""
    seg_table = _get_table(seg, config, batch_name, lang)
    if not seg_table:
        underlang = f"_{lang}" if lang else ""
        seg_table = f"{seg}{underlang}"

    # SEGMENT
    annotations: str = (
        ", annotations"
        if any(p.get("contains", "") == tok for l, p in layers.items() if l != seg)
        else ""
    )
    seg_mapping = _get_mapping(seg, config, batch_name, lang)
    prep_table: str = seg_mapping.get("prepared", {}).get(
        "relation", f"prepared_{seg_table}"
    )
    prep_cte = f"SELECT {seg}_id, id_offset, content{annotations} FROM {schema}.{prep_table} WHERE {seg}_id = ANY(:sids)"

    # META
    has_media = config.get("meta", config).get("mediaSlots", {})
    parents_of_seg = [
        k for k in layers if _parent_of(cast(CorpusConfig, config), seg, k)
    ]
    parents_with_attributes: dict[str, int] = {seg: 1}  # Query the segment layer itself
    parents_with_attributes.update(
        {k: 1 for k in parents_of_seg if layers[k].get("attributes")}
    )
    # Make sure to always include Document in there
    parents_with_attributes[doc] = 1

    selects: dict[str, int] = {}
    group_by: dict[str, int] = {}
    joins: dict[str, dict[str, int]] = {}
    meta_select_labels: dict[str, int] = {}
    seg_stream_ref = ""
    sqlc = SQLCorpus(config, schema, batch_name, lang)
    for layer in parents_with_attributes:
        entity_lab = layer  # .lower()
        entity_ref = sqlc.layer(entity_lab, layer, pointer=True)
        for tab, conds in entity_ref.joins.items():
            conditions = [c for c in conds]
            if tab.endswith(sql_str(" {}", entity_ref.alias)):
                if layer == seg:
                    seg_stream_ref = sqlc.anchor(entity_lab, layer, "stream").ref
                    conditions.insert(
                        0,
                        sql_str(f"{entity_ref.ref} = preps.{LR}", f"{seg.lower()}_id"),
                    )
                else:
                    layer_stream_ref = sqlc.anchor(entity_lab, layer, "stream")
                    conditions.insert(0, f"{layer_stream_ref} @> {seg_stream_ref}")
            joins[tab] = {**joins.get(tab, {}), **{c: 1 for c in conditions}}
        layer_alias = entity_ref.alias
        if not layer_alias.endswith("_id"):
            layer_alias += "_id"
        selects[sql_str(f"{entity_ref.ref} AS {LR}", layer_alias)] = 1
        meta_select_labels[layer_alias] = 1
        for anchor in ("stream", "time", "location"):
            if not _is_anchored(layers[layer], config, anchor):
                continue
            layer_anchor_ref = sqlc.anchor(entity_lab, layer, anchor)
            selects[
                sql_str(f"{layer_anchor_ref.ref} AS {LR}", layer_anchor_ref.alias)
            ] = 1
            meta_select_labels[layer_anchor_ref.alias] = 1
        if layer == doc and has_media:
            doc_media_ref = sqlc.not_attribute(
                entity_lab, layer, "media", cast="::jsonb"
            )
            doc_name_ref = sqlc.not_attribute(entity_lab, layer, "name", cast="::text")
            filt_aliases = (doc_media_ref.alias, doc_name_ref.alias)
            selects = {
                s: 1
                for s in selects
                if not any(s.endswith(sql_str(" AS {}", x)) for x in filt_aliases)
            }
            selects[sql_str(f"{doc_media_ref.ref} AS {LR}", doc_media_ref.alias)] = 1
            selects[sql_str(f"{doc_name_ref.ref} AS {LR}", doc_name_ref.alias)] = 1
            meta_select_labels[doc_media_ref.alias] = 1
            meta_select_labels[doc_name_ref.alias] = 1
        group_by[entity_ref.ref] = 1
        meta_attrs = layers[layer].get("attributes", {}).get("meta", {})
        for attr_name, attr_props in _get_all_attributes(layer, config, lang).items():
            attr_ref = sqlc.attribute(entity_lab, layer, attr_name)
            attr_alias = attr_ref.alias
            is_meta = attr_name in meta_attrs
            if is_meta:
                attr_ref = sqlc.attribute(entity_lab, layer, "meta")
                if not attr_ref.ref.endswith("::jsonb"):
                    attr_ref.ref += "::jsonb"
                attr_alias = f"{layer}_meta"
            for tab, conds in attr_ref.joins.items():
                joins[tab] = {**joins.get(tab, {}), **{c: 1 for c in conds}}
            if attr_props.get("type") == "labels" and not is_meta:
                nbit = attr_props.get("nlabels", 1)
                labels_map = _get_mapping(layer, config, batch_name, lang)
                attr_map = labels_map.get("attributes", {}).get(attr_name, {})
                labels_rel = attr_map.get("name", f"{layer}_labels")
                labels_tab = sql_str("{}.{} {}", schema, labels_rel, attr_ref.alias)
                labels_cond = sql_str(
                    f"get_bit({attr_ref}, {nbit-1}-{LR}.bit) > 0", attr_ref.alias
                )
                joins[labels_tab] = {**joins.get(tab, {}), labels_cond: 1}
                selects[
                    sql_str("array_agg({}.label) AS {}", attr_ref.alias, attr_ref.alias)
                ] = 1
            else:
                selects[sql_str(f"{attr_ref.ref} AS {LR}", attr_alias)] = 1
            meta_select_labels[attr_alias] = 1
            group_by[attr_ref.ref] = 1

    selects_formed = ", ".join(selects)
    # left join = include non-empty entities even if other ones are empty
    joins_formed = f"\n    LEFT JOIN ".join(
        f"{t} ON {' AND '.join(c)}" for t, c in joins.items()
    )
    joins_formed = "" if not joins_formed else f"LEFT JOIN {joins_formed}"
    group_by_formed = ", ".join(group_by)
    meta_script = META_QUERY.format(
        selects_formed=selects_formed,
        joins_formed=joins_formed,
        group_by_formed=group_by_formed,
    )

    # SEGMENTS + META
    preps_annotations = ", preps.annotations" if annotations else ""
    meta_array = ", ".join(sql_str("meta.{}", lb) for lb in meta_select_labels)
    script = f"""WITH preps AS ({prep_cte}),
    meta AS ({meta_script})
SELECT -1::int2 AS rstype, jsonb_build_array(preps.{seg.lower()}_id, preps.id_offset, preps.content{preps_annotations}) FROM preps
UNION ALL
SELECT -2::int2 AS rstype, jsonb_build_array({meta_array}) FROM meta;
    """
    print("segment_meta_script", script)
    return script, [msl for msl in meta_select_labels]


async def copy_to_table(
    connection: Connection,
    table: str,
    source: BytesIO,
    schema: str,
    columns: list[str],
    timeout=0,
    force_delimiter: str | None = None,
    force_quote: str | None = None,
    force_escape: str | None = None,
) -> None:
    if timeout == 0:
        timeout = os.getenv("UPLOAD_TIMEOUT", 300)
    await connection.copy_to_table(
        table,
        source=source,
        schema_name=schema,
        columns=columns,
        delimiter=(force_delimiter or ","),
        quote=(force_quote or '"'),
        escape=(force_escape or force_quote or None),
        format="csv",
        timeout=timeout,
    )
    return None

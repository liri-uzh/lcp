"""
utils.py: all miscellaneous helpers and tools used by backend
"""

import asyncio
import csv
import json
import logging
import math
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
from uuid import uuid4, UUID
from rq import Callback
from rq.exceptions import NoSuchJobError
from rq.registry import FinishedJobRegistry

from aiohttp import web

# here we remove __slots__ from these superclasses because mypy can't handle them...
from redis import Redis as RedisConnection

from redis._parsers import _AsyncHiredisParser, _AsyncRESP3Parser

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
    Batch,
    Config,
    JSON,
    JSONObject,
    MainCorpus,
    SentJob,
    QueryArgs,
    RequestInfo,
    Websockets,
)

CSV_DELIMITERS = [",", "\t"]
CSV_QUOTES = ['"', "\b"]

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
    -2::int2 AS rstype,
    {selects_formed}
FROM
    {froms_formed}
    {joins_formed}
WHERE
    {wheres_formed}
GROUP BY
    {group_by_formed}
;"""
slb = r"[\s\n]+"
META_QUERY_REGEXP = rf"""SELECT
    -2::int2 AS rstype,{slb}((.+ AS .+)+?)
FROM(.|{slb})+
"""


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
        self.job: Job | None = None


class LCPApplication(web.Application):

    def __init__(self, failure_cb: Callable, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._keys: dict[str, web.AppKey] = {}
        # Needed in to_job, pass as an argument to avoid import dependency issues
        self._general_failure = failure_cb
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

    def to_job(self, fn: Callable, *args, **kwargs) -> CustomFuture:
        """
        Send a method to be exected by the worker in the background
        Return a future that resolves to the return value of the method
        """
        fut: CustomFuture = CustomFuture()
        msg_id = str(uuid4())
        self["futures"][msg_id] = fut
        job = self["background"].enqueue(
            fn,
            on_success=Callback(_futurecb, 5000),
            on_failure=Callback(self._general_failure, 5000),
            args=args,
            kwargs=kwargs,
        )
        job.meta["msg_id"] = msg_id
        job.save_meta()
        fut.job = job
        return fut


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
        default: JSON = json.JSONEncoder.default(self, obj)
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


def _get_status(
    query_info: dict,
    request_info: RequestInfo,
    # n_results: int,
    # total_results_requested: int,
    # done_batches: list[Batch],
    # all_batches: list[Batch],
    search_all: bool = False,
    # time_so_far: float = 0.0,
) -> str:
    """
    Is a query finished, or do we need to do another iteration?

        finished: no more batches available
        overtime: query with time limitation ran out of time
        partial: currently fewer than total_results_requested
        satisfied: >= total_results_requested
    """
    n_results = query_info.get("total_results_so_far", 0)
    done_batches = query_info.get("done_batches", [])
    all_batches = query_info.get("all_batches", [])
    time_so_far = query_info.get("total_duration", 0.0)
    total_results_requested = request_info.get("total_results_requested", 0)
    full = request_info.get("full", False)

    if len(done_batches) == len(all_batches):
        return "finished"
    allowed_time = float(os.getenv("QUERY_ALLOWED_JOB_TIME", 0.0))
    too_long: bool = time_so_far > allowed_time
    if allowed_time > 0.0 and search_all and too_long and not full:
        return "overtime"
    if search_all:
        return "partial"
    if total_results_requested in {-1, False, None}:
        return "partial"
    if n_results >= total_results_requested and not full:
        return "satisfied"
    return "partial"


def _get_query_info(
    connection: RedisConnection, hash: str = "", job: Job | None = None
) -> dict[str, Any]:
    if job:
        job = _get_first_job(job, connection)
    if not hash and job:
        hash = job.id
    qi_key = f"query_info_{hash}"
    query_info = json.loads(connection.get(qi_key) or "{}")
    return query_info


def _update_query_info(
    connection: RedisConnection,
    hash: str = "",
    job: Job | None = None,
    info: dict[str, Any] = {},
) -> dict[str, Any]:
    if job:
        job = _get_first_job(job, connection)
    if not hash and job:
        hash = job.id
    qi_key = f"query_info_{hash}"
    query_info = json.loads(connection.get(qi_key) or "{}")
    for k, v in info.items():
        query_info[k] = v
    query_info["hash"] = hash
    connection.set(qi_key, json.dumps(query_info))
    connection.expire(qi_key, MESSAGE_TTL)
    return query_info


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


def _handle_large_msg(strung: str, limit: int) -> list[bytes] | list[str]:
    """
    Before we publish a message to redis pubsub, check if it's larger
    than the pubsub limit. If it is, we break it into chunks, wait between
    each publish, then join them back together on the other side

    strung is a serialised JSON object, return a list str/bytes to send,
    with a wait time determined by redis config in between each
    """
    # just a bit of extra room around our redis hard limit
    buffer = 100

    if limit == -1:
        return [strung]

    enc: bytes = strung.encode("utf-8")

    if len(enc) < limit:
        return [strung]
    cz = limit - buffer
    n_chunks = math.ceil(len(enc) / cz)
    chunks: list[bytes] = [enc[0 + i : cz + i] for i in range(0, len(enc), cz)]
    out: list[bytes] = []
    uu = str(uuid4())[:8]
    for i, chunk in enumerate(chunks, start=1):
        formed = f"#CHUNK#{uu}#{i}#{n_chunks}#".encode("utf-8")
        formed += chunk
        out.append(formed)
    return out


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
        if authenticator.check_corpus_allowed(idx, corpus, user_data, app_type, get_all)
    }
    return corpora


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
    query_info = _get_query_info(connection, job=main_job)
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


def format_meta_lines(
    query: str, result: list[dict[int, str | dict[Any, Any]]]
) -> dict[str, Any] | None:
    if not result:
        return {}
    # replace this with actual upstream handling of column names
    pre_columns = re.match(META_QUERY_REGEXP, query)
    if not pre_columns:
        return None
    columns: list[str] = [
        p.split(" AS ")[1].strip() for p in pre_columns[1].split(", ")
    ]  # [seg_id, layer1, layer2, etc.]
    layers: dict[str, None] = {
        c.split("_")[0]: None for c in columns if not c.endswith("_id")
    }
    formatted: dict[str, Any] = {}
    for res in result:
        seg_id = "0"
        segment: dict[str, dict[Any, Any]] = {layer: {} for layer in layers}
        for n, layer_prop in enumerate(columns):
            if not res[n + 1]:
                continue
            if layer_prop == "seg_id":
                seg_id = cast(str, res[n + 1])
            else:
                m = re.match(rf"^([^_]+)_(.+)$", layer_prop)
                if not m:
                    continue
                layer, prop = m.groups()
                if prop == "meta":
                    meta: str | dict[Any, Any]
                    if isinstance(res[n + 1], str):
                        meta = json.loads(cast(str, res[n + 1]))
                    else:
                        meta = res[n + 1]
                    if not isinstance(meta, dict):
                        continue
                    segment[layer] = {**(segment[layer]), **meta}
                else:
                    if isinstance(res[n + 1], Range):
                        segment[layer][prop] = [
                            cast(Range, res[n + 1]).lower,
                            cast(Range, res[n + 1]).upper,
                        ]
                    elif isinstance(res[n + 1], Box):
                        segment[layer][prop] = [
                            cast(Box, res[n + 1]).low.x,
                            cast(Box, res[n + 1]).low.y,
                            cast(Box, res[n + 1]).high.x,
                            cast(Box, res[n + 1]).high.y,
                        ]
                    elif any(
                        isinstance(res[n + 1], typ)
                        for typ in [int, str, bool, list, tuple, UUID, date]
                    ):
                        segment[layer][prop] = str(res[n + 1])
                    elif isinstance(res[n + 1], dict):
                        segment[layer][prop] = json.dumps(res[n + 1])
        segment = {
            layer: props
            for layer, props in segment.items()
            if props and [x for x in props if x != "id"]
        }
        if not segment:
            continue
        formatted[str(seg_id)] = segment
    return formatted


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


def _get_first_job(job: Job, connection: "RedisConnection[bytes]") -> Job:
    """
    Helper to get the base job from a group of query jobs
    """
    first_job = job
    first_job_id_from_kwargs = cast(dict, job.kwargs).get("first_job")
    if first_job_id_from_kwargs:
        try:
            first_job = Job.fetch(first_job_id_from_kwargs, connection=connection)
        except NoSuchJobError:
            pass
    return first_job


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


def _decide_can_send(
    status: str, is_full: bool, is_base: bool, from_memory: bool
) -> bool:
    """
    Helper to figure out if we can send query message to the user or not

    We don't exit early if we can't send, because we still need to store the
    message and potentially trigger a new job
    """
    if not is_full or status == "finished":
        return True
    elif is_base and from_memory:
        return True
    elif not is_base and not from_memory:
        return True
    return False


def _get_progress(job: Job, query_info: dict, request_info: RequestInfo) -> dict:
    allowed_time = float(os.getenv("QUERY_ALLOWED_JOB_TIME", 0.0))
    do_full = request_info.get("full", False)
    status = _get_status(query_info, request_info)
    total_requested = request_info["total_results_requested"]
    total_found = query_info["total_results_so_far"]
    done_batches = query_info["done_batches"]
    total_words_processed_so_far = sum([x[-1] for x in query_info["done_batches"]]) or 1
    use = total_words_processed_so_far * 100.0 / query_info["word_count"]
    total_duration = query_info.get("total_duration", 0.0)
    time_remaining = _time_remaining(status, total_duration, use)
    ended_at = cast(datetime, job.ended_at)
    started_at = cast(datetime, job.started_at)
    duration: float = round((ended_at - started_at).total_seconds(), 3)
    time_perc = 0.0
    if allowed_time > 0.0 and do_full:
        time_perc = total_duration * 100.0 / allowed_time
    batches_done_string = f"{len(done_batches)}/{len(query_info['all_batches'])}"
    total_words_processed_so_far = sum([x[-1] for x in done_batches]) or 1
    proportion_that_matches = total_found / total_words_processed_so_far
    projected_results = int(query_info["word_count"] * proportion_that_matches)
    if status == "finished":
        projected_results = total_found if do_full else -1
        perc_words = 100.0
        perc_matches = 100.0
        if do_full:
            perc_matches = time_perc
        query_info["percentage_done"] = 100.0
    elif status in {"partial", "satisfied", "overtime"}:
        done_batches = query_info["done_batches"]
        total_words_processed_so_far = sum([x[-1] for x in done_batches]) or 1
        proportion_that_matches = total_found / total_words_processed_so_far
        projected_results = int(query_info["word_count"] * proportion_that_matches)
        if not do_full:
            projected_results = -1
        perc_words = total_words_processed_so_far * 100.0 / query_info["word_count"]
        perc_matches = (
            min(total_found, total_requested) * 100.0 / (total_requested or total_found)
        )
        if do_full:
            perc_matches = time_perc
        query_info["percentage_done"] = round(perc_matches, 3)
    if request_info.get("from_memory"):
        projected_results = query_info["projected_results"]
        perc_matches = query_info["percentage_done"]
        perc_words = query_info["percentage_words_done"]
        total_found = query_info["total_results_so_far"]
        batches_done_string = query_info["batches_done_string"]
        status = query_info["status"]
        total_duration = query_info["total_duration"]
    return {
        "remaining": time_remaining,
        "job": job.id,
        "first_job": query_info.get("hash", ""),
        "user": request_info.get("user", ""),
        "room": request_info.get("room", ""),
        "duration": duration,
        "batches_done": batches_done_string,
        "total_duration": total_duration,
        "projected_results": projected_results,
        "percentage_done": round(perc_matches, 3),
        "percentage_words_done": round(perc_words, 3),
        "total_results_so_far": total_found,
        "action": "background_job_progress",
    }


def _get_total_requested(kwargs: dict[str, Any], job: Job) -> int:
    """
    Helper to find the total requested -- remove this after cleanup ideally
    """
    total_requested = cast(int, kwargs.get("total_results_requested", -1))
    if total_requested > 0:
        return total_requested
    total_requested = cast(dict, job.kwargs).get("total_results_requested", -1)
    if total_requested > 0:
        return total_requested
    return -1


def _get_request_info(connection: RedisConnection, hash: str) -> list[RequestInfo]:
    qas_json = connection.get(f"request_info_{hash}")
    qas = json.loads(qas_json) if qas_json else []
    return qas


def _set_request_info(connection: RedisConnection, request_info: RequestInfo) -> None:
    hash = request_info.get("hash", "")
    all_request_info: list[RequestInfo] = _get_request_info(connection, hash)
    if not next((x for x in all_request_info if x == request_info), None):
        all_request_info.append(request_info)
    qa_key = f"request_info_{hash}"
    connection.set(qa_key, json.dumps(all_request_info))
    timeout = int(os.getenv("QUERY_TIMEOUT", 1000))
    whole_corpus_timeout = int(os.getenv("QUERY_ENTIRE_CORPUS_CALLBACK_TIMEOUT", 99999))
    connection.expire(
        qa_key,
        (
            whole_corpus_timeout
            if any(x.get("full") for x in all_request_info)
            else timeout
        ),
    )


def _update_request_info(
    connection: RedisConnection, request_info: RequestInfo, new_info: RequestInfo
) -> RequestInfo:
    forbidden_keys = QueryArgs.__optional_keys__.union(QueryArgs.__required_keys__)
    all_ris = _get_request_info(connection, request_info["hash"])
    ret_ri: RequestInfo
    for ri in all_ris:
        if ri != request_info:
            continue
        ret_ri = ri
        for k, v in new_info.items():
            assert (
                k not in forbidden_keys
            ), f"Cannot change {k} in a request info after it's been created"
            ri[k] = v  # type: ignore
    qa_key = f"request_info_{hash}"
    connection.set(qa_key, json.dumps(all_ris))
    timeout = int(os.getenv("QUERY_TIMEOUT", 1000))
    whole_corpus_timeout = int(os.getenv("QUERY_ENTIRE_CORPUS_CALLBACK_TIMEOUT", 99999))
    connection.expire(
        qa_key,
        (whole_corpus_timeout if any(x.get("full") for x in all_ris) else timeout),
    )
    return ret_ri


def _delete_request_info(connection: RedisConnection, qi_args: RequestInfo) -> None:
    hash = qi_args.get("hash", "")
    all_request_info: list[RequestInfo] = _get_request_info(connection, hash)
    if not all_request_info:
        return
    all_request_info = [x for x in all_request_info if x != qi_args]
    qa_key = f"request_info_{hash}"
    if not all_request_info:
        connection.delete(qa_key)
        _update_query_info(connection, hash=hash, info={"running": False})
        return
    connection.set(qa_key, json.dumps(all_request_info))
    timeout = int(os.getenv("QUERY_TIMEOUT", 1000))
    whole_corpus_timeout = int(os.getenv("QUERY_ENTIRE_CORPUS_CALLBACK_TIMEOUT", 99999))
    connection.expire(qa_key, whole_corpus_timeout if qi_args.get("full") else timeout)


def _sign_payload(
    payload: dict[str, Any] | JSONObject | SentJob,
    kwargs: dict[str, Any] | RequestInfo | SentJob,
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


def _parent_of(
    current_batch: Batch, config: CorpusConfig, child: str, parent: str
) -> bool:
    if not current_batch:
        raise ValueError("Need batch")
    return _layer_contains(config, parent, child)


def _is_time_anchored(current_batch: Batch, config: CorpusConfig, layer: str) -> bool:
    if not current_batch:
        raise ValueError("Need batch")
    layer_config = config["layer"].get(layer)
    if not layer_config:
        return False
    if "anchoring" in layer_config:
        return layer_config["anchoring"].get("time", False)
    if "contains" in layer_config:
        return _is_time_anchored(
            current_batch,
            config,
            layer_config.get("contains", config["firstClass"]["token"]),
        )
    return False


def _default_tracks(config: CorpusConfig) -> dict:
    ret: dict = {}
    segment: str = config["firstClass"]["segment"]
    ret["layers"] = {segment: {}}
    return ret


def _meta_query(current_batch: Batch, config: CorpusConfig) -> str:
    if not current_batch:
        raise ValueError("Need batch")
    doc = config["document"]
    seg = config["segment"]
    layer_info = config["layer"]
    schema = current_batch[1]
    lang = _determine_language(current_batch[2])
    seg_name = _get_table(seg, config, current_batch[2], lang or "")

    has_media = config.get("meta", config).get("mediaSlots", {})

    parents_of_seg = [
        k for k in layer_info if _parent_of(current_batch, config, seg, k)
    ]
    parents_with_attributes = {
        k: None for k in parents_of_seg if layer_info[k].get("attributes")
    }
    # Make sure to include Document in there, even if it's not a parent of Segment
    if has_media or layer_info[doc].get("attributes"):
        parents_with_attributes[doc] = None

    parents_with_attributes[seg] = None  # Also query the segment layer itself
    selects = [f"s.{seg}_id AS seg_id"]
    froms = [f"{schema}.{seg_name} s"]
    wheres = [f"s.{seg}_id = ANY(:ids)"]
    joins: dict[str, Any] = {}
    group_by = []
    for layer in parents_with_attributes:
        alias = "s" if layer == seg else layer
        layer_mapping = config["mapping"]["layer"].get(layer, {})
        mapping_attrs = layer_mapping.get("attributes", {})
        partitions = None if layer == seg else layer_mapping.get("partitions")
        alignment = {} if layer == seg else layer_mapping.get("alignment", {})
        relation = alignment.get("relation", None)
        if not relation and layer != seg:
            relation = layer_mapping.get("relation", layer.lower())
        if not relation and lang and partitions:
            relation = partitions.get(lang, {}).get("relation")
        prefix_id: str = layer.lower()
        if alignment:
            prefix_id = "alignment"
        # Select the ID
        iddotref = f"{alias}.{prefix_id}_id"
        selects.append(f"{iddotref} AS {layer}_id")
        group_by.append(iddotref)
        joins_later: dict[str, Any] = {}
        attributes: dict[str, Any] = layer_info[layer].get("attributes", {})
        relational_attributes = {
            k: v
            for k, v in attributes.items()
            if mapping_attrs.get(k, {}).get("type") == "relation"
        }
        # Make sure one gets the data in a pure JSON format (not just a string representation of a JSON object)
        selects += [
            f"{alias}.\"{attr}\"{'::jsonb' if attr=='meta' else ''} AS {layer}_{attr}"
            for attr, v in attributes.items()
            if attr not in relational_attributes and v.get("type") != "vector"
        ]
        for attr, v in relational_attributes.items():
            # Quote attribute name (is arbitrary)
            attr_mapping = mapping_attrs.get(attr, {})
            # Mapping is "relation" for dict-like attributes (eg ufeat or agent)
            attr_table = attr_mapping.get("name", "")
            alias_attr_table = f"{layer}_{attr}_{attr_table}"
            attr_table_key = attr_mapping.get("key", attr)
            attr_name = f'"{attr_table_key}"'
            on_cond = f"{alias}.{attr}_id = {alias_attr_table}.{attr_table_key}_id"
            dotref = f"{alias_attr_table}.{attr_name}"
            sel = f"{dotref} AS {layer}_{attr}"
            if v.get("type") == "labels":
                nbit: int = cast(int, attributes[attr].get("nlabels", 1))
                on_cond = (
                    f"get_bit({alias}.{attr}, {nbit-1}-{alias_attr_table}.bit) > 0"
                )
                sel = f"array_agg({alias_attr_table}.label) AS {layer}_{attr}"
            else:
                group_by.append(dotref)
            # Join the lookup table
            joins_later[f"{schema}.{attr_table} {alias_attr_table} ON {on_cond}"] = None
            # Select the attribute from the lookup table
            selects.append(sel)

        # Will get char_range from the appropriate table
        char_range_table: str = alias
        # join tables
        if lang and partitions:
            interim_relation = partitions.get(lang, {}).get("relation")
            if not interim_relation:
                # This should never happen?
                continue
            if alignment and relation:
                # The partition table is aligned to a main document table
                joins[
                    f"{schema}.{interim_relation} {alias}_{lang} ON {alias}_{lang}.char_range @> s.char_range"
                ] = None
                joins[
                    f"{schema}.{relation} {alias} ON {alias}_{lang}.alignment_id = {alias}.alignment_id"
                ] = None
                char_range_table = f"{alias}_{lang}"
            else:
                # This is the main document table for this partition
                joins[
                    f"{schema}.{interim_relation} {layer} ON {alias}.char_range @> s.char_range"
                ] = None
        elif relation:
            joins[
                f"{schema}.{relation} {alias} ON {layer}.char_range @> s.char_range"
            ] = None
        for k in joins_later:
            joins[k] = None
        # Get char_range from the main table
        chardotref = char_range_table + '."char_range"'
        selects.append(f"{chardotref} AS {layer}_char_range")
        group_by.append(chardotref)
        # And frame_range if applicable
        if _is_time_anchored(current_batch, config, layer):
            selects.append(f'{char_range_table}."frame_range" AS {layer}_frame_range')
        # And xy_box if applicable
        if config["layer"].get(layer, {}).get("anchoring", {}).get("location", False):
            selects.append(f'{char_range_table}."xy_box" AS {layer}_xy_box')

    # Add code here to add "media" if dealing with a multimedia corpus
    if has_media:
        selects.append(f"{doc}.media::jsonb AS {doc}_media")

    selects_formed = ", ".join(selects)
    froms_formed = ", ".join(froms)
    wheres_formed = " AND ".join(wheres)
    # left join = include non-empty entities even if other ones are empty
    joins_formed = f"\n    LEFT JOIN ".join(joins)
    joins_formed = "" if not joins_formed else f"LEFT JOIN {joins_formed}"
    group_by_formed = ", ".join(group_by)
    script = META_QUERY.format(
        selects_formed=selects_formed,
        froms_formed=froms_formed,
        joins_formed=joins_formed,
        wheres_formed=wheres_formed,
        group_by_formed=group_by_formed,
    )
    print("meta script", script)
    return script


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

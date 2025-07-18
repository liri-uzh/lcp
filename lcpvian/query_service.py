"""
query_service.py: all database queries not related to a DQD query


PRE-OVERHAUL

query_service.py: control submission of RQ jobs

We use RQ/Redis for long-running DB queries. The QueryService class has a method
for each type of DB query that we need to run (query, sentence-query, upload,
create schema, store query, delete_query, fetch query, etc.). Jobs are run by a dedicated
worker process.

After the job is complete, callback functions can be run by worker for success and
failure. Typically, these callbacks will post-process the data and publish it
to Redis PubSub, which we listen on in the main process so we can send
the data to user via websocket.

Before submitting jobs to RQ/Redis, we can often hash the incoming job data to
create an identifier for the job. If identical input data is provided in a
subsequent job, the same hash will be generated, So, we can check in Redis for
this job ID; if it's available, we can trigger the callback manually, and thus
save ourselves from running duplicate DB queries.
"""

import json
import os
import uuid

from typing import Any, final, cast

from aiohttp import web
from redis import Redis as RedisConnection
from rq import Callback
from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation, NoSuchJobError
from rq.job import Job

from .callbacks import (
    _config,
    _document,
    _document_ids,
    _general_failure,
    _upload_failure,
    _queries,
    _schema,
    _upload,
    _deleted,
)
from .export import _export_notifs
from .jobfuncs import _db_query, _upload_data, _create_schema
from .typed import (
    BaseArgs,
    Config,
    CorpusConfig,
    DocIDArgs,
    JSONObject,
)
from .utils import (
    _default_tracks,
    _format_config_query,
    _set_config,
    hasher,
    range_to_array,
)
from .abstract_query.utils import _get_table, _get_mapping


@final
class QueryService:
    """
    This magic class will handle our queries by alerting you when they are done
    """

    # __slots__: list[str] = ["app", "timeout", "upload_timeout", "query_ttl"]

    def __init__(self, app: web.Application) -> None:
        self.app = app
        self.timeout = int(os.getenv("QUERY_TIMEOUT", 1000))
        self.whole_corpus_timeout = int(
            os.getenv("QUERY_ENTIRE_CORPUS_CALLBACK_TIMEOUT", 99999)
        )
        self.callback_timeout = int(os.getenv("QUERY_CALLBACK_TIMEOUT", 5000))
        self.upload_timeout = int(os.getenv("UPLOAD_TIMEOUT", 43200))
        self.query_ttl = int(os.getenv("QUERY_TTL", 5000))
        self.use_cache = app["_use_cache"]

    def document_ids(
        self,
        schema: str,
        corpus_id: int,
        user: str,
        room: str | None,
        config: dict,
        queue: str = "internal",
    ) -> Job:
        """
        Fetch document id: name data from DB.

        The fetch from cache should not be needed, as on subsequent jobs
        we can get the data from app["config"]
        """
        doc_layer = config.get("document", "document").lower()
        query = f"SELECT {doc_layer}_id, name, media, frame_range FROM {schema}.{doc_layer};"
        kwargs: DocIDArgs = {
            "user": user,
            "room": room,
            "corpus_id": corpus_id,
        }
        hashed = str(hasher((query, corpus_id)))
        job: Job
        if self.use_cache:
            try:
                job = Job.fetch(hashed, connection=self.app["redis"])
                if job and job.get_status(refresh=True) == "finished":
                    _document_ids(job, self.app["redis"], job.result, **kwargs)
                    return job
            except NoSuchJobError:
                pass
        job = self.app[queue].enqueue(
            _db_query,
            on_success=Callback(_document_ids, self.timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            args=(query, {}),
            kwargs=kwargs,
        )
        return job

    def document(
        self,
        schema: str,
        corpus: int,
        doc_id: int,
        user: str,
        room: str | None,
        config: CorpusConfig,
        queue: str = "internal",
    ) -> Job:
        """
        Fetch info about a document from DB/cache
        """
        tracks: dict = cast(dict, config.get("tracks", _default_tracks(config)))
        # assert "tracks" in config, KeyError(
        #     "Couldn't find 'tracks' in the corpus configuration"
        # )
        global_tables: dict = {}
        doc_layer = config.get("document")
        query = f"WITH doc AS (SELECT frame_range FROM {schema}.{doc_layer} WHERE {doc_layer}_id = :doc_id)"
        glob_attrs: dict = cast(dict, config.get("globalAttributes", {}))
        for layer in tracks.get("layers", {}):
            layer_table = _get_table(
                layer, config, "", ""
            )  # no batch and no lang for now
            attributes = config["layer"].get(layer, {}).get("attributes", {})
            attributes_names: dict[str, None] = {k: None for k in attributes}
            mapping = _get_mapping(layer, config, "", "")
            mapping_attrs: dict[str, Any] = mapping.get("attributes", {})
            for k in mapping_attrs:
                attributes_names[k] = None
            crossjoin = ""
            whereand = ""
            lab = layer_table[0]
            selects = ["'frame_range'", range_to_array(f"{lab}.frame_range")]
            if layer.lower() == config.get("segment", "").lower():
                prepared_table = mapping.get("prepared", {}).get(
                    "relation", f"prepared_{layer}"
                )
                crossjoin = f"\n    CROSS JOIN {schema}.{prepared_table} ps"
                whereand = f"\n    AND {lab}.{layer}_id = ps.{layer}_id"
                selects += ["'prepared'", "ps.content"]
            for attr_name in attributes_names:
                attr_type = attributes.get(attr_name, {}).get("type")
                if attr_type in ("labels", "vector"):
                    continue
                mappings = mapping_attrs.get(attr_name, {})
                mapping_type = mappings.get("type")
                name = attr_name
                ref = f"{lab}.{name}"
                if mapping_type == "relation":
                    if attributes.get(attr_name, {}).get("ref") in glob_attrs:
                        name = f"{mappings.get('key', name)}_id"
                        ref = f"{lab}.{name}"
                    else:
                        table = mappings.get("name", name)
                        crossjoin += f"\n    CROSS JOIN {schema}.{table} {name}"
                        key = mappings.get("key", name)
                        whereand += f"\n    AND {lab}.{key}_id = {name}.{key}_id"
                        ref = f"{name}.{name}"
                selects += [f"'{name}'", ref]
            for attr_name, attr_props in mapping_attrs.items():
                if attr_name not in glob_attrs:
                    continue
                global_tables[attr_name] = attr_props.get("name", attr_name)
            query += f""",
{layer} AS (
    SELECT 'layer', '{layer}', jsonb_build_object({','.join(selects)}) AS props
    FROM {schema}.{layer_table} {lab}, doc {crossjoin}
    WHERE {lab}.frame_range <@ doc.frame_range {whereand}
)"""
        layers_ctes = [x for x in tracks.get("layers", {})]
        for gar in tracks.get("group_by", []):
            assert "globalAttributes" in config, KeyError(
                "Could not find globalAttributes in corpus config"
            )
            gar_table = global_tables.get(gar, gar)
            lab = gar_table[0]
            gar_props = [f"({x}.props->'{gar}_id')::text" for x in layers_ctes]
            selects = [f"'{gar}'", f"{lab}.{gar}", f"'{gar}_id'", f"{lab}.{gar}_id"]
            query += f""",
{gar} AS (
    SELECT DISTINCT 'glob', '{gar}', jsonb_build_object({','.join(selects)}) AS props
    FROM {schema}.{gar_table} {lab}
)"""
        # , {', '.join(layers_ctes)}
        # WHERE {lab}.{gar}_id IN ({','.join(gar_props)})
        # Trying to remove WHEREs under the assumption that global attributes will always be small
        query += f"\nSELECT * FROM {next(x for x in tracks['layers'])}"
        for n, layer in enumerate(tracks["layers"]):
            if n == 0:
                continue
            query += f"\nUNION ALL SELECT * FROM {layer}"
        for gar in tracks.get("group_by", {}):
            query += f"\nUNION ALL SELECT * FROM {gar}"
        doc_range = range_to_array("doc.frame_range")
        query += f"\nUNION ALL SELECT 'doc', '{doc_layer}', jsonb_build_object('frame_range',{doc_range}) AS props FROM doc"
        query += ";"
        print("document query", query)
        params = {"doc_id": doc_id}
        hashed = str(hasher((query, doc_id)))
        job: Job
        if self.use_cache:
            try:
                job = Job.fetch(hashed, connection=self.app["redis"])
                if job and job.get_status(refresh=True) == "finished":
                    kwa: BaseArgs = {"user": user, "room": room}
                    _document(job, self.app["redis"], job.result, **kwa)
                    return job
            except NoSuchJobError:
                pass

        kwargs = {
            "document": True,
            "corpus": corpus,
            "user": user,
            "room": room,
            "doc": doc_id,
        }
        job = self.app[queue].enqueue(
            _db_query,
            on_success=Callback(_document, self.timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query, params),
            kwargs=kwargs,
        )
        return job

    async def get_config(self, force_refresh: bool = False) -> Job:
        """
        Get initial app configuration JSON
        """
        job: Job
        job_id = "app_config"

        query = _format_config_query(
            "SELECT {selects} FROM main.corpus mc {join} WHERE mc.enabled = true;"
        )

        redis: RedisConnection[bytes] = self.app["redis"]
        opts: dict[str, bool] = {"is_main": True}  # query on main.*
        if self.use_cache and not force_refresh:
            try:
                already = Job.fetch(job_id, connection=redis)
                if already and already.result is not None:
                    payload: dict[str, str | bool | Config] = _config(
                        already, redis, already.result, publish=False
                    )
                    await _set_config(cast(JSONObject, payload), self.app)
                    print("Loaded config from redis (flush redis if new corpora added)")
                    return already
            except NoSuchJobError:
                pass
        job = self.app["internal"].enqueue(
            _db_query,
            on_success=Callback(_config, self.callback_timeout),
            job_id=job_id,
            on_failure=Callback(_general_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query,),
            kwargs=opts,
        )
        return job

    async def get_export_notifs(self, user_id: str = "", hash: str = "") -> Job:
        """
        Get initial app configuration JSON
        """
        job: Job

        query: str
        # TODO: better check on symbols (use pgsql)
        if user_id:
            assert ";" not in user_id and "'" not in user_id
            query = f"SELECT * FROM main.exports WHERE user_id = '{user_id}';"
        elif hash:
            assert ";" not in hash and "'" not in hash
            query = f"SELECT * FROM main.exports WHERE query_hash = '{hash}';"

        job = self.app["internal"].enqueue(
            _db_query,
            on_success=Callback(_export_notifs, self.callback_timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query,),
            kwargs={"user": user_id, "hash": hash, "is_main": True},
        )
        return job

    def fetch_queries(
        self,
        user: str,
        room: str,
        query_type: str,
        queue: str = "internal",
        limit: int = 10,
    ) -> Job:
        """
        Get previous saved queries for this user/room
        """
        params: dict[str, str] = {"user": user}

        # room_info: str = ""
        # if room:
        #     room_info = " AND room = :room"
        #     params["room"] = room

        # query = f"""SELECT * FROM lcp_user.queries WHERE "user" = :user {room_info} ORDER BY created_at DESC LIMIT {limit};"""

        if query_type:
            params["query_type"] = query_type

            query = (
                """SELECT * FROM lcp_user.queries
                WHERE "user" = :user AND query_type = :query_type
                ORDER BY created_at DESC LIMIT {limit};"""
            ).format(limit=limit)
        else:
            query = (
                """SELECT * FROM lcp_user.queries
                WHERE "user" = :user
                ORDER BY created_at DESC LIMIT {limit};"""
            ).format(limit=limit)

        opts = {
            "user": user,
            "room": room,
            "config": True,
            "query_type": query_type,
            "is_main": True,  # query on main.* or something similar
        }
        job: Job = self.app[queue].enqueue(
            _db_query,
            on_success=Callback(_queries, self.callback_timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query.strip(), params),
            kwargs=opts,
        )
        return job

    def store_query(
        self,
        query_data: JSONObject,
        idx: int,
        user: str,
        room: str,
        queue: str = "internal",
    ) -> Job:
        """
        Add a saved query to the db
        """
        query = (
            'INSERT INTO lcp_user.queries (idx, query, "user", room, query_name, query_type) '
            "VALUES (:idx, :query, :user, :room, :query_name, :query_type);"
        )
        kwargs = {
            "user": user,
            "room": room,
            "store": True,
            "is_main": True,  # query on main.* or something similar
            "query_id": idx,
        }
        params: dict[str, Any] = {
            "idx": idx,
            "query": json.dumps(query_data, default=str),
            "user": user,
            "room": room,
            "query_name": query_data["query_name"],
            "query_type": query_data["query_type"],
        }
        job: Job = self.app[queue].enqueue(
            _db_query,
            result_ttl=self.query_ttl,
            on_success=Callback(_queries, self.callback_timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            job_timeout=self.timeout,
            args=(query, params),
            kwargs=kwargs,
        )
        return job

    def delete_query(
        self, user_id: str, room_id: str, query_id: str, queue: str = "internal"
    ) -> Job:
        """
        Delete a query using a background job.
        """
        # Convert the query_id string to a UUID object for proper binding.
        try:
            query_uuid = uuid.UUID(query_id)
        except ValueError:
            raise ValueError("Invalid query id provided")

        # Build parameters with the UUID object.
        params: dict[str, Any] = {"user": user_id, "room": room_id, "idx": query_uuid}

        # DELETE query without a RETURNING clause.
        query = """DELETE FROM lcp_user.queries
            WHERE "user" = :user
            AND idx = :idx"""

        opts = {
            "user": user_id,
            "room": room_id,
            "idx": query_id,  # keep as string for logging and later use in the callback
            "delete": True,
            "config": True,
        }

        job: Job = self.app[queue].enqueue(
            _db_query,
            on_success=Callback(_deleted, self.callback_timeout),
            on_failure=Callback(_general_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query.strip(), params),
            kwargs=opts,
        )
        return job

    def update_descriptions(
        self,
        corpus_id: int,
        query_data: JSONObject,
        lg: str = "en",
        queue: str = "internal",
    ) -> Job:
        """
        Update the descriptions of the layers and attributes in a corpus
        """
        # TODO: check localizableString in corpus_template schema instead?
        MONOLINGUAL = {"name", "revision", "license", "language"}

        kwargs = {
            "store": True,
            "is_main": True,  # query on main.*
            "has_return": False,
            "refresh_config": True,
        }
        query = f"""CALL main.update_corpus_descriptions(:corpus_id, :descriptions ::jsonb);"""
        params: dict[str, str | int | None | JSONObject] = {
            "corpus_id": corpus_id,
            "descriptions": json.dumps(query_data),
        }
        self.app["config"][str(corpus_id)]["meta"] = query_data
        job: Job = self.app[queue].enqueue(
            _db_query,
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query, params),
            kwargs=kwargs,
        )
        return job

    def update_metadata(
        self,
        corpus_id: int,
        query_data: JSONObject,
        lg: str = "en",
        queue: str = "internal",
    ) -> Job:
        """
        Update metadata for a corpus
        """
        # TODO: check localizableString in corpus_template schema instead?
        MONOLINGUAL = {"name", "revision", "license", "language", "swissubase"}

        kwargs = {
            "store": True,
            "is_main": True,  # query on main.*
            "has_return": False,
            "refresh_config": True,
        }
        query = f"""CALL main.update_corpus_meta(:corpus_id, :metadata_json ::jsonb);"""
        existing_meta: dict = self.app["config"][str(corpus_id)]["meta"]
        for k, v in query_data.items():
            if k in MONOLINGUAL:
                continue
            is_str = isinstance(existing_meta.get(k), str)
            if is_str:
                if lg == "en" or existing_meta[k] == v:
                    continue
                query_data[k] = {"en": existing_meta[k]}
            if not isinstance(query_data[k], dict):
                query_data[k] = (
                    {**existing_meta[k]}
                    if isinstance(existing_meta.get(k), dict)
                    else {}
                )
            query_data[k][lg] = v  # type: ignore
            if "en" not in query_data[k]:  # type: ignore
                query_data[k]["en"] = v  # type: ignore
        params: dict[str, str | int | None | JSONObject] = {
            "corpus_id": corpus_id,
            "metadata_json": json.dumps(query_data),
        }
        self.app["config"][str(corpus_id)]["meta"] = query_data
        job: Job = self.app[queue].enqueue(
            _db_query,
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query, params),
            kwargs=kwargs,
        )
        return job

    def update_projects(
        self,
        corpus_id: int,
        project_ids: list,
        queue: str = "internal",
    ) -> Job:
        """
        Update which project(s) a corpus belongs to
        """
        kwargs = {
            "store": True,
            "is_main": True,  # query on main.*
            "has_return": False,
            "refresh_config": True,
        }
        args = {
            "corpus_id": corpus_id,
            "pid": str(project_ids[0]),
            "pids": "[" + ",".join(f'"{str(pid)}"' for pid in project_ids) + "]",
        }
        query = f"""CALL main.update_corpus_projects(:corpus_id, :pid ::uuid, :pids ::text);"""
        job: Job = self.app[queue].enqueue(
            _db_query,
            result_ttl=self.query_ttl,
            job_timeout=self.timeout,
            args=(query, args),
            kwargs=kwargs,
        )
        return job

    def upload(
        self,
        user: str,
        project: str,
        room: str | None = None,
        queue: str = "background",
        gui: bool = False,
        user_data: JSONObject | None = None,
        **kwargs,
    ) -> Job:
        """
        Upload a new corpus to the system
        """
        kwargs = {"gui": gui, "user_data": user_data, **kwargs}
        job: Job = self.app[queue].enqueue(
            _upload_data,
            on_success=Callback(_upload, self.callback_timeout),
            on_failure=Callback(_upload_failure, self.callback_timeout),
            result_ttl=self.query_ttl,
            job_timeout=self.upload_timeout,
            args=(project, user, room, self.app["_debug"]),
            kwargs=kwargs,
        )
        return job

    def create(
        self,
        create: str,
        project: str,
        path: str,
        schema_name: str,
        user: str | None,
        room: str | None,
        project_name: str,
        corpus_name: str,
        queue: str = "background",
        # drops: list[str] | None = None,
        gui: bool = False,
    ) -> Job:
        kwargs = {
            "project": project,
            "user": user,
            "room": room,
            "path": path,
            "project_name": project_name,
            "corpus_name": corpus_name,
            "gui": gui,
        }
        job: Job = self.app[queue].enqueue(
            _create_schema,
            # schema job remembered for one day?
            result_ttl=60 * 60 * 24,
            job_timeout=self.timeout,
            on_success=Callback(_schema, self.callback_timeout),
            on_failure=Callback(_upload_failure, self.callback_timeout),
            # args=(create, schema_name, drops),
            args=(create, schema_name),
            kwargs=kwargs,
        )
        return job

    def cancel(self, job: Job | str) -> str:
        """
        Cancel a running job
        """
        if isinstance(job, str):
            job_id = job
            job = Job.fetch(job, connection=self.app["redis"])
        else:
            job_id = job.id
        job.cancel()
        send_stop_job_command(self.app["redis"], job_id)
        if job not in self.app["canceled"]:
            self.app["canceled"].append(job)
        return job.get_status()

    def cancel_running_jobs(
        self,
        user: str,
        room: str,
        specific_job: str | None = None,
        base: str | None = None,
    ) -> list[str]:
        """
        Cancel all running jobs for a user/room, or a `specific_job`.

        Return the ids of canceled jobs in a list.
        """
        if specific_job:
            rel_jobs = [str(specific_job)]
        else:
            rel_jobs = self.app["query"].started_job_registry.get_job_ids()
            rel_jobs += self.app["query"].scheduled_job_registry.get_job_ids()

        jobs = set(rel_jobs)
        ids = []

        for job in jobs:
            maybe = Job.fetch(job, connection=self.app["redis"])
            mk = cast(dict, maybe.kwargs)
            if base and mk.get("simultaneous", "") != base:
                continue
            if base and mk.get("is_sentences", False):
                continue
            if job in self.app["canceled"]:
                continue
            if room and mk.get("room") != room:
                continue
            if user and mk.get("user") != user:
                continue
            try:
                self.cancel(maybe)
                ids.append(job)
            except InvalidJobOperation:
                print(f"Already canceled: {job}")
            except Exception as err:
                print("Unknown error, please debug", err, job)
        return ids

    def get(self, job_id: str) -> Job | None:
        try:
            job = Job.fetch(job_id, connection=self.app["redis"])
            return job
        except NoSuchJobError:
            return None

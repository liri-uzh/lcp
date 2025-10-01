import asyncio
import json
import traceback
import os

from aiohttp import web
from redis import Redis as RedisConnection
from rq import Callback, Queue
from rq.command import send_stop_job_command
from rq.job import Job
from types import TracebackType
from typing import cast, Any, Callable
from uuid import uuid4

from .abstract_query.create import json_to_sql
from .abstract_query.typed import QueryJSON
from .callbacks import _general_failure
from .convert import _aggregate_results
from .jobfuncs import _db_query, _export_db
from .redis_proxies import RedisDict, RedisList
from .typed import JSONObject, Batch
from .utils import (
    _get_query_batches,
    _publish_msg,
    hasher,
    push_msg,
    CustomEncoder,
)

MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))
QUERY_TTL = int(os.getenv("QUERY_TTL", 5000))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", 1000))
FULL_QUERY_TIMEOUT = int(os.getenv("QUERY_ENTIRE_CORPUS_CALLBACK_TIMEOUT", 99999))
MAX_KWIC_LINES = int(os.getenv("DEFAULT_MAX_KWIC_LINES", 9999999))

SERIALIZABLES = (
    int,
    float,
    bool,
    str,
    bytes,
    bytearray,
    list,
    tuple,
    set,
    frozenset,
    dict,
)


def _qi_job_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    qi_hash: str = job.meta.get("qi_hash", "")
    qi: QueryInfo = QueryInfo(qi_hash, connection)
    tb = traceback.format_exc()
    qi.publish("\n".join([str(value), tb]), "failure")
    return _general_failure(job, connection, typ, value, trace)


def _merge_results(exisitng: dict, incoming: dict):
    for k in incoming:
        if isinstance(exisitng.get(k), dict):
            exisitng[k].update(incoming[k])
        elif isinstance(exisitng.get(k), list):
            exisitng[k] += incoming[k]
        else:
            exisitng[k] = incoming[k]


class Request:
    """
    Received POST requests
    """

    def __init__(self, connection: RedisConnection, request: dict = {}):
        self._connection = connection
        request = cast(dict, request)
        id: str = str(request.get("id") or uuid4())
        redis_request = RedisDict(connection, id)
        self._redis_request = redis_request

        if "hash" in redis_request:
            self.hash: str = cast(str, redis_request["hash"])
        self._full = cast(bool, request.get("full", False))
        self._id = cast(str, id)

        if "id" in redis_request:
            return

        for k, v in request.items():
            redis_request[k] = v
        # The attributes below are immutable
        self.id: str = cast(str, redis_request["id"] or id)
        self.synchronous: bool = cast(bool, redis_request.get("synchronous", False))
        self.requested: int = cast(int, redis_request.get("requested", 0))
        self.full: bool = cast(bool, redis_request.get("full", False))
        self.offset: int = cast(int, redis_request.get("offset", 0))
        self.corpus: int = cast(int, redis_request.get("corpus", 1))
        self.user: str = cast(str, redis_request.get("user", ""))
        self.room: str = cast(str, redis_request.get("room", ""))
        self.languages: RedisList = cast(
            RedisList,
            redis_request.get("languages", RedisList(connection, f"{id}:languages")),
        )
        self.query: str = cast(str, redis_request.get("query", ""))
        self.to_export = cast(None | RedisDict, redis_request.get("to_export", None))
        if not isinstance(self.to_export, RedisDict):
            redis_request["to_export"] = {"format": "xml"} if self.to_export else {}
            self.to_export = redis_request["to_export"]
        # The attributes below are dynamic and need to update redis
        # job1: [200,400,30] --> sent lines 200 through 400, need 30 segments
        self.lines_batch: RedisDict = cast(
            RedisDict,
            redis_request.get(
                "lines_batch", RedisDict(connection, f"{id}:lines_batch")
            ),
        )
        # keep track of which hashes were already sent ({hash: 1, hash: 0})
        self.sent_hashes: RedisDict = cast(
            RedisDict,
            redis_request.get(
                "sent_hashes", RedisDict(connection, f"{id}:sent_hashes")
            ),
        )
        # {hash: {N: M}}
        self.segment_lines_for_hash: RedisDict = cast(
            RedisDict,
            redis_request.get(
                "segment_lines_for_hash",
                RedisDict(connection, f"{id}:segment_lines_for_hash"),
            ),
        )

    def __getattribute__(self, name: str):
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            full = self._full
        except:
            full = False
        # manual re-implementation of @property decorator
        if name == "lines_sent_so_far":
            lines_batch = cast(dict, self.lines_batch)
            return sum(up for _, up, _ in lines_batch.values())
        elif full and name in ("requested", "offset"):
            return 0 if name == "offset" else MAX_KWIC_LINES
        try:
            # Try to retrieve the value from redis first
            assert name in self._redis_request, ReferenceError(
                f"Could not fint attribute {name} on request {self._id}"
            )
            value = self._redis_request[name]
        except:
            # Retrieve the internal value instead
            value = super().__getattribute__(name)
        return value

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if not name.startswith("_"):
            self._redis_request[name] = value

    def serialize(self) -> dict:
        """
        Return a dict that only contains key-value pairs in SERIALIZABLES.
        Use this to update the associated redis entry
        """
        obj: dict = {}
        for k in dir(self):
            if k.startswith("_"):
                continue
            attr = getattr(self, k)
            if not isinstance(attr, SERIALIZABLES):
                continue
            obj[k] = attr
        return obj

    def all_queries_done(self, qi: "QueryInfo") -> bool:
        so_far = int(self.lines_sent_so_far or 0)
        if so_far >= self.requested:
            return True
        if qi.status != "complete":
            return False
        relevant_batches: list[str] = []
        nlines = 0
        for batch_hash, n in qi.query_batches.values():
            if nlines >= self.offset:
                relevant_batches.append(batch_hash)
            nlines += n
        return all(bh in self.sent_hashes for bh in relevant_batches)

    def is_done(self, qi: "QueryInfo") -> bool:
        """
        A request is done if the qi is complete (exhausted all batches)
        or if the number of lines sent reaches the requested amount
        """
        if not self.all_queries_done(qi):
            return False
        if not qi.kwic_keys:
            return True
        all_segs_sent = True
        for batch_hash, (_, _, req_segs) in self.lines_batch.items():  # type: ignore
            batch_name = qi.get_batch_from_hash(batch_hash)
            batch_seg_hashes = qi.segments_for_batch.get(batch_name, {})
            batch_segs_sent = (
                sum(n for (sh, n) in self.sent_hashes.items() if sh in batch_seg_hashes)  # type: ignore
                >= req_segs
            )
            all_segs_sent = all_segs_sent and batch_segs_sent
        return all_segs_sent

    def delete_if_done(self, qi: "QueryInfo"):
        if not self.is_done(qi):
            return
        print(f"[{self.id}] DELETE REQUEST NOW")
        qi.delete_request(self)

    def lines_for_batch(self, qi: "QueryInfo", batch_name: str) -> tuple[int, int]:
        """
        Return the offset and number of lines required in the current job
        """
        offset_and_lines_for_req = (0, 0)
        lines_before_job, lines_job = qi.get_lines_batch(batch_name)
        if self.offset > lines_before_job + lines_job:
            return offset_and_lines_for_req
        if self.offset + self.requested < lines_before_job:
            return offset_and_lines_for_req
        lines_for_req: int = self.requested
        offset_for_req: int = self.offset - lines_before_job
        if offset_for_req < 0:
            # we got lines before: we need fewer this time around
            lines_for_req += offset_for_req
            offset_for_req = 0
        if offset_for_req + lines_for_req > lines_job:
            lines_for_req = lines_job - offset_for_req
        offset_and_lines_for_req = (offset_for_req, lines_for_req)
        return offset_and_lines_for_req

    def get_payload(self, qi: "QueryInfo", batch_name: str = "") -> dict:
        ret: dict = {
            "job": qi.hash,
            "user": self.user,
            "room": self.room,
            "hash": self.hash,
            "batch_name": batch_name,
            "status": "satisfied" if self.is_done(qi) else "started",
        }
        if (
            ret["status"] == "satisfied"
            and qi.status == "complete"
            and self.all_queries_done(qi)
        ):
            ret["status"] = "finished"
        if not batch_name:
            batch_name = next(reversed(qi.done_batches))
        lines_before_batch, lines_this_batch = qi.get_lines_batch(batch_name)
        ret["total_results_so_far"] = lines_before_batch + lines_this_batch
        done_batches: list = []
        for name, n in qi.done_batches.items():
            done_batches.append([name, n])
            if name == batch_name:
                break
        done_words = sum(int(n) for (_, n) in done_batches)
        total_words = sum(int(n) for (_, n) in qi.all_batches) or 1
        ret["percentage_words_done"] = 100.0 * done_words / total_words
        len_done_batches = len(done_batches)
        len_all_batches = len(qi.all_batches)
        ret["batches_done"] = f"{len_done_batches}/{len_all_batches}"
        ret["percentage_done"] = 100.0 * len_done_batches / len_all_batches
        ret["projected_results"] = int(
            100 * (ret["total_results_so_far"] / (ret["percentage_words_done"] or 100))
        )
        return ret

    async def send_segments(
        self, app: web.Application, qi: "QueryInfo", batch_name: str
    ):
        """
        Fetch the segments lines for the batch, filter the ones needed for this request
        and send them to the client
        """
        print(f"[{self.id}] send segments {batch_name}")
        seg_hashes: list[str] = [x for x in qi.segments_for_batch[batch_name]]
        if all(x in self.sent_hashes for x in seg_hashes):
            return
        results: dict[str, Any] = {}
        for seg_hash in seg_hashes:
            if seg_hash in self.sent_hashes:
                continue
            seg_lines: dict[int, int] = self.segment_lines_for_hash[seg_hash]  # type: ignore
            seg_res: list = [
                line
                for nline, line in enumerate(qi.get_from_cache(seg_hash))
                if str(nline) in seg_lines
            ]
            # prep_seg_lines = [line for rtype, *line in seg_res if rtype == -1]
            prep_seg_lines = {
                sid: line for rtype, (sid, *line) in seg_res if rtype == -1
            }
            meta_lines = [line for rtype, line in seg_res if rtype == -2]
            _merge_results(
                results,
                {
                    "-1": prep_seg_lines,
                    "-2": meta_lines,
                },
            )
            self.sent_hashes[seg_hash] = len(prep_seg_lines)
        # print("after updaing sent_hashes", self.sent_hashes)
        results["0"] = {"result_sets": qi.result_sets, "meta_labels": qi.meta_labels}
        nsegs = len(results["-1"])
        payload = self.get_payload(qi, batch_name)
        payload.update({"action": "segments", "result": results, "n_results": nsegs})
        if not self.is_done(qi):
            payload["more_data_available"] = True
        to_msg = (
            "to sync request"
            if self.synchronous
            else f"to user '{self.user}' room '{self.room}'"
        )
        batch_hash, _ = qi.query_batches[batch_name]
        print(
            f"[{self.id}] Sending {nsegs} segments for batch {batch_name} (hash {qi.hash}; batch hash {batch_hash}) {to_msg}"
        )
        if self.to_export:
            xp_format = self.to_export.get("format", "xml") or "xml"
            export = app["exporters"][xp_format].export
            qi.enqueue(export, self.id, self.hash, payload)
        elif self.synchronous:
            req_buffer = app["query_buffers"][self.id]
            _merge_results(req_buffer, results)
        else:
            await push_msg(
                app["websockets"],
                self.room,
                payload,
                skip=None,
                just=(self.room, self.user),
            )
        print(f"[{self.id}] sent {nsegs} segments {batch_name}")

    async def send_query(self, app: web.Application, qi: "QueryInfo", batch_name: str):
        """
        Fetch the query results for the batch, filter the lines needed for this request
        and send them to the client
        """
        print(f"[{self.id}] send query {batch_name}")
        batch_hash, _ = qi.query_batches[batch_name]
        if batch_hash in self.sent_hashes:
            # If some lines were already sent for this job
            return
        batch_res: list = qi.get_from_cache(batch_hash)
        offset_this_batch, lines_this_batch = self.lines_for_batch(qi, batch_name)
        n_seg_ids: int = 0
        if lines_this_batch > 0 and qi.kwic_keys:
            n_seg_ids = len(
                qi.segment_ids_in_results(
                    batch_res,
                    qi.kwic_keys,
                    offset_this_batch,
                    offset_this_batch + lines_this_batch,
                )
            )
        self.lines_batch[batch_hash] = [offset_this_batch, lines_this_batch, n_seg_ids]
        _, results = qi.get_stats_results()  # fetch any stats results first
        lines_so_far = -1
        for k, v in batch_res:
            sk = str(k)
            if sk not in qi.kwic_keys:
                continue
            if sk not in results:
                results[sk] = []
            lines_so_far += 1
            if lines_so_far < offset_this_batch:
                continue
            if lines_so_far >= offset_this_batch + lines_this_batch:
                continue
            results[sk].append(v)
        self.sent_hashes[batch_hash] = len(results)
        results["0"] = {"result_sets": qi.result_sets, "meta_labels": qi.meta_labels}
        try:
            stats_key = f"{qi.hash}::stats"
            _, stats_res = qi.get_from_cache(stats_key)
            results.update(stats_res)
        except:
            pass
        payload = self.get_payload(qi, batch_name)
        payload.update({"action": "query_result", "result": results})
        more_in_batch = (
            offset_this_batch + lines_this_batch < qi.get_lines_batch(batch_name)[1]
        )
        payload["more_data_available"] = more_in_batch
        to_msg = (
            "to sync request"
            if self.synchronous
            else f"to user '{self.user}' room '{self.room}'"
        )
        print(
            f"[{self.id}] Sending {lines_this_batch} results lines for batch {batch_name} ({batch_hash}; QI {qi.hash}) {to_msg}"
        )
        if self.to_export:
            xp_format = self.to_export.get("format", "xml") or "xml"
            export = app["exporters"][xp_format].export
            qi.enqueue(export, self.id, self.hash, payload)
        elif self.synchronous:
            req_buffer = app["query_buffers"][self.id]
            _merge_results(req_buffer, results)
        else:
            await push_msg(
                app["websockets"],
                self.room,
                cast(JSONObject, payload),
                skip=None,
                just=(self.room, self.user),
            )

    async def error(
        self, app: web.Application, qi: "QueryInfo", error: str = "unknown"
    ):
        print(f"[{self.id}] Error while running the query:", error)
        if self.to_export:
            qi.enqueue(
                _export_db,
                qi.hash,
                self.to_export.get("format", "xml"),
                "update",
                self.offset,
                self.requested,
                failure=True,
                message=error,
            )
        if self.synchronous:
            try:
                req_buffer = app["query_buffers"][self.id]
                req_buffer["error"] = error
            except:
                pass
        else:
            payload = {
                "status": "failed",
                "kind": "error",
                "value": f"Error while running the query: {error}",
            }
            await push_msg(
                app["websockets"],
                self.room,
                cast(JSONObject, payload),
                skip=None,
                just=(self.room, self.user),
            )
        qi.delete_request(self)

    async def respond(self, app: web.Application, payload: dict):
        """
        This method is called by the main app in sock.py
        after QI publishes a "callback_query" message with the batch name
        """
        typ: str = payload["callback_query"]
        qi: QueryInfo = QueryInfo(payload["hash"], connection=self._connection)
        batch_name: str = payload["batch"]
        if typ == "failure":
            await self.error(app, qi, payload.get("batch", "unknown"))
            return
        try:
            # handle redis sync issues (up to 2s to sync)
            async with asyncio.timeout(2):
                while batch_name not in qi.query_batches:
                    await asyncio.sleep(0.1)
            if typ == "main":
                await self.send_query(app, qi, batch_name)
            elif typ == "segments":
                await self.send_segments(app, qi, batch_name)
            if not self.to_export:
                self.delete_if_done(qi)
        except Exception as e:
            tb = traceback.format_exc()
            qi.publish("\n".join([str(e), tb]), "failure")


class QueryInfo:
    """
    Model the query based on the SQL of the first batch
    There is a single QueryInfo for potentially multiple POST requests (Request)
    """

    @staticmethod
    def segment_ids_in_results(
        results: list, kwic_keys: list[str], offset: int = 0, upper: int | None = None
    ) -> dict[str, int]:
        """
        Return the unique segment IDs listed in the results for the provided offset+upper
        """
        counter = -1
        segment_ids: dict[str, int] = {}
        for key, (sid, *_) in results:
            if str(key) not in kwic_keys:
                continue
            counter += 1
            if counter < offset:
                continue
            if upper is not None and counter >= upper:
                break
            segment_ids[str(sid)] = 1
        return segment_ids

    def __init__(
        self,
        qhash: str,
        connection: RedisConnection,
        json_query: dict | None = None,
        meta_json: dict | None = None,
        post_processes: dict | None = None,
        languages: list[str] | None = None,
        config: dict | None = None,
        local_queries: dict = {},
    ):
        self._connection = connection
        self.hash = qhash
        qi = self.qi
        self.json_query = qi.setdefault("json_query", json_query or {})
        if config:
            config["batches"] = config.get("_batches", {})
        self.config = qi.setdefault("config", config or {})
        self.meta_json = qi.setdefault("meta_json", meta_json or {})
        self.post_processes = qi.setdefault("post_processes", post_processes or {})
        self.meta_labels = qi.setdefault("meta_labels", [])
        self.languages = qi.setdefault("languages", languages or [])
        self.local_queries = qi.setdefault("local_queries", local_queries or {})
        self.result_sets = cast(dict, self.meta_json).get("result_sets", [])

    def enqueue(
        self,
        method,
        *args,
        job_id: str | None = None,
        callback: Callable | None = None,
        **kwargs,
    ) -> Job:
        """
        Adds a job to the background queue
        Can be called either from the main app or from a worker
        """
        queue: str = (
            "background" if all(r.to_export for r in self.requests) else "query"
        )
        q = Queue(queue, connection=self._connection)
        enqueued_job_ids = [jid for jid in self.enqueued_jobs]
        # Clear any job that needs to be cleared
        for jid in enqueued_job_ids:
            try:
                job = Job.fetch(jid, self._connection)
                if not (job.is_started or job.is_scheduled or job.is_queued):
                    self.enqueued_jobs.pop(jid, "")
            except:
                self.enqueued_jobs.pop(jid, "")
        on_success: Callback | None = (
            Callback(callback, QUERY_TIMEOUT) if callback else None
        )
        j = q.enqueue(
            method,
            on_success=on_success,
            on_failure=Callback(_qi_job_failure, QUERY_TIMEOUT),
            result_ttl=QUERY_TTL,
            job_timeout=FULL_QUERY_TIMEOUT if self.full else QUERY_TIMEOUT,
            args=args,
            job_id=job_id,
        )
        j.meta["qi_hash"] = self.hash  # used in failure callback
        j.save_meta()
        self.enqueued_jobs[j.id] = 1
        return j

    def set_cache(self, key: str, data: Any):
        self._connection.set(key, json.dumps(data, cls=CustomEncoder))
        self._connection.expire(key, QUERY_TTL)

    def get_from_cache(self, key: str) -> list:
        res_json: str = cast(str, self._connection.get(key))
        self._connection.expire(key, QUERY_TTL)
        return cast(list, json.loads(res_json))

    async def query(self, qhash: str, script: str, params: dict = {}) -> Any:
        """
        Helper to make sure the results are stored in redis
        """
        res = await _db_query(script, params=params)
        self.set_cache(qhash, res)
        return res

    def publish(self, batch_name: str, typ: str, custom_payload: dict[str, Any] = {}):
        """
        Notify the app that results are available
        """
        if typ == "failure":
            self.running_batch = ""
        msg_id: str = str(uuid4())
        payload: dict[str, Any] = {
            "callback_query": typ,
            "batch": batch_name,
            "hash": self.hash,
        }
        for k, v in custom_payload.items():
            if v is None:
                payload.pop(k, None)
                continue
            payload[k] = v
        _publish_msg(
            self._connection,
            payload,
            msg_id=msg_id,
        )

    def get_batch_from_hash(self, batch_hash: str) -> str:
        """
        Return the batch name correpsonding to a batch query hash
        """
        batch_name = next(
            (bn for bn, (bh, _) in self.query_batches.items() if bh == batch_hash), ""
        )
        return batch_name

    # Getters and setters to keep in sync with redis
    @property
    def enqueued_jobs(self) -> dict[str, int]:
        if "enqueued_jobs" not in self.qi:
            self.qi["enqueued_jobs"] = {}
        return cast(dict[str, int], self.qi["enqueued_jobs"])

    @enqueued_jobs.setter
    def enqueued_jobs(self, value: dict[str, int]):
        if "enqueued_jobs" not in self.qi:
            self.qi["enqueued_jobs"] = {}
        for k, v in value.items():
            self.qi["enqueued_jobs"][k] = v

    @property
    def running_batch(self) -> str:
        return self.qi.get("running_batch", "")

    @running_batch.setter
    def running_batch(self, value: str):
        self.qi["running_batch"] = value

    @property
    def done_batches(self) -> dict[str, int]:
        if "done_batches" not in self.qi:
            self.qi["done_batches"] = {}
        done_batches = cast(dict[str, int], self.qi["done_batches"])
        return done_batches

    @done_batches.setter
    def done_batches(self, value: dict[str, int]):
        if "done_batches" not in self.qi:
            self.qi["done_batches"] = {}
        for k, v in value.items():
            self.qi["done_batches"][k] = v

    @property
    def query_batches(self) -> dict:
        """
        Map batch names with (batch_hash, n_kwic_lines)
        """
        if "query_batches" not in self.qi:
            self.qi["query_batches"] = {}
        return cast(dict, self.qi["query_batches"])

    @query_batches.setter
    def query_batches(self, value: dict):
        if "query_batches" not in self.qi:
            self.qi["query_batches"] = {}
        for k, v in value.items():
            self.qi["query_batches"][k] = v

    @property
    def segments_for_batch(self) -> dict[str, dict[str, dict[str, int]]]:
        """
        batch_hash->{segment_hash->segment_ids, segment_hash->segment_ids}
        """
        if "segments_for_batch" not in self.qi:
            self.qi["segments_for_batch"] = {}
        return cast(dict[str, dict[str, dict[str, int]]], self.qi["segments_for_batch"])

    @segments_for_batch.setter
    def segments_for_batch(self, value: dict):
        if "segments_for_batch" not in self.qi:
            self.qi["segments_for_batch"] = {}
        for k, v in value.items():
            self.qi["segments_for_batch"][k] = v

    def has_request(self, request: Request):
        return any(r.id == request.id for r in self.requests)

    def add_request(self, request: Request):
        request.hash = self.hash
        if "requests" not in self.qi:
            self.qi["requests"] = []
        if request.id in self.qi["requests"]:
            return
        self.qi["requests"].append(request.id)

    def delete_request(self, request: Request):
        idx = next(
            (n for n, rid in enumerate(self.qi["requests"]) if rid == request.id), -1
        )
        if idx < 0:
            return
        self.qi["requests"].pop(idx)

    def stop_request(self, request: Request):
        """
        Stop an active request and cancels any related active query as applicable
        """
        self.delete_request(request)
        if self.requests:
            return
        jids = [jid for jid in self.enqueued_jobs]
        for jid in jids:
            try:
                job = Job.fetch(jid, self._connection)
                if job.is_started or job.is_scheduled or job.is_queued:
                    job.cancel()
                    send_stop_job_command(self._connection, jid)
                    self.enqueued_jobs.pop(jid, "")
            except:
                self.enqueued_jobs.pop(jid, "")

    def get_lines_batch(self, batch_name: str) -> tuple[int, int]:
        """
        Return the number of kwic lines in the batches before this one
        and the number of kwic lines in this batch
        """
        lines_before_batch: int = 0
        lines_this_batch: int = 0
        for bn, (_, nlines) in self.query_batches.items():
            if bn == batch_name:
                lines_this_batch = nlines
                break
            lines_before_batch += nlines
        return (lines_before_batch, lines_this_batch)

    def get_stats_results(self) -> tuple[list, dict]:
        """
        All the non-KWIC results
        """
        if not self.query_batches:
            return ([], {})
        try:
            first_job = next(
                Job.fetch(qjid, self._connection)
                for qjid, _ in self.query_batches.values()
            )
            batches, stats = first_job.meta.get("stats_results", ([], {}))
            return (batches, stats)
        except:
            return ([], {})

    def decide_next_batch(self, previous_batch: str | None = None) -> list:
        """
        Return the batches in an optimized ordered.

        Pick the smallest batch first. Query the smallest available result until
        `requested` results are collected. Then, using the result count of the
        queried batches and the word counts of the remaining batches, predict the
        smallest next batch that's likely to yield enough results and return it.

        If no batch is predicted to have enough results, pick the smallest
        available (so more results go to the frontend faster).
        """
        if not previous_batch or not len(self.done_batches):
            return self.all_batches[0]
        list_done_batches = [[b, n] for b, n in self.done_batches.items()]
        next_batch: list = next(
            (
                b
                for n, b in enumerate(list_done_batches)
                if n > 0 and list_done_batches[n - 1][0] == previous_batch
            ),
            [],
        )
        if next_batch:
            return next_batch

        buffer = 0.1  # set to zero for picking smaller batches
        while len(self.done_batches) < len(self.all_batches):
            so_far = self.total_results_so_far
            # set here ensures we don't double count, even though it should not happen
            total_words_processed_so_far = (
                sum([int(x) for x in self.done_batches.values()]) or 1
            )
            proportion_that_matches = so_far / total_words_processed_so_far
            first_not_done: list[str | int] | None = None
            for batch in self.all_batches:
                if batch[0] in self.done_batches:
                    continue
                if self.full:
                    return batch
                if not first_not_done:
                    first_not_done = batch
                expected = cast(int, batch[-1]) * proportion_that_matches
                if float(expected) >= float(self.required + (self.required * buffer)):
                    return batch
            return cast(list, first_not_done)

        return []

    # Pseudo-attributes (no need to keep in sync)
    @property
    def qi(self) -> dict:
        qi = cast(dict, RedisDict(self._connection, self.hash))
        return qi

    @property
    def requests(self) -> list[Request]:
        """
        Return the associated requests
        The class Request already implements utmost recency
        """
        reqs: list[Request] = []
        for rid in self.qi["requests"]:
            try:
                reqs.append(Request(self._connection, {"id": rid}))
            except:
                # Do no create a Request object if the ID isn't in redis
                pass
        return reqs

    @property
    def all_batches(self) -> list[list[str | int]]:
        return _get_query_batches(self.config, self.languages)

    @property
    def kwic_keys(self) -> list[str]:
        return [
            str(n)
            for n, mr in enumerate(self.result_sets, start=1)
            if mr.get("type") == "plain"
        ]

    @property
    def stats_keys(self) -> list[str]:
        return [
            str(n)
            for n, mr in enumerate(self.result_sets, start=1)
            if mr.get("type") != "plain"
        ]

    @property
    def status(self) -> str:
        if len(self.done_batches) >= len(self.all_batches):
            return "complete"
        if self.total_results_so_far >= self.required:
            return "satisfied"
        return "started"

    @property
    def full(self) -> bool:
        return any(r.full for r in self.requests) if self.requests else False

    @property
    def required(self) -> int:
        """
        The required number of results lines is the max offset+requested out of all the Request's
        """
        return (
            max(r.offset + r.requested for r in self.requests) if self.requests else 0
        )

    @property
    def total_results_so_far(self) -> int:
        return sum(nlines for _, nlines in self.query_batches.values())

    # methods called from worker

    async def run_aggregate(
        self,
        offset: int,
        batch: list,
    ):
        """
        Aggregate the stats results, or fetch from cache
        """
        if not self.stats_keys:
            return
        batch_name: str = batch[0]
        stats_key = f"{self.hash}::stats"
        try:
            stats_batches, stats_results = self.get_from_cache(stats_key)
            if batch_name in stats_batches:
                # No need to run aggregate: cache already has this batch
                return
        except:
            stats_batches, stats_results = [], {}
        new_stats_batches = [b for b in stats_batches] + [batch_name]
        meta_json: dict = self.meta_json
        post_processes: dict = self.post_processes
        batch_hash, _ = self.query_batches[batch_name]
        res: list = self.get_from_cache(batch_hash)
        # lines_so_far, n_res = self.get_lines_batch(batch_name)
        # if n_res == 0 or lines_so_far + n_res < offset:
        #     # Indicate we have processed this batch
        #     self.set_cache(stats_key, [new_stats_batches, stats_results])
        #     return
        done_batches = cast(
            list[Batch],
            [
                (1, self.config.get("schema_path", ""), b, n)  # dummy corpus id
                for b, n in self.done_batches.items()
            ],
        )
        (_, to_send, _, _, _) = _aggregate_results(
            res,
            stats_results,
            meta_json,
            post_processes,
            batch,
            done_batches,
        )
        new_stats_results = {
            k: v for k, v in to_send.items() if str(k) in self.stats_keys
        }
        self.set_cache(stats_key, [new_stats_batches, new_stats_results])
        return

    async def run_query_on_batch(self, batch) -> str:
        """
        Send and run a SQL query againt the DB
        then update the QueryInfo and Request's accordingly
        and launch any required sentence/meta queries
        """
        batch_name, batch_n = batch
        sql_query, _, _ = json_to_sql(
            cast(QueryJSON, self.json_query),
            schema=self.config.get("schema_path", ""),
            batch=batch_name,
            config=self.config,
            lang=self.languages[0] if self.languages else None,
        )
        batch_hash = hasher(sql_query)
        res = await self.query(batch_hash, sql_query)
        res = res if res else []
        n_res = sum(1 if str(r) in self.kwic_keys else 0 for r, *_ in res)
        self.query_batches[batch_name] = (batch_hash, n_res)
        if batch_name not in self.done_batches:
            self.done_batches[batch_name] = batch_n
        return batch_hash

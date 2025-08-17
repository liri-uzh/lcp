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
from .jobfuncs import _db_query
from .typed import JSONObject, ObservableDict, ObservableList
from .utils import (
    _get_query_batches,
    _publish_msg,
    _get_query_info,
    _update_query_info,
    _get_request,
    _update_request,
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
        try:
            request = _get_request(connection, request["id"])
        except:
            request["id"] = str(request.setdefault("id", uuid4()))
            # The attributes below are immutable
            self.id: str = request["id"]
            self.synchronous: bool = request.get("synchronous", False)
            self.requested: int = request.get("requested", 0)
            self.full: bool = request.get("full", False)
            self.offset: int = request.get("offset", 0)
            self.corpus: int = request.get("corpus", 1)
            self.user: str = request.get("user", "")
            self.room: str = request.get("room", "")
            self.languages: list[str] = request.get("languages", [])
            self.query: str = request.get("query", "")
            to_export = request.get("to_export", None)
            if not isinstance(to_export, dict):
                to_export = {"format": "xml"} if to_export else {}
            self.to_export: dict | None = to_export
            # The attributes below are dynamic and need to update redis
            # job1: [200,400,30] --> sent lines 200 through 400, need 30 segments
            self.lines_batch: dict[str, tuple[int, int, int]] = request.get(
                "lines_batch", {}
            )
            # keep track of which hashes were already sent
            self.sent_hashes: dict[str, int] = request.get("sent_hashes", {})
            self.segment_lines_for_hash: dict[str, dict[int, int]] = request.get(
                "segment_lines_for_hash", {}
            )
            if "hash" in request:
                self.hash: str = request["hash"]
        self._full = request.get("full", False)
        self._id = request["id"]

    def update(self, name: str | None = None, value: Any = None):
        """
        Update the associated redis entry
        """
        try:
            redis = self._connection
            id = self.id
        except:
            return
        if name == "query_batches":
            return
        if name:
            _update_request(redis, id, info={"id": id, name: value})
        else:
            self_serialized = self.serialize()
            self_serialized.pop("query_batches", None)
            self_serialized["id"] = id
            _update_request(redis, id, info=self_serialized)

    def update_dict(self, attribute_name: str, update_dict: dict):
        """
        Update a dict attribute and make sure redis is synced.
        This is necessary because setting a key would not call setattr
        """
        attribute: dict = cast(dict, self.__getattribute__(attribute_name))
        attribute.update(update_dict)
        self.update(attribute_name, attribute)

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
            connection = super().__getattribute__("_connection")
            request = _get_request(connection, self._id)
            assert name in request, Exception()
            value = request[name]
        except:
            # Retrieve the internal value instead
            value = super().__getattribute__(name)
        return value

    def __setattr__(self, name, value):
        self.update(name, value)  # make sure to update redis first
        super().__setattr__(name, value)

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
        if self.lines_sent_so_far >= self.requested:
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
        for batch_hash, (_, _, req_segs) in self.lines_batch.items():
            batch_name = qi.get_batch_from_hash(batch_hash)
            batch_seg_hashes = qi.segments_for_batch.get(batch_name, {})
            batch_segs_sent = (
                sum(n for (sh, n) in self.sent_hashes.items() if sh in batch_seg_hashes)
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
            batch_name = qi.done_batches[-1][0]
        lines_before_batch, lines_this_batch = qi.get_lines_batch(batch_name)
        ret["total_results_so_far"] = lines_before_batch + lines_this_batch
        done_batches = []
        for name, n in qi.done_batches:
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
        sent_hashes = {}
        for seg_hash in seg_hashes:
            if seg_hash in self.sent_hashes:
                continue
            seg_lines: dict[int, int] = self.segment_lines_for_hash[seg_hash]
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
            sent_hashes[seg_hash] = len(prep_seg_lines)
        self.update_dict("sent_hashes", sent_hashes)
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
        self.update_dict(
            "lines_batch",
            {batch_hash: (offset_this_batch, lines_this_batch, n_seg_ids)},
        )
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
        self.update_dict("sent_hashes", {batch_hash: len(results)})
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
    ):
        self._connection = connection
        self.hash = qhash
        qi = self.qi
        self.json_query: dict = json_query or qi.get("json_query", {})
        self.config: dict = config or qi.get("config", {})
        self.meta_json: dict = meta_json or qi.get("meta_json", {})
        self.post_processes: dict = post_processes or qi.get("post_processes", {})
        self.result_sets: list = self.meta_json.get("result_sets", [])
        self.meta_labels: list[str] = qi.get("meta_labels", [])
        self.languages: list[str] = languages or qi.get("languages", [])
        if not qi:
            self.update()

    def update(self, obj: dict = {}):
        """
        Update the attributes of this instance and the entry in Redis
        """
        if obj:
            _update_query_info(self._connection, self.hash, info=obj)
            return
        qi = _get_query_info(self._connection, self.hash)
        for aname in dir(self):
            if aname.startswith("_") or aname == "requests":
                continue
            attr = getattr(self, aname)
            if not isinstance(attr, SERIALIZABLES):
                continue
            qi[aname] = attr
        _update_query_info(self._connection, self.hash, info=qi)

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

    def get_observer(self, attribute_name: str) -> Callable:
        """
        Trigger an update in redis whenever the observable is modified
        """
        return lambda event, value, *_: self.update({attribute_name: value})

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
        enqueued_jobs = self.qi.get("enqueued_jobs", {})
        return cast(
            dict[str, int],
            ObservableDict(
                **enqueued_jobs, observer=self.get_observer("enqueued_jobs")
            ),
        )

    @enqueued_jobs.setter
    def enqueued_jobs(self, value: dict[str, int]):
        self.update({"enqueued_jobs": value})

    @property
    def running_batch(self) -> str:
        return self.qi.get("running_batch", "")

    @running_batch.setter
    def running_batch(self, value: str):
        self.update({"running_batch": value})

    @property
    def done_batches(self) -> list:
        done_batches = self.qi.get("done_batches", [])
        return cast(
            list,
            ObservableList(*done_batches, observer=self.get_observer("done_batches")),
        )

    @done_batches.setter
    def done_batches(self, value: list):
        self.update({"done_batches": value})

    @property
    def query_batches(self) -> dict:
        """
        Map batch names with (batch_hash, n_kwic_lines)
        """
        query_batches: dict = {}
        for k in self.qi.get("query_batches", {}):
            try:
                batch_key: str = f"{self.hash}::query_batch::{k}"
                value = (self._connection.get(batch_key) or b"").decode("utf-8")
                query_batches[k] = json.loads(value)
            except:
                print(f"Could not find batch {k} in Redis memory for qi {self.hash}")
        observer = lambda event, value, *_: self.__setattr__("query_batches", value)
        return cast(dict, ObservableDict(observer=observer, **query_batches))

    @query_batches.setter
    def query_batches(self, value: dict):
        query_batches = self.qi.get("query_batches", {})
        for k, v in value.items():
            if k not in query_batches:
                query_batches[k] = False
            redis_key: str = f"{self.hash}::query_batch::{k}"
            self._connection.set(redis_key, json.dumps(v, cls=CustomEncoder))
            self._connection.expire(redis_key, MESSAGE_TTL)
        self.update({"query_batches": query_batches})

    @property
    def segments_for_batch(self) -> dict[str, dict[str, dict[str, int]]]:
        """
        batch_hash->{segment_hash->segment_ids, segment_hash->segment_ids}
        """
        segments_for_batch: dict = {}
        prefix: str = f"{self.hash}::segments_for_batch::*"
        for redis_key in self._connection.scan_iter(prefix):
            rk = redis_key.decode("utf-8")
            batch_name = str(rk).split("::segments_for_batch::")[-1]
            try:
                value = (self._connection.get(rk) or b"").decode("utf-8")
                segments_for_batch[batch_name] = json.loads(value)
            except:
                pass
        observer = lambda event, value, *_: self.__setattr__(
            "segments_for_batch", value
        )
        return cast(dict, ObservableDict(observer=observer, **segments_for_batch))

    @segments_for_batch.setter
    def segments_for_batch(self, value: dict):
        for k, v in value.items():
            redis_key: str = f"{self.hash}::segments_for_batch::{k}"
            self._connection.set(redis_key, json.dumps(v, cls=CustomEncoder))
            self._connection.expire(redis_key, MESSAGE_TTL)

    def has_request(self, request: Request):
        return any(r.id == request.id for r in self.requests)

    def add_request(self, request: Request):
        request.hash = self.hash
        requests = self.requests
        if request in self.requests:
            return
        rids = [r.id for r in requests]
        rids.append(request.id)
        _update_query_info(self._connection, self.hash, info={"requests": rids})

    def delete_request(self, request: Request):
        rids = [r.id for r in self.requests if r.id != request.id]
        _update_query_info(self._connection, self.hash, info={"requests": rids})
        rkey = f"request::{request.id}"
        try:
            self._connection.delete(rkey)
        except:
            pass

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
        next_batch: list = next(
            (
                b
                for n, b in enumerate(self.done_batches)
                if n > 0 and self.done_batches[n - 1][0] == previous_batch
            ),
            [],
        )
        if next_batch:
            return next_batch

        buffer = 0.1  # set to zero for picking smaller batches
        while len(self.done_batches) < len(self.all_batches):
            so_far = self.total_results_so_far
            # set here ensures we don't double count, even though it should not happen
            total_words_processed_so_far = sum([x[-1] for x in self.done_batches]) or 1
            proportion_that_matches = so_far / total_words_processed_so_far
            first_not_done: list[str | int] | None = None
            for batch in self.all_batches:
                if batch in self.done_batches:
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
        return _get_query_info(self._connection, hash=self.hash)

    @property
    def requests(self) -> list[Request]:
        """
        Return the associated requests
        The class Request already implements utmost recency
        """
        qi = _get_query_info(self._connection, self.hash)
        reqs = []
        for rid in qi.get("requests", []):
            try:
                _get_request(self._connection, f"request::{rid}")
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
        (_, to_send, _, _, _) = _aggregate_results(
            res,
            stats_results,
            meta_json,
            post_processes,
            batch,
            self.done_batches,
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
        batch_name, _ = batch
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
        if batch not in self.done_batches:
            self.done_batches.append(batch)
        return batch_hash

import datetime
import duckdb
import os
import pandas
import shutil

from aiohttp import web
from redis import Redis as RedisConnection
from rq import Callback, Queue
from rq.job import get_current_job, Job
from typing import Any, cast
from uuid import uuid4

from .callbacks import _general_failure
from .jobfuncs import _handle_export, _db_query
from .query_classes import Request, QueryInfo
from .utils import _get_mapping, _publish_msg, sanitize_filename

EXPORT_TTL = 5000
RESULTS_DIR = os.getenv("RESULTS", "results")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")


class Exporter:

    def __init__(self, request: Request, qi: QueryInfo) -> None:
        self._request: Request = request
        self._qi: QueryInfo = qi
        self._config: dict = qi.config
        seg_layer: str = self._config["segment"]
        seg_mapping: dict[str, Any] = _get_mapping(
            seg_layer, qi.config, "", qi.languages[0]
        )
        self._column_headers: list[str] = seg_mapping["prepared"]["columnHeaders"]
        self._form_index = self._column_headers.index("form")
        self._results_info: list[dict[str, Any]] = []
        self._info: dict[str, Any] = {}

        filename: str = cast(str, (request.to_export or {}).get("filename", ""))
        if not filename:
            filename = f"{qi.config.get('shortname')} {datetime.datetime.now().strftime('%Y-%m-%d %I:%M%p')}.db"
        self._filename = sanitize_filename(filename)
        corpus_folder = sanitize_filename(
            qi.config.get("shortname") or qi.config["project_id"]
        )
        userpath: str = os.path.join(corpus_folder, filename)
        suffix: int = 0
        while os.path.exists(os.path.join(RESULTS_USERS, request.user, userpath)):
            suffix += 1
            userpath = os.path.join(
                corpus_folder, f"{os.path.splitext(filename)[0]} ({suffix}).db"
            )
        self._userpath = userpath

    @staticmethod
    def get_dl_path_from_hash(
        hash: str,
        offset: int = 0,
        requested: int = 0,
        full: bool = False,
        filename: bool = False,
    ) -> str:
        hash_folder = os.path.join(RESULTS_DIR, hash)
        swissdox_folder = os.path.join(hash_folder, "swissdox")
        if not os.path.exists(swissdox_folder):
            os.makedirs(swissdox_folder)
        if filename:
            swissdox_folder = os.path.join(swissdox_folder, "results.db")
        return swissdox_folder

    @staticmethod
    def finish_immediately(
        job: Job,
        connection: RedisConnection,
        result: Any,
    ) -> None:
        """
        Callback to initiate_db.
        Immediately mark as finished if no need to run export.
        """
        should_run: bool = cast(dict, job.kwargs).get("should_run", True)
        if should_run:
            return
        qhash, _, _, offset, requested = job.args
        full: bool = cast(dict, job.kwargs).get("full", False)
        Exporter.finish_db(connection, qhash, offset, requested, requested, full)

    @classmethod
    def finish_db(
        cls,
        connection: RedisConnection,
        qhash: str,
        offset: int,
        requested: int,
        delivered: int,
        full: bool,
    ):
        """
        Mark an export in the DB as finished
        """
        q = Queue("internal", connection=connection)
        q.enqueue(
            _handle_export,  # finish_export
            on_failure=Callback(_general_failure),
            args=(qhash, "swissdox"),
            kwargs={
                "create": False,
                "offset": offset,
                "requested": requested,
                "delivered": delivered,
                "path": cls.get_dl_path_from_hash(
                    qhash, offset, requested, full, filename=True
                ),
            },
        )
        payload: dict[str, Any] = {
            "action": "export_complete",
            "hash": qhash,
        }
        _publish_msg(
            connection,
            payload,
            msg_id=str(uuid4()),
        )

    @classmethod
    def initiate_db(
        cls,
        app: web.Application,
        shash: str,
        config: dict,
        request: Request,
    ) -> bool:
        """
        Mark an export in the DB as initiated and return whether a query should be run
        """
        should_run: bool = True
        to_export: dict = cast(dict, request.to_export)
        xp_format: str = to_export.get("format", "xml") or "xml"
        epath = app["exporters"][xp_format].get_dl_path_from_hash(
            shash, request.offset, request.requested, request.full
        )
        ext: str = ".db"
        filename: str = cast(str, to_export.get("filename", ""))
        cshortname = config.get("shortname")
        if not filename:
            filename = f"{cshortname} {datetime.datetime.now().strftime('%Y-%m-%d %I:%M%p')}{ext}"
        filename = sanitize_filename(filename)
        corpus_folder = sanitize_filename(cshortname or config.get("project_id", ""))
        userpath: str = os.path.join(corpus_folder, filename)
        suffix: int = 0
        while os.path.exists(os.path.join(RESULTS_USERS, request.user, userpath)):
            suffix += 1
            userpath = os.path.join(
                corpus_folder, f"{os.path.splitext(filename)[0]} ({suffix}){ext}"
            )
        should_run = not os.path.exists(
            os.path.join(RESULTS_SWISSDOX, "exports", f"{shash}.db")
        )
        app["internal"].enqueue(
            _handle_export,  # init_export
            on_success=Callback(cls.finish_immediately),
            on_failure=Callback(_general_failure),
            result_ttl=EXPORT_TTL,
            job_timeout=EXPORT_TTL,
            args=(shash, xp_format, True, request.offset, request.requested),
            kwargs={
                "user_id": request.user,
                "userpath": userpath,
                "corpus_id": request.corpus,
                "should_run": should_run,
                "full": request.full,
            },
        )
        if should_run:
            shutil.rmtree(epath)
        return should_run

    @classmethod
    async def export(cls, request_id: str, qhash: str, payload: dict) -> None:
        """
        Entrypoint to export a payload; run finalize if all the payloads have been processed
        """
        job: Job = cast(Job, get_current_job())
        request: Request = Request(job.connection, {"id": request_id})
        qi: QueryInfo = QueryInfo(qhash, job.connection)
        offset = request.offset
        requested = request.requested
        full = request.full
        try:
            exporter = cls(request, qi)
            wpath = exporter.get_working_path()
            await exporter.process_lines(payload)
            if not request.is_done(qi):
                return
            # each payload needs corresponding *_query/*_segments subfolders
            qb_hashes = [bh for bh, _ in qi.query_batches.values()]
            for h, nlines in request.sent_hashes.items():
                if h not in qb_hashes or nlines <= 0:
                    continue
                if not os.path.exists(os.path.join(wpath, f"{h}_segments")):
                    return
            delivered = request.lines_sent_so_far
            await exporter.finalize()
            shutil.rmtree(exporter.get_working_path())
            for h in request.sent_hashes:
                hpath = os.path.join(wpath, f"{h}_segments")
                if os.path.exists(hpath):
                    shutil.rmtree(hpath)
            print(
                f"SWISSDOX Exporting complete for request {request.id} (hash: {request.hash}) ; DELETED REQUEST"
            )
            qi.delete_request(request)
            cls.finish_db(qi._connection, qi.hash, offset, requested, delivered, full)
        except Exception as e:
            shutil.rmtree(cls.get_dl_path_from_hash(qhash, offset, requested, full))
            print("ERROR", e)
            raise e

    def get_working_path(self, subdir: str = "") -> str:
        """
        The working path will be deleted after finalizing the results file
        If subdir is defined, it will append it at the end of the path
        Will create the directory if necessary
        """
        epath = Exporter.get_dl_path_from_hash(
            self._request.hash,
            self._request.offset,
            self._request.requested,
            self._request.full,
        )
        retpath = os.path.join(epath, ".working")
        if subdir:
            retpath = os.path.join(retpath, subdir)
        if not os.path.exists(retpath):
            os.makedirs(retpath)
        return retpath

    async def report_articles(self, payload: dict, batch_hash: str) -> None:
        """
        Write the article ids in batch-specific subfolders to avoid parallel io conflicts
        """
        print(
            f"[SWISSDOX Export {self._request.id}] Process segments for {batch_hash} (QI {self._request.hash})"
        )
        res = payload.get("result", [])
        index_aid = self._qi.meta_labels.index("Article_id")
        filepath = os.path.join(self.get_working_path(batch_hash), "article_ids")
        with open(filepath, "w") as output:
            output.write("\n".join(r[index_aid] for r in res["-2"]))
        print(
            f"[SWISSDOX Export {self._request.id}] Done processing segments for {batch_hash} (QI {self._request.hash})"
        )

    async def finalize(self) -> None:
        """
        Gather all the article IDs, send the query to the DB, and write to files
        """
        print(
            f"[SWISSDOX Export {self._request.id}] Finalizing... (QI {self._request.hash})"
        )
        article_ids = set()
        wpath = self.get_working_path()
        for batch_hash in self._request.sent_hashes:
            aid_file = os.path.join(wpath, batch_hash, "article_ids")
            if not os.path.exists(aid_file):
                continue
            with open(aid_file, "r") as aid_input:
                while line := aid_input.readline():
                    article_ids.add(line.strip())
        schema: str = self._qi.config["schema_path"]
        query = (
            f"""SELECT * FROM main.export_to_swissdoxviz('{schema}', :article_ids);"""
        )
        print(
            f"[SWISSDOX Export {self._request.id}] Running query with {len(article_ids)} article IDs"
        )
        res = await _db_query(
            query, {"article_ids": [aid for aid in article_ids]}, is_main=True
        )
        print("export complete!")
        dest_folder = os.path.join(RESULTS_SWISSDOX, "exports")
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        dest = os.path.join(dest_folder, f"{self._qi.hash}.db")
        if os.path.exists(dest):
            os.remove(dest)
        for table_name, index_col, data in cast(list, res):
            df = pandas.DataFrame.from_dict(
                {cname: cvalue if cvalue else [] for cname, cvalue in data.items()}
            )
            df.set_index(index_col)
            con = duckdb.connect(database=dest, read_only=False)
            con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        user = self._request.user
        userpath = os.path.join(RESULTS_SWISSDOX, user)
        if not os.path.exists(userpath):
            os.makedirs(userpath)
        original_userpath = self._userpath
        fn = os.path.basename(original_userpath)
        userdest = os.path.join(userpath, fn)
        if not os.path.exists(userdest) and not os.path.islink(userdest):
            os.symlink(os.path.abspath(dest), userdest)
        jso: dict[str, Any] = {
            "action": "export_complete",
            "format": "swissdox",
            "hash": self._qi.hash,
            "offset": 0,
            "total_results_requested": 200,
            "callback_query": None,
        }
        self._qi.publish("placholder", "export", jso)
        print(
            f"[SWISSDOX Export {self._request.id}] Complete (QI {self._request.hash})"
        )

    async def process_lines(self, payload: dict) -> None:
        """
        Take a payload and call process_query or process_segments
        """
        action = payload.get("action", "")
        batch_name = payload.get("batch_name", "")
        batch_hash = self._qi.query_batches[batch_name][0]
        if action == "query_result":
            # Only care for article_ids from segments
            pass
        elif action == "segments":
            await self.report_articles(payload, batch_hash)
            self.get_working_path(f"{batch_hash}_segments")  # creates the dir

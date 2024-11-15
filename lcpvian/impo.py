"""
Importer class: add corpora to our Postgres DB, as well as a relevant entry
in the main.corpus table where config is stored.

This code is as async as possible, so we can run multiple operations concurrently,
with concurrency settings stored in .env

Basically, the whole process is already heavily optimised, it will be hard
to improve performance except by tweaking .env settings and/or adding compute.

Users upload data by a command-line tool, `lcp-upload`, a submodule of this repo.

Eventually they can also upload corpora through the web-app frontend.

This all happens as one long pipeline. To provide the user with feedback, we
don't just print progress info, but also write it to file in a special format.

The CLI tool polls the /create and /upload endpoints to check progress; the
code in upload.py reads the temporary file and calculates progress info to
return to the user based on its contents.

A parseable line in the file, <project-uuid>/.progress.txt looks like:

    `:progress:<bytes_done>:<total_bytes>:<filename>:`

There are many of these lines -- the bytes_done from all of them are summed,
to provide a percentage total via tqdm progress bar

In the last stages of the upload process, the corpus is indexed in the DB. For
that, progress looks like:

    `:progress:1:<num_jobs>:extras:`

This can be used to show the user how many indexing jobs are done and left to go

Look at upload._get_progress to understand how the pgoress info is parsed

"""

import importlib
import json
import os
import re

from collections.abc import Callable, Coroutine, Sequence
from io import BytesIO
from textwrap import dedent
from typing import Any, cast

from aiofiles import open as aopen
from aiofiles.threadpool.binary import AsyncBufferedReader

from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from .configure import CorpusTemplate, Meta
from .typed import JSONObject, MainCorpus, Params, RunScript
from .utils import (
    _format_config_query,
    format_query_params,
    gather,
    _schema_from_corpus_name,
)


class SQLstats:
    def __init__(self) -> None:
        self.check_tbl: Callable[[str, str], str] = lambda x, y: dedent(
            f"""
            SELECT EXISTS (
                   SELECT 1
                     FROM information_schema.tables
                    WHERE table_schema = '{x}'
                      AND table_name = '{y}');"""
        )

        self.copy_table: Callable[[str, str, str], str] = lambda x, y, z: dedent(
            f"""
            COPY {x}.{y} {z}
            FROM STDIN
            WITH CSV QUOTE E'\b' DELIMITER E'\t';"""
        )

        # self.main_corp: str = _format_config_query(
        #     dedent(
        #         """
        #     WITH mc AS (
        #         INSERT
        #         INTO main.corpus (name, current_version, corpus_template, project_id, schema_path, token_counts, mapping, enabled)
        #         VALUES (:name, :ver, :template, :project, :schema, :counts, :mapping, true)
        #         RETURNING *
        #     )
        #     SELECT {selects}
        #     FROM mc
        #     {join} WHERE mc.enabled = true;"""
        #     )
        # )
        self.main_corp: str = _format_config_query(
            dedent(
                """
            WITH mc AS (SELECT * FROM main.finish_import(:tmp_schema ::uuid, :new_schema ::text, :mapping ::jsonb, :counts ::jsonb, :sample_query ::text))
            SELECT {selects}
            FROM mc
            {join} WHERE mc.enabled = true;"""
            )
        )

        self.token_count: Callable[[str, str], str] = lambda x, y: dedent(
            f"""
            SELECT count(*)
              FROM "{x}".{y};"""
        )


class Table:
    def __init__(
        self, schema: str, name: str, columns: list[str] | None = None
    ) -> None:
        self.schema: str = schema
        self.name: str = name
        self.columns: list[str] | None = columns

    def col_repr(self) -> str:
        if self.columns:
            return "(" + ", ".join(self.columns) + ")"
        else:
            return ""


class Importer:
    def __init__(
        self, pool: AsyncEngine, data: JSONObject, project_dir: str, debug: bool = False
    ) -> None:
        """
        Manage the import of a corpus into the DB via async postgres connection
        """
        _loader: str = str(importlib.import_module(self.__module__).__loader__)
        self.sql: SQLstats = SQLstats()
        self.pool: AsyncEngine = pool
        self.template = cast(CorpusTemplate, data["template"])
        self.template["uploaded"] = True
        meta: Meta = cast(Meta, self.template.get("meta", {}))
        self.name: str = meta.get("name", "Untitled corpus")
        self.version: int | str | float = meta.get("version", "1")
        self.schema = self.template.get("schema_name", "")
        self.batches = cast(list[str], data["batchnames"])
        self.insert = cast(str, data["prep_seg_insert"])
        self.updates = cast(list[str], data["prep_seg_updates"])
        self.constraints = cast(list[str], data["constraints"])
        self.create = cast(str, data["prep_seg_create"])
        self.m_token_freq = cast(str, data["m_token_freq"])
        self.m_token_n = cast(str, data["m_token_n"])
        self.m_lemma_freqs = cast(str, data["m_lemma_freqs"])
        self.refs = cast(list[str], data["refs"])
        self.grant_query_select = cast(str, data["grant_query_select"])
        self.n_batches = len(self.batches)
        self.num_extras = self.n_batches + len(self.constraints)
        self.token_count: dict[str, int] = {}
        self.mapping = cast(JSONObject, data["mapping"])
        self.project_dir: str = project_dir
        self.corpus_size: int = 0
        self.max_concurrent = int(os.getenv("IMPORT_MAX_CONCURRENT", 2))
        self.mypy = "SourceFileLoader" not in _loader
        self.batchsize = int(float(os.getenv("IMPORT_MAX_COPY_GB", 1)) * 1e9)
        self.max_gb = int(os.getenv("IMPORT_MAX_MEMORY_GB", "1"))
        self.max_bytes = int(max(0, self.max_gb) * 1e9)
        self.upload_timeout = int(os.getenv("UPLOAD_TIMEOUT", 300))
        self.debug = debug
        # self.drops: list[str] = cast(list[str], data.get("drops", []))
        return None

    def update_progress(self, msg: str) -> None:
        """
        Both print and write progress information. We do this so the webapp
        can read this file to calculate progress information to show the user
        """
        print(msg)
        path = os.path.join(self.project_dir, ".progress.txt")
        with open(path, "a") as fo:
            fo.write(msg.rstrip() + "\n")
        return None

    async def cleanup(self) -> None:
        """
        Drop all the data we just tried to import -- used as exception handling
        """
        script = f"CALL main.cleanup('{self.schema}'::uuid);"
        self.update_progress(f"Running cleanup:\n{script}")
        await self.run_script(script)
        return None

    async def _get_positions(
        self, f: AsyncBufferedReader, size: int
    ) -> list[tuple[int, int]]:
        """
        Get the locations in an open aiofile to seek and read to

        We can't make this into an async generator yet because mypy doesn't support this
        """
        start_at = await f.tell()
        to_go = size - start_at
        positions: list[tuple[int, int]] = []

        while True:
            bat = int(self.batchsize)
            if start_at >= size:
                break
            await f.seek(start_at)
            lines = await f.read(self.batchsize)
            if not lines or not lines.strip():
                break
            if not lines.endswith(b"\n"):
                rest = await f.readline()
                bat += len(rest)
            positions.append((start_at, min(bat, to_go)))
            start_at = await f.tell()
        return positions

    async def copy_batch(
        self,
        start: int,
        chunk: int,
        csv_path: str,
        fsize: int,
        tot: int,
        schema: str,
        table: str,
        columns: list[str],
    ) -> None:
        """
        Copy a chunk of CSV into the DB, going no larger than self.batchsize
        plus potentially the remainder of a line
        """
        base = os.path.basename(csv_path)
        async with aopen(csv_path, "rb") as f:
            async with self.pool.begin() as conn:
                raw = await conn.get_raw_connection()
                await f.seek(start)
                data = await f.read(chunk)
                if not data or not data.strip():
                    return None
                await raw.cursor()._connection.copy_to_table(
                    table,
                    source=BytesIO(data),
                    schema_name=schema,
                    columns=columns,
                    delimiter="\t",
                    quote="\b",
                    format="csv",
                    timeout=self.upload_timeout,
                )
            self.update_progress(f":progress:{len(data)}:{tot}:{base}:")
        return None

    async def _copy_tbl(self, csv_path: str, fsize: int, tot: int) -> None:
        """
        Import csv_path to the DB, with or without concurrency
        """
        base = os.path.basename(csv_path)
        async with aopen(csv_path, "rb") as fop:
            headers = await fop.readline()
            headlen = len(headers)
            positions = await self._get_positions(fop, fsize)

        self.update_progress(f":progress:{headlen}:{tot}:{base}:")
        tab = base.split(".")[0]
        table = Table(self.schema, tab, headers.decode("utf-8").strip().split("\t"))
        script = self.sql.check_tbl(table.schema, table.name)
        exists = cast(list[tuple[bool]], await self.run_script(script, give=True))
        if exists[0][0] is False:
            raise ValueError(f"Table not found: {self.schema}.{tab}")

        if self.max_concurrent != 1:
            args = (
                csv_path,
                fsize - headlen,
                tot,
                table.schema,
                table.name,
                table.columns,
            )
            await self.process_data(positions, self.copy_batch, *args)
            return None

        # no concurrency:
        async with aopen(csv_path, "rb") as f:
            async with self.pool.begin() as conn:
                raw = await conn.get_raw_connection()
                for start, chunk in positions:
                    await f.seek(start)
                    data = await f.read(chunk)
                    await raw.cursor()._connection.copy_to_table(
                        table.name,
                        source=BytesIO(data),
                        schema_name=self.schema,
                        columns=table.columns,
                        delimiter="\t",
                        quote="\b",
                        format="csv",
                        timeout=self.upload_timeout,
                    )
                    sz = len(data)
                    self.update_progress(f":progress:{sz}:{tot}:{base}:")
        return None

    async def import_corpus(self) -> None:
        """
        Import all the .csv files in the corpus path and count the total tokens
        """
        self.update_progress("Importing corpus...")
        path = self.project_dir
        sizes = [
            (os.path.join(path, f), os.path.getsize(os.path.join(path, f)))
            for f in os.listdir(path)
            if f.endswith((".csv", ".tsv"))
        ]
        self.corpus_size = sum(s[1] for s in sizes)

        token_anchoring = self.template["layer"][
            self.template["firstClass"]["token"]
        ].get("anchoring", {})

        # Do some checks on the layer files
        for layer, layer_attrs in self.template["layer"].items():
            lowlayer = layer.lower()
            fpath = os.path.join(
                path,
                lowlayer
                + (
                    "0.csv"
                    if layer
                    in (
                        self.template["firstClass"]["token"],
                        self.template["firstClass"]["segment"],
                    )
                    else ".csv"
                ),
            )
            if not os.path.exists(fpath):
                fpath = fpath.replace(".csv", ".tsv")
            assert os.path.exists(fpath), FileNotFoundError(
                f"Could not find a file named {lowlayer}.csv for layer '{layer}'"
            )
            if layer_attrs.get("layerType") == "relation":
                continue
            with open(fpath, "r") as layer_file:
                columns = layer_file.readline().rstrip().split("\t")
                assert lowlayer + "_id" in columns, ReferenceError(
                    f"Column '{lowlayer}_id' missing from file {lowlayer}.csv"
                )
                anchoring = layer_attrs.get("anchoring", {})
                anchored_stream = (
                    anchoring.get("stream")
                    or layer in self.template["firstClass"]
                    and token_anchoring.get("stream")
                )
                anchored_time = (
                    anchoring.get("time")
                    or layer in self.template["firstClass"]
                    and token_anchoring.get("time")
                )
                assert not anchored_stream or "char_range" in columns, ReferenceError(
                    f"Column 'char_range' missing from file {lowlayer}.csv"
                )
                assert not anchored_time or "frame_range" in columns, ReferenceError(
                    f"Column 'frame_range' missing from file {lowlayer}.csv"
                )
                if layer != self.template["firstClass"]["document"]:
                    continue
                # self.partition_on_doc_range(
                #     columns,
                #     "char_range" if anchored_stream else "frame_range",
                #     layer_file,
                # )

        await self.process_data(sizes, self._copy_tbl, *(self.corpus_size,))
        return None

    def partition_on_doc_range(
        self, columns: list[str], anchoring: str, file: Any
    ) -> None:
        ncol: int = next(n for n, col in enumerate(columns) if col == anchoring)
        ranges: list[tuple[int, int]] = []

        while line := file.readline():
            range_min, range_max = [
                int(i)
                for i in line.split("\t")[ncol].lstrip("[ ").rstrip(") ").split(",")
            ]
            ranges.append((range_min, range_max))

        ranges = sorted(ranges, key=lambda r: r[0])
        num_partitions = 10
        partition_ranges: list[tuple[int, int]] = []

        for np in range(num_partitions - 1):  # split n-1 times to get n partitions
            last_iteration = np == (num_partitions - 2)
            if len(ranges) == 1:
                partition_ranges.append((ranges[0][0], ranges[-1][1]))
                ranges = []
            if not ranges:
                break
            mid_r = ranges[0][0] + ((ranges[-1][1] - ranges[0][0]) / 2)
            # include in left as long as 'mid' falls further than the range's mid-point
            left_ranges = [
                r for r in ranges if r[1] < mid_r or (mid_r - r[0] > r[1] - mid_r)
            ]
            right_ranges = [r for r in ranges if r not in left_ranges]
            if last_iteration:
                more_chars_in_left = (left_ranges[-1][1] - left_ranges[0][0]) > (
                    right_ranges[-1][1] - right_ranges[0][0]
                )
                first_ranges = left_ranges if more_chars_in_left else right_ranges
                second_ranges = right_ranges if more_chars_in_left else left_ranges
                partition_ranges.append((first_ranges[0][0], first_ranges[-1][1]))
                partition_ranges.append((second_ranges[0][0], second_ranges[-1][1]))
                ranges = []
            else:
                # Keep as many documents as possible in the next range, to maximize the chances of further splitting
                more_docs_in_left = len(left_ranges) > len(right_ranges)
                ranges_to_add = right_ranges if more_docs_in_left else left_ranges
                partition_ranges.append((ranges_to_add[0][0], ranges_to_add[-1][1]))
                ranges = left_ranges if more_docs_in_left else right_ranges

        for first_layer in cast(dict[str, str], self.template["firstClass"]).values():
            for n, pr in enumerate(partition_ranges, start=1):
                suffix = str(n)
                if n == len(partition_ranges):
                    suffix = "rest"
                print(
                    f"CREATE TABLE {first_layer.lower()}{suffix} PARTITION OF document FOR VALUES FROM ('[{pr[0]},{pr[0]+1})'::int4range) TO ('[{pr[1]-1},{pr[1]})'::int4range)"
                )

    async def process_data(
        self,
        iterable: Sequence[str | tuple[str | int, int]],
        method: Callable[..., Coroutine[None, None, RunScript]],
        *args: int | None | str | list[str],
        **kwargs: bool | str | None | Params,
    ) -> list[RunScript]:
        """
        Do the execution of copy_batch or copy_table (method) from iterable data

        If the size of the combined tasks goes beyond self.max_bytes, we start
        those in the queue and wait for them to finish before adding more.

        All processing occurs with self.max_concurrent respected
        """
        mc = self.max_concurrent
        name = "import"
        current_size = 0
        tasks: list[Coroutine[None, None, RunScript]] = []
        batches = f"in batches of {mc}" if mc > 0 else "concurrently"
        gathered: list[Any] = []
        cs: float | int = 0.0
        first: str | int = ""
        more: list[RunScript] | list[Any] = []
        give: bool = cast(bool, kwargs.get("give", False))
        mname = method.__name__
        progs = "Doing {} {} tasks {}...({}MB vs {}GB)"
        for tup in iterable:
            if isinstance(tup, (str, int)):
                first = tup
                size = 0
            else:
                first, size = tup
            current_size += size
            too_big = self.max_bytes and current_size >= self.max_bytes and len(tasks)
            if too_big:
                cs = current_size / 1e6
                msg = progs.format(len(tasks), mname, batches, f"{cs:.2f}", self.max_gb)
                self.update_progress(msg)
                more = await gather(mc, tasks, name=name)
                if len(more) and give is True:
                    gathered += more
                tasks = []
                current_size = 0
            tasks.append(method(first, size, *args, **kwargs))

        if tasks:
            cs = current_size / 1e6
            rem = f"remaining {mname}"
            msg = progs.format(len(tasks), rem, batches, f"{cs:.2f}", self.max_gb)
            self.update_progress(msg)
            more = await gather(mc, tasks, name=name)
            if len(more) and give is True:
                gathered += more
        return gathered

    async def get_token_count(self) -> dict[str, int]:
        """
        count inserted words/tokens in DB and return
        TODO: not working for parallel
        """
        fc = cast(dict[str, str], self.template.get("firstClass", {}))
        token = fc["token"].lower()
        names: list[str] = []
        queries: list[str] = []
        for i in range(self.n_batches + 1):
            formed = f"{token}{i}" if i < self.n_batches else f"{token}rest"
            names.append(formed)
            query: str = self.sql.token_count(self.schema, formed)
            queries.append(query)
        task = self.process_data(queries, self.run_script, give=True)
        response = cast(list[list[tuple[int]]], await task)
        res: dict[str, int] = {k: int(v[0][0]) for k, v in zip(names, response)}
        return res

    async def run_script(
        self,
        script: str,
        *args: Any,
        give: bool = False,
        progress: str | None = None,
        params: dict[str, int | str] = {},
    ) -> RunScript:
        """
        Run a simple script, and return the result if give

        If progress, also print/write progress info

        Messing with this method in even trivial ways can cause segfaults for mysterious reasons
        """

        base: dict[str, int | str] = {}
        out: list[tuple[Any, ...]]
        params = params or base
        ares: list[Row[Any]] | str | None
        async with self.pool.begin() as conn:
            # bit of a hack to deal with sqlalchemy problem with prepared_statements
            if script.count(";") > 1:
                raw = await conn.get_raw_connection()
                con = raw._connection  # type: ignore
                async with con.transaction():
                    script, new_params = format_query_params(script, params)
                    # i believe this first one is broken but unused:
                    if new_params:
                        ares = await con.execute(script, new_params)
                    else:
                        ares = await con.execute(script)
                    if progress:
                        self.update_progress(progress)
                    if give and ares:
                        out = [tuple(i) for i in ares]
                        return cast(RunScript, out)
                    return None
            res = await conn.execute(text(script), params)
            if progress:
                self.update_progress(progress)
            if not give:
                return None
            out = [tuple(i) for i in res.fetchall()]
            return cast(RunScript, out)
        return None

    async def prepare_segments(
        self,
        progress: str | None = None,
    ) -> None:
        """
        Run the prepared segment scripts, potentially concurrently
        """
        self.update_progress("Computing prepared segments...")
        await self.run_script(self.create)
        msg = f"Running {len(self.batches)} insert tasks:\n{self.insert}\n"
        self.update_progress(msg)
        inserts = [self.insert.format("{}", batch=batch) for batch in self.batches]
        await self.process_data(inserts, self.run_script, progress=progress)
        msg = f"Running {len(self.updates)} * {len(self.batches)} prepared annotations tasks:\n{self.updates}\n"
        self.update_progress(msg)
        updates = [
            u.format(LB="{", RB="}", batch=batch)
            for batch in self.batches
            for u in self.updates
        ]
        await self.process_data(updates, self.run_script, progress=progress)
        return None

    async def collocations(self) -> None:
        """
        Run the prepared segment scripts, potentially concurrently
        """
        self.update_progress("Creating materialized views for collocations...")
        self.update_progress("- token_freq")
        await self.run_script(self.m_token_freq)
        self.update_progress("- token_n")
        await self.run_script(self.m_token_n)
        self.update_progress("- lemma_freqs")
        await self.run_script(self.m_lemma_freqs)
        self.update_progress("Done with collocations!")
        return None

    async def create_entry_maincorpus(self) -> MainCorpus:
        """
        Add a row to main.corpus with metadata about the imported corpus
        """
        self.update_progress("Adding to corpus list...")
        new_name: str = _schema_from_corpus_name(
            self.name.lower(), self.template.get("project", "")
        )
        # Default sample query
        segment_name: str = self.template["firstClass"]["segment"]
        token_name: str = self.template["firstClass"]["token"]
        segment_label: str = segment_name[0].lower()
        token_label: str = token_name[0].lower()
        if token_label == segment_label:
            token_label = token_name[0:1].lower()
        sample_query: str = f"""{segment_name} {segment_label}

{token_name}@{segment_label} {token_label}

res => plain
    context
        {segment_label}
    entities
        {token_label}"""
        if "meta" in self.template and "sample_query" in self.template["meta"]:
            sample_query = self.template["meta"].get("sample_query", "")
        params: dict[str, str | int] = dict(
            # name=self.name,
            # ver=int(self.version),
            tmp_schema=self.schema,
            new_schema=new_name,
            # project_id=self.template.get("project", ""),
            # template=json.dumps(dict(self.template)),
            # project=self.template.get("project", ""),
            # schema=self.schema,
            mapping=json.dumps(dict(self.mapping)),
            counts=json.dumps(self.token_count),
            sample_query=sample_query,
        )
        mc: str = self.sql.main_corp
        task = self.run_script(mc, give=True, params=params)
        rows = cast(list[MainCorpus], await task)
        # The row is now in main.corpus, time to update the app's config?
        return rows[0]

    async def pipeline(self) -> MainCorpus:
        """
        Run the entire import pipeline: add data, set indices, grant rights
        """
        await self.import_corpus()
        self.token_count = await self.get_token_count()
        pro = f":progress:1:{self.num_extras}:extras:"
        cons = "\n".join(self.constraints)
        self.update_progress(f"Setting constraints...\n{cons}")
        await self.process_data(self.constraints, self.run_script, progress=pro)
        if len(self.refs):
            strung = "\n".join(self.refs)
            self.update_progress(f"Running:\n{strung}")
            await self.run_script(strung)
        await self.prepare_segments(progress=pro)
        await self.collocations()
        self.update_progress(f"Granting select privileges for querying...")
        await self.run_script(self.grant_query_select)
        self.update_progress(f"Privileges granted!")
        # run the config glob_attr
        main_corp = cast(MainCorpus, await self.create_entry_maincorpus())
        return main_corp

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

import csv
import importlib

import importlib.util
import json
import os

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
    copy_to_table,
    _format_config_query,
    format_query_params,
    gather,
    _schema_from_corpus_name,
)

# passing the file name and path as argument
lcpcli_spec = importlib.util.spec_from_file_location(
    "lcpcli",
    os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        "lcpcli",
        "lcpcli",
        "check_files.py",
    ),
)
assert lcpcli_spec, RuntimeError("Could not find LCPCLI")
assert lcpcli_spec.loader, RuntimeError("Could not find a loader for LCPCLI")
lcpcli = importlib.util.module_from_spec(lcpcli_spec)
lcpcli_spec.loader.exec_module(lcpcli)


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
        self,
        pool: AsyncEngine,
        data: JSONObject,
        project_dir: str,
        debug: bool = False,
        **kwargs,
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
        self.filenames_to_delimiters_quotes: dict[str, tuple[str, str]] = {}
        self.force_delimiter: str = cast(str, kwargs.get("delimiter", ""))
        self.force_quote: str = cast(str, kwargs.get("quote", ""))
        self.force_escape: str | None = kwargs.get("escape") or None
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
                try:
                    await copy_to_table(
                        raw.cursor()._connection,
                        table,
                        BytesIO(data),
                        schema,
                        columns,
                        timeout=self.upload_timeout,
                        force_delimiter=(self.force_delimiter or ","),
                        force_quote=(self.force_quote or '"'),
                        force_escape=self.force_escape,
                    )
                except Exception as e:
                    print(f"Failed to copy table {table} with columns {columns}")
                    raise e
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
        parsed_headers = next(
            csv.reader(
                [headers.decode("utf-8")],
                delimiter=self.force_delimiter or ",",
                quotechar=self.force_quote or '"',
                escapechar=self.force_escape,
            )
        )
        table = Table(self.schema, tab, parsed_headers)
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
                    try:
                        await copy_to_table(
                            raw.cursor()._connection,
                            table.name,
                            BytesIO(data),
                            self.schema,
                            cast(list[str], table.columns),
                            timeout=self.upload_timeout,
                            force_delimiter=(self.force_delimiter or ","),
                            force_quote=(self.force_quote or '"'),
                            force_escape=self.force_escape,
                        )
                    except Exception as e:
                        print(
                            f"Failed to copy table {table.name} with columns {table.columns}"
                        )
                        raise e
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

        # Do some checks on the layer files
        checker = lcpcli.Checker(
            self.template,
            quote=self.force_quote or '"',
            delimter=self.force_delimiter or ",",
            escape=self.force_escape,
        )
        checker.run_checks(path, full=True, add_zero=True)

        await self.process_data(sizes, self._copy_tbl, *(self.corpus_size,))
        return None

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
        self.update_progress(f"Computing prepared segments...\n{self.create}\n")
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
        tok = self.template["firstClass"]["token"]
        tok_attrs = cast(dict, self.template["layer"][tok])["attributes"]
        if "lemma" in tok_attrs:
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
        self.token_count = await self.get_token_count()
        self.update_progress(f"Granting select privileges for querying...")
        await self.run_script(self.grant_query_select)
        self.update_progress(f"Privileges granted!")
        # run the config glob_attr
        main_corp = cast(MainCorpus, await self.create_entry_maincorpus())
        return main_corp

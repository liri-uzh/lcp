import json
import logging
import os
import pandas
import shutil
import traceback

import duckdb

from asyncpg import Range
from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from rq.connections import get_current_connection
from rq.job import get_current_job, Job

from .api import refresh_config
from .configure import CorpusTemplate
from .impo import Importer
from .typed import DBQueryParams, JSONObject, MainCorpus, Sentence, UserQuery
from .utils import _get_sent_ids


async def _upload_data(
    project: str,
    user: str,
    room: str | None,
    debug: bool,
    **kwargs: dict[str, JSONObject | bool],
) -> MainCorpus | None:
    """
    Script to be run by rq worker, convert data and upload to postgres
    """
    uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
    corpus = os.path.join(uploads_path, project)
    data_path = os.path.join(corpus, "_data.json")

    with open(data_path, "r") as fo:
        data: JSONObject = json.load(fo)

    # constraints = cast(list[str], data["constraints"])
    # perms = cast(str, data["perms"])
    # constraints.append(perms)

    # template = cast(CorpusTemplate, data["template"])

    # if not template.get("project"):
    #     template["project"] = project

    upool = get_current_job()._upool  # type: ignore
    importer = Importer(upool, data, corpus, debug)
    extra = {"user": user, "room": room, "project": project}
    row: MainCorpus | None = None
    try:
        msg = f"Starting corpus import for {user}: {project}"
        logging.info(msg, extra=extra)
        row = await importer.pipeline()
    except Exception as err:
        tb = traceback.format_exc()
        msg = f"Error during import/upload: {err}"
        print(msg, tb)
        extra["traceback"] = tb
        logging.error(msg, extra=extra)
        await importer.cleanup()
    finally:
        shutil.rmtree(corpus)  # todo: should we do this?
    if not row:
        raise RuntimeError(msg)
    return row


async def _create_schema(
    create: str,
    schema_name: str,
    # drops: list[str] | None,
    user: str = "",
    room: str | None = None,
    **kwargs: str | None,
) -> None:
    """
    To be run by rq worker, create schema in DB for a new corpus
    """
    # extra = {"user": user, "room": room, "drops": drops, "schema": schema_name}
    extra = {"user": user, "room": room, "schema": schema_name}

    # todo: figure out how to make this block a little nicer :P
    async with get_current_job()._upool.begin() as conn:  # type: ignore
        raw = await conn.get_raw_connection()
        con = raw._connection
        async with con.transaction():
            try:
                # Move this to the end of a successful upload pipeline instead
                # if drops:
                #     msg = f"Attempting schema drop (create) * {len(drops)-1}"
                #     create = "\n".join(drops) + "\n" + create
                print("Creating schema...\n", create)
                await con.execute(create)
            except Exception as err:
                print("Error when creating the schema", err)
                pass  # All is handled as one transaction now in open_import
                # script = f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'
                # extra.pop("drops")
                # msg = f"Attempting schema drop (create): {schema_name}"
                # logging.info(msg, extra=extra)
                # await con.execute(script)
    return None


async def _db_query(
    query: str,
    params: DBQueryParams = {},
    config: bool = False,
    store: bool = False,
    document: bool = False,
    **kwargs: str | None | int | float | bool | list[str],
) -> (
    list[tuple[Any, ...]]
    | tuple[Any, ...]
    | list[JSONObject]
    | JSONObject
    | list[MainCorpus]
    | list[UserQuery]
    | list[Sentence]
    | None
):
    """
    The function queued by RQ, which executes our DB query
    """
    # this can only be done after the previous job finished...
    if "depends_on" in kwargs and "sentences_query" in kwargs:
        dep = cast(list[str] | str, kwargs["depends_on"])
        total = cast(int, kwargs.get("total_results_requested"))
        offset = cast(int, kwargs.get("offset", -1))
        needed = cast(int, kwargs.get("needed", total))
        needed = max(-1, needed)  # todo: fix this earlier?
        ids: list[str] | list[int] | None = _get_sent_ids(dep, needed, offset=offset)
        if not ids:
            return None
        params = {"ids": ids}

    name = "_upool" if store else ("_wpool" if config else "_pool")
    job = get_current_job()
    pool = getattr(job, name)
    method = "begin" if store else "connect"

    first_job_id = cast(str, kwargs.get("first_job", ""))
    if first_job_id:
        first_job: Job = Job.fetch(first_job_id, connection=get_current_connection())
        if first_job:
            first_job_status = first_job.get_status(refresh=True)
            if first_job_status in ("stopped", "canceled"):
                print("First job was stopped or canceled - not executing the query")
                raise SQLAlchemyError("Job canceled")

    params = params or {}

    if job and cast(dict, job.kwargs).get("refresh_config", None):
        await refresh_config()

    async with getattr(pool, method)() as conn:
        try:
            res = await conn.execute(text(query), params)
            if store:
                return None
            out: list[tuple[Any, ...]] = [tuple(i) for i in res.fetchall()]
            return out
        except SQLAlchemyError as err:
            print(f"SQL error: {err}")
            raise err


# TODO:
# - save to proper path (based on hash) + create symlinks in projects (name queries?)
# - handle existing duckdb files (duckdb won't overwrite)
# - what happens for huge results? might need rethinking approach
# - launch export even when queries fetched from cache
# - communicate with frontend
async def _swissdox_export(
    job_ids: dict[str, str],
    documents: dict[str, Any] = {},
    config: dict[str, Any] = {},
    underlang: str = "",
    ne_cols: list[str] = [],
    download: bool = False,
) -> None:
    """
    Take all the results from the relevant jobs and write them to storage
    """
    conn = get_current_connection()

    prepared_segments_job: Job = Job.fetch(
        job_ids["prepared_segments"], connection=conn
    )
    named_entities_job: Job = Job.fetch(job_ids["named_entities"], connection=conn)

    project_path = os.path.join(
        os.environ.get("RESULTS_PATH", "results"),
        config.get("project_id", "all"),
    )
    if not os.path.exists(project_path):
        os.mkdir(project_path)
    path = os.path.join(project_path, config["meta"].get("name", "anonymous_corpus"))
    if not os.path.exists(path):
        os.mkdir(path)
    elif os.path.exists(os.path.join(path, "swissdox.db")):
        os.remove(os.path.join(path, "swissdox.db"))
        # return None

    sources: dict[str, str] = {}

    # Documents
    COLUMNS_TO_KEEP = ("pubdate", "doctype")
    docs_by_range: dict[int, tuple[int, str]] = {}
    lg = next((x for x in ("de", "fr", "it", "en", "rm") if underlang[1:] == x), "")
    doc_columns = [c for c in documents["columns"] if c in COLUMNS_TO_KEEP]
    doc_indices = []
    doc_rows = []
    doc_attrs = config["layer"][config["document"]]["attributes"]
    for n, row in enumerate(documents["rows"]):
        id = row.pop("id", n)
        doc_indices.append(str(id))
        if "char_range" in row and isinstance(row["char_range"], Range):
            cr = cast(Range, row["char_range"])
            lower, upper = (int(cr.lower or 0), int(cr.upper or 0))
            docs_by_range[lower] = (upper, id)
        # Sanitize types -- should do the same for all dfs
        formed_row = []
        for cl in doc_columns:
            c = row.get(cl, "")
            type = doc_attrs.get(cl, doc_attrs.get("meta", {}).get(cl, {})).get("type")
            if type == "integer":
                c = int(c or 0)
            elif type in ("text", "string", "vector"):
                c = str(c)
            formed_row.append(c)
        formed_row.append(lg)
        sources[row["source"]] = row["source_name"]
        formed_row.append(str(len(sources)))
        formed_row.append(str(id))
        doc_rows.append(formed_row)
    doc_columns += ["language", "source_id", "doc_id"]
    doc_pandas = pandas.DataFrame(data=doc_rows, index=doc_indices, columns=doc_columns)
    # doc_pandas.to_feather(os.path.join(path, "documents.feather"))

    # Tokens
    seg: str = config["segment"]
    segment_mapping: dict[str, Any] = config["mapping"]["layer"][seg]
    if "partitions" in segment_mapping and underlang:
        segment_mapping = segment_mapping["partitions"][underlang[1:]]
    column_headers = segment_mapping.get("prepared", {}).get("columnHeaders", [])
    tok_columns = [
        "form",
        "lemma",
        "upos",
        "xpos",
        "tense",
        "voice",
        "mood",
        "doc_id",
        "position",
    ]
    tok_indices = []
    tok_rows = []
    n_tok = 1
    for content, char_range in prepared_segments_job.result:
        if char_range.lower is None:
            continue  # Ignore segments that are not anchored
        doc_id: str = ""
        for lower, (upper, did) in docs_by_range.items():
            if lower > char_range.upper or upper < char_range.lower:
                continue
            doc_id = str(did)
            break
        for n, token in enumerate(content):
            tok_indices.append(str(n_tok))
            row = []
            for col in tok_columns[0:4]:
                row.append(str(token[column_headers.index(col)]))
            if token[4]:
                ufeat: dict = {}
                if isinstance(token[4], str):
                    ufeat = json.loads(token[4])
                else:
                    ufeat = token[4] or {}
                row.append(ufeat.get("Tense", None))
                row.append(ufeat.get("Voice", None))
                row.append(ufeat.get("Mood", None))
            else:
                row += [None, None, None]
            row.append(doc_id)
            row.append(str(n))
            tok_rows.append(row)
            n_tok += 1
    tok_pandas = pandas.DataFrame(data=tok_rows, index=tok_indices, columns=tok_columns)

    # Named entities to docs
    ne_to_id: dict[tuple[str, str], str] = {}  # map (form,type) to ne_id
    ne_to_docs: dict[str, dict[str, int]] = {}  # map ne_id to {doc_id: n}

    # Named entities
    # TODO: store named entities as a dict, whose keys are tuple[form,type]
    # if a key already exists, don't add it again (or do, whatever)
    ne_columns: list[str] = ["form", "type", "ned_id"]
    ne_indices = []
    ne_rows = []
    for char_range, form, typ in named_entities_job.result:
        doc_id = ""
        for lower, (upper, did) in docs_by_range.items():
            if lower > char_range.upper or upper < char_range.lower:
                continue
            doc_id = str(did)
            break
        ne_id: str = ne_to_id.get((form, typ), "")
        if not ne_id:
            ne_id = str(len(ne_to_id) + 1)
            ne_to_id[(form, typ)] = ne_id
            ne_to_docs[ne_id] = {}
        ne_to_docs[ne_id][doc_id] = ne_to_docs[ne_id].get(doc_id, 0) + 1
    for (form, typ), ne_id in ne_to_id.items():
        ne_indices.append(ne_id)
        ne_rows.append([form, typ, ne_id])
    ne_pandas = pandas.DataFrame(data=ne_rows, index=ne_indices, columns=ne_columns)

    ne_doc_columns: list[str] = ["doc_id", "ne_id", "freq"]
    ne_doc_indices = []
    ne_doc_rows: list[tuple[str, str, str]] = []
    ne_doc_idx = 1
    for ne_id, doc_counts in ne_to_docs.items():
        for doc_id, count in doc_counts.items():
            ne_doc_indices.append(str(ne_doc_idx))
            ne_doc_idx += 1
            ne_doc_rows.append((doc_id, ne_id, str(count)))
    ne_document_pandas = pandas.DataFrame(
        data=ne_doc_rows, index=ne_doc_indices, columns=ne_doc_columns
    )

    # Source
    source_columns: list[str] = ["source_id", "code", "name"]
    source_indices = []
    source_rows = []
    for source_id, (code, name) in enumerate(sources.items(), start=1):
        source_indices.append(str(source_id))
        source_rows.append((source_id, code, name))
    source_pandas = pandas.DataFrame(
        data=source_rows, index=source_indices, columns=source_columns
    )

    assert all(
        isinstance(x, pandas.DataFrame)
        for x in (doc_pandas, tok_pandas, ne_pandas, ne_document_pandas, source_pandas)
    )

    # # Zip file
    # with zipfile.ZipFile(os.path.join(path, "swissdox.zip"), mode="w") as archive:
    #     # archive.write(f"results/{corpus_index}/documents.tsv", "documents.tsv")
    #     archive.write(os.path.join(path, "documents.feather"), "documents.feather")
    #     archive.write(os.path.join(path, "tokens.feather"), "tokens.feather")
    #     archive.write(
    #         os.path.join(path, "namedentities.feather"), "namedentities.feather"
    #     )

    con = duckdb.connect(database=os.path.join(path, "swissdox.db"), read_only=False)

    con.execute("CREATE TABLE token AS SELECT * FROM tok_pandas")
    con.execute("CREATE TABLE ne AS SELECT * FROM ne_pandas")
    con.execute("CREATE TABLE document AS SELECT * FROM doc_pandas")
    con.execute("CREATE TABLE ne_document AS SELECT * FROM ne_document_pandas")
    con.execute("CREATE TABLE source AS SELECT * FROM source_pandas")

    # con.execute("ALTER TABLE token ADD FOREIGN KEY (doc_id) REFERENCES document(doc_id)")
    # con.execute("ALTER TABLE ne_document ADD FOREIGN KEY (doc_id) REFERENCES document(doc_id)")
    # con.execute("ALTER TABLE ne_document ADD FOREIGN KEY (ne_id) REFERENCES ne(ned_id)")

    con.close()

    return None

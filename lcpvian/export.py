from aiohttp import web
from asyncio import sleep
from rq import Callback, Queue
from rq.connections import get_current_connection
from rq.job import Job
from rq.registry import FinishedJobRegistry
from typing import Any, cast

from .callbacks import _export_complete, _general_failure
from .jobfuncs import _db_query, _swissdox_export
from .typed import JSONObject
from .utils import (
    _determine_language,
    format_meta_lines,
    hasher,
    push_msg,
    results_dir_for_corpus,
    META_QUERY_REGEXP,
)

import json
import os
import re

EXPORT_TTL = 5000
CHUNKS = 1000000  # SIZE OF CHUNKS TO STREAM, IN # OF CHARACTERS

SWISSDOX_PREPARED_QUERY = """SELECT ps.content, sg.char_range
FROM "{schema}".prepared_{seg_table}{underlang} ps
CROSS JOIN "{schema}".{seg_table}{underlang}0 sg
WHERE ps.{seg_table}_id = sg.{seg_table}_id
AND {doc_multi_range} @> sg.char_range;"""

SWISSDOX_NE_QUERY = """SELECT {ne_selects_str}
FROM "{schema}".{ne_table} ne {ne_joins_str}
WHERE {ne_wheres_str};"""
SWISSDOX_NE_SELECTS = ["form", "type"]


def _format_kwic(
    args: list, columns: list, sentences: dict[str, tuple], result_meta: dict, config={}
) -> tuple[str, str, dict, list, list]:
    """
    Return (kwic_name, sid, matches, tokens, annotations) for (sid,[tokens])+
    """
    kwic_name: str = result_meta.get("name", "")
    attributes: list = result_meta.get("attributes", [])
    entities_attributes: dict = next(
        (x for x in attributes if x.get("name", "") == "entities"), dict({})
    )
    entities: list = entities_attributes.get("data", [])
    sid, matches, *frame_range = (
        args  # TODO: pass doc info to compute timestamp from frame_range
    )
    first_token_id, prep_seg, annotations = sentences[sid]
    matching_entities: dict[str, int | list[int]] = {}
    for n in entities:
        n_type = n.get("type", "")
        is_span = n_type in ("sequence", "set") or (
            config.get("layer", {}).get(n_type, {}).get("contains", "").lower()
            == config["token"].lower()
        )
        if is_span:
            matching_entities[n["name"]] = []
        else:
            matching_entities[n["name"]] = 0

    tokens: list[dict] = list()
    for n, token in enumerate(prep_seg):
        token_id = int(first_token_id) + n
        for n_m, m in enumerate(matches):
            if isinstance(m, int):
                if m == token_id:
                    matching_entities[entities[n_m]["name"]] = cast(int, token_id)
            elif isinstance(m, list):
                if token_id in m:
                    me: list[int] = cast(
                        list[int], matching_entities[entities[n_m]["name"]]
                    )
                    me.append(token_id)
        token_dict = {columns[n_col]: col for n_col, col in enumerate(token)}
        token_dict["token_id"] = token_id
        tokens.append(token_dict)
    return (kwic_name, sid, matching_entities, tokens, annotations)


async def kwic(jobs: list[Job], resp: Any, config):
    sentence_jobs = []
    meta_jobs = []
    for j in jobs:
        j_kwargs = cast(dict, j.kwargs)
        if not j_kwargs.get("sentences_query"):
            continue
        if j_kwargs.get("meta_query"):
            meta_jobs.append(j)
        else:
            sentence_jobs.append(j)
    query_jobs = [j for j in jobs if j not in sentence_jobs and j not in meta_jobs]

    buffer: str = ""
    for j in query_jobs:
        j_kwargs = cast(dict, j.kwargs)
        if "current_batch" not in j_kwargs:
            continue
        segment_mapping = config["mapping"]["layer"][config["segment"]]
        columns: list = []
        if "partitions" in segment_mapping and "languages" in j_kwargs:
            lg = j_kwargs["languages"][0]
            columns = segment_mapping["partitions"].get(lg)["prepared"]["columnHeaders"]
        else:
            columns = segment_mapping["prepared"]["columnHeaders"]

        sentences: dict[str, tuple] = {}
        for sentence_job in sentence_jobs:
            if sentence_job.kwargs.get("depends_on") != j.id:
                continue
            if not sentence_job or not sentence_job.result:
                continue
            for row in sentence_job.result:
                uuid: str = str(row[0])
                first_token_id = row[1]
                tokens = row[2]
                annotations = []
                if len(row) > 3:
                    annotations = row[3]
                sentences[uuid] = (first_token_id, tokens, annotations)

        formatted_meta: dict[str, Any] = {}
        for meta_job in meta_jobs:
            if meta_job.kwargs.get("depends_on") == j.id:
                continue
            if not meta_job:
                continue
            result = meta_job.result or []
            incoming_meta: dict[str, Any] = cast(
                dict[str, Any],
                format_meta_lines(meta_job.kwargs.get("meta_query"), result),
            )
            formatted_meta.update(incoming_meta)

        meta = j_kwargs.get("meta_json", {}).get("result_sets", [])
        kwic_indices = [n + 1 for n, o in enumerate(meta) if o.get("type") == "plain"]

        for n_type, args in j.result:
            # We're only handling kwic results here
            if n_type not in kwic_indices:
                continue
            try:
                kwic_name, sid, matching_entities, tokens, annotations = _format_kwic(
                    args, columns, sentences, meta[n_type - 1], config=config
                )
                data = {
                    "sid": sid,
                    "matches": matching_entities,
                    "segment": tokens,
                    "annotations": annotations,
                }
                if sid in formatted_meta:
                    # TODO: check frame_range in meta here + return frame_range from _format_kwic to compute time?
                    data["meta"] = formatted_meta[sid]
                line: str = "\t".join(
                    [str(n_type), "plain", kwic_name, json.dumps(data)]
                )
            except Exception as err:
                print("Issue with _format_kwic when exporting", err)
                # Because queries for prepared segments only fetch what's needed for previewing purposes,
                # queries with lots of matches can only output a small subset of lines
                continue
            if len(f"{buffer}{line}\n") > CHUNKS:
                resp.write(buffer)
                await sleep(0.01)  # Give the machine some time to breathe!
                buffer = ""
            buffer += f"{line}\n"
    if buffer:
        resp.write(buffer)


async def export_dump(
    filepath: str, job_id: str, config: dict, download=False, **kwargs
) -> None:
    """
    Read the results from all the query, sentence and meta jobs and write them in dump.tsv
    """
    # if os.path.exists(filepath):
    #     return
    output = open(filepath, "w")
    output.write((("\t".join(["index", "type", "label", "data"]) + f"\n")))

    conn = get_current_connection()
    job = Job.fetch(job_id, connection=conn)
    finished_jobs = [
        Job.fetch(jid, connection=conn)
        for registry in [
            FinishedJobRegistry(name=x, connection=conn)
            for x in ("query", "background")
        ]
        for jid in registry.get_job_ids()
    ]
    associated_jobs = [
        j for j in finished_jobs if cast(dict, j.kwargs).get("first_job") == job_id
    ]

    job_kwargs = cast(dict, job.kwargs)

    meta = job_kwargs.get("meta_json", {}).get("result_sets", {})

    # Write query itself in first row
    output.write(
        "\t".join(
            ["0", "query", "query", json.dumps(job_kwargs.get("original_query", {}))]
        )
        + f"\n"
    )

    # Write KWIC results
    if next((m for m in meta if m.get("type") == "plain"), None):
        await kwic([job, *associated_jobs], output, config)

    # Write non-KWIC results
    for n_type, data in job.meta.get("all_non_kwic_results", {}).items():
        if n_type in (0, -1):
            continue
        info: dict = meta[n_type - 1]
        name: str = info.get("name", "")
        type: str = info.get("type", "")
        attr: list[dict] = info.get("attributes", [])
        for line in data:
            d: dict[str, list] = {}
            for n, v in enumerate(line):
                attr_name: str = attr[n].get("name", f"entry_{n}")
                d[attr_name] = v
            output.write(("\t".join([str(n_type), type, name, json.dumps(d)]) + f"\n"))

    output.close()


async def swissdox_query(query: str, use_cache: bool = True) -> Job:
    """
    Here we send the query to RQ and therefore to redis
    """
    conn = get_current_connection()

    hashed = str(hasher(query))
    job: Job | None

    if use_cache:
        try:
            job = Job.fetch(hashed, connection=conn)
            if job is not None:
                return cast(Job, job)
        except:
            pass

    q = Queue("background", connection=conn)
    job = q.enqueue(
        _db_query,
        # on_success=Callback(_query, self.timeout),
        on_failure=Callback(_general_failure, EXPORT_TTL),
        result_ttl=EXPORT_TTL,
        job_timeout=EXPORT_TTL,
        job_id=hashed,
        args=(query,),
    )
    return cast(Job, job)


async def export_swissdox(
    # app: web.Application,
    first_job_id: str,
    underlang: str,
    config,
    download=False,
    **kwargs,
) -> Job:
    """
    Schedule jobs to fetch all the prepared segments and named entities associated of the matched documents
    Return a job depending on the former to execute _swissdox_export (see jobfuncs)
    """
    # conn = app["redis"]
    conn = get_current_connection()

    finished_jobs = [
        Job.fetch(jid, connection=conn)
        for registry in [
            FinishedJobRegistry(name=x, connection=conn)
            for x in ("query", "background")
        ]
        for jid in registry.get_job_ids()
    ]
    jobs = [
        j
        for j in finished_jobs
        if j.id == first_job_id or cast(dict, j.kwargs).get("first_job") == first_job_id
    ]

    meta_jobs: list[Job] = [j for j in jobs if cast(dict, j.kwargs).get("meta_query")]

    document_layer: str = config["firstClass"]["document"]

    documents: dict[str, Any] = {"columns": set({}), "rows": [], "ranges": dict({})}
    for j in meta_jobs:
        if not j.result:
            continue
        cols_from_sql = re.match(
            META_QUERY_REGEXP, cast(dict, j.kwargs).get("meta_query", "")
        )
        if not cols_from_sql:
            continue
        column_names = [
            p.split(" AS ")[1].strip() for p in cols_from_sql[1].split(", ")
        ]
        doc_columns: dict[str, int] = {
            p[len(f"{document_layer}_") :]: n + 1
            for n, p in enumerate(column_names)
            if p.startswith(f"{document_layer}_")
        }
        if not doc_columns:
            continue
        if not documents["columns"]:
            documents["columns"] = {k for k in doc_columns if k != "meta"}
        for res in j.result:
            doc: dict[str, Any] = {}
            for col_name, ncol in doc_columns.items():
                if col_name == "meta":
                    meta_obj: dict
                    if isinstance(res[ncol], str):
                        meta_obj = json.loads(res[ncol])
                    else:
                        meta_obj = res[ncol]
                    for k, v in meta_obj.items():
                        documents["columns"].add(k)
                        doc[k] = v
                else:
                    doc[col_name] = res[ncol]
                    if col_name == "char_range":
                        documents["ranges"][int(res[ncol].lower)] = res[ncol].upper
            documents["rows"].append(doc)

    # Optimize the list of ranges to look up (merge sequential ones)
    current_range: dict = {}
    doc_ranges = []
    for l, u in documents["ranges"].items():
        if not current_range:
            current_range = {"lower": l, "upper": u}
        if u < current_range["upper"]:
            continue
        next_lower_range = current_range["upper"] + 1
        if l > next_lower_range:
            doc_ranges.append(current_range)
            current_range = {"lower": l, "upper": u}
            next_lower_range = u + 1
        if next_lower_range in documents["ranges"]:
            current_range["upper"] = documents["ranges"][next_lower_range]["upper"]
    if current_range:
        doc_ranges.append(current_range)

    doc_multi_range = ",".join([f"[{r['lower']},{r['upper']})" for r in doc_ranges])
    doc_multi_range = "'{" + doc_multi_range + "}'::int8multirange"
    schema: str = cast(str, config["schema_path"])

    seg_table: str = cast(str, config["firstClass"]["segment"]).lower()
    query_prepared_segments: str = SWISSDOX_PREPARED_QUERY.format(
        schema=schema,
        seg_table=seg_table,
        underlang=underlang,
        doc_multi_range=doc_multi_range,
    )

    ne_table = "namedentity"
    ne_mapping = config["mapping"]["layer"]["NamedEntity"]
    if "partitions" in ne_mapping and underlang:
        ne_mapping = ne_mapping["partitions"][underlang[1:]]
    if "relation" in ne_mapping:
        ne_table = ne_mapping["relation"]
    ne_cols = ["id", "char_range"]
    # ne_selects = ["ne.namedentity_id AS id", "ne.char_range AS char_range"]
    ne_selects = ["ne.char_range AS char_range"]
    ne_joins = []
    ne_wheres = [f"{doc_multi_range} @> ne.char_range"]
    ne_attributes = config["layer"]["NamedEntity"].get("attributes", {})
    # for attr_name, attr_values in ne_attributes.items():
    for attr_name in ne_attributes:
        if attr_name not in SWISSDOX_NE_SELECTS:
            continue
        ne_cols.append(attr_name)
        # if attr_values.get("type", "") == "text":
        mapping = ne_mapping.get("attributes", {}).get(attr_name, {})
        if mapping.get("type") == "relation":
            lookup_key = mapping.get("key", attr_name)
            lookup_table = mapping.get("name", attr_name)
            new_label = f"ne_{attr_name}".lower()
            join_table: str = f"{schema}.{lookup_table} {new_label}"
            formed_join_condition = f"ne.{lookup_key}_id = {new_label}.{lookup_key}_id"
            ne_joins.append(join_table)
            ne_wheres.append(formed_join_condition)
            ne_selects.append(f"{new_label}.{attr_name} AS {attr_name}")
        else:
            ne_selects.append(f"ne.{attr_name} AS {attr_name}")

    ne_selects_str = ", ".join(ne_selects)
    ne_joins_str = "\n        CROSS JOIN ".join(ne_joins)
    if ne_joins_str:
        ne_joins_str = f"\n        CROSS JOIN {ne_joins_str}"
    ne_wheres_str = "\n        AND ".join(ne_wheres)
    query_named_entities: str = SWISSDOX_NE_QUERY.format(
        ne_selects_str=ne_selects_str,
        schema=schema,
        ne_table=ne_table,
        ne_joins_str=ne_joins_str,
        ne_wheres_str=ne_wheres_str,
    )

    prepared_segments_job = await swissdox_query(query_prepared_segments)
    named_entities_job = await swissdox_query(query_named_entities)
    depends_on = [prepared_segments_job.id, named_entities_job.id]

    print("Scheduled swissdox export depending on", depends_on)
    # q = app["background"]
    q = Queue("background", connection=conn)
    return q.enqueue(
        _swissdox_export,
        on_success=Callback(_export_complete, EXPORT_TTL),
        on_failure=Callback(_general_failure, EXPORT_TTL),
        result_ttl=EXPORT_TTL,
        job_timeout=EXPORT_TTL,
        depends_on=depends_on,
        args=(
            {
                "prepared_segments": prepared_segments_job.id,
                "named_entities": named_entities_job.id,
            },
            documents,
            config,
            underlang,
        ),
        kwargs={"ne_cols": ne_cols, "download": download},
    )


async def export(app: web.Application, payload: JSONObject, first_job_id: str) -> Job:
    """
    Schedule job(s) to export data to storage
    Called in sock.py after the last batch was queried
    """
    export_format = payload.get("format", "")
    room = payload.get("room", "")
    user = payload.get("user", "")
    print("All batches done! Ready to start exporting")
    corpus_conf = payload.get("config", {})
    # Retrieve the first job to get the list of all the sentence and meta jobs that export_dump depends on (also batch for swissdox)
    first_job = Job.fetch(first_job_id, connection=app["redis"])
    depends_on = [
        jid
        for ks in ("_sent_jobs", "_meta_jobs")
        for jid in first_job.meta.get(ks, {}).keys()
    ]
    job: Job
    if export_format == "dump":
        rest: dict[str, Any] = {}
        if depends_on:
            print("Scheduled dump export depending on", depends_on)
            rest = {"depends_on": depends_on}
        job = app["background"].enqueue(
            export_dump,
            on_success=Callback(_export_complete, EXPORT_TTL),
            on_failure=Callback(_general_failure, EXPORT_TTL),
            result_ttl=EXPORT_TTL,
            job_timeout=EXPORT_TTL,
            args=(
                os.path.join(
                    results_dir_for_corpus(corpus_conf), f"dump_{first_job_id}.tsv"
                ),
                first_job_id,
                corpus_conf,
            ),
            kwargs={
                "download": payload.get("download", False),
                "room": room,
                "user": user,
            },
            **rest,
        )
    elif export_format == "swissdox":
        batch: str = cast(dict, first_job.kwargs).get("current_batch", ["", "", ""])[2]
        underlang = _determine_language(batch) or ""
        if underlang:
            underlang = f"_{underlang}"
        job = app["background"].enqueue(
            export_swissdox,
            on_failure=Callback(_general_failure, EXPORT_TTL),
            result_ttl=EXPORT_TTL,
            job_timeout=EXPORT_TTL,
            depends_on=depends_on,
            args=(first_job_id, underlang, corpus_conf),
            kwargs={
                "download": payload.get("download", False),
                "room": room,
                "user": user,
            },
        )

    room = cast(str, payload.get("room", ""))
    user = cast(str, payload.get("user", ""))
    export_msg: JSONObject = cast(
        JSONObject,
        {
            "room": room,
            "user": user,
            "action": "started_export",
            "job_id": str(job.id),
        },
    )
    await push_msg(
        app["websockets"],
        room,
        export_msg,
        skip=None,
        just=(room, user),
    )

    return job


async def download_export(request: web.Request) -> web.FileResponse:
    fn = request.match_info["fn"]
    path = os.path.join(results_dir_for_corpus(request.match_info), fn)
    return web.FileResponse(path)

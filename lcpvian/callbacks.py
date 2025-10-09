"""
callbacks.py: post-process the result of an SQL query and broadcast
it to the relevant websockets

These jobs are usually run in the worker process, but in exceptional
circumstances, they are run in the main thread, like when fetching
jobs that were run earlier

These callbacks are hooked up as on_success and on_failure kwargs in
calls to Queue.enqueue in query_service.py
"""

import duckdb
import json
import lxml.etree
import os
import pandas
import shutil
import tempfile
import traceback
import zipfile


from datetime import datetime
from types import TracebackType
from typing import Any, Unpack, cast
from lxml.builder import E
from uuid import uuid4
from xml.sax.saxutils import escape, quoteattr


from redis import Redis as RedisConnection
from rq.job import Job

from .configure import _get_batches
from .typed import (
    BaseArgs,
    Config,
    DocIDArgs,
    JSONObject,
    MainCorpus,
    UserQuery,
)
from .utils import (
    Interrupted,
    _row_to_value,
    _publish_msg,
    _sharepublish_msg,
)


PUBSUB_LIMIT = int(os.getenv("PUBSUB_LIMIT", 31999999))
MESSAGE_TTL = int(os.getenv("REDIS_WS_MESSSAGE_TTL", 5000))
RESULTS_SWISSDOX = os.environ.get("RESULTS_SWISSDOX", "results/swissdox")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
UPLOAD_MEDIA_PATH = os.environ.get("UPLOAD_MEDIA_PATH", "media")


def _document(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[BaseArgs],
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    action = "document"
    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))
    if not room:
        return
    msg_id = str(uuid4())
    jso = {
        "document": result,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
        "corpus": job_kwargs["corpus"],
        "doc_id": job_kwargs["doc"],
    }
    return _publish_msg(connection, jso, msg_id)


def _document_ids(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[DocIDArgs],
) -> None:
    """
    When a user requests a document, we give it to them via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))
    kind = cast(str, kwargs.get("kind", job_kwargs.get("kind", "audio")))
    if not room:
        return None
    msg_id = str(uuid4())
    formatted = {str(idx): info for idx, info in cast(list[tuple[int, dict]], result)}
    action = "document_ids"
    jso = {
        "document_ids": formatted,
        "action": action,
        "user": user,
        "msg_id": msg_id,
        "room": room,
        "job": job.id,
        "corpus_id": job_kwargs["corpus_id"],
        "kind": kind,
    }
    return _publish_msg(connection, jso, msg_id)


def _image_annotations(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[BaseArgs],
) -> None:
    """
    When a user requests image annotations, we give it to them via websocket
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    action = "image_annotations"
    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))
    if not room:
        return
    layer = cast(str, kwargs.get("layer", job_kwargs["layer"]))
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "annotations": result,
        "layer": layer,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
    }
    return _publish_msg(connection, jso, msg_id)


def _clip_media(
    job: Job,
    connection: RedisConnection,
    result: list[JSONObject] | JSONObject,
    **kwargs: Unpack[BaseArgs],
) -> None:
    """
    When a user requests image annotations, we give it to them via websocket
    """
    # TODO: maybe rewrite and/or move this to make things cleaner?
    job_kwargs: dict = cast(dict, job.kwargs)

    user = cast(str, kwargs.get("user", job_kwargs["user"]))
    room = cast(str | None, kwargs.get("room", job_kwargs["room"]))

    config = cast(dict, kwargs.get("config", job_kwargs.get("config", {})))
    span: list = cast(list, kwargs.get("span", job_kwargs.get("span", [0, 0])))
    doc = config.get("document", "")
    seg = config.get("segment", "")
    tok = config.get("token", "")
    layers = config.get("layer", {})
    columns = config["mapping"]["layer"][seg]["prepared"]["columnHeaders"]
    form_idx = columns.index("form")

    contain_seg = [doc]
    while 1:
        child = next(
            (l for l, p in layers.items() if p.get("contains", "") == contain_seg[-1]),
            None,
        )
        if child is None:
            break
        contain_seg.append(child)
        if child == seg:
            break
    if seg not in contain_seg:
        contain_seg.append(seg)

    globs: dict = {}
    contained: dict = {}
    uncontained: dict = {}
    prepared: dict = {}
    whens: dict = {}
    for x in result:
        layer, id, *more = cast(list, x)[0]
        if layer == "_prepared":
            prepared[id] = {"offset": more[0], "tokens": more[1]}
            continue
        fr_str: str = cast(dict, more[0]).get("frame_range", "")
        if fr_str is None:
            continue
        data = contained if layer in contain_seg else uncontained
        data[layer] = data.get(layer, {})
        data[layer][id] = more[0]
        fr_low, fr_up = [
            int(x) for x in fr_str.replace("[", "").replace(")", "").split(",")
        ]
        for k, v in more[0].items():
            attr = layers[layer].get("attributes", {}).get(k)
            if not attr:
                continue
            if "ref" in attr:
                sorted_obj = {x: v[x] for x in sorted(v.keys())}
                json_obj = json.dumps(sorted_obj)
                if json_obj not in globs:
                    globs[json_obj] = sorted_obj
                glob_idx = next(n for n, k in enumerate(globs) if k == json_obj)
                more[0][k] = f"#G{glob_idx + 1}"
        data[layer][id]["frame_range"] = [fr_low, fr_up]
        data[layer][id]["_id"] = id
        whens[fr_low] = whens.get(fr_low, {})
        whens[fr_low][layer] = whens[fr_low].get(layer, [])
        whens[fr_low][layer].append(more[0])
        whens[fr_up] = whens.get(fr_up, {})
        whens[fr_up][layer] = whens[fr_up].get(layer, [])

    assert doc in contained, AssertionError(f"Could not find {doc} in payload")
    doc_data = next(v for v in contained[doc].values())

    span_dur = float(span[1]) - float(span[0])
    doc_dur = doc_data["frame_range"][1] / 25.0 - doc_data["frame_range"][0] / 25.0
    assert span_dur < 10.0 or span_dur / doc_dur < 0.5, PermissionError(
        "Clipped media can only have a duration of up to 10 seconds or 50 percent of the original document"
    )

    whens_sorted = sorted(whens.keys())
    whens_sorted_idx = {w: n for n, w in enumerate(whens_sorted, start=1)}

    current_contains: dict = {}
    built_contains: str = ""
    open_at: dict = {}
    for w in whens_sorted:
        for n, c in enumerate(contain_seg):
            current = current_contains.get(c, [])
            found = whens[w].get(c, [])
            if not found:
                continue
            for f in found:
                if f in current:
                    continue
                indent = "      " + "".join(["  " for _ in range(n)])
                for n2, c2 in enumerate(contain_seg):
                    if n2 <= n:
                        continue
                    indent2 = "      " + "".join(["  " for _ in range(n2)])
                    while open_at.get(n2, 0) > 0:
                        open_at[n2] -= 1
                        built_contains += f"\n{indent2}</{c2}>"
                if open_at.get(n, 0) > 0:
                    built_contains += f"\n{indent}</{c}>"
                    open_at[n] = open_at[n] - 1
                open_at[n] = open_at.get(n, 0) + 1
                current = [x for x in current if x != f]
                current.append(f)
                start, end = [whens_sorted_idx[x] for x in f["frame_range"]]
                built_contains += f'\n{indent}<{c} start="#T{start}" end="#T{end}" '
                built_contains += " ".join(
                    f"{escape(k)}={quoteattr(str(v))}"
                    for k, v in f.items()
                    if k not in ("start", "end")
                )
                built_contains += ">"
                if c == seg:
                    counter = int(f["char_range"].split(",")[0].replace("[", ""))
                    for t in prepared[f["_id"]]["tokens"]:
                        tattrs = " ".join(
                            f"{escape(columns[n])}={quoteattr(str(t[n]))}"
                            for n in range(len(t))
                            if n != form_idx
                        )
                        cr = f'char_range="[{counter},{counter+len(t[form_idx])})"'
                        built_contains += f"\n{indent}  <{tok} {cr} {tattrs}>{escape(t[form_idx])}</{tok}>"
                        counter += len(t[form_idx]) + 1
            current_contains[c] = current
    for n, c in enumerate(reversed(contain_seg)):
        indent = "      " + "".join(["  " for _ in range(len(contain_seg) - 1 - n)])
        while open_at.get(n, 0) > 0:
            built_contains += f"\n{indent}</{c}>"
            open_at[n] = open_at[n] - 1

    glob_notes = [
        E.note(
            id=f"G{n}",
            type="global",
            **{str(x): str(y) for x, y in globs[k].items()},
        )
        for n, k in enumerate(globs, start=1)
    ]

    main_node = E.TEI(
        *(
            [
                E.teiHeader(
                    E.fileDesc(
                        E.notesStmt(
                            E.note(
                                *glob_notes,
                                type="TEMPLATE_DESC",
                            )
                        )
                    )
                )
            ]
            if globs
            else []
        ),
        E.text(
            E.timeline(
                E.when(absolute=str(span[0]), id="T0"),
                *[
                    E.when(
                        interval=str(
                            (int(x) - doc_data["frame_range"][0]) / 25.0 - span[0]
                        ),
                        since="#T0",
                        id=f"T{n}",
                    )
                    for n, x in enumerate(whens_sorted, start=1)
                ],
            ),
            E.body(
                *[
                    getattr(E, l)(
                        **{
                            str(k): str(v)
                            for k, v in x.items()
                            if k not in ("start", "end")
                        },
                        start="#T" + str(whens_sorted_idx[x["frame_range"][0]]),
                        end="#T" + str(whens_sorted_idx[x["frame_range"][1]]),
                    )
                    for l, vs in uncontained.items()
                    for x in sorted(vs.values(), key=lambda v: v["frame_range"][0])
                ],
                lxml.etree.XML(built_contains),
            ),
        ),
        xmlns="https://tei-c.org/ns/1.0/",
    )

    user_dir = os.path.join(RESULTS_USERS, user)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    xml_path = os.path.join(user_dir, "clip.xml")
    string_formed = lxml.etree.tostring(main_node, encoding="UTF-8", pretty_print="True", xml_declaration=True)  # type: ignore
    with open(xml_path, "w+", encoding="utf-8") as xml_out:
        xml_out.write(string_formed.decode())

    zip_fn = os.path.join(user_dir, "clip.zip")
    zf = zipfile.ZipFile(zip_fn, "w")
    zf.write(xml_path, "clip.xml")

    media_col, media_props = next(
        (x for x in config["meta"].get("mediaSlots", {}).items()), ("", "")
    )
    if media_fn := doc_data.get("media", {}).get(media_col):
        ext = media_fn[-3:]
        start, end = [float(x) for x in span]  # type: ignore
        fullpath = os.path.join(UPLOAD_MEDIA_PATH, config["schema_path"], media_fn)
        out_clip = os.path.join(user_dir, f"clip.{ext}")
        import ffmpeg

        stream = ffmpeg.input(fullpath)
        aud = stream.filter_("atrim", start=start, end=end).filter_(
            "asetpts", "PTS-STARTPTS"
        )
        if cast(dict, media_props).get("mediaType") == "video":
            vid = stream.trim(start=start, end=end).setpts("PTS-STARTPTS")
            joined = ffmpeg.concat(vid, aud, v=1, a=1).node
            output = ffmpeg.output(joined[0], joined[1], out_clip)
            output.run(overwrite_output=True)
        else:
            output = ffmpeg.output(aud, out_clip)
            output.run(overwrite_output=True)
        zf.write(out_clip, f"clip.{ext}")

    zf.close()

    action = "clip_media"
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "file": os.path.basename(zip_fn),
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
    }

    return _publish_msg(connection, jso, msg_id)


def _schema(
    job: Job,
    connection: RedisConnection,
    result: bool | None = None,
) -> None:
    """
    This callback is executed after successful creation of schema.
    We might want to notify some WS user?
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    user = job_kwargs.get("user")
    room = job_kwargs.get("room")
    if not room:
        return None
    msg_id = str(uuid4())
    action = "uploaded"
    jso = {
        "user": user,
        "status": "success" if not result else "error",
        "project": job_kwargs["project"],
        "project_name": job_kwargs["project_name"],
        "corpus_name": job_kwargs["corpus_name"],
        "action": action,
        "gui": job_kwargs.get("gui", False),
        "room": room,
        "msg_id": msg_id,
    }
    if result:
        jso["error"] = result

    return _publish_msg(connection, jso, msg_id)


def _upload(
    job: Job,
    connection: RedisConnection,
    result: MainCorpus | None,
) -> None:
    """
    Success callback when user has uploaded a dataset
    """
    if result is None:
        print("Result was none. Skipping callback.")
        return None
    project: str = job.args[0]
    user: str = job.args[1]
    room: str | None = job.args[2]
    job_kwargs: dict = cast(dict, job.kwargs)
    user_data: JSONObject = job_kwargs["user_data"]
    gui: bool = job_kwargs["gui"]
    msg_id = str(uuid4())
    action = "uploaded"

    # if not room or not result:
    #     return None
    jso = {
        "user": user,
        "room": room,
        "id": result[0],
        "user_data": user_data,
        "entry": _row_to_value(result, project=project),
        "status": "success" if not result else "error",
        "project": project,
        "action": action,
        "gui": gui,
        "msg_id": msg_id,
    }

    # We want to notify *all* the instances of the new corpus
    return _sharepublish_msg(cast(JSONObject, jso), msg_id)
    # return _publish_msg(connection, cast(JSONObject, jso), msg_id)


def _upload_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    """
    Cleanup on upload fail, and maybe send ws message
    """
    print(f"Upload failure: {typ} : {value}: {traceback}")
    msg_id = str(uuid4())

    project: str
    user: str
    room: str | None

    job_kwargs: dict = cast(dict, job.kwargs)

    if "project_name" in job_kwargs:  # it came from create schema job
        project = job_kwargs["project"]
        user = job_kwargs["user"]
        room = job_kwargs["room"]
    else:  # it came from upload job
        project = job.args[0]
        user = job.args[1]
        room = job.args[2]

    uploads_path = os.getenv("TEMP_UPLOADS_PATH", "uploads")
    path = os.path.join(uploads_path, project)
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")

    form_error = str(trace)

    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    action = "upload_fail"

    if user and room:
        jso = {
            "user": user,
            "room": room,
            "project": project,
            "action": action,
            "status": "failed",
            "job": job.id,
            "msg_id": msg_id,
            "traceback": form_error,
            "kind": str(typ),
            "value": str(value),
        }
        return _publish_msg(connection, jso, msg_id)


def _general_failure(
    job: Job,
    connection: RedisConnection,
    typ: type,
    value: BaseException,
    trace: TracebackType,
) -> None:
    """
    On job failure, return some info ... probably hide some of this from prod eventually!
    """
    msg_id = str(uuid4())
    form_error = str(trace)
    action = "failed"
    try:
        form_error = "".join(traceback.format_tb(trace))
    except Exception as err:
        print(f"cannot format object: {trace} / {err}")

    print("Failure of some kind:", job, trace, typ, value)
    if isinstance(typ, Interrupted) or typ == Interrupted:
        # no need to send a message to the user for interrupts
        # jso = {"status": "interrupted", "action": "interrupted", "job": job.id}
        return None
    else:
        jso = {
            "status": "failed",
            "kind": str(typ),
            "value": str(value),
            "action": action,
            "msg_id": msg_id,
            "traceback": form_error,
            "job": job.id,
            **cast(dict, job.kwargs),
        }
    # this is just for consistency with the other timeout messages
    if "No such job" in jso["value"]:
        jso["status"] = "timeout"
        jso["action"] = "timeout"

    return _publish_msg(connection, jso, msg_id)


def _queries(
    job: Job,
    connection: RedisConnection,
    result: list[UserQuery] | None,
) -> None:
    """
    Fetch or store queries
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    is_store: bool = job_kwargs.get("store", False)
    is_delete: bool = job_kwargs.get("delete", False)

    action = "fetch_queries"

    if is_store:
        action = "store_query"
    elif is_delete:
        action = "delete_query"

    # action = "store_query" if is_store else "fetch_queries"

    room: str | None = job_kwargs.get("room")
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": str(job_kwargs["user"]),
        "room": room,
        "status": "success",
        "action": action,
        "queries": [],
        "msg_id": msg_id,
    }
    if is_store:
        jso["query_id"] = str(job_kwargs["query_id"])
        jso.pop("queries")
    elif is_delete:
        jso.pop("queries")
    elif result:
        cols = ["idx", "query", "username", "room", "created_at"]
        queries: list[dict[str, Any]] = []
        for x in result:
            dct: dict[str, Any] = dict(zip(cols, x))
            queries.append(dct)
        jso["queries"] = json.dumps(queries, default=str)

    return _publish_msg(connection, jso, msg_id)


def _deleted(job: Job, connection: RedisConnection, result: Any) -> None:
    """
    Callback for successful deletion.
    """
    job_kwargs: dict = cast(dict, job.kwargs)
    action = "delete_query"
    room: str = job_kwargs.get("room") or ""
    # Since DELETE without RETURNING doesn't provide row data, we use the original query_id.
    deleted_idx = job_kwargs.get("idx")
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "user": str(job_kwargs["user"]),
        "room": room,
        "idx": deleted_idx,
        "status": "success",
        "action": action,
        "msg_id": msg_id,
        "queries": "[]",
    }

    return _publish_msg(connection, jso, msg_id)


def _swissdox_to_db_file(
    job: Job,
    connection: RedisConnection,
    result: list[UserQuery] | None,
) -> None:
    print("export complete!")
    j_kwargs = cast(dict, job.kwargs)
    hash = j_kwargs.get("hash", "swissdox")
    dest_folder = os.path.join(RESULTS_SWISSDOX, "exports")
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
    dest = os.path.join(dest_folder, f"{hash}.db")
    if os.path.exists(dest):
        os.remove(dest)

    for table_name, index_col, data in job.result:
        df = pandas.DataFrame.from_dict(
            {cname: cvalue if cvalue else [] for cname, cvalue in data.items()}
        )
        df.set_index(index_col)
        con = duckdb.connect(database=dest, read_only=False)
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")

    user = j_kwargs.get("user")
    room = j_kwargs.get("room")

    if user and room:
        userpath = os.path.join(RESULTS_SWISSDOX, user)
        if not os.path.exists(userpath):
            os.makedirs(userpath)
        cname = j_kwargs.get("name", "swissdox")
        original_userpath = j_kwargs.get("userpath", "")
        if not original_userpath:
            original_userpath = f"{cname}_{str(datetime.now()).split('.')[0]}.db"
        fn = os.path.basename(original_userpath)
        userdest = os.path.join(userpath, fn)
        if os.path.exists(userdest):
            os.remove(userdest)
        os.symlink(os.path.abspath(dest), userdest)
        msg_id = str(uuid4())
        jso: dict[str, Any] = {
            "user": user,
            "room": room,
            "action": "export_complete",
            "msg_id": msg_id,
            "format": "swissdox",
            "hash": hash,
            "offset": 0,
            "total_results_requested": 200,
        }
        _publish_msg(connection, jso, msg_id)


def _config(
    job: Job,
    connection: RedisConnection,
    result: list[MainCorpus],
    publish: bool = True,
) -> dict[str, str | bool | Config]:
    """
    Run by worker: make config data
    """
    action = "set_config"
    fixed: Config = {}
    msg_id = str(uuid4())
    for tup in result:
        made = _row_to_value(tup)
        if not made.get("enabled"):
            continue
        fixed[str(made["corpus_id"])] = made

    for conf in fixed.values():
        if "_batches" not in conf:
            conf["_batches"] = _get_batches(conf)

    jso: dict[str, str | bool | Config] = {
        "config": fixed,
        "_is_config": True,
        "action": action,
        "msg_id": msg_id,
    }
    if publish:  # refresh the config for all instances
        _sharepublish_msg(cast(JSONObject, jso), msg_id)
        # _publish_msg(connection, cast(JSONObject, jso), msg_id)
    return jso

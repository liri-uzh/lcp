"""
Async tasks called from document.py
"""

import json
import lxml.etree
import os
import zipfile

from arq.jobs import Job, ResultNotFound
from lxml.builder import E
from typing import Any, cast
from uuid import uuid4
from xml.sax.saxutils import escape, quoteattr

from ..jobfuncs import _db_query
from ..typed import CorpusConfig
from ..utils import (
    SQLCorpus,
    _get_all_attributes,
    _publish_msg,
    get_aligned_annotations,
    get_corpus_int_range,
    hasher,
    literal_sql,
    sql_str,
)

RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))
UPLOAD_MEDIA_PATH = os.environ.get("UPLOAD_MEDIA_PATH", "media")


async def document(
    ctx,
    schema: str,
    corpus: int,
    doc_id: int,
    user: str,
    room: str | None,
    config: CorpusConfig,
):
    """
    Fetch info about a document from DB/cache
    """
    doc_low = config["document"].lower()
    from_cte = sql_str(
        "SELECT d.frame_range FROM {}.{} d WHERE d.{} = ",
        schema,
        doc_low,
        f"{doc_low}_id",
    ) + literal_sql(str(doc_id))

    aligned = get_aligned_annotations(
        cast(dict, config),
        "",
        "",
        from_cte,
        anchor="time",
        # include={l: {} for l in tracks.get("layers", {})},
        exclude={config["token"]: {}},
        contains=False,
        pointer_global_attributes=True,
    )

    seg = config["segment"]
    seg_id = seg + "_id"
    query = aligned + sql_str(
        "\nUNION ALL SELECT jsonb_build_array('_prepared', {}.{}, prep.id_offset, prep.content, {}.char_range) AS res FROM {} JOIN {}.{} prep ON prep.{} = {}.{};",
        seg,
        seg_id,
        seg,
        seg,
        schema,
        f"prepared_{seg.lower()}",
        f"{seg.lower()}_id",  # prep.segment_id
        seg,
        seg_id,
    )
    # print("document query", query)

    hashed = str(hasher(query))
    job = Job(hashed, redis=ctx["redis"])
    try:
        result = await job.result()
    except ResultNotFound:
        result = await _db_query(ctx, query, {})

    action = "document"
    if not room:
        return
    msg_id = str(uuid4())
    warning = ""
    jso = {
        "document": result,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
        "corpus": corpus,
        "doc_id": doc_id,
    }
    if warning:
        jso["warning"] = warning
    await _publish_msg(ctx["redis"], jso, msg_id)


async def document_ids(
    ctx,
    schema: str,
    corpus_id: int,
    user: str,
    room: str | None,
    config: dict,
    kind: str = "audio",
    language: str = "",
    limit: int = -1,
):
    """
    Fetch document id + info from DB.
    """
    doc_layer = config.get("document", "document")
    batch = next(x for x in config["_batches"])
    partitions = config.get("partitions", {}).get("values", [""])
    lang = language or next(x for x in partitions)
    sqlc = SQLCorpus(config, schema, batch, lang)
    # info: name -> column
    info: dict[str, str] = {
        "name": "name",
        "media": "media",
        "frame_range": "frame_range",
    }
    if kind == "image":
        info = {"xy_box": "xy_box"}
    elif kind == "plain":
        info = {"char_range": "char_range"}
    joins: dict = {}
    layer_attrs = _get_all_attributes(doc_layer, config)
    if "name" in layer_attrs:
        name_ref = sqlc.attribute("d", doc_layer, "name")
        joins = name_ref.joins
        info["name"] = name_ref.ref
    jsonb_info = (
        "jsonb_build_object("
        + ",".join(literal_sql(k) + "," + sql_str(v) for k, v in info.items())
        + ")"
    )
    doc_id = sqlc.layer("d", doc_layer, pointer=True)
    doc_table = next(x for x in doc_id.joins)
    query = f"SELECT {doc_id.ref}, {jsonb_info} FROM {doc_table}"
    for jtab, jconds in joins.items():
        if not jconds:
            continue
        query += f" JOIN {jtab} ON " + " AND ".join(jconds)
    if limit > 0:
        query += f" LIMIT {limit}"
    hashed = str(hasher((query, corpus_id)))
    job: Job
    try:
        job = Job(hashed, redis=ctx["redis"])
        result = await job.result()
    except ResultNotFound:
        result = await _db_query(ctx, query, {})

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
        "job": job.job_id,
        "corpus_id": corpus_id,
        "kind": kind,
    }
    await _publish_msg(ctx["redis"], jso, msg_id)


async def annotations(
    ctx,
    config: CorpusConfig,
    anchor: str,
    rang: list[int],
    corpus: str,
    language: str,
    limit: int,
    user: str,
    room: str | None,
):
    """
    Fetch all the annotations aligned with the anchor
    """
    schema: str = config["schema_path"]
    col_name: str = "frame_range" if anchor == "time" else "char_range"
    irange: str = get_corpus_int_range(config)
    from_cte: str = f"SELECT {irange}({rang[0]},{rang[1]}) AS {col_name}"
    aligned = get_aligned_annotations(
        cast(dict, config),
        "",
        language,
        from_cte,
        anchor=anchor,
        exclude={config["token"]: {}},
        contains=False,
        pointer_global_attributes=True,
    )

    seg = config["segment"]
    seg_id = seg + "_id"
    seg_map = config["mapping"]["layer"][seg]
    prep_tab = (
        seg_map.get("partitions", {})
        .get(language, seg_map)
        .get("prepared", {})
        .get("relation", f"prepared_{seg}")
    ).lower()
    query = aligned + sql_str(
        "\nUNION ALL SELECT jsonb_build_array('_prepared', {}.{}, prep.id_offset, prep.content, {}.char_range) AS res FROM {} JOIN {}.{} prep ON prep.{} = {}.{};",
        seg,
        seg_id,
        seg,
        seg,
        schema,
        prep_tab,
        f"{seg.lower()}_id",  # prep.segment_id
        seg,
        seg_id,
    )
    print("annotation query", query)

    hashed = str(hasher(query))
    try:
        job = Job(hashed, redis=ctx["redis"])
        result = await job.result()
    except ResultNotFound:
        result = await _db_query(ctx, query, {})

    if limit > 0:
        if isinstance(result, dict):
            result = {k: v for n, (k, v) in enumerate(result.items()) if n < limit}
        elif isinstance(result, list):
            result = cast(list[list[str]], result)
            # list each prepared segment along with its metadata in order, then subset
            chopped = False
            ranges = ("char_range", "frame_range", "xy_box")
            sorted_preps = sorted(
                [
                    [json.loads(x[-1].replace(")", "]")), *x]
                    for x, *_ in result
                    if x[0] == "_prepared"
                ],
                key=lambda x: x[0][0],
            )
            sorted_non_preps = sorted(
                [
                    [
                        json.loads(
                            next(
                                (cast(dict, x[2]).get(rg) or "").strip()
                                for rg in ranges
                                if (cast(dict, x[2]).get(rg) or "").strip()
                            ).replace(")", "]")
                        ),
                        *x,
                    ]
                    for x, *_ in result
                    if x[0] != "_prepared"
                    and any((cast(dict, x[2]).get(rg) or "").strip() for rg in ranges)
                ],
                key=lambda x: x[0],
            )
            added_non_preps: dict[tuple[str, int | str], int] = {}
            reordered_result: list = []
            for prep in sorted_preps:
                lb, ub = prep.pop(0)
                to_add: list = [
                    (prep,),
                    *[
                        (x[1:],)
                        for x in sorted_non_preps
                        if x[0][0] <= lb
                        and x[0][1] >= ub
                        and (x[1], x[2]) not in added_non_preps
                    ],
                ]
                if len(reordered_result) + len(to_add) > limit:
                    chopped = True
                    break
                added_non_preps.update(
                    {(l, i): 1 for (l, i, *_), *_ in to_add if l[0] != "_prepared"}
                )
                reordered_result += to_add
            if chopped:
                warning = f"Payload includes only the first {limit} annotation lines from the document (out of {len(result)})"
            result = cast(list, reordered_result)

    action = "document"
    if not room:
        return
    msg_id = str(uuid4())
    warning = ""
    jso = {
        "document": result,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
        "corpus": corpus,
        "doc_id": "",
    }
    if warning:
        jso["warning"] = warning
    await _publish_msg(ctx["redis"], jso, msg_id)


async def image_annotations(
    ctx,
    config: CorpusConfig,
    layer: str,
    ids: list[int],
    xy_box: list[int],
    user: str,
    room: str | None,
):
    """
    Fetch annotation related to an image layer from DB/cache
    """
    schema = config["schema_path"]
    from_cte = ""
    if ids:
        from_cte = sql_str(
            "SELECT d.xy_box FROM {}.{} d WHERE ",
            schema,
            layer.lower(),
        ) + (
            sql_str("d.{}", layer.lower() + "_id")
            + f" IN ({','.join(str(id) for id in ids)})"
        )
    elif xy_box:
        formed_box = literal_sql(f"({xy_box[0]},{xy_box[1]}),({xy_box[2]},{xy_box[3]})")
        from_cte = f"SELECT {formed_box}::box AS xy_box"

    exclude: dict[str, Any] = {}
    tok = config["token"]
    if not config["layer"][tok].get("anchoring", {}).get("location", False):
        exclude["exclude"] = {tok: {}}
    print("exclude", exclude)

    aligned = get_aligned_annotations(
        cast(dict, config),
        "",
        "",
        from_cte,
        anchor="location",
        contains=True,
        **exclude,
    )

    seg = config["segment"]
    seg_id = seg + "_id"
    query = aligned + sql_str(
        "\nUNION ALL SELECT jsonb_build_array('_prepared', {}.{}, prep.id_offset, prep.content, {}.char_range) AS res FROM {} JOIN {}.{} prep ON prep.{} = {}.{};",
        seg,
        seg_id,
        seg,
        seg,
        schema,
        f"prepared_{seg.lower()}",
        f"{seg.lower()}_id",  # prep.segment_id
        seg,
        seg_id,
    )
    # print("document query", query)

    hashed = str(hasher(query))
    job: Job
    try:
        job = Job(hashed, redis=ctx["redis"])
        result = await job.result()
    except ResultNotFound:
        result = await _db_query(ctx, query, {})

    action = "image_annotations"
    if not room:
        return
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "annotations": result,
        "layer": layer,
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
    }
    await _publish_msg(ctx["redis"], jso, msg_id)


async def clip_media(
    ctx,
    config: CorpusConfig,
    span: list,
    doc_id: str,
    user: str,
    room: str | None,
):
    """
    Clip the media and export the correponding annotations
    """
    schema = config["schema_path"]

    tok = config["token"]
    seg = config["segment"]
    doc = config["document"]
    doc_l = doc.lower()
    sp_from, sp_to = [round(float(x) * 25.0) for x in span]

    doc_fr = "d.frame_range"
    doc_low = f"lower({doc_fr})"
    doc_up = f"upper({doc_fr})"
    from_cte = f"SELECT int4range(least({doc_low} + {sp_from}, {doc_up}), least({doc_low} + {sp_to}, {doc_up})) AS frame_range"
    from_cte += sql_str(
        " FROM {}.{} d WHERE d.{} = ", schema, doc_l, f"{doc_l}_id"
    ) + str(doc_id)

    aligned = get_aligned_annotations(
        cast(dict, config),
        "",
        "",
        from_cte,
        anchor="time",
        contains=True,
        exclude={tok: {}},
    )

    seg_id = seg + "_id"
    query = aligned + sql_str(
        "\nUNION ALL SELECT jsonb_build_array('_prepared', {}.{}, prep.id_offset, prep.content) AS res FROM {} JOIN {}.{} prep ON prep.{} = {}.{};",
        seg,
        seg_id,
        seg,
        schema,
        f"prepared_{seg.lower()}",
        f"{seg.lower()}_id",  # prep.segment_id
        seg,
        seg_id,
    )
    # print("document query", query)

    result = await _db_query(ctx, query, {})

    layers = config.get("layer", {})
    mapping = config.get("mapping", {}).get("layer", {})
    columns = mapping.get(seg, {}).get("prepared", {}).get("columnHeaders") or ["form"]
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
    for x in result or []:
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

    media_slots = config.get("meta", {}).get("mediaSlots", {})
    media_col, media_props = next((x for x in media_slots.items()), ("", ""))
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
    if not room:
        return
    msg_id = str(uuid4())
    jso: dict[str, Any] = {
        "file": os.path.basename(zip_fn),
        "action": action,
        "user": user,
        "room": room,
        "msg_id": msg_id,
    }

    await _publish_msg(ctx["redis"], jso, msg_id)

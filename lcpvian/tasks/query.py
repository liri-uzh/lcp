"""
Async tasks called from query.py
"""

import re

from arq.jobs import Job
from intervaltree import IntervalTree
from redis import Redis as RedisConnection
from typing import cast
from uuid import uuid4

from ..redis_proxies import RedisDict
from ..utils import (
    get_segment_meta_script,
    range_from_str,
)
from ..redis import get_sync_redis


# This can be called from the main app or from a worker
async def schedule_next_batch(
    qhash: str,
    connection: RedisConnection,
    previous_batch_name: str | None = None,
    ctx: dict = {},
) -> Job | None:
    """
    Find the next batch to run based on the previous one
    and return the corresponding job (None if no next batch)
    """
    qi = ctx["_queryInfo"](qhash, connection=connection)
    if not qi.requests:
        return None
    if previous_batch_name and not qi.full:
        lines_before, lines_batch = qi.get_lines_batch(previous_batch_name)
        if lines_before + lines_batch >= qi.required:
            qi.running_batches = {}
            return None
    next_batch = qi.decide_next_batch(previous_batch_name)
    min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
    while next_batch and min_offset > 0 and next_batch[0] in qi.done_batches:
        lines_before_batch, lines_next_batch = qi.get_lines_batch(next_batch[0])
        if min_offset <= lines_before_batch + lines_next_batch:
            break
        next_batch = qi.decide_next_batch(next_batch[0])
    if not next_batch:
        qi.running_batches = {}
        return None
    job = await qi.enqueue("query.do_batch", qhash, list(next_batch))
    return cast(Job | None, job)


async def do_segment_and_meta(
    ctx,
    qhash: str,
    batch_name: str,
    offset_this_batch: int,
    lines_this_batch: int,
):
    """
    Fetch from cache or run a segment+meta query on the given batch
    """
    connection = get_sync_redis()
    qi = ctx["_queryInfo"](qhash, connection=connection)
    if not qi.requests:
        return
    if all(r.raw_hits for r in qi.requests):
        return
    batch_hash, _ = qi.query_batches[batch_name]
    batch_results: list = qi.get_from_cache(batch_hash)

    segment: str = qi.config["firstClass"]["segment"]
    export_to_xml = any(
        r.to_export and r.to_export.get("format") == "xml" for r in qi.requests
    )

    kwics = [x for x in qi.result_sets if x.get("type") == "plain"]
    kwics_ids = [
        next(y for y in x.get("attributes", []) if y.get("name") == "identifier")
        for x in kwics
    ]
    context: None | str = kwics_ids[0].get("layer", segment)
    assert all(x.get("layer") == context for x in kwics_ids), ReferenceError(
        f"All contexts in the plain results must refer to the same annotation layer"
    )
    if not export_to_xml:
        context = None

    script, meta_labels = get_segment_meta_script(
        qi.config, qi.languages, batch_name, context=context
    )

    all_segment_ids: dict[str, int | list[int]] = qi.segment_ids_in_results(
        batch_results,
        offset_this_batch,
        offset_this_batch + lines_this_batch,
    )
    segments_this_batch = qi.segments_for_batch.get(batch_name, {})
    if isinstance(segments_this_batch, RedisDict):
        segments_this_batch = segments_this_batch.to_dict()
    existing_sids: dict[str, int] = {
        sid: 1 for _, sids in segments_this_batch.items() for sid in sids
    }
    needed_sids: dict[str, int] = {
        sid: 1 for sid in all_segment_ids if sid not in existing_sids
    }
    if existing_sids:
        print(
            f"Found {len(existing_sids)}/{len(all_segment_ids)} segments in cache for {batch_name}"
        )
    if export_to_xml and context != segment:
        # Force re-querying the segments and their meta for wide contexts when exporting to XML
        needed_sids = {sid: 1 for sid in all_segment_ids}
        print(
            f"Running the segment query (again?) for export purposes -- it might take a while"
        )
    if not needed_sids:
        print(f"No new segment query needed for {batch_name}")
    else:
        qi.qi["meta_labels"] = meta_labels
        squery_id = str(uuid4())
        print(
            f"Running new segment query for {batch_name} -- {squery_id} ({len(needed_sids)} sids)"
        )
        await qi.query(
            squery_id, script, params={"sids": [sid for sid in needed_sids]}, ctx=ctx
        )
        if batch_name not in qi.segments_for_batch:
            qi.segments_for_batch[batch_name] = {}
        qi.segments_for_batch[batch_name][squery_id] = needed_sids
    # Calculate which lines from res should be sent to each request
    reqs_offsets = {r.id: r.lines_for_batch(qi, batch_name) for r in qi.requests}
    reqs_sids: dict[str, dict[str, int | list[int]]] = {
        req_id: qi.segment_ids_in_results(batch_results, o, o + l)
        for req_id, (o, l) in reqs_offsets.items()
    }
    reqs_itvls: dict[str, IntervalTree] = {}
    for req_id, sids_to_crs in reqs_sids.items():
        reqs_itvls[req_id] = IntervalTree()
        for char_range in sids_to_crs.values():
            reqs_itvls[req_id][range(*cast(list[int], char_range))] = 1
    segments_this_batch = cast(RedisDict, qi.segments_for_batch[batch_name]).to_dict()
    for sqid in segments_this_batch:
        reqs_nlines: dict[str, dict[str, int]] = {req_id: {} for req_id in reqs_sids}
        lines: list
        try:
            lines = qi.get_from_cache(sqid)
        except:
            sids = [si for si in segments_this_batch[sqid]]
            lines = await qi.query(sqid, script, params={"sids": sids}, ctx=ctx)
        # Be smart about which lines to include
        for nline, (rtype, content) in enumerate(lines):
            for req_id, sids_in_req in reqs_sids.items():
                # No longer using sids_in_req here since we're using char_range
                cr: str | dict = content[-1]
                if isinstance(cr, dict):
                    cr = cr.get("char_range", "")
                if not isinstance(cr, str) or not re.match(r"\[\d+,\d+\)", cr):
                    continue
                if not reqs_itvls[req_id][range_from_str(cast(str, cr))]:
                    continue
                reqs_nlines[req_id][str(nline)] = 1
        for r in qi.requests:
            if sqid in r.segment_lines_for_hash:
                continue
            r.segment_lines_for_hash[sqid] = reqs_nlines[r.id]
    await qi.publish(batch_name, "segments")


async def do_batch(ctx, qhash: str, batch: list):
    """
    Fetch from cache or run a main query on a batch from within a worker
    and aggregate the results for stats if needed
    """
    connection = get_sync_redis()
    qi = ctx["_queryInfo"](qhash, connection=connection)
    if not qi.requests:
        return
    batch_name = cast(str, batch[0])
    if batch_name in qi.running_batches:
        # This batch is already running: stop here
        return
    try:
        # First try to retrieve from cache, otherwise actually run the query
        try:
            assert batch_name in qi.query_batches
            batch_hash, _ = qi.query_batches[batch_name]
            qi.get_from_cache(batch_hash)
            print(f"Retrieved query from cache: {batch_name} -- {batch_hash}")
        except:
            print(f"No job in cache for {batch_name}, running it now")
            qi.running_batches[batch_name] = 1
            await qi.run_query_on_batch(batch, ctx=ctx)
            batch_hash, _ = qi.query_batches.get(batch_name, ("", 0))
        min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
        await qi.run_aggregate(min_offset, batch)
        await qi.publish(batch_name, "main")
        del qi.running_batches[batch_name]

        if not batch_name:
            return

        # do next batch if needed (all already scheduled if full)
        if not qi.full:
            await schedule_next_batch(qhash, connection, batch_name, ctx)

        # run needed segment+meta queries
        lines_before, lines_now = qi.get_lines_batch(batch_name)
        lines_so_far = lines_before + lines_now

        # send sentences if needed
        if not qi.kwic_keys or all(r.raw_hits for r in qi.requests):
            return

        min_offset = min(r.offset for r in qi.requests) if qi.requests else 0
        # Send only if this batch exceeds the offset and this batch starts before what's required
        need_segments_this_batch = (
            lines_now > 0
            and lines_so_far >= min_offset
            and (qi.full or qi.required > lines_before)
        )
        print(
            f"need segments for {batch_name}?",
            min_offset,
            lines_so_far,
            need_segments_this_batch,
        )
        if not need_segments_this_batch:
            return

        offset_this_batch = max(0, min_offset - lines_so_far)
        lines_this_batch = (
            lines_now if qi.full else min(lines_now, qi.required - lines_before)
        )
        await qi.enqueue(
            "query.do_segment_and_meta",
            qi.hash,
            batch_name,
            offset_this_batch,
            lines_this_batch,
        )
    except:
        if batch_name in qi.running_batches:
            del qi.running_batches[batch_name]

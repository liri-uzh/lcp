"""
Functions used in the conversion of SQL to JSON results

The role of these functions is to work together to create the Results
object, which holds kwic, collocation and frequency results, plus query
metadata and prepared_segment objects.

If a query has res1=kwic, res2=collocation, res3=freq, two objects would
be created. First, the non-kwic data would be made by _aggregate_results
via callbacks._query:

{0: query_metadata, 2: collocation_data, 3: freq_data}

and after that, _format_kwics via callbacks._sentences would produce:

{-1: prepared_segment_data, 0: query_metadata, 1: kwic_data}

the dicts could therefore be combined without losing any info if need be

Once non-kwic results are created, they need to be filtered with _apply_filters
so that certain transformations not possible to do in SQL can be applied.
Most commonly, this is when there is a "frequency > 10" type filter: we cannot
apply it in postgres because a given match could have 5 matches in one batch,
and 5 in another...

KWIC results need the results of queries over the prepared_segment table, which
is inserted as the -1 key in the Results object. FE does the job of formatting
the kwic line from matching token ids plus the relevant prepared_segment.
"""

import operator

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from redis import Redis as RedisConnection
from rq.job import Job

from .typed import (
    Batch,
    QueryMeta,
    RawSent,
    ResultSents,
    ResultsValue,
    Results,
    Sentence,
)
from .utils import _get_associated_query_job

OPS = {
    "<": operator.lt,
    "<=": operator.le,
    "=": operator.eq,
    "==": operator.eq,
    "<>": operator.ne,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
}


def _prepare_existing(
    res: Results, kwics: set[int], colls: set[int]
) -> dict[int, dict[str, tuple[int, float]]]:
    out: dict[int, Any] = {}
    for k, v in res.items():
        k = int(k)
        if k < 1 or k in kwics:
            continue
        if k not in out:
            out[k] = {}
        v = cast(list, v)
        if k in colls:
            for text, total, e in v:
                if text not in out[k]:
                    out[k][text] = (total, e)
                else:
                    print("Todo: if this happens, we need to combine scores")
                    pretotal, pree = out[k][text]
                    out[k][text] = (total + pretotal, (e + pree / 2))
        else:
            for r in v:
                body = r[:-1]
                if tuple(body) not in out[k]:
                    out[k][tuple(body)] = 0
                out[k][tuple(body)] += r[-1]
    return out


def _unfold(exist: dict, kwics: set[int], colls: set[int]) -> Results:
    out: Results = {}
    for k, v in exist.items():
        k = int(k)
        if k < 1:
            continue
        if k in kwics:
            continue
        if k not in out:
            out[k] = []
        if k in colls:
            for text, (a, b) in v.items():
                ok = cast(list, out[k])
                ok.append([text, a, b])
        else:
            for body, score in v.items():
                ok = cast(list, out[k])
                ok.append(list(body) + [score])
    return out


def _aggregate_results(
    result: list,
    existing: Results,
    meta_json: QueryMeta,
    post_processes: dict[int, Any],
    current: Any,
    done: list[Batch] | None = None,
) -> tuple[Results, Results, int, bool, bool]:
    """
    Combine non-kwic results for storing and for sending to frontend
    """
    results_to_send: Results = {0: meta_json}
    n_results = 0
    rs = meta_json["result_sets"]
    kwics = set([i for i, r in enumerate(rs, start=1) if r.get("type") == "plain"])
    freqs = set([i for i, r in enumerate(rs, start=1) if r.get("type") == "analysis"])
    colls = set(
        [i for i, r in enumerate(rs, start=1) if r.get("type") == "collocation"]
    )
    counts: defaultdict[int, int] = defaultdict(int)

    minus_one: ResultsValue = existing.get(-1, cast(ResultsValue, {}))
    zero: ResultsValue = existing.get(0, cast(ResultsValue, {}))

    precalcs: dict = _prepare_existing(existing, kwics, colls)

    for line in result:
        key = int(line[0])
        rest: list[Any] = line[1]
        if not key and not n_results:
            n_results = rest[0]
            continue
        if key in kwics:
            counts[key] += 1
            continue
        if key not in existing:
            existing[key] = []
        if key not in precalcs:
            precalcs[key] = {}
        if key in colls:
            text, total_this_batch, e = rest
            preexist, preexist_e = precalcs[key].get(text, (0, 0))
            combined = preexist + total_this_batch
            counts[key] = combined
            combined_e = _combine_e(e, preexist_e, current, done)
            precalcs[key][text] = (combined, combined_e)
            continue
        # frequency table:
        body = cast(list, [str(x) for x in rest[:-1]])
        total_this_batch = rest[-1]
        # need_update = body in precalcs[key]
        preexist = precalcs[key].get(tuple(body), 0)
        combined = preexist + total_this_batch
        precalcs[key][tuple(body)] = combined
        counts[key] = combined

    existing = _unfold(precalcs, kwics, colls)
    existing[-1] = minus_one
    existing[0] = zero

    results_to_send = _apply_filters(existing, post_processes)

    show_total = bool(kwics) or (not kwics and len(freqs) == 1)

    return existing, results_to_send, n_results, not bool(kwics), show_total


def _combine_e(
    this_time_e: int | float,
    e_so_far: int | float,
    current: Batch | None,
    done: list[Batch] | None,
):
    """
    Get the combined E value for collocation
    """
    assert current is not None and done is not None
    if not done:
        return this_time_e
    current_size: int = current[-1]
    done_size = sum(d[-1] for d in done if d != current)
    prop = this_time_e * current_size
    done_prop = e_so_far * done_size
    return (prop + done_prop) / (current_size + done_size)


def _format_kwics(
    result: list | None,
    meta_json: QueryMeta,
    sents: list[RawSent] | None,
    total: int,
    is_first: bool,
    offset: int,
    max_kwic: int,
    current_lines: int,
    full: bool,
) -> Results:
    """
    Take a DB query result, plus `sents`, the result of the query on the
    prepared_segment table, and create the data needed by frontend to display
    KWIC lines.

    {0: meta_json, -1: {sent_id: [sent_offset, sent_data]}, 1: [token_ids, ...]}

    Often we don't want all the sentences, we use `offset` and `total` to get
    only a certain subset of them...
    """
    sen: ResultSents = {}
    out: Results = {0: meta_json, -1: sen}
    rs: list[dict] = meta_json["result_sets"]
    kwics = set([i for i, r in enumerate(rs, start=1) if r.get("type") == "plain"])
    counts: defaultdict[int, int] = defaultdict(int)
    stops: set[int] = set()
    skipped: defaultdict[int, int] = defaultdict(int)

    if sents is None:
        print("Sentences is None: expired?")
        sents = []

    if result is None:
        print("Result is None: expired?")
        result = []

    for sent in sents:
        add_to = cast(ResultSents, out[-1])
        add_to[str(sent[0])] = cast(Sentence, [*sent[1:]])

    for a, line in enumerate(result):
        key = int(line[0])
        rest = line[1]
        if max_kwic and counts.get(key, 0) > max_kwic:
            continue
        # we should have one 0: n_results key always
        if not key:
            continue
        if key not in kwics:
            continue
        if key in stops:
            continue
        if total is not None and total > 0 and counts[key] >= total:
            stops.add(key)
            continue
        if offset is not None and offset > 0 and skipped[key] < offset:
            skipped[key] += 1
            continue
        if key not in out:
            out[key] = []
        if key == "frame_range":
            rest = rest[:2]
        if str(rest[0]) not in out[-1]:
            continue
        bit = cast(list, out[key])
        bit.append(rest)
        counts[key] += 1

    if max_kwic and not full:
        out = _limit_kwic_to_max(out, current_lines, max_kwic)

    return out


def _get_all_sents(
    job: Job,
    base: Job,
    meta_json: QueryMeta,
    max_kwic: int,
    current_lines: int,
    full: bool,
    connection: RedisConnection,
) -> Results:
    """
    Combine all sent jobs into one -- only done at the end of a `full` query
    """
    sen: ResultSents = {}
    out: Results = {0: meta_json, -1: sen}
    is_first = True
    got: Results
    for jid in base.meta["_sent_jobs"]:
        j = job if job.id == jid else Job.fetch(jid, connection=connection)
        jk = cast(dict, j.kwargs)
        dep = _get_associated_query_job(jk["depends_on"], connection)
        resume = jk.get("resume", False)
        offset = jk.get("offset", 0) if resume else -1
        needed = jk.get("needed", -1)
        got = _format_kwics(
            dep.result,
            meta_json,
            j.result,
            needed,
            is_first,
            offset,
            0,
            0,
            full,
        )
        if got.get(-1):
            sents = cast(dict, out[-1])
            sents.update(cast(dict, got[-1]))
        for k, v in got.items():
            if k < 1:
                continue
            if k not in out:
                out[k] = []
            add_to = cast(list, out[k])
            add_to += cast(list, v)

    if max_kwic > 0:
        out = _limit_kwic_to_max(out, current_lines, max_kwic)

    return out


def _limit_kwic_to_max(to_send: Results, current_lines: int, max_kwic: int) -> Results:
    """
    Do not allow too many KWIC results to go to FE
    """
    too_many = False
    allowed: set[str | int] = set()
    for k, v in to_send.items():
        if k <= 0:
            continue
        size = len(v)
        if size + current_lines > max_kwic:
            most_allowed = max_kwic - current_lines
            if not too_many and len(v) > most_allowed:
                too_many = True
            assert isinstance(to_send[k], list)
            to_send[k] = cast(list, v)[:most_allowed]
            allowed.update(set(i[0] for i in cast(list, to_send[k])))
    if too_many:
        to_send[-1] = {k: v for k, v in cast(dict, to_send[-1]).items() if k in allowed}

    return to_send


def _make_filters(
    post: dict[int, list[dict[str, Any]]]
) -> dict[int, list[tuple[str, str, str | int | float]]]:
    """
    Because we iterate over them a lot, turn the filters object into something
    as performant as possible
    """
    out = {}
    for idx, filters in post.items():
        fixed: list[tuple[str, str, str | int | float]] = []
        for filt in filters:
            name, comp = cast(tuple[str, dict[str, Any]], list(filt.items())[0])
            if name != "comparison":
                raise ValueError("expected comparison")
            if "entity" not in comp:
                raise ValueError("expected function-free comparison")

            entity = comp["entity"]
            operator = comp["operator"]
            value = next(
                c[1] for c in comp.items() if c[0] not in ("entity", "operator")
            )
            if value.isnumeric():
                value = int(value)
            elif value.replace(".", "").isnumeric():
                value = float(value)
            made = cast(tuple[str, str, int | str | float], (entity, operator, value))
            fixed.append(made)
        out[idx] = fixed
    return out


def _apply_filters(results_so_far: Results, post_processes: dict[int, Any]) -> Results:
    """
    Take the unioned results and apply any post process functions
    """
    if not post_processes:
        return results_so_far
    out: Results = {}
    post = _make_filters(post_processes)
    for k, v in results_so_far.items():
        for key, filters in post.items():
            if not filters:
                continue
            if int(k) < 1:
                continue
            if int(k) != int(key):
                continue
            for name, op, num in filters:
                v = _apply_filter(cast(list, v), name, op, num)
        out[k] = v
    return out


def _apply_filter(result: list, name: str, op: str, num: int | str | float) -> list:
    """
    Apply a single filter to a group of results, returning only those that match
    """
    out: list = []
    for r in result:
        total = r[-1]
        res = OPS[op](total, num)
        if res and r not in out:
            out.append(r)
    return out


def _fix_freq(v: list[list]) -> list[list]:
    """
    Sum frequency objects and remove duplicate
    """
    fixed = []
    for r in v:
        body = r[:-1]
        total = sum(x[-1] for x in v if x[:-1] == body)
        body.append(total)
        if body not in fixed:
            fixed.append(body)
    return fixed

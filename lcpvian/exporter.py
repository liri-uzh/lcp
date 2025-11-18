import datetime
import json
import lxml.etree
import os
import re
import shutil

from aiohttp import web
from base64 import b64decode as btoa
from functools import cmp_to_key
from io import TextIOWrapper
from intervaltree import IntervalTree
from lxml.builder import E
from redis import Redis as RedisConnection
from rq import Callback, Queue
from rq.job import get_current_job, Job
from types import TracebackType
from typing import Any, cast
from uuid import uuid4

from xml.sax.saxutils import escape, quoteattr

from .callbacks import _general_failure
from .jobfuncs import _export_db
from .query_classes import Request, QueryInfo
from .typed import CorpusConfig
from .utils import (
    _get_iso639_3,
    _get_mapping,
    _is_anchored,
    _publish_msg,
    is_prepared_annotation,
    range_from_str,
    sanitize_filename,
)

EXPORT_TTL = 5000
RESULTS_DIR = os.getenv("RESULTS", "results")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


def _btoa(val: str) -> str:
    encs = ("utf-8", "iso-8859-1")
    if not val:
        return ""
    ret: str = ""
    for enc in encs:
        try:
            ret = btoa(val).decode(enc)  # type: ignore
            if ret:
                break
        except:
            pass
    if not ret:
        raise Exception(f"Could not decode {val}")
    return ret


def _token_value(val: str) -> str:
    try:
        ret = json.loads(val)
    except:
        ret = val
    return "" if not ret else str(ret)


def _xml_attr(s: str) -> str:
    return escape(
        s.replace("(", "")
        .replace(")", "")
        .replace("[", "")
        .replace("]", "")
        .replace(" ", "_")
    )


def _node_to_string(node, prefix: str = "") -> str:
    ret = lxml.etree.tostring(
        node, encoding="unicode", pretty_print="True"  # type: ignore
    )
    if prefix:
        ret = re.sub(r"(^|\n)(.)", "\\1  \\2", ret)
    return ret


def _get_attributes(attrs: dict) -> tuple[str, str]:
    """
    Given a dictionary of attributes, return (simple,complex) attribute strings
    """
    attr_str = " ".join(
        f"{_xml_attr(k)}={quoteattr(str(v))}"
        for k, v in attrs.items()
        if not isinstance(v, dict)
    )
    comp: list[str] = []
    for complex_attribute, sub_attributes in attrs.items():
        if not isinstance(sub_attributes, dict):
            continue
        sub_attrs_str = " ".join(
            f"{_xml_attr(k)}={quoteattr(str(v))}" for k, v in sub_attributes.items()
        )
        comp.append(f"<{complex_attribute} {sub_attrs_str}/>")
    return (attr_str, "".join(comp))


def _get_indent(n: int) -> str:
    return "    " + "".join("  " for _ in range(n))


def _next_line(inp: dict[str, TextIOWrapper | str | int], indented_layers: list[str]):
    """
    Move the input to the next line and fills the details
    """
    line: str = cast(str, cast(TextIOWrapper, inp["io"]).readline())
    inp["line"] = line
    if not line:
        return
    inp["char_range"] = int(
        (re.search(r"char_range=\"\[(\d+),(\d+)\)\"", line) or [0, 0])[1]
    )
    layer: str = cast(str, (re.match(r"<([^>\s]+)", line) or ["", ""])[1])
    inp["layer"] = layer
    inp["embedding"] = indented_layers.index(layer)


def _sorter(
    inp1: dict[str, TextIOWrapper | str | int],
    inp2: dict[str, TextIOWrapper | str | int],
):
    """
    Sort inputs based on the line's character range + level of embedding
    """
    if not inp2["line"]:
        return -1
    if not inp1["line"]:
        return 1
    c1 = cast(int, inp1["char_range"])
    c2 = cast(int, inp2["char_range"])
    e1 = cast(int, inp1["embedding"])
    e2 = cast(int, inp2["embedding"])
    if c1 < c2:
        return -1
    if c1 > c2:
        return 1
    if e1 > e2:
        return -1
    return 1


def _paste_file(
    output: TextIOWrapper,
    fn: str,
    prefix: str = "",
):
    with open(fn, "r") as input:
        while line := input.readline():
            output.write(prefix + line)


def _get_top_layer(config: CorpusConfig, restrict: set = set()) -> str:
    top_layer = config["document"]
    while 1:
        container: str | None = next(
            (x for x, y in config["layer"].items() if y.get("contains") == top_layer),
            None,
        )
        if container is None or container not in restrict:
            break
        top_layer = container
    return top_layer


class Exporter:
    xp_format = "xml"

    def __init__(self, request: Request, qi: QueryInfo) -> None:
        self._request: Request = request
        self._qi: QueryInfo = qi
        self._config: dict = qi.config.to_dict()
        seg_layer: str = self._config["segment"]
        seg_mapping: dict[str, Any] = _get_mapping(
            seg_layer, self._config, "", qi.languages[0]
        )
        self._column_headers: list[str] = seg_mapping["prepared"]["columnHeaders"]
        self._form_index = self._column_headers.index("form")
        self._results_info: list[dict[str, Any]] = []
        self._info: dict[str, Any] = {}

    @staticmethod
    def get_dl_path_from_hash(
        hash: str,
        offset: int = 0,
        requested: int = 0,
        full: bool = False,
        filename: bool = False,
    ) -> str:
        hash_folder = os.path.join(RESULTS_DIR, hash)
        xml_folder = os.path.join(hash_folder, "xml")
        if full:
            full_folder = os.path.join(xml_folder, "full")
            if not os.path.exists(full_folder):
                os.makedirs(full_folder)
            return full_folder
        offset_folder = os.path.join(xml_folder, str(offset))
        requested_folder = os.path.join(offset_folder, str(requested))
        if not os.path.exists(requested_folder):
            os.makedirs(requested_folder)
        if filename:
            requested_folder = os.path.join(requested_folder, "results.xml")
        return requested_folder

    @staticmethod
    def try_finish_immediately(
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
        xp_format: str = cast(str, job.args[1])
        Exporter.finish_export_db(
            connection, qhash, offset, requested, requested, full, xp_format
        )

    @staticmethod
    def error_export(
        job: Job,
        connection: RedisConnection,
        typ: type,
        value: BaseException,
        trace: TracebackType,
    ) -> None:
        """
        Callback calling _general_failure
        """
        qhash, xp_format, _, offset, requested = job.args
        msg = str(value)
        q = Queue("internal", connection=connection)
        q.enqueue(
            _export_db,  # finish export
            on_failure=Callback(_general_failure),
            args=(qhash, xp_format, "update", offset, requested),
            kwargs={
                "failure": True,
                "message": msg,
            },
        )
        _general_failure(job, connection, typ, value, trace)

    @classmethod
    def finish_export_db(
        cls,
        connection: RedisConnection,
        qhash: str,
        offset: int,
        requested: int,
        delivered: int,
        full: bool,
        xp_format: str = "xml",
    ):
        """
        Mark an export in the DB as finished
        """
        q = Queue("internal", connection=connection)
        q.enqueue(
            _export_db,  # finish export
            on_failure=Callback(cls.error_export),
            args=(qhash, xp_format, "finish", offset, requested),
            kwargs={
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
        ext: str = ".xml",
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
        filepath = app["exporters"][xp_format].get_dl_path_from_hash(
            shash, request.offset, request.requested, request.full, filename=True
        )
        should_run = not os.path.exists(filepath)
        app["internal"].enqueue(
            _export_db,  # init_export
            on_success=Callback(cls.try_finish_immediately),
            on_failure=Callback(cls.error_export),
            result_ttl=EXPORT_TTL,
            job_timeout=EXPORT_TTL,
            args=(shash, xp_format, "create", request.offset, request.requested),
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
        else:
            if not os.path.exists(userpath) and not os.path.islink(userpath):
                try:
                    os.symlink(os.path.abspath(filepath), userpath)
                except Exception as e:
                    print(f"Problem with creating symlink {filepath}->{userpath}", e)
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
            upd_exp_args = (qhash, cls.xp_format, "update", offset, requested)
            await _export_db(
                *upd_exp_args,
                export=True,
                message=f"{payload.get('percentage_done', 'NA')}%",
            )
            exporter = cls(request, qi)
            wpath = exporter.get_working_path()
            await exporter.process_lines(payload)
            if not request.is_done(qi):
                return
            await _export_db(
                *upd_exp_args,
                export=True,
                message=f"100% - finalizing...",
            )  # each payload needs corresponding *_query/*_segments subfolders
            qb_hashes = [bh for bh, _ in qi.query_batches.values()]
            for h, nlines in request.sent_hashes.items():
                if h not in qb_hashes or cast(int, nlines) <= 0:
                    continue
                hpath = os.path.join(wpath, h)
                if not os.path.exists(f"{hpath}_query"):
                    return
                seg_exists = os.path.exists(f"{hpath}_segments")
                if qi.kwic_keys and not seg_exists:
                    return
            delivered: int = cast(int, request.lines_sent_so_far)
            await exporter.finalize()
            shutil.rmtree(exporter.get_working_path())
            for h in request.sent_hashes:
                hpath = os.path.join(wpath, h)
                if os.path.exists(f"{hpath}_query"):
                    shutil.rmtree(f"{hpath}_query")
                if os.path.exists(f"{hpath}_segments"):
                    shutil.rmtree(f"{hpath}_segments")
            print(
                f"Exporting complete for request {request.id} (hash: {request.hash}) ; DELETED REQUEST"
            )
            qi.delete_request(request)
            cls.finish_export_db(
                qi._connection, qi.hash, offset, requested, delivered, full
            )
        except Exception as e:
            shutil.rmtree(cls.get_dl_path_from_hash(qhash, offset, requested, full))
            await _export_db(
                qhash,
                cls.xp_format,
                "update",
                offset,
                requested,
                failure=True,
                message=str(e),
            )
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

    async def process_query(self, payload: dict, batch_hash: str) -> None:
        """
        Write the stats file the hit files as applicable
        """
        print(
            f"[Export {self._request.id}] Process query {batch_hash} (QI {self._request.hash})"
        )
        res = payload.get("result", [])
        all_stats = []
        result_sets = self._qi.result_sets
        for k in self._qi.stats_keys:
            if k not in res:
                continue
            k_in_rs = int(k) - 1
            stats_name = result_sets[k_in_rs]["name"]
            stats_type = result_sets[k_in_rs]["type"]
            stats_attrs = [x["name"] for x in result_sets[k_in_rs]["attributes"]]
            total_stats = [x["name"] for x in result_sets[k_in_rs].get("total", {})]
            all_stats.append(
                getattr(E, stats_type)(
                    *[
                        (
                            E.observation(
                                *[
                                    getattr(E, aname)(str(aval))
                                    for aname, aval in zip(
                                        (
                                            stats_attrs
                                            if stats_type == "collocation"
                                            or l[0] in (False, "False")
                                            else total_stats
                                        ),
                                        l if stats_type == "collocation" else l[1:],
                                    )
                                ]
                            )
                        )
                        for l in res[k]
                    ],
                    name=stats_name,
                )
            )
        if all_stats:
            stats = E.stats(*all_stats)
            # Just update the main stats.xml file at the root of the working path
            stats_path: str = os.path.join(self.get_working_path(), "stats.xml")
            with open(stats_path, "w") as stats_output:
                stats_str = _node_to_string(stats)
                stats_output.write(stats_str)
        for k in self._qi.kwic_keys:
            if k not in res:
                continue
            # Prepare all the info before looping over the results
            k_in_rs = int(k) - 1
            kwic_name = result_sets[k_in_rs]["name"]
            matches_info = next(
                a["data"]
                for a in result_sets[k_in_rs]["attributes"]
                if a["name"] == "entities"
            )
            for sid, matches, *_ in res[k]:
                prefix = sid[0:3]
                seg_path: str = self.get_working_path(prefix)
                fpath = os.path.join(seg_path, f"{sid}_kwic.xml")
                with open(fpath, "a") as kwic_output:
                    kwic_output.write(f"<hit name={quoteattr(kwic_name)}>\n")
                    matches_line = "\n".join(
                        f"  <{minfo['type']} name={quoteattr(minfo['name'])} refers_to={quoteattr(str(mid))} />"
                        for mid, minfo in zip(matches, matches_info)
                    )
                    kwic_output.write(str(matches_line) + "\n")
                    kwic_output.write(f"</hit>\n")

    def build_token(self, tok_lab: str, n: int, token: list) -> Any:
        tok = getattr(E, tok_lab)(
            token[self._form_index] or "",
            id=str(n),
            **{
                _xml_attr(k): _token_value(v)
                for k, v in zip(self._column_headers, token)
                if k != "form" and not isinstance(v, dict)
            },
        )
        for complex_attr, sub_attrs in zip(self._column_headers, token):
            if not isinstance(sub_attrs, dict):
                continue
            tok.append(
                getattr(E, _xml_attr(complex_attr))(
                    **{_xml_attr(k): str(v) for k, v in sub_attrs.items()}
                )
            )
        return tok

    def build_tokens(self, offset: int, tokens: list) -> Any:
        config = self._config
        tok = config["token"]
        return [self.build_token(tok, offset + n, t) for n, t in enumerate(tokens)]

    def write_unit(self, output, id: str, layer: str, unit: dict):
        """
        Write a layer unit to a file
        """
        attr_str, complex_attrs = _get_attributes(unit)
        output.write(
            f"<{layer} {_xml_attr('_id')}={quoteattr(str(id))} {attr_str}>{complex_attrs}\n"
        )

    async def process_segments(self, payload: dict, batch_hash: str) -> None:
        """
        Write one file per doc in meta with the contained layers ordered by char_range
        Write one file per segment with the content of prepared_segment
        The doc files are in batch-specific subfolders to avoid parallel io conflicts
        Seg files are specific to their batch so there's no risk of io conflicts
        """
        print(
            f"[Export {self._request.id}] Process segments for {batch_hash} (QI {self._request.hash})"
        )
        work_path = self.get_working_path(batch_hash)
        res = payload.get("result", [])
        # SEGMENTS
        for sid, (offset, tokens, annotations, char_range) in res["-1"].items():
            prefix = sid[0:3]
            seg_path = self.get_working_path(prefix)
            fpath = os.path.join(seg_path, f"{sid}.xml")
            with open(fpath, "w") as seg_output:
                ann_layer, ann_occurs = next(
                    ((k, v) for k, v in annotations.items()), ("", [(None, None, None)])
                )
                for ann_pos, n_anns, ann_props in ann_occurs:
                    if not ann_pos or not ann_props:
                        continue
                    props = {
                        "from": str(ann_pos),
                        "to": str(ann_pos + n_anns),
                        **{k: str(v) for k, v in ann_props.items()},
                    }
                    ann_node = getattr(E, ann_layer)(**props)
                    seg_output.write(_node_to_string(ann_node))
                for token in self.build_tokens(offset, tokens):
                    seg_output.write(_node_to_string(token))
        # META
        config = cast(CorpusConfig, self._config)
        top_conf: dict = cast(dict, config["layer"][config["firstClass"]["document"]])
        valid_anchors = [
            a
            for a in ("stream", "time")
            if _is_anchored(top_conf, cast(dict, config), a)
        ]
        anchor_col = {"stream": "char_range", "time": "frame_range"}
        layers_by_id: dict[str, dict] = {l: {} for l in config["layer"]}
        layer_ids_by_anchor = {
            l: {a: IntervalTree() for a in valid_anchors} for l in config["layer"]
        }
        layers_in_meta: dict = {}
        for _, lname, lid, meta in res["-2"]:
            layers_in_meta[lname] = 1
            layers_by_id[lname][lid] = meta
            for a in valid_anchors:
                anc_meta = meta.get(anchor_col[a], "")
                if not anc_meta:
                    continue
                itv = range_from_str(anc_meta)
                layer_ids_by_anchor[lname][a][itv] = lid
        top_layer = _get_top_layer(config, restrict=set(layers_in_meta))
        nested_layers: list[str] = []
        # Add the layers contained in the top layer first
        contained_layer = top_layer
        while 1:
            contained_layer = (
                config["layer"].get(contained_layer, {}).get("contains", "")
            )
            if not contained_layer:
                break
            if contained_layer not in layers_in_meta:
                continue
            nested_layers.append(contained_layer)

        # Write the files
        for lid, attrs in layers_by_id[top_layer].items():
            fpath = os.path.join(work_path, f"{lid}.xml")
            top_itv_by_anchor = {
                a: range_from_str(attrs[anchor_col[a]]) for a in valid_anchors
            }
            with open(fpath, "w") as top_output:
                self.write_unit(top_output, lid, top_layer, attrs)
                bottom_layer = next(x for x in reversed(nested_layers))
                bottom_anchors = layer_ids_by_anchor[bottom_layer]
                for a in valid_anchors:
                    if a != "stream":
                        continue  # restrict to stream for now
                    top_itv = top_itv_by_anchor[a]
                    interim_units: dict[str, str] = {
                        l: "" for l in nested_layers if l != bottom_layer
                    }
                    # Retrieve the bottom units
                    for bottom_unit_id in sorted(bottom_anchors[a][top_itv]):
                        bottom_unit = layers_by_id[bottom_layer][bottom_unit_id.data]
                        bottom_unit_itv = range_from_str(bottom_unit[anchor_col[a]])
                        for iu_layer, iu_id in interim_units.items():
                            new_iu_id = next(
                                (
                                    x.data
                                    for x in layer_ids_by_anchor[iu_layer][a][
                                        bottom_unit_itv
                                    ]
                                ),
                                None,
                            )
                            if not new_iu_id or new_iu_id == iu_id:
                                continue
                            self.write_unit(
                                top_output,
                                new_iu_id,
                                iu_layer,
                                layers_by_id[iu_layer][new_iu_id],
                            )
                            interim_units[iu_layer] = new_iu_id
                        self.write_unit(
                            top_output, bottom_unit_id.data, bottom_layer, bottom_unit
                        )
                for unnested_layer in layers_in_meta:
                    if unnested_layer == top_layer or unnested_layer in nested_layers:
                        continue
                    for a in valid_anchors:
                        if a != "stream":
                            continue
                        for unnested_unit_id in sorted(
                            layer_ids_by_anchor[unnested_layer][a][top_itv]
                        ):
                            unnested_unit = layers_by_id[unnested_layer][
                                unnested_unit_id.data
                            ]
                            self.write_unit(
                                top_output,
                                unnested_unit_id.data,
                                unnested_layer,
                                unnested_unit,
                            )
        print(
            f"[Export {self._request.id}] Done processing segments for {batch_hash} (QI {self._request.hash})"
        )

    async def finalize(self) -> None:
        """
        Go through the files generated by each payload and concatenate them
        For kwics, the lines need to be ordered by char_range + depth of embedding
        """
        print(f"[Export {self._request.id}] Finalizing... (QI {self._request.hash})")
        req = self._request
        opath = self.get_dl_path_from_hash(
            req.hash,
            req.offset,
            req.requested,
            req.full,
        )
        wpath = self.get_working_path()
        with open(os.path.join(opath, "results.xml"), "w") as output:
            output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            output.write("<results>\n")
            config = self._config
            meta = {
                k: v
                for k, v in config["meta"].items()
                if k not in ("sample_query", "swissubase")
            }
            try:
                if isinstance(meta["userLicense"], str):
                    meta["userLicense"] = _btoa(meta["userLicense"])  # type: ignore
                else:
                    new_user_license = {
                        k: _btoa(v)  # type: ignore
                        for k, v in meta["userLicense"].items()
                    }
                    meta["userLicense"] = new_user_license
            except:
                pass
            partitions = config.get("partitions", {}).get("values", [])
            tok = config["token"].lower()
            tok_map = config["mapping"]["layer"][config["token"]]
            tok_counts = config["token_counts"]
            if len(partitions) > 1:
                tok_map = tok_map.get("partitions", {})
                meta["total_tokens"] = {
                    lg: tok_counts.get(
                        tok_map.get(lg, {})
                        .get("relation", f"{tok}_{lg}")
                        .replace("<batch>", "")
                        + "0",
                        "-1",
                    )
                    for lg in partitions
                }
            else:
                tok0 = tok_map.get("relation", tok).replace("<batch>", "") + "0"
                meta["total_tokens"] = tok_counts.get(tok0, "-1")
            corpus_node = E.corpus(
                *[
                    x
                    for k, v in meta.items()
                    for x in (
                        # multilingual field
                        [
                            getattr(E, k)(escape(str(vv)), lang=vk)
                            for vk, vv in v.items()
                        ]
                        if (isinstance(v, dict) and all(_get_iso639_3(vk) for vk in v))
                        # monolingual field
                        else [getattr(E, k)(escape(str(v)))]
                    )
                ]
            )
            output.write(_node_to_string(corpus_node, prefix="  "))
            batch_names = [self._qi.get_batch_from_hash(bh) for bh in req.lines_batch]
            percentage_words_done = max(
                req.get_payload(self._qi, bn)["percentage_words_done"]
                for bn in batch_names
            )
            query_node = E.query(
                E.date(str(datetime.datetime.now(datetime.UTC))),
                E.languages(*[E.language(str(lg)) for lg in req.languages]),
                E.offset(str(req.offset)),
                E.requested(str(req.requested)),
                E.full(str(req.full)),
                E.delivered(str(req.lines_sent_so_far)),
                E.coverage(str(percentage_words_done)),
                E.json("\n" + json.dumps(self._qi.json_query, indent=2) + "\n  "),
                E.locals(
                    *[
                        getattr(E, k)(v)
                        for k, v in self._qi.local_queries.to_dict().items()
                    ]
                ),
            )
            output.write(_node_to_string(query_node, prefix="  "))
            # STATS
            if self._qi.stats_keys:
                with open(os.path.join(wpath, "stats.xml"), "r") as stats_input:
                    while line := stats_input.readline():
                        output.write("  " + line)
            if not self._qi.kwic_keys:
                print(f"[Export {self._request.id}] Complete (QI {self._request.hash})")
                return
            # KWICS
            # layers_in_meta: set[str] = {
            #     l.split("_", 1)[0] for l in self._qi.meta_labels
            # }
            layers_in_meta: set[str] = {
                ln
                for ln in config["layer"]
                if ln != tok and not is_prepared_annotation(config, ln)
            }
            current_layer = _get_top_layer(
                cast(CorpusConfig, config), restrict=layers_in_meta
            )
            indented_layers: list[str] = [current_layer]
            while current_layer := (
                config["layer"].get(current_layer, {}).get("contains", "")
            ):
                # if current_layer not in layers_in_meta:
                #     continue
                indented_layers.append(current_layer)
            output.write("  <plain>\n")
            # associate each doc with all its files from all the batch subfolders
            top_files: dict[str, list[str]] = {}
            all_batches = [bh for (bh, _) in self._qi.query_batches.values()]
            for b in all_batches:
                bpath = os.path.join(wpath, b)
                if not os.path.exists(bpath):
                    continue
                for filename in os.listdir(bpath):
                    paths: list[str] = top_files.setdefault(filename, [])
                    paths.append(bpath)
            # for each doc, go through the files in parallel, one line at a time
            # based on the char_range of the line and the embedding level
            for top_file, paths in top_files.items():
                # handler to read the files in parallel (see _next_line)
                inputs: list[dict[str, TextIOWrapper | str | int]] = [
                    {
                        "io": open(os.path.join(p, top_file), "r"),
                        "line": "",
                        "layer": "",
                        "char_range": 0,
                    }
                    for p in paths
                ]
                try:
                    # First line is document
                    for i in inputs:
                        _next_line(i, indented_layers)
                    line = cast(str, inputs[0]["line"])
                    output.write("    " + line)
                    layers_to_close: list[str] = [cast(str, inputs[0]["layer"])]
                    # Now proceed with the actual lines
                    for i in inputs:
                        _next_line(i, indented_layers)
                    embedding_from = 0
                    while 1:
                        # _sorter ensures the first input always has the lowest char_range + deepest embedding
                        inputs.sort(key=cmp_to_key(_sorter))
                        inp = inputs[0]
                        line = cast(str, inp["line"])
                        if not line:
                            break  # we're done: we've read all the lines
                        embedding = cast(int, inp["embedding"])
                        # close any embedded node
                        while embedding_from >= embedding and layers_to_close:
                            layer_to_close = layers_to_close[-1]
                            embedding_to_close = indented_layers.index(layer_to_close)
                            if embedding_to_close < embedding:
                                # if we're skipping some intermediate layers
                                break
                            ind = _get_indent(embedding_from)
                            output.write(f"{ind}</{layer_to_close}>\n")
                            embedding_from += -1
                            layers_to_close.pop()
                        ind = _get_indent(embedding)
                        output.write(f"{ind}{line}")
                        if inp["layer"] == config["segment"]:
                            # insert the content of the corresponding segment files
                            sid = (re.search(r" _id=\"([^\"]+)\"", line) or ("", ""))[1]
                            sprefix = sid[0:3]
                            kwicfn = os.path.join(wpath, sprefix, f"{sid}_kwic.xml")
                            if os.path.exists(kwicfn):
                                output.write(f"\n{_get_indent(embedding+1)}<hits>\n")
                                _paste_file(output, kwicfn, _get_indent(embedding + 2))
                                output.write(f"{_get_indent(embedding+1)}</hits>\n")
                            fn = os.path.join(wpath, sprefix, f"{sid}.xml")
                            if os.path.exists(fn):
                                _paste_file(output, fn, _get_indent(embedding + 1))
                        # we'll need to close this later
                        layers_to_close.append(cast(str, inp["layer"]))
                        embedding_from = embedding
                        for x in inputs:
                            if x["line"] != line:
                                continue
                            _next_line(x, indented_layers)
                    # close any pending node
                    while layers_to_close:
                        layer_to_close = layers_to_close.pop()
                        embedding = indented_layers.index(cast(str, layer_to_close))
                        ind = _get_indent(embedding)
                        output.write(f"{ind}</{layer_to_close}>\n")
                except Exception as e:
                    raise e
                finally:
                    # make sure to always close all the input files
                    for i in inputs:
                        cast(TextIOWrapper, i["io"]).close()
            output.write("  </plain>\n")
            output.write("</results>")
        print(f"[Export {self._request.id}] Complete (QI {self._request.hash})")

    async def process_lines(self, payload: dict) -> None:
        """
        Take a payload and call process_query or process_segments
        """
        action = payload.get("action", "")
        batch_name = payload.get("batch_name", "")
        batch_hash = self._qi.query_batches[batch_name][0]
        if action == "query_result":
            await self.process_query(payload, batch_hash)
            self.get_working_path(f"{batch_hash}_query")  # creates dir
        elif action == "segments":
            await self.process_segments(payload, batch_hash)
            self.get_working_path(f"{batch_hash}_segments")  # creates dir

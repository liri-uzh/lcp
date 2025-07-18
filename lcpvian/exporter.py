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
from lxml.builder import E
from redis import Redis as RedisConnection
from rq import Callback, Queue
from rq.job import get_current_job, Job
from typing import Any, cast
from uuid import uuid4

from xml.sax.saxutils import escape, quoteattr

from .callbacks import _general_failure
from .jobfuncs import _handle_export
from .query_classes import Request, QueryInfo
from .typed import CorpusConfig
from .utils import _get_iso639_3, _get_mapping, _publish_msg, sanitize_filename

EXPORT_TTL = 5000
RESULTS_DIR = os.getenv("RESULTS", "results")
RESULTS_USERS = os.environ.get("RESULTS_USERS", os.path.join("results", "users"))


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
    def finish_immediately(
        job: Job,
        connection: RedisConnection,
        result: Any,
    ) -> None:
        should_run: bool = cast(dict, job.kwargs).get("should_run", True)
        if should_run:
            return
        qhash, _, _, offset, requested = job.args
        full: bool = cast(dict, job.kwargs).get("full", False)
        Exporter.finish_export_db(connection, qhash, offset, requested, requested, full)

    @classmethod
    def finish_export_db(
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
            _handle_export,  # init_export
            on_failure=Callback(_general_failure),
            args=(qhash, "xml"),
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
        ext: str = ".xml"  # ".db" if xp_format == "swissdox" else ".xml"
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
                hpath = os.path.join(wpath, h)
                if not os.path.exists(f"{hpath}_query"):
                    return
                seg_exists = os.path.exists(f"{hpath}_segments")
                if qi.kwic_keys and not seg_exists:
                    return
            delivered = request.lines_sent_so_far
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
            raise e

    def get_working_path(self, subdir: str = "") -> str:
        """
        The working path will be deleted after finalizing the results file
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
        for k in self._qi.stats_keys:
            if k not in res:
                continue
            k_in_rs = int(k) - 1
            stats_name = self._qi.result_sets[k_in_rs]["name"]
            stats_type = self._qi.result_sets[k_in_rs]["type"]
            stats_attrs = [
                x["name"] for x in self._qi.result_sets[k_in_rs]["attributes"]
            ]
            all_stats.append(
                getattr(E, stats_type)(
                    *[
                        E.observation(
                            *[
                                getattr(E, aname)(str(aval))
                                for aname, aval in zip(stats_attrs, l)
                            ]
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
            kwic_name = self._qi.result_sets[k_in_rs]["name"]
            matches_info = next(
                a["data"]
                for a in self._qi.result_sets[k_in_rs]["attributes"]
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
            token[self._form_index],
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

    def write_containees(
        self,
        output,
        all_layers: dict,
        ordered_containers: dict,
        layer: str,
        ids: dict[str, int],
    ):
        """
        Write all the units in IDS and their contained units, recursively, ordered by char_range
        """
        units = [all_layers[layer][cid] for cid in ids]
        units.sort(key=lambda x: int(x.get("char_range", "[0,0)")[1:].split(",")[0]))
        for unit in units:
            attr_str, complex_attrs = _get_attributes(unit)
            output.write(f"\n<{layer} {attr_str}>{complex_attrs}")
            if layer not in ordered_containers:
                continue
            contained_layer, containees_by_cid = ordered_containers[layer]
            self.write_containees(
                output,
                all_layers,
                ordered_containers,
                contained_layer,
                containees_by_cid[unit["id"]],
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
        meta_labels = self._qi.meta_labels
        layers_in_meta: set[str] = {l.split("_", 1)[0] for l in meta_labels}
        config = cast(CorpusConfig, self._config)
        seg = config["segment"]
        all_layers: dict[str, dict[str, dict]] = {l: {} for l in layers_in_meta}
        # all_layers:
        # {
        #     "Document": {
        #         "docid1": {"a1": "v1", "a2": "v2", etc.}
        #     })
        # }
        ordered_containers: dict[str, tuple[str, dict[str, dict[str, int]]]] = {}
        # ordered_containers:
        # {
        #     "Document": ("Division", {
        #         "docid1": {"divid1": 1, "divid2": 1},
        #         "docid2": {"divid3": 1, "divid4": 1}
        #     }),
        #     "Division": ("Segment", {
        #         "divid1": {"segid1": 1, "segid2": 1}
        #         "divid2": {"segid3": 1, "segid4": 1}
        #     })
        # }
        top_layer = _get_top_layer(config, restrict=layers_in_meta)
        current_layer = last_container = top_layer
        while 1:
            current_layer = config["layer"].get(current_layer, {}).get("contains", "")
            if not current_layer:
                break
            if current_layer in layers_in_meta:
                ordered_containers[last_container] = (current_layer, {})
                last_container = current_layer
        layer_to_container = {y: x for x, (y, _) in ordered_containers.items()}
        unordered_layers_by_top: dict[str, dict[str, dict[str, int]]] = {
            k: {}
            for k in layers_in_meta
            if k not in layer_to_container and k != top_layer
        }
        # unordered_layers_by_doc:
        # {
        #     "Namedentity": {
        #        "docid1": {"neid1": 1, "neid2": 1, etc.}
        #     }
        # }
        # META
        for meta_line in res["-2"]:
            layer_to_attrs = {
                l: {
                    meta_labels[n].split("_", 1)[1]: v
                    for n, v in enumerate(meta_line)
                    if meta_labels[n].startswith(f"{l}_")
                }
                for l in layers_in_meta
            }
            top_id = layer_to_attrs[top_layer]["id"]
            for l in layers_in_meta:
                lid = layer_to_attrs[l]["id"]
                all_layers[l][lid] = layer_to_attrs[l]
                if l == top_layer:
                    continue
                if c := layer_to_container.get(l):
                    cid = layer_to_attrs[c].get("id", "")
                    oc = ordered_containers[c][1].setdefault(cid, {})
                    oc[lid] = 1
                else:
                    ulbc = unordered_layers_by_top[l].setdefault(top_id, {})
                    ulbc[lid] = 1
            # SEGMENTS
            sid = layer_to_attrs[seg]["id"]
            offset, tokens, *annotations = res["-1"][sid]
            prefix = sid[0:3]
            seg_path = self.get_working_path(prefix)
            fpath = os.path.join(seg_path, f"{sid}.xml")
            with open(fpath, "w") as seg_output:
                for token in self.build_tokens(offset, tokens):
                    seg_output.write(_node_to_string(token))
        for top_id, attrs in all_layers[top_layer].items():
            fpath = os.path.join(work_path, f"{top_id}.xml")
            with open(fpath, "w") as doc_output:
                # attr_str = " ".join(
                #     f"{_xml_attr(k)}={quoteattr(str(v))}" for k, v in attrs.items()
                # )
                attr_str, complex_attrs = _get_attributes(attrs)
                doc_output.write(f"<{top_layer} {attr_str}>{complex_attrs}")
                # contained layers (div, segs, etc.)
                contained_layer, containees_by_top_id = ordered_containers[top_layer]
                self.write_containees(
                    doc_output,
                    all_layers,
                    ordered_containers,
                    contained_layer,
                    containees_by_top_id[top_id],
                )
                # undordered layers (named entity)
                for unordered_layer in unordered_layers_by_top:
                    for ul_id in unordered_layers_by_top[unordered_layer][top_id]:
                        ul_attrs = all_layers[unordered_layer][ul_id]
                        # ul_attr_str = " ".join(
                        #     f"{_xml_attr(k)}={quoteattr(str(v))}"
                        #     for k, v in ul_attrs.items()
                        # )
                        ul_attr_str, ul_complex_attrs = _get_attributes(ul_attrs)
                        doc_output.write(
                            f"\n<{unordered_layer} {ul_attr_str}>{ul_complex_attrs}"
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
                k: v for k, v in config["meta"].items() if k not in ("sample_query",)
            }
            try:
                meta["userLicense"] = btoa(meta["userLicense"]).decode("utf-8")  # type: ignore
            except:
                pass
            corpus_node = E.corpus(
                *[
                    x
                    for k, v in meta.items()
                    for x in (
                        # multilingual field
                        [getattr(E, k)(str(vv), lang=vk) for vk, vv in v.items()]
                        if (isinstance(v, dict) and all(_get_iso639_3(vk) for vk in v))
                        # monolingual field
                        else [getattr(E, k)(str(v))]
                    )
                ]
            )
            output.write(_node_to_string(corpus_node, prefix="  "))
            last_payload = {}
            for batch_hash in req.lines_batch:
                batch_name = self._qi.get_batch_from_hash(batch_hash)
                last_payload = req.get_payload(self._qi, batch_name)
                if last_payload["status"] == "finished":
                    break
            query_node = E.query(
                E.date(str(datetime.datetime.now(datetime.UTC))),
                E.languages(*[E.language(lg) for lg in req.languages]),
                E.offset(str(req.offset)),
                E.requested(str(req.requested)),
                E.full(str(req.full)),
                E.delivered(str(req.lines_sent_so_far)),
                E.coverage(str(last_payload["percentage_done"])),
                E.json("\n" + json.dumps(self._qi.json_query, indent=2) + "\n  "),
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
            layers_in_meta: set[str] = {
                l.split("_", 1)[0] for l in self._qi.meta_labels
            }
            current_layer = _get_top_layer(
                cast(CorpusConfig, config), restrict=layers_in_meta
            )
            indented_layers: list[str] = [current_layer]
            while current_layer := (
                config["layer"].get(current_layer, {}).get("contains", "")
            ):
                if current_layer not in layers_in_meta:
                    continue
                indented_layers.append(current_layer)
            output.write("  <plain>\n")
            # associate each doc with all its files from all the batch subfolders
            doc_files: dict[str, list[str]] = {}
            all_batches = [bh for (bh, _) in self._qi.query_batches.values()]
            for b in all_batches:
                bpath = os.path.join(wpath, b)
                if not os.path.exists(bpath):
                    continue
                for filename in os.listdir(bpath):
                    paths: list[str] = doc_files.setdefault(filename, [])
                    paths.append(bpath)
            # for each doc, go through the files in parallel, one line at a time
            # based on the char_range of the line and the embedding level
            for doc_file, paths in doc_files.items():
                # handler to read the files in parallel (see _next_line)
                inputs: list[dict[str, TextIOWrapper | str | int]] = [
                    {
                        "io": open(os.path.join(p, doc_file), "r"),
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
                    layers_to_close = [inputs[0]["layer"]]
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
                            layer_to_close = layers_to_close.pop()
                            ind = _get_indent(embedding_from)
                            output.write(f"{ind}</{layer_to_close}>\n")
                            embedding_from += -1
                        ind = _get_indent(embedding)
                        output.write(f"{ind}{line}")
                        if inp["layer"] == config["segment"]:
                            # insert the content of the corresponding segment files
                            sid = (re.search(r" id=\"([^\"]+)\"", line) or ("", ""))[1]
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
                        layers_to_close.append(inp["layer"])
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

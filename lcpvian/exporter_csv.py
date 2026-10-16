# TODO: move exporters into a subfolder
# TODO: rename expoter.py to exporter_xml.py
# TODO: have a generic exporter.py that exports raw text files
# TODO: pass 'include' to download_export and generate a unique folder in get_dl_path...?

import csv
import logging
import os
import zipfile

from aiohttp import web
from redis.asyncio import Redis as RedisConnection

from typing import Any, cast

from .exporter import Exporter as ExporterXML
from .query_classes import Request, QueryInfo

# hardcoded for now -- pass request.url instead?
LCP_URL = "https://catchphrase.linguistik.uzh.ch/"


class Exporter(ExporterXML):
    xp_format = "csv"

    def __init__(self, request: Request, qi: QueryInfo) -> None:
        super().__init__(request, qi)

    async def initiate_db(
        self,
        app: web.Application,
        ext: str = "csv",
    ) -> bool:
        if len(self._qi.kwic_keys) + len(self._qi.stats_keys) > 1:
            ext = "zip"
        ret = await super().initiate_db(app, ext=ext)
        return ret

    @classmethod
    async def finish_export_db(
        cls,
        connection: RedisConnection,
        qhash: str,
        offset: int,
        requested: int,
        delivered: int,
        full: bool,
        xp_format: str = "csv",
    ):
        await super().finish_export_db(
            connection, qhash, offset, requested, delivered, full, "csv"
        )

    @classmethod
    def get_dl_path_from_hash(
        cls,
        hash: str,
        offset: int = 0,
        requested: int = 0,
        full: bool = False,
        filename: bool = False,
    ) -> str:
        ret = super().get_dl_path_from_hash(hash, offset, requested, full, filename)
        if filename is True:
            ret = ret.removesuffix(".csv") + ".zip"
        return ret

    async def finalize(self, ctx: dict = {}) -> None:
        logging.debug(
            f"[Export {self._request.id} CSV] Finalizing... (QI {self._request.hash})"
        )
        corpus_id = self._qi.config["corpus_id"]
        corpus_name = self._qi.config["shortname"]
        req = self._request
        opath = self.get_dl_path_from_hash(
            req.hash,
            req.offset,
            req.requested,
            req.full,
        )

        result_sets = self._qi.result_sets

        zip_fn = os.path.join(opath, "results.zip")
        zf = zipfile.ZipFile(zip_fn, "w")

        # STATS
        for k in self._qi.stats_keys:
            k_in_rs = int(k) - 1
            stats_name = result_sets[k_in_rs]["name"]
            fn = f"{stats_name}.csv"
            stats_path: str = os.path.join(self.get_working_path(), fn)
            if not os.path.isfile(stats_path):
                continue
            zf.write(stats_path, fn)

        # KWICS
        for k in self._qi.kwic_keys:
            k_in_rs = int(k) - 1
            matches_info = next(
                a["data"]
                for a in result_sets[k_in_rs]["attributes"]
                if a["name"] == "entities"
            )
            context_layer = next(
                a["layer"]
                for a in result_sets[k_in_rs]["attributes"]
                if a["name"] == "identifier"
            )
            kwic_name = result_sets[k_in_rs]["name"]
            kwic_path: str = self.get_working_path(kwic_name)
            kwic_fn = os.path.join(kwic_path, f"{kwic_name}.csv")
            with open(kwic_fn, "w") as kwic_output:
                writer = csv.writer(kwic_output)
                headers = [f"{context_layer}_id", "url", "left_context"]
                # as many '(right_)context' as there are matching entities
                headers += [
                    x
                    for n, minfo in enumerate(matches_info)
                    for x in (
                        minfo["name"],
                        ("context" if n + 1 < len(matches_info) else "right_context"),
                    )
                ]
                # add headers for the meta attributes
                meta_include: dict = (
                    cast(dict, self._request.to_export or {}).get("include") or {}
                )
                for lname in sorted(meta_include):
                    lattrs = sorted(meta_include[lname])
                    all_attrs: dict = (
                        self._qi.config["layer"][lname].get("attributes") or {}
                    )
                    lname_low = lname.lower()
                    if lattrs:
                        headers += [f"{lname_low}_{k}" for k in lattrs]
                    if not lattrs:
                        headers += [f"{lname_low}_id"]
                        headers += [
                            f"{lname_low}_{k}" for k in sorted(all_attrs.keys())
                        ]
                writer.writerow(headers)
                # find all the .hits files in all the subfolders
                for subdir in os.listdir(kwic_path):
                    subpath = os.path.join(kwic_path, subdir)
                    if not os.path.isdir(subpath):
                        continue
                    for f in os.listdir(subpath):
                        hitspath = os.path.join(subpath, f)
                        if not hitspath.endswith(".hits") or not os.path.isfile(
                            hitspath
                        ):
                            continue
                        hitsfn = hitspath.split(os.path.sep)[-1]
                        sid = hitsfn.split(".")[0]
                        prefix = sid[0:3]
                        seg_path = self.get_working_path(prefix)
                        # find the corresponding .tokens file
                        tokenspath = os.path.join(seg_path, f"{sid}.tokens")
                        if not os.path.isfile(tokenspath):
                            continue
                        hits: list[int | list[int]] = []
                        # Read .hits and store in list
                        with open(hitspath, "r") as hits_input:
                            while line := hits_input.readline():
                                if not line.strip():
                                    continue
                                hit = line.strip()
                                if "," not in hit:
                                    hits.append(int(hit))
                                else:
                                    # a little crude, use json.loads?
                                    hits.append(
                                        [
                                            int(x.strip())
                                            for x in hit.replace("[", "")
                                            .replace("]", "")
                                            .split(",")
                                        ]
                                    )
                        min_hits: list[int] = [
                            hit if isinstance(hit, int) else hit[0] for hit in hits
                        ]
                        max_hits: list[int] = [
                            hit if isinstance(hit, int) else hit[-1] for hit in hits
                        ]
                        info: dict[str, int] = {}
                        # Read .tokens and store tokens in list
                        texts: list[list[str]] = [[]]
                        with open(tokenspath, "r") as tokens_input:
                            n_token = 0
                            while line := tokens_input.readline():
                                line = line.strip()
                                if not line:
                                    continue
                                if "range" not in info:
                                    info["range"] = int(
                                        line.split(",")[0].replace("[", "")
                                    )
                                elif "offset" not in info:
                                    info["offset"] = int(line)
                                else:
                                    form = line
                                    # Start a new chunk if in min hits (current token to be added to it)
                                    if n_token + info["offset"] in min_hits:
                                        texts.append([])
                                    text = texts[-1]
                                    text.append(form)
                                    n_token += 1
                                    # Start a new chunk if in max hits (next token to be added to it -- if not a hit, else empty string)
                                    if n_token + info["offset"] - 1 in max_hits:
                                        texts.append([])
                        # Read optional .meta file and report key-value pairs
                        url = f"{LCP_URL}query/{corpus_id}/{corpus_name}?stream={info['range']}&segment={sid}"
                        row = [sid, url, *[" ".join(t) for t in texts]]
                        # Process meta, if any: store unsorted lname->aname->avalue
                        meta: dict[str, dict] = {}
                        metapath = os.path.join(seg_path, f"{sid}.meta")
                        if os.path.isfile(metapath):
                            with open(metapath, "r") as meta_input:
                                lname = ""
                                while mline := meta_input.readline():
                                    mline = mline.strip()
                                    if not mline:
                                        continue
                                    # Read 3 lines at a time: layer name, attribute name, attribute value
                                    try:
                                        # there can be more than one occurrence for the layer
                                        # ignore the index after space for now and only keep the last one
                                        lname = mline.split(" ")[0]
                                        aname = meta_input.readline().strip()
                                        avalue = meta_input.readline().strip()
                                        attrs = meta.setdefault(lname, {})
                                        attrs[aname] = avalue
                                    except:
                                        pass
                        # Now add the layer_attributes as provided, else all of them
                        for lname in sorted(meta_include):
                            lmeta: dict = meta.get(lname, {}) or dict()
                            lconf = self._qi.config["layer"][lname]
                            all_attrs = {"_id": 1, **(lconf.get("attributes") or {})}
                            for aname in sorted(meta_include[lname] or all_attrs):
                                row.append(lmeta.get(aname) or "")
                        while len(row) < len(headers):
                            row.append("")
                        writer.writerow(row)
            zf.write(kwic_fn, f"{kwic_name}.csv")

        zf.close()

        print(f"[Export {self._request.id} CSV] Complete (QI {self._request.hash})")

    async def process_query(self, payload: dict, batch_hash: str) -> None:
        """
        Write the stats file and the hit files as applicable
        """
        print(
            f"[Export {self._request.id} CSV] Process query {batch_hash} (QI {self._request.hash})"
        )
        res = payload.get("result", [])
        result_sets = self._qi.result_sets
        # STATS
        for k in self._qi.stats_keys:
            if k not in res:
                continue
            k_in_rs = int(k) - 1
            stats_name = result_sets[k_in_rs]["name"]
            stats_type = result_sets[k_in_rs]["type"]
            stats_path: str = os.path.join(self.get_working_path(), f"{stats_name}.csv")
            stats_attrs = [x["name"] for x in result_sets[k_in_rs]["attributes"]]
            total_stats = [x["name"] for x in result_sets[k_in_rs].get("total", {})]
            # Indices of columns from non-total rows that contain a grouping value
            group_idx = [
                n
                for a_tot in total_stats
                for n, a_sta in enumerate(stats_attrs)
                if a_tot == a_sta
            ]
            with open(stats_path, "w") as output:
                writer = csv.writer(output)
                stats_headers = list(stats_attrs)
                if stats_type == "analysis" and total_stats:
                    stats_headers.append(total_stats[-1])
                    stats_headers.append("relative_frequency")
                writer.writerow(stats_headers)
                totals_by_group = {}
                for l in res[k]:
                    row = list(l)
                    if total_stats and row[0] == "True":
                        val = row.pop(-1)
                        groups = tuple(row[1:])
                        totals_by_group[groups] = val
                        continue
                    # Remove first entry (True/False) if analysis
                    row = row[1:] if stats_type == "analysis" else row
                    if total_stats:
                        groups = tuple([row[i] for i in group_idx])
                        total = float(totals_by_group.get(groups, 1.0))
                        freq = int(row[-1])
                        ratio = float(freq / total)
                        row.append(total)
                        row.append(ratio)
                    writer.writerow(row)
        # KWICS
        for k in self._qi.kwic_keys:
            if k not in res:
                continue
            # Prepare all the info before looping over the results
            k_in_rs = int(k) - 1
            kwic_name = result_sets[k_in_rs]["name"]
            for sid, matches, *_ in res[k]:
                prefix = sid[0:3]
                subdir = os.path.join(kwic_name, prefix)
                seg_path: str = self.get_working_path(subdir)
                n = 2
                fpath = os.path.join(seg_path, f"{sid}.{n}.hits")
                while os.path.exists(fpath):
                    n += 1
                    fpath = os.path.join(seg_path, f"{sid}.{n}.hits")
                with open(fpath, "a") as kwic_output:
                    kwic_output.write("\n".join(str(mid) for mid in matches))

    async def process_segments(self, payload: dict, batch_hash: str) -> None:
        """
        Write one file per doc in meta with the contained layers ordered by char_range
        Write one file per segment with the content of prepared_segment
        The doc files are in batch-specific subfolders to avoid parallel io conflicts
        Seg files are specific to their batch so there's no risk of io conflicts
        """
        print(
            f"[Export {self._request.id} CSV] Process segments for {batch_hash} (QI {self._request.hash})"
        )
        res = payload.get("result", [])
        to_export: dict = self._request.to_export or {}
        include_meta = to_export.get("include") or {}
        # Reference meta per segment ID: sid->lname->[{info layer 1}, {info layer 2}, ...]
        meta_per_segment: dict[str, dict] = {}
        for sids, lname, lid, linfo in res.get("-2", []):
            # No need to process anything if nothing to include
            if not include_meta:
                break
            # No need to process this layer if not in include
            if lname not in include_meta:
                continue
            attrs_to_include = include_meta[lname]
            sid_entries: list[dict] = [
                meta_per_segment.setdefault(sid, {}) for sid in sids
            ]
            for sid_entry in sid_entries:
                layers_for_seg = sid_entry.setdefault(lname, [])
                linfo_to_report = (
                    {"_id": lid, **linfo}
                    if not attrs_to_include
                    else {k: v for k, v in linfo.items() if k in attrs_to_include}
                )
                layers_for_seg.append(linfo_to_report)
        # SEGMENTS
        for sid, (offset, tokens, annotations, char_range) in res["-1"].items():
            prefix = sid[0:3]
            seg_path = self.get_working_path(prefix)
            # Write tokens
            tpath = os.path.join(seg_path, f"{sid}.tokens")
            with open(tpath, "w") as tseg_output:
                tseg_output.write(char_range)
                tseg_output.write("\n" + str(offset))
                for t in tokens:
                    tseg_output.write("\n" + t[self._form_index])
            # Write meta
            if sid not in meta_per_segment:
                continue
            meta = meta_per_segment[sid]
            mpath = os.path.join(seg_path, f"{sid}.meta")
            with open(mpath, "w") as mseg_output:
                for lname, lentries in meta.items():
                    for n, linfo in enumerate(lentries):
                        for aname, avalue in linfo.items():
                            # Always 3 lines per layer attribute: 1. layer name, 2. attr name, 3. attr value
                            mseg_output.write(f"{lname} {n}\n")
                            mseg_output.write(aname + "\n")
                            # coerce the value to a string and strip all linebreaks
                            val = str(avalue).replace("\n", "").replace("\r", "") + "\n"
                            mseg_output.write(val)

        print(
            f"[Export {self._request.id} CSV] Done processing segments for {batch_hash} (QI {self._request.hash})"
        )

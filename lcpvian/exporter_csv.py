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

    @classmethod
    async def initiate_db(
        cls,
        app: web.Application,
        shash: str,
        config: dict,
        request: Request,
        ext: str = "csv",
    ) -> bool:
        ret = await super().initiate_db(app, shash, config, request, ext=".csv")
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

        for k in self._qi.stats_keys:
            k_in_rs = int(k) - 1
            stats_name = result_sets[k_in_rs]["name"]
            stats_type = result_sets[k_in_rs]["type"]
            fn = f"{stats_name}_{stats_type}.csv"
            stats_path: str = os.path.join(self.get_working_path(), fn)
            if not os.path.isfile(stats_path):
                continue
            zf.write(stats_path, fn)

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
                ents_context = [
                    x
                    for n, minfo in enumerate(matches_info)
                    for x in (
                        minfo["name"],
                        ("context" if n + 1 < len(matches_info) else "right_context"),
                    )
                ]
                writer.writerow(
                    [
                        f"{context_layer}_id",
                        "url",
                        "left_context",
                        *ents_context,
                    ]
                )
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
                        tokenspath = os.path.join(seg_path, f"{sid}.tokens")
                        if not os.path.isfile(tokenspath):
                            continue
                        hits: list[int | list[int]] = []
                        with open(hitspath, "r") as hits_input:
                            while line := hits_input.readline():
                                if not line.strip():
                                    continue
                                hit = line.strip()
                                if "," not in hit:
                                    hits.append(int(hit))
                                else:
                                    # a little curde, use json.loads?
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
                                    if n_token + info["offset"] in min_hits:
                                        texts.append([])
                                    elif n_token + info["offset"] - 1 in max_hits:
                                        texts.append([])
                                    text = texts[-1]
                                    text.append(form)
                                    n_token += 1
                        url = f"{LCP_URL}query/{corpus_id}/{corpus_name}?stream={info['range']}&segment={sid}"
                        writer.writerow([sid, url, *[" ".join(t) for t in texts]])
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
        for k in self._qi.stats_keys:
            if k not in res:
                continue
            k_in_rs = int(k) - 1
            stats_name = result_sets[k_in_rs]["name"]
            stats_type = result_sets[k_in_rs]["type"]
            stats_path: str = os.path.join(
                self.get_working_path(), f"{stats_name}_{stats_type}.csv"
            )
            stats_attrs = [x["name"] for x in result_sets[k_in_rs]["attributes"]]
            total_stats = [x["name"] for x in result_sets[k_in_rs].get("total", {})]
            with open(stats_path, "w") as output:
                writer = csv.writer(output)
                writer.writerow(
                    stats_attrs
                    if stats_type == "collocation" or not total_stats
                    else total_stats
                )
                for l in res[k]:
                    writer.writerow(l if stats_type == "collocation" else l[1:])
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
                    for mid in matches:
                        kwic_output.write(str(mid))

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
        # SEGMENTS
        for sid, (offset, tokens, annotations, char_range) in res["-1"].items():
            prefix = sid[0:3]
            seg_path = self.get_working_path(prefix)
            fpath = os.path.join(seg_path, f"{sid}.tokens")
            with open(fpath, "w") as seg_output:
                seg_output.write(char_range)
                seg_output.write("\n" + str(offset))
                for t in tokens:
                    seg_output.write("\n" + t[self._form_index])
        print(
            f"[Export {self._request.id} CSV] Done processing segments for {batch_hash} (QI {self._request.hash})"
        )

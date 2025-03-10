import os

from redis import Redis as RedisConnection
from typing import cast
from xml.sax.saxutils import escape, quoteattr

from .exporter import Exporter
from .utils import sanitize_xml_attribute_name

RESULTS_DIR = os.getenv("RESULTS", "results")


def xmlattr(val: str) -> str:
    if not val:
        return "''"
    return quoteattr(str(val))


class ExporterXml(Exporter):
    format = "xml"

    def __init__(
        self,
        hash: str,
        connection: "RedisConnection[bytes]",
        config: dict,
        partition: str = "",
        total_results_requested: int = 200,
        offset: int = 0,
        full: bool = False,
    ) -> None:
        super().__init__(
            hash, connection, config, partition, total_results_requested, offset, full
        )

    @staticmethod
    def get_dl_path_from_hash(
        hash: str, offset: int = 0, requested: int = 0, full: bool = False
    ) -> str:
        filename = "results.xml"
        hash_folder = os.path.join(RESULTS_DIR, hash)
        xml_folder = os.path.join(hash_folder, "xml")
        if full:
            full_folder = os.path.join(xml_folder, "full")
            if not os.path.exists(full_folder):
                os.makedirs(full_folder)
            return os.path.join(full_folder, filename)
        offset_folder = os.path.join(xml_folder, str(offset))
        requested_folder = os.path.join(offset_folder, str(requested))
        if not os.path.exists(requested_folder):
            os.makedirs(requested_folder)
        filepath = os.path.join(requested_folder, filename)
        return filepath

    async def kwic(self) -> None:
        filepath = ExporterXml.get_dl_path_from_hash(
            self._hash, self._offset, self._total_results_requested, self._full
        )
        folder = os.path.dirname(filepath)

        kwic_info = [r for r in self.results_info if r.get("type") == "plain"]

        if not kwic_info:
            return

        with open(os.path.join(folder, "_kwic.xml"), "w") as output:
            last_kwic_name = ""
            for kwic_line in self.kwic_lines():
                name, segment, tokens = (
                    kwic_line.name,
                    kwic_line.segment,
                    kwic_line.tokens,
                )
                if name != last_kwic_name:
                    if last_kwic_name:
                        output.write(f"\n</result>")
                    output.write(f"\n<result type='plain' name='{name}'>")
                    last_kwic_name = name

                output.write(f"\n    <u id='{segment.id}'>")
                for token in tokens:
                    str_args = [
                        f"{sanitize_xml_attribute_name(ta_n)}={xmlattr(ta_v)}"
                        for ta_n, ta_v in token.attributes.items()
                    ]
                    str_args.append(f"id='{token.id}'")
                    form: str = escape(token.form)
                    if token.match_label:
                        output.write(
                            f"""
        <hit name={xmlattr(token.match_label)}>
            <w {' '.join(str_args)}>{form}</w>
        </hit>"""
                        )
                    else:
                        output.write(f"\n        <w {' '.join(str_args)}>{form}</w>")
                output.write(f"\n    </u>")
            if last_kwic_name:
                output.write(f"\n</result>")

    async def non_kwic(self) -> None:
        job = self._query_jobs[-1]
        hash: str = cast(dict, job.kwargs).get("first_job", "")
        if not hash:
            hash = job.id

        non_kwic_info = [r for r in self.results_info if r.get("type") != "plain"]

        if not non_kwic_info:
            return

        filename = ExporterXml.get_dl_path_from_hash(
            self._hash, self._offset, self._total_results_requested, self._full
        )
        folder = os.path.dirname(filename)
        with open(os.path.join(folder, "_non_kwic.xml"), "w") as output:
            for info in non_kwic_info:
                if (n := info.get("res_index", 0)) <= 0:
                    continue
                name: str = info.get("name", "")
                typ: str = info.get("type", "")
                info_attrs: list[dict] = info.get("attributes", [])
                output.write(f"\n<result type='{typ}' name='{name}'>")
                for result_n, result in job.result:
                    if result_n != n:
                        continue
                    output.write(f"\n    <entry>")
                    for n_attr, attr in enumerate(result):
                        info_attr = info_attrs[n_attr]
                        name_attr = info_attr.get("name", f"attr_{n_attr}")
                        output.write(f"\n        <{name_attr}>{attr}</{name_attr}>")
                    output.write(f"\n    </entry>")
                output.write(f"\n</result>")

    async def export(self, filepath: str = "") -> None:
        results_filpath = ExporterXml.get_dl_path_from_hash(
            self._hash, self._offset, self._total_results_requested, self._full
        )
        folder = os.path.dirname(results_filpath)

        await self.kwic()
        await self.non_kwic()

        with open(results_filpath, "w") as output:
            output.write('<?xml version="1.0" encoding="utf_8"?>')
            delivered = self.n_results
            n = str(
                delivered
                if self._full
                else min(delivered, self._total_results_requested)
            )
            requested = "full" if self._full else str(self._total_results_requested)
            output.write(
                f"""
<results
    n={xmlattr(n)}
    requested={xmlattr(requested)}
    found-so-far={xmlattr(str(delivered))}
    projected={xmlattr(self.info['projected'])}
    corpus-coverage={xmlattr(round(100.0 * self.info['percentage'],2))}
>
    <meta>
        <submitted-at>{self.info['submitted_at']}</submitted-at>
        <completed-at>{self.info['completed_at']}</completed-at>
        <query>{self.info['query']}</query>
    </meta>
    <corpus>
        <name>{self.info['name']}</name>
        <word-count>{self.info['word_count']}</word-count>
    </corpus>"""
            )
            kwic_filename = os.path.join(folder, "_kwic.xml")
            non_kwic_filename = os.path.join(folder, "_non_kwic.xml")
            if os.path.exists(kwic_filename):
                with open(kwic_filename, "r") as input:
                    while line := input.readline():
                        output.write(f"    {line}")
                os.remove(kwic_filename)
            if os.path.exists(non_kwic_filename):
                with open(non_kwic_filename, "r") as input:
                    while line := input.readline():
                        output.write(f"    {line}")
                os.remove(non_kwic_filename)
            output.write(f"\n</results>")

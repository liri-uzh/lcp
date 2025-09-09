"""
ddl_gen.py: create SQL code for corpus creation based on uploaded metadata JSON
"""

import json
import math
import os
import re
import sys

from collections import abc, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from textwrap import dedent
from typing import Any, cast

from .typed import JSONObject
from .utils import is_prepared_annotation

TYPES_MAP = {
    "number": "int",
    "dict": "jsonb",
    "array": "text[]",
    "vector": "main.vector",
    "image": "text",
}


@dataclass
class DataNeededLater:
    """
    Everything that generate_ddl needs to return to upload.create function,
    which has been called by the /create endpoint.
    """

    create: str = ""
    constraints: list[str] = field(default_factory=list)
    prep_seg_create: str = ""
    prep_seg_insert: str = ""
    prep_seg_updates: list[str] = field(default_factory=list)
    m_token_n: str = ""
    m_token_freq: str = ""
    m_lemma_freqs: str = ""
    batchnames: list[str] = field(default_factory=list)
    mapping: dict[str, JSONObject] = field(default_factory=dict)
    # perms: str = ""
    refs: list[str] = field(default_factory=list)
    grant_query_select: str = ""

    def asdict(
        self,
    ) -> dict[str, str | list[str] | dict[str, int]]:
        return asdict(self)


class Globs:
    def __init__(self) -> None:
        self.base_map: dict[str, str] = {}
        self.layers: dict[str, dict[str, Any | str | list[str]]] = {}
        self.schema: list[str] = []
        self.tables: list[Table] = []
        self.types: list[Type] = []
        self.num_partitions: int = 0
        self.prep_seg_create: str = ""
        self.prep_seg_insert: str = ""
        self.prep_seg_updates: list[str] = []
        self.m_token_n: str = ""
        self.m_token_freq: str = ""
        self.m_lemma_freqs: str = ""
        self.batchnames: list[str] = []
        self.mapping: dict[str, JSONObject] = {}
        # self.perms: str = ""


LB = "{"
RB = "}"
SG = "'"


class DDL:
    """
    base DDL class for DB entities
    """

    def __init__(self) -> None:
        self.create_scm: Callable[[str, str, str], str] = lambda x, y, z: dedent(
            f"""
            CALL main.open_import('{x}'::uuid, '{y}'::uuid, '{z.replace("'","''")}');
            SET search_path TO "{x}";"""
        )

        self.create_prepared_segs: Callable[[str, str], str] = lambda x, y: dedent(
            f"""
            CREATE TABLE prepared_{x.rstrip("0")} (
                {y}         uuid    PRIMARY KEY REFERENCES {x} ({y}),
                id_offset   int8,
                content     jsonb,
                annotations jsonb
            );"""
        )

        self.compute_prep_segs: Callable[[str, str, str], str] = lambda x, y, z: dedent(
            f"""
             INSERT INTO {z.rstrip("0")}
                   (SELECT {x}
                        , min({y}) AS id_offset
                        , to_jsonb(array_agg(toks ORDER BY {y})) AS content
                        , '{LB}{RB}'::jsonb AS annotations
                     FROM (
                          SELECT {x}
                               , {y}
                               , jsonb_build_array(
                                    %s
                           ORDER BY {y}) x
                    GROUP BY {x});"""
        )

        self.update_prep_segs: Callable[[str, list[str], str, str, list[str]], str] = (
            lambda layer, attrs, seg, tok, joins: dedent(
                f"""
            UPDATE prepared_{seg} ps
            SET annotations = jsonb_set(ps.annotations, '{LB}LB{RB}{layer}{LB}RB{RB}', cte.annotations::jsonb)
            FROM (
                SELECT
                    sub.{seg}_id,
                    array_to_json(array_agg(sub.annotations)) annotations
                FROM (
                    SELECT
                        subs.{seg}_id,
                        jsonb_build_array(
                            (array_agg({tok}_id))[1],
                            array_length(array_agg({tok}_id),1),
                            json_build_object({', '.join([SG+a+SG+', subs.'+a for a in [x.split('.')[1] for x in attrs]])})
                        ) AS annotations
                    FROM (
                        SELECT
                            t.{seg}_id,
                            ann.{layer.lower()}_id{', '+(', '.join(attrs) if attrs else '')},
                            ann.char_range,
                            t.{tok}_id
                        FROM {LB}batch{RB} t
                        JOIN {layer.lower()} ann ON t.char_range && ann.char_range
                        {'JOIN '+' JOIN '.join(joins) if joins else ''}
                    ) subs
                    GROUP BY {layer.lower()}_id{(', '+', '.join([a.split('.')[1] for a in attrs]) if attrs else '')}, {seg}_id
                ) sub GROUP BY {seg}_id
            ) cte
            WHERE cte.{seg}_id = ps.{seg}_id;"""
            )
        )

        self.m_token_n: Callable[[str, str], str] = lambda x, y: dedent(
            f"""
                CREATE MATERIALIZED VIEW {x}_n AS
                SELECT count(*) AS freq
                  FROM {y};"""
        )

        self.m_lemma_freq: Callable[[str, str], str] = lambda x, y: dedent(
            f"""
                CREATE MATERIALIZED VIEW m_lemma_freq{x} AS
                SELECT x.lemma_id
                     , x.freq
                     , sum(x.freq) OVER () AS total
                  FROM (
                        SELECT lemma_id,
                               count(*) AS freq
                          FROM {y}{x}
                         GROUP BY lemma_id) x
                 ORDER BY x.freq DESC;"""
        )

        self.m_token_freq: Callable[[str, str, str], str] = lambda x, y, z: dedent(
            f"""
                CREATE MATERIALIZED VIEW {x}_freq AS
                  SELECT {y}
                       , count(*) AS freq
                    FROM {z}
                GROUP BY CUBE ({y});"""
        )

        self.t = "\t"
        self.nl = "\n\t"
        self.end = "\n);"
        self.tabwidth = 8

        self.anchoring = {
            "location": ("xy_box", "box"),
            "stream": ("char_range", "int4range"),
            "time": ("frame_range", "int4range"),
        }

        self._type_sizes = {
            "bigint": 8,
            "float": 8,
            "int": 4,
            "int2": 2,
            "int4": 4,
            "int8": 8,
            "int4range": 17,
            "int8range": 25,
            "smallint": 2,
            "text": 4,
            "uuid": 16,
        }
        return None

    def create_str(self) -> None:
        raise NotImplementedError

    @staticmethod
    def fmt(string: str, quote: bool = True, comma: bool = False) -> str:
        if quote:
            string = re.sub(r"'", "''", string)
            string = "'" + string + "'"
        if comma:
            return string + ","
        else:
            return string

    def inlined(self, args: list[str]) -> str:
        """
        method returning indented lines with comma at end for printing
        """
        return (
            self.nl
            + self.nl.join(map(lambda x: x + ",", args[:-1]))
            + self.nl
            + args[-1]
        )


class Column(DDL):
    _not_null_constr = "ALTER COLUMN {} SET NOT NULL;"
    _pk_constr = "ADD PRIMARY KEY ({});"
    _fk_constr = 'ADD FOREIGN KEY ({}) REFERENCES "{}".{}({});'
    _uniq_constr = "ADD UNIQUE ({});"
    _idx_constr = "{} ({});"

    def __init__(
        self, name: str, typ: str, **constrs: bool | None | str | dict[str, str]
    ) -> None:
        super().__init__()
        self.name = name
        self.type = typ
        self.constrs = constrs
        self.tabwidth = 8
        # self.analyse_constr(constr)

    def ret_tabulate(self, maxi: int) -> str:
        """
        method for tabulating DDL rows.

        """
        return (
            self.name
            + self.t * math.ceil((maxi - len(self.name)) / self.tabwidth)
            + self.type
        )
        # + self.t * (math.ceil((self._max_strtype - len(self.type)) / 8) + 1)

    def ret_constrs(self, schema: str) -> str:
        """
        method for generating all DLL constraints for a column (if there are any)
        """
        ret = []

        if not self.constrs:
            return ""

        for k, v in self.constrs.items():
            if k == "primary_key" and v:
                ret.append(self._pk_constr.format(self.name))
            elif k == "foreign_key" and v:
                assert isinstance(v, dict)
                ret.append(
                    self._fk_constr.format(self.name, schema, v["table"], v["column"])
                )
            elif k == "unique" and v:
                ret.append(self._uniq_constr.format(self.name))
            elif k == "not_null" and v:
                ret.append(self._not_null_constr.format(self.name))

        return "\n".join(ret)

    def ret_idx(self) -> str:
        """
        method for generating the DLL index for a column (ATM everything is indexed)
        """
        if self.constrs.get("primary_key", False):
            return ""
        elif self.type == "jsonb":
            return ""
        elif self.type in ("int4range", "int8range", "point", "box"):
            return self._idx_constr.format("USING gist", self.name)
        elif self.type == "tsvector":
            return self._idx_constr.format("USING rum", self.name)
        else:
            return self._idx_constr.format("", self.name)


class Table(DDL):
    def __init__(
        self,
        name: str,
        cols: list[Column],
        anchorings: list[str] | None = None,
        parent: str | None = None,
    ) -> None:
        super().__init__()
        name = name.strip()
        self.parent = (parent or "").strip().lower()
        if self.parent:
            name = f"{self.parent}_{name}"
        self.name = name
        self.header_txt = f"CREATE TABLE {self.name} ("
        self.cols = cols
        self.tabwidth = 8
        self.type_sizes: dict[str, int] = {}
        if anchorings:
            for anchor in set(anchorings):
                self.cols.append(Column(*self.anchoring[anchor]))
        self._max_ident = (
            math.ceil((max([len(col.name) for col in cols]) + 1) / self.tabwidth)
            * self.tabwidth
        )
        # self._max_strtype = max([len(col.type) for col in cols])
        # self._order_cols()

    def primary_key(self) -> list[Column]:
        return [x for x in self.cols if x.constrs.get("primary_key")]

    # def _order_cols(self) -> None:
    #    """
    #    method for ordering attributes for optimized storage

    #    this method breaks mypy so it is temporarily disabled
    #    """
    #    self.cols = sorted(
    #        self.cols,
    #        key=lambda x: (self.type_sizes.get(x.type, 4), reversor(x.name)),
    #        reverse=True,
    #    )
    #    return None

    def create_tbl(self) -> str:
        return (
            self.header_txt
            + self.inlined(
                [
                    self.fmt(col.ret_tabulate(self._max_ident), quote=False)
                    for col in self.cols
                ]
            )
            + self.end
        )

    def create_constrs(self, schema: str) -> list[str]:
        ret = [
            f'ALTER TABLE "{schema}".{self.name} ' + constr
            for col in self.cols
            if (constr := col.ret_constrs(schema))
        ]
        return ret

    def create_idxs(self, schema: str, no_index: set[str] = set()) -> list[str]:
        ret = [
            f'CREATE INDEX ON "{schema}".{self.name} ' + idx
            for col in self.cols
            if (idx := col.ret_idx()) and col.name.lower() not in no_index
        ]
        return ret

    def create_DDL(self, schema: str) -> str:
        return (
            self.create_tbl()
            + "\n\n"
            + "\n".join(self.create_constrs(schema))
            + "\n\n"
            + "\n".join(self.create_idxs(schema))
        )

    def __lt__(self, other: object) -> bool:
        o = cast(Table, other)
        assert hasattr(o, "name") and hasattr(self, "name")
        return bool(self.name < o.name)

    def __eq__(self, other: object) -> bool:
        o = cast(Table, other)
        assert hasattr(o, "name") and hasattr(self, "name")
        return bool(self.name == o.name)


class PartitionedTable(Table):
    max_id = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

    @staticmethod
    def half_hex(num: int | str) -> str:
        if isinstance(num, str):
            num = int(num, 16)
        res = hex(int(num / 2))

        return res

    @staticmethod
    def hex2uuid(num: int | str) -> str:
        if isinstance(num, int):
            num = hex(num)
        form = re.match(
            "(.{8})(.{4})(.{4})(.{4})(.{12})", num.replace("0x", "").rjust(32, "0")
        )
        if not form:
            raise ValueError(f"Cannot match {num}")

        return f"{form[1]}-{form[2]}-{form[3]}-{form[4]}-{form[5]}"

    def __init__(
        self,
        name: str,
        cols: list[Column],
        anchorings: list[str] | None = None,
        column_part: str = "segment_id",
        num_part: int = 10,
    ) -> None:
        super().__init__(name, cols, anchorings)
        self.base_name = self.name
        self.name = f"{self.base_name}0"
        self.num_partitions = num_part
        self.col_partitions = column_part
        self.header_txt = f"CREATE TABLE {self.name} ("

    def _create_maintbl(self) -> str:
        return (
            self.header_txt
            + self.inlined(
                [
                    self.fmt(col.ret_tabulate(self._max_ident), quote=False)
                    for col in self.cols
                ]
            )
            + f"\n) PARTITION BY RANGE ({self.col_partitions});"
        )

    def _create_subtbls(self) -> list[str]:
        tbls: list[str] = []
        cur_max: str | int = self.max_id

        for i in range(1, self.num_partitions + 1):
            end = "rest" if i == self.num_partitions else str(i)
            batchname = f"{self.base_name}{end}"
            tbl_n = f"CREATE TABLE {batchname} PARTITION OF {self.name}"
            cur_min = self.half_hex(cur_max)

            mmax = self.hex2uuid(cur_max)
            mmin = self.hex2uuid(cur_min if end != "rest" else 0)

            defn = f"{self.nl}FOR VALUES FROM ('{mmin}'::uuid) TO ('{mmax}'::uuid); "
            tbls.append(tbl_n + defn)

            cur_max = cur_min

        return tbls

    def create_constrs(self, schema: str) -> list[str]:
        ret = []

        pks = []
        for col in self.cols:
            if col.constrs.get("primary_key"):
                pks.append(col.name)
                col.constrs.pop("primary_key")

        # mypy cannot handle the lambda that used to be here :(
        starts = [i for i in pks if i == self.col_partitions]
        ends = [i for i in pks if i != self.col_partitions]
        pks = starts + ends

        ret.append(
            f"ALTER TABLE \"{schema}\".{self.name} ADD PRIMARY KEY ({', '.join(pks)});"
        )

        ret += [
            f'ALTER TABLE "{schema}".{self.name} ' + constr
            for col in self.cols
            if (constr := col.ret_constrs(schema))
        ]
        return ret

    def create_tbl(self) -> str:
        main_t = [self._create_maintbl()]
        sub_ts = self._create_subtbls()

        return "\n\n".join(main_t + sub_ts)


class Type(DDL):
    def __init__(self, name: str, values: list[str]) -> None:
        super().__init__()
        self.name = name.strip()
        self.header_txt = f"CREATE TYPE {self.name} AS ENUM ("
        self.values = sorted(set(values))

    def create_DDL(self) -> str:
        return (
            self.header_txt
            + self.inlined([self.fmt(x) for x in self.values])
            + self.end
        )

    def __lt__(self, other: object) -> bool:
        o = cast(Type, other)
        assert hasattr(o, "name") and hasattr(self, "name")
        return bool(self.name < o.name)

    def __eq__(self, other: object) -> bool:
        o = cast(Type, other)
        assert hasattr(o, "name") and hasattr(self, "name")
        return bool(self.name == o.name)


class CTProcessor:
    def __init__(
        self,
        corpus_template: dict[str, Any],
        project_id: str,
        glos: Globs,
        corpus_version: int = 1,
    ) -> None:
        self.corpus_temp = corpus_template
        self.project_id = project_id
        self.schema_name = corpus_template.get("schema_name", "testcorpus")
        self.layers = self._order_ct_layers(corpus_template["layer"])
        self.global_attributes = corpus_template.get("globalAttributes", {})
        self.globals = glos
        self.ddl = DDL()
        self.corpus_version = corpus_version

    @staticmethod
    def _order_ct_layers(
        layers: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        # check if all layers referred to do exist
        referred = set([ref for v in layers.values() if (ref := v.get("contains"))])
        exists = set(layers)

        if not exists > referred:
            not_ex = referred - exists
            str_not_ex = ", ".join(sorted(["'" + elem + "'" for elem in not_ex]))

            raise Exception(f"The following referred layers do not exist: {str_not_ex}")

        ordered = {}
        to_append, last_append = [], []

        for k, v in layers.items():
            if v.get("layerType") == "relation":
                last_append.append((k, v))
            elif not v.get("contains"):
                ordered[k] = v
            else:
                to_append.append((k, v))

        while to_append:
            to_remove = set()
            for n, (k, v) in enumerate(to_append):
                if v["contains"] in ordered:
                    ordered[k] = v
                    to_remove.add(n)
            to_append = [x for n, x in enumerate(to_append) if n not in to_remove]

        for k, v in last_append:
            ordered[k] = v

        return ordered

    def _process_attributes(
        self,
        attr_structure: abc.ItemsView[str, Any],
        tables: list[Table],
        table_cols: list[Column],
        types: list[Type],
        entity_name: str,
    ) -> tuple[list[Table], list[Column]]:

        entity_mapping: dict[str, JSONObject | bool] = cast(
            dict[str, JSONObject | bool], self.globals.mapping["layer"][entity_name]
        )
        map_attr: dict[str, dict] = {}

        for attr, vals in attr_structure:
            nullable = vals.get("nullable", False) or False
            # TODO: make this working also for e.g. "isGlobal" & "text"
            typ = vals.get("type")
            ref = vals.get("ref", "")
            if typ == "text" or ref:
                norm_type = "text"
                parent = entity_name.lower()
                if ref:
                    assert ref in self.global_attributes, ReferenceError(
                        f"Global attribute {ref} could not be found"
                    )
                    norm_type = self.global_attributes[ref].get("type", "text")
                    parent = "global_attribute"

                ref_or_attr = (ref or attr).lower()

                norm_col = f"{ref_or_attr}_id"
                norm_table: Table
                existing_table: Table | None = next(
                    (
                        t
                        for t in self.globals.tables
                        if t.name == f"global_attribute_{ref}"
                    ),
                    None,
                )
                if existing_table is not None:
                    norm_table = existing_table
                else:
                    norm_table = Table(
                        ref_or_attr,
                        [
                            Column(norm_col, "text", primary_key=True),
                            Column(ref_or_attr, TYPES_MAP.get(norm_type, norm_type)),
                        ],
                        parent=parent,
                    )
                map_attr[attr] = {
                    "name": norm_table.name,
                    "type": "relation",
                    "key": ref_or_attr,
                }

                table_cols.append(
                    Column(
                        attr.lower() + "_id",
                        "text",
                        foreign_key={"table": norm_table.name, "column": norm_col},
                        nullable=nullable,
                    )
                )

                if existing_table is None:
                    tables.append(norm_table)

            elif typ == "dict":
                norm_col = f"{attr}_id"
                norm_table = Table(
                    attr,
                    [
                        Column(norm_col, "int", primary_key=True),
                        Column(attr, TYPES_MAP.get("dict", "jsonb"), unique=True),
                    ],
                    parent=entity_name.lower(),
                )
                map_attr[attr] = {"name": norm_table.name, "type": "relation"}

                table_cols.append(
                    Column(
                        norm_col,
                        "int",
                        foreign_key={"table": norm_table.name, "column": norm_col},
                        nullable=nullable,
                    )
                )

                tables.append(norm_table)

            elif typ == "categorical":
                if vals.get("isGlobal"):
                    table_cols.append(Column(attr, f"main.{attr}", nullable=nullable))
                else:
                    assert (
                        "values" in vals
                    ), f"List of values is needed when type is categorical ({entity_name}:{attr})"
                    enum_name = f"{entity_name}_{attr}".lower()
                    enum_type = Type(enum_name, vals["values"])
                    types.append(enum_type)
                    table_cols.append(Column(attr, enum_name, nullable=nullable))

            elif typ == "date":
                table_cols.append(Column(attr, "date", nullable=nullable))

            elif typ == "number":
                table_cols.append(Column(attr, "int", nullable=nullable))

            elif typ == "image":
                table_cols.append(Column(attr, "text", nullable=nullable))

            elif typ == "uuid":
                table_cols.append(Column(attr, "uuid", nullable=nullable))

            elif typ == "boolean":
                table_cols.append(Column(attr, "boolean", nullable=nullable))

            elif typ == "array":
                # For now we treat all arrays as text arrays
                table_cols.append(Column(attr, "text[]", nullable=nullable))

            elif typ == "vector":
                table_cols.append(Column(attr, "main.vector", nullable=nullable))

            elif typ == "labels":
                entity_attrs = self.layers[entity_name].get("attributes", {})
                assert attr in entity_attrs, ReferenceError(
                    f"Could not find attribute {attr} on {entity_name}"
                )
                assert "nlabels" in entity_attrs[attr], AttributeError(
                    f"Attribute {entity_name}->{attr} is of type labels but no number of distinct labels was provided for it"
                )
                nbit = entity_attrs[attr]["nlabels"]
                assert str(nbit).isnumeric(), TypeError(
                    f"The value of {entity_name}->{attr}'s 'nlabels' should be an integer; got '{nbit}' instead"
                )
                table_cols.append(Column(attr, f"bit({nbit})", nullable=nullable))
                # Create lookup table if needed
                label_lookup_table_name = f"{entity_name.lower()}_{attr.lower()}"
                map_attr[attr] = {"name": label_lookup_table_name, "type": "relation"}
                if label_lookup_table_name not in [t.name for t in tables]:
                    inttype = "int2"
                    if int(nbit) > 32767:
                        inttype = "int4"
                    elif int(nbit) > 2147483647:
                        inttype = "int8"
                    elif int(nbit) > 9223372036854775807:
                        raise ValueError(
                            f"Cannot accommodate more than 9223372036854775807 distinct labels"
                        )
                    label_lookup_table = Table(
                        attr.lower(),
                        [
                            Column("bit", inttype, primary_key=True),
                            Column("label", "text", unique=True),
                        ],
                        parent=entity_name.lower(),
                    )
                    tables.append(label_lookup_table)

            elif attr == "meta":
                table_cols.append(Column(attr, "jsonb", nullable=nullable))
                entity_mapping["hasMeta"] = True

            else:
                raise Exception(
                    f"unknown type for attribute: '{entity_name}'->'{attr}'"
                )

        if map_attr:
            entity_mapping["attributes"] = cast(JSONObject, map_attr)

        self.globals.mapping["layer"][entity_name] = cast(
            dict[str, Any], entity_mapping
        )
        return tables, table_cols

    def _process_unitspan(self, entity: dict[str, dict[str, Any]]) -> None:
        l_name, l_params = list(entity.items())[0]
        tables: list[Table] = []
        table_cols: list[Column] = []
        types: list[Type] = []

        table_name = l_name.lower()

        # create primary key column (if table that will be used to partition -> UUID)
        if l_name == self.globals.base_map["segment"]:
            table_cols.append(Column(f"{table_name}_id", "uuid", primary_key=True))
        else:
            table_cols.append(Column(f"{table_name}_id", "int", primary_key=True))
        tables, table_cols = self._process_attributes(
            l_params.get("attributes", {}).items(), tables, table_cols, types, l_name
        )

        anchs = [k for k, v in l_params.get("anchoring", {}).items() if v]
        if l_params.get("layerType") == "span" and (child := l_params.get("contains")):
            anchs += self.globals.layers[child]["anchoring"]

        if l_name == self.globals.base_map["token"]:
            part_ent = self.globals.base_map["segment"].lower()
            part_ent_col = f"{part_ent}_id"

            part_col = Column(
                part_ent_col,
                "uuid",
                primary_key=True,
                foreign_key={"table": part_ent + "0", "column": part_ent_col},
            )
            table_cols.append(part_col)
            ptable = PartitionedTable(
                table_name, table_cols, anchorings=anchs, column_part=part_ent_col
            )
            tables.append(ptable)
        elif l_name == self.globals.base_map["segment"]:
            part_ent = self.globals.base_map["segment"].lower()
            part_ent_col = f"{part_ent}_id"

            ptable = PartitionedTable(
                table_name, table_cols, anchorings=anchs, column_part=part_ent_col
            )
            tables.append(ptable)
        else:
            has_media = self.corpus_temp["meta"].get("mediaSlots", {})
            if l_name == self.globals.base_map["document"] and has_media:
                table_cols.append(Column("media", "jsonb"))
                if any(
                    x.get("mediaType") in ("audio", "video") for x in has_media.values()
                ):
                    table_cols.append(Column("name", "text"))
            ptable = None
            # If this layer is contained in another, add an FK column
            for parent_layer, pl_conf in self.layers.items():
                if pl_conf.get("contains") != l_name:
                    continue
                table_cols.append(Column(f"{parent_layer.lower()}_id", "int"))
            table = Table(table_name, table_cols, anchorings=anchs)
            tables.append(table)

        layer_mapping: dict = cast(dict, self.globals.mapping["layer"][l_name])
        if ptable:
            layer_mapping["relation"] = ptable.name.rstrip("0") + "<batch>"
            if not self.globals.num_partitions:
                self.globals.num_partitions = ptable.num_partitions
        else:
            layer_mapping["relation"] = table.name

        self.globals.layers[l_name] = {}
        self.globals.layers[l_name]["anchoring"] = anchs
        self.globals.layers[l_name]["table_name"] = (
            table.name if not ptable else ptable.name
        )

        self.globals.tables += tables
        self.globals.types += types

    def _process_relation(self, entity: dict[str, dict[str, Any]]) -> None:
        # TODO: create FK constraints
        l_name, l_params = list(entity.items())[0]
        table_name = l_name.lower()
        tables: list[Table] = []
        table_cols: list[Column] = []
        types: list[Type] = []

        assert "source" in l_params["attributes"], ReferenceError(
            f"The attributes of '{l_name}' must include 'source'"
        )
        assert "target" in l_params["attributes"], ReferenceError(
            f"The attributes of '{l_name}' must include 'target'"
        )
        source_col = self._get_relation_col(l_params["attributes"]["source"])
        target_col = self._get_relation_col(l_params["attributes"]["target"])

        if not source_col and target_col:
            raise Exception

        table_cols.append(source_col)
        table_cols.append(target_col)

        attributes_to_process = {
            k: v
            for k, v in l_params.get("attributes", {}).items()
            if k not in ("source", "target")
        }
        tables, table_cols = self._process_attributes(
            attributes_to_process.items(), tables, table_cols, types, l_name
        )

        table = Table(table_name, table_cols)

        tables.append(table)

        layer_mapping: dict = cast(dict, self.globals.mapping["layer"][l_name])
        layer_mapping["relation"] = table.name

        self.globals.layers[l_name] = {}
        self.globals.layers[l_name]["table_name"] = table.name

        self.globals.tables += tables
        self.globals.types += types

    def _get_relation_col(self, rel_structure: dict[str, str]) -> Column:
        name = rel_structure["name"]
        table_name = self.globals.layers[rel_structure["entity"]]["table_name"]
        table = next(x for x in self.globals.tables if x.name == table_name)
        fk_col = f"{rel_structure['entity'].lower()}_id"
        typ = next(x for x in table.cols if x.name == fk_col).type
        nullable = rel_structure.get("nullable")

        return Column(name, typ, nullable=nullable)

    def process_layers(self) -> None:
        self.globals.mapping["layer"] = cast(dict[str, Any], {})
        for layer, params in self.layers.items():
            self.globals.mapping["layer"][layer] = cast(dict[str, Any], {})
            if (layer_type := params.get("layerType")) in ["unit", "span"]:
                self._process_unitspan({layer: params})
            elif layer_type == "relation":
                self._process_relation({layer: params})
            else:
                raise Exception(
                    f"unknown layer type '{layer_type}' for layer '{layer}'."
                )

    def create_fts_table(self) -> None:
        part_ent = self.globals.base_map["segment"].lower()
        part_ent_col = f"{part_ent}_id"

        part_col = Column(
            part_ent_col,
            "uuid",
            primary_key=True,
            foreign_key={"table": part_ent + "0", "column": part_ent_col},
        )

        fts_col = Column("vector", "tsvector")

        part_ent = self.globals.base_map["segment"].lower()
        part_ent_col = f"{part_ent}_id"

        ptable = PartitionedTable(
            "fts_vector", [part_col, fts_col], column_part=part_ent_col
        )

        self.globals.tables.append(ptable)

        mapd: dict[str, Any] = self.globals.mapping
        mapd["hasFTS"] = True
        tok_tab = next(
            x
            for x in self.globals.tables
            if x.name == self.globals.base_map["token"].lower() + "0"
        )
        rel_cols = [
            x.name.removesuffix("_id")
            for x in tok_tab.cols
            if not (x.constrs.get("primary_key") or x.type in ("int4range", "box"))
        ]
        mapd["FTSvectorCols"] = {n: rc for n, rc in enumerate(rel_cols, start=1)}
        self.globals.mapping = mapd

    def process_schema(self) -> str:
        original_name = self.corpus_temp["meta"]["name"]
        corpus_name = re.sub(r"\W", "_", original_name.lower())
        corpus_name = re.sub(r"_+", "_", corpus_name)
        # corpus_version = str(int(self.corpus_temp["meta"]["version"]))
        # corpus_version = re.sub(r"\W", "_", corpus_version.lower())
        # corpus_version = re.sub(r"_+", "_", corpus_version)
        # corpus_version = str(self.corpus_version)
        schema_name: str = self.schema_name
        project_id: str = self.project_id
        copy_corpus_temp: dict[str, Any] = json.loads(json.dumps(self.corpus_temp))
        # remove any left_anchor/right_anchor for the relational layers
        for lname, lattrs in cast(dict, copy_corpus_temp)["layer"].items():
            if lattrs.get("layerType") != "relation":
                continue
            lattrs["attributes"].pop("left_anchor", "")
            lattrs["attributes"].pop("right_anchor", "")
        corpus_template: str = json.dumps(copy_corpus_temp)
        # scm: str = self.ddl.create_scm(schema_name, corpus_name, corpus_version)
        scm: str = self.ddl.create_scm(schema_name, project_id, corpus_template)
        self.globals.schema.append(scm)
        # query_user = os.getenv("SQL_QUERY_USERNAME", "lcp_dev_webuser")
        # perms: str = self.ddl.perms(schema_name, query_user)
        # self.globals.perms = perms
        return schema_name

    def create_collocation_views(self) -> None:
        search_path = f'\nSET search_path TO "{self.schema_name}";'
        tok_tbl = self.globals.base_map["token"].lower()
        statement: str = self.ddl.m_token_n(tok_tbl, tok_tbl + "0")

        self.globals.m_token_n = f"\n\n{search_path}\n{statement}"

        views = [f"\n\n{search_path}\n"]

        for i in range(self.globals.num_partitions):
            part: str = "rest" if i + 1 == self.globals.num_partitions else str(i)

            statement = self.ddl.m_lemma_freq(part, tok_tbl)
            views.append(statement)

        self.globals.m_lemma_freqs = "\n".join(views)

        [token_tbl] = (x for x in self.globals.tables if x.name == tok_tbl + "0")
        rel_cols = ", ".join(
            [
                x.name
                for x in token_tbl.cols
                if not (x.constrs.get("primary_key") or x.type in ("int4range", "box"))
            ]
        )
        statement = self.ddl.m_token_freq(tok_tbl, rel_cols, tok_tbl + "0")

        self.globals.m_token_freq = f"\n\n{search_path}\n{statement}"

    def create_compute_prep_segs(self) -> None:
        tok_lower = self.globals.base_map["token"].lower()
        tok_tab = next(x for x in self.globals.tables if x.name == tok_lower + "0")
        seg_tab = next(
            x
            for x in self.globals.tables
            if x.name == self.globals.base_map["segment"].lower() + "0"
        )

        tok_pk = next(x for x in tok_tab.primary_key() if tok_lower in x.name)
        rel_cols = sorted(
            [
                x
                for x in tok_tab.cols
                if not (x.constrs.get("primary_key") or x.type in ("int4range", "box"))
            ],
            key=lambda x: x.name,
        )
        rel_cols_names = [x.name.removesuffix("_id") for x in rel_cols]
        # Process any token dependency
        for lay_name, lay_conf in self.layers.items():
            if lay_conf.get("layerType") != "relation":
                continue
            target = lay_conf.get("attributes", {}).get("target", {})
            source = lay_conf.get("attributes", {}).get("source", {})
            if (
                not target
                or not source
                or not all(
                    x.get("entity", "") == self.globals.base_map["token"]
                    for x in (target, source)
                )
            ):
                continue
            name = target.get("name")
            if not name:
                continue
            rel_cols_names.append(name)
            dep_table = next(
                (x for x in self.globals.tables if x.name.lower() == lay_name.lower()),
                None,
            )
            if not dep_table or not source.get("name"):
                continue
            dep_column = Column(
                name,
                "int",
                foreign_key={
                    "table": dep_table.name,
                    "condition": f"{tok_lower}_id = {source.get('name')}",
                },
            )
            rel_cols.append(dep_column)
            for an, at in lay_conf.get("attributes", {}).items():
                if at.get("type") != "categorical":
                    continue
                rel_cols_names.append(an)

        mapd: dict[str, Any] = self.globals.mapping
        tokname = self.globals.base_map["token"]
        batchname = f"{tokname}<batch>"
        mapd["layer"][tokname]["batches"] = self.globals.num_partitions
        segname = self.globals.base_map["segment"]
        mapd["layer"][segname]["prepared"] = {
            "relation": ("prepared_" + segname),
            "columnHeaders": rel_cols_names,
        }
        self.globals.mapping = mapd

        searchpath = f'\nSET search_path TO "{self.schema_name}";'

        ddl: str = self.ddl.create_prepared_segs(
            seg_tab.name, seg_tab.primary_key()[0].name
        )

        self.globals.prep_seg_create = f"\n\n{searchpath}\n{ddl}"

        json_joins = []
        for x in rel_cols:
            fk = x.constrs.get("foreign_key")
            if not fk or not isinstance(fk, dict):
                continue
            right_part = (
                f" ON {fk['condition']}"
                if "condition" in fk
                else f" USING ({fk['column']})"
            )
            json_joins.append(fk["table"] + right_part)

        json_joins_str = "JOIN " + f"\n                LEFT JOIN ".join(json_joins)
        json_sel = (
            "\n                      , ".join(rel_cols_names)
            + f"\n                     ) AS toks\n                FROM {{batch}}\n                "
            + json_joins_str
        )

        query: str = (
            self.ddl.compute_prep_segs(
                seg_tab.primary_key()[0].name,
                tok_pk.name,
                f"prepared_{seg_tab.name}",
            )
            % json_sel
        )

        self.globals.prep_seg_insert = f"\n\n{searchpath}\n{query}"

        self.globals.prep_seg_updates = []
        for layer, props in self.corpus_temp["layer"].items():
            if not is_prepared_annotation(self.corpus_temp, layer):
                continue
            if not props.get("attributes", {}):
                continue
            mapping_attrs = cast(
                dict[str, Any], self.globals.mapping["layer"].get(layer, {})
            ).get("attributes", {})
            attrs = []
            joins: list[str] = []
            for a in props.get("attributes", {}):
                info: dict[str, Any] = mapping_attrs.get(a, {})
                if info.get("type") != "relation":
                    attrs.append(f"ann.{a}")
                    continue
                table = info.get("name", "")
                assert table, LookupError(f"Mapping missing 'name' for {layer}->{a}")
                attrs.append(f"ann_{a}.{a}")
                key = info.get("key", a)
                joins.append(f"{table} ann_{a} ON ann.{key}_id = ann_{a}.{key}_id")
            update: str = (
                # layer, attrs, seg, tok, joins
                self.ddl.update_prep_segs(layer, attrs, segname, tokname, joins)
            )
            self.globals.prep_seg_updates.append(update)

        # todo: check this again
        for i in range(1, self.globals.num_partitions):
            if i == self.globals.num_partitions - 1 and i > 1:
                batch = batchname.replace("<batch>", "rest")
            else:
                batch = batchname.replace("<batch>", str(i))
            self.globals.batchnames.append(batch)


def generate_ddl(
    corpus_temp: dict[str, Any],
    project_id: str,
    corpus_version: int = 1,
    no_index: list[list[str]] = [],
) -> dict[str, str | list[str] | dict[str, int]]:
    globs = Globs()
    globs.base_map = corpus_temp["firstClass"]

    processor = CTProcessor(corpus_temp, project_id, globs, corpus_version)

    schema_name = processor.process_schema()
    processor.process_layers()
    processor.create_fts_table()
    processor.create_compute_prep_segs()
    processor.create_collocation_views()

    # Remove empty mappings (use * keys to avoid "dictionary changed size during iteration" error)
    for layer in [*globs.mapping["layer"].keys()]:
        mappings = globs.mapping["layer"].get(layer)
        if not mappings:
            globs.mapping["layer"].pop(layer)

    create_schema = "\n\n".join([x for x in globs.schema])
    create_types = "\n\n".join([x.create_DDL() for x in sorted(t for t in globs.types)])
    create_tbls = "\n\n".join([x.create_tbl() for x in sorted(t for t in globs.tables)])

    create = "\n".join([create_schema, create_types, create_tbls])

    # todo: i don't think this defaultdict trick is needed, all the tables
    # must have unique names right?
    QUERY_USER: str = os.getenv("SQL_QUERY_USERNAME", "lcp_dev_webuser")
    constraints: defaultdict[str, list[str]] = defaultdict(list)
    refs: list[str] = []
    for table in sorted(globs.tables):
        no_index_table = {
            attr.lower() for lay, attr in no_index if lay.lower() == table.parent
        }
        constraints[table.name] += table.create_idxs(schema_name, no_index_table)
        cons = table.create_constrs(schema_name)
        for c in cons:
            if " REFERENCES " in c:
                refs.append(c)
            else:
                constraints[table.name].append(c)
    grant_query_select = (
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema_name}" TO {QUERY_USER}'
    )
    formed_constraints = ["\n".join(i) for i in constraints.values()]

    return DataNeededLater(
        create,
        formed_constraints,
        globs.prep_seg_create,
        globs.prep_seg_insert,
        globs.prep_seg_updates,
        globs.m_token_n,
        globs.m_token_freq,
        globs.m_lemma_freqs,
        globs.batchnames,
        globs.mapping,
        # globs.perms,
        refs,
        grant_query_select,
    ).asdict()


def main(corpus_template_path: str) -> None:
    with open(corpus_template_path) as f:
        corpus_temp = json.load(f)

    data = generate_ddl(corpus_temp, "project_id")

    # print(json.dumps(data, indent=4))
    print(data["create"])
    print()
    for ref in sorted(data["refs"]):
        print(ref)
    for ref in sorted(data["constraints"]):
        print(ref)
    print(data["prep_seg_create"])
    print(data["prep_seg_insert"])
    print(data["prep_seg_updates"])
    print(data["m_token_n"])
    print(data["m_token_freq"])
    print(data["m_lemma_freqs"])
    # print(data["perms"])
    print(data["grant_query_select"])

    print("Mapping:", data["mapping"])

    return


if __name__ == "__main__":
    main(sys.argv[-1])

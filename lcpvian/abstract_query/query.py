import json
import re

from typing import Any, cast

from .constraint import Constraints, _get_constraints, process_set
from .prefilter import Prefilter
from .sequence import Cte, SQLSequence
from .sequence_members import Sequence
from .typed import JSONObject, Joins, LabelLayer, QueryJSON, QueryPart
from .utils import (
    Config,
    QueryData,
    _flatten_coord,
    _get_table,
    _get_mapping,
    _get_batch_suffix,
    _get_underlang,
    _joinstring,
    _layer_contains,
    _bound_label,
)

MATCH_LIST = """
WITH RECURSIVE fixed_parts AS (
    SELECT {selects}
        FROM {from_table}
        {joins}
        {needed_where}
        {conditions}
        {group_by}
        {havings}
),
{additional_ctes}
match_list AS (
    SELECT {match_selects}
        FROM {match_from}
),
"""

SELECT_PH = "{selects}"
CARRY_PH = "{carry_over}"


class Token:
    def __init__(
        self,
        layer: str,
        part_of: list[dict[str, str]],
        label: str,
        constraints: Any,
        order: int | None,
        prev_label: str | None,
        conf: Config,
        quantor: str | None,
        label_layer: LabelLayer,
        set_objects: set[str],
        entities: set[str] | None,
        n: int,
    ) -> None:
        """
        Model a single Token object, whether in a sequence or not
        Constraints are stored in self.conn_obj, and have their own
        joins and selects associated with them
        """
        self.layer = layer
        self.part_of = part_of
        self.label = label
        self.constraints = constraints
        self.order = order
        self.set_objects = set_objects
        self.prev_label = prev_label
        self.conf = conf
        self.config = conf.config
        self.schema = conf.schema
        self.lang = conf.lang
        self.entities = entities
        self.batch = conf.batch
        self.token = self.config["token"]
        self.segment = self.config["segment"]
        self.document = self.config["document"]
        self.label_layer = label_layer
        self.quantor = quantor
        self._n: int = n or 1
        self._needs_lang: bool = False
        self.conn_obj = _get_constraints(
            self.constraints,
            self.layer,
            self.label,
            self.conf,
            quantor=quantor,
            label_layer=self.label_layer,
            n=self._n,
            order=self.order,
            set_objects=self.set_objects,
            prev_label=self.prev_label,
            entities=self.entities,
            part_of=part_of,
        )

    def joins(self) -> Joins:
        """
        Get a set (dict keys) of joins needed for one token
        """
        out: Joins = {}
        if self.quantor:
            return out
        if self.layer and self.label:
            lay = (
                self.batch
                if self.layer.lower() == self.config["token"].lower()
                else self.layer
            )
            lay = lay.lower()
            formed = f"{self.schema.lower()}.{lay} {self.label.lower()}"
            out[formed] = None
        joins = self.conn_obj.joins() if self.conn_obj else {}
        for k, v in joins.items():
            if k.strip():
                out[k] = v
        return out

    def conditions(self) -> set[str]:
        """
        Get all conditions for a single token (possibly within a sequence)
        """
        out: set[str] = set()
        if self.conn_obj is None:
            return out
        if self.quantor:
            out.add(self.conn_obj._build_subquery(self.conn_obj))
            return out
        conditions: str = self.conn_obj.conditions() if self.conn_obj else ""
        if conditions.strip():
            out.add(conditions)
        return out


class QueryMaker:
    def __init__(
        self,
        query_json: QueryJSON,
        result_data: QueryData,
        conf: Config,
    ) -> None:
        """
        A class to oversee the generation of the query part of the SQL
        Use the query() method to actually make the SQL after instantiating
        """
        self.query_json: QueryJSON = query_json
        self.r = result_data
        self.conf = conf
        self.schema: str = conf.schema
        self.batch: str = conf.batch
        self.config: JSONObject = conf.config
        self.lang: str | None = conf.lang
        self._one_done: bool = False
        self._n = 1
        self.selects: set[str] = set()
        self.joins: Joins = {}
        self.conditions: set[str] = set()
        self.group_by: str = ""
        self.having: str = ""
        self.template: str = MATCH_LIST
        self.token = cast(str, self.config["token"])
        self.segment = cast(str, self.config["segment"])
        self.document = cast(str, self.config["document"])
        mapping = cast(dict[str, Any], self.config["mapping"])
        layers = cast(JSONObject, mapping["layer"])
        _cols = cast(JSONObject, layers[self.segment])
        self._needs_lang: bool = self.lang in cast(
            JSONObject, _cols.get("partitions", {})
        )
        self.has_fts: bool = cast(bool, mapping.get("hasFTS", False))
        self.main_layer = ""
        self.main_label = ""
        # _table is the main table on which the query is run: (table, lab)
        self._table: tuple[str, str] | None = None
        self._backup_table: tuple[str, str] | None = None
        self._base = ""
        self._underlang = _get_underlang(self.lang, self.config)
        self._has_segment: str = ""
        layer_info: dict[str, Any] = cast(dict[str, Any], layers[self.token])
        self.n_batches: int = (
            layer_info["partitions"][self.lang].get("batches", 1)
            if "partitions" in layer_info
            else layer_info.get("batches", 1)
        )
        self.sqlsequences: list[SQLSequence] = self.r.sqlsequences  # []

    def _token(
        self,
        obj: JSONObject,  # obj should be a "unit" object as defined in cobquec
        _layer: str,
        _label: str,
        _part_of: list[dict[str, str]],
        j: int | None = None,
        prev_label: str | None = None,
    ) -> tuple[Joins, set[str]]:
        """
        Create a Token object and get its joins and conditions
        """
        layer = cast(str, obj.get("layer", _layer))
        label = cast(str, obj.get("label", ""))
        if not label:
            if j is not None:
                label = f"anonymous_token_from_{_label}_{str(j)}".lower()
            else:
                label = _label
        part_of = cast(list[dict[str, str]], obj.get("partOf", _part_of))
        constraints = cast(JSONObject, obj.get("constraints", []))
        # todo: should we turn Token into Token0 here?
        tok = Token(
            layer,
            part_of,
            label,
            constraints,
            j,
            prev_label,
            self.conf,
            cast(str | None, obj.get("quantor", None)),
            self.r.label_layer,
            self.r.set_objects,
            self.r.entities,
            self._n,
        )
        self._n += 1
        joins = tok.joins()
        conditions = tok.conditions()
        if (
            self.r.entities
            and label.lower() not in self.r.entities
            and layer not in (self.token, self.batch)
        ):
            conditions = set()
        return joins, conditions

    def _get_label_as(self, select: str) -> str:
        return re.split(" as ", select, flags=re.IGNORECASE)[-1]

    def _make_main(self, query_part: QueryPart) -> tuple[str, str, str]:
        """
        Establish whether or not we can work with a segment base
        """
        main_layer = self.segment
        has_segment = next(
            (
                x
                for x in query_part
                if cast(dict, x).get("unit", {}).get("layer") == self.segment
            ),
            None,
        )
        if has_segment and (
            label := cast(dict, has_segment.get("unit", {})).get("label")
        ):
            return label, main_layer, label
        alt: dict | None = next((s for s in query_part if s.get("unit")), None)
        if alt is not None:
            main_layer = alt["unit"].get("layer")
            main_label = alt["unit"].get("label", main_layer)
        return "", main_layer, main_label

    def _process_sequences(self) -> None:
        """
        A dedicated method to process sequences since it's quite complex
        """
        # TODO

    def process_disjunction(self, members: list) -> list[list[str]]:
        token_table = _get_table(self.token, self.config, self.batch, self.lang or "")
        disjunction_ctes: list[list[str]] = []
        unions: list[str] = []
        for m in _flatten_coord(members, "OR"):
            if not isinstance(m, dict):
                continue
            log_exp = m.get("logicalExpression", {})
            log_op = log_exp.get("naryOperator")
            if "unit" in m:
                uly = m["unit"].get("layer", "")
                ulb = m["unit"].get("label") or self.r.unique_label(
                    "t", layer=self.token
                )
                upo = m["unit"].get("partOf", [])
                joins, conds = self._token(m["unit"], uly, ulb, upo)
                if not conds:
                    continue
                from_built = " CROSS JOIN ".join(["{prev_table}"] + [j for j in joins])
                joins_values: list[set[str]] = [
                    j for j in joins.values() if j and isinstance(j, set)
                ]
                joins_conds: set[str] = set(
                    str(x) for j in joins_values for x in j if str(x).strip()
                )
                conds_built = " AND ".join(conds.union(joins_conds))
                unions.append(
                    f"SELECT {SELECT_PH}, {CARRY_PH}jsonb_build_array({ulb}.{self.token}_id) AS disjunction_matches FROM {from_built} WHERE {conds_built}"
                )
            elif "sequence" in m:
                seq: Sequence = Sequence(QueryData(), self.conf, m)
                sqlseq: SQLSequence = SQLSequence(seq)
                sqlseq.categorize_members()
                assert not sqlseq.ctes, RuntimeError(
                    "Cannot nest a complex sequence inside a disjunction"
                )
                # if sqlseq.get_first_stream_part_of() != seg_lab:
                #     continue
                seq_where: list[str] = []
                fixed_where, fixed_joins = sqlseq.where_fixed_members(set(), self.token)
                if fixed_where:
                    seq_where += fixed_where
                batch_suffix = _get_batch_suffix(self.batch, self.n_batches)
                _, _, simple_where = sqlseq.simple_sequences_table(
                    fixed_part_ts="",
                    from_table="{prev_table}",
                    tok=self.token,
                    batch_suffix=batch_suffix,
                    seg=self.segment,
                    schema=self.schema.lower(),
                )
                if simple_where:
                    seq_where.append(simple_where)
                if not seq_where:
                    continue
                token_labels = [t.internal_label for t, *_ in sqlseq.fixed_tokens]
                seq_from = " CROSS JOIN ".join(
                    ["{prev_table}"]
                    + [f"{self.schema}.{token_table} {tlab}" for tlab in token_labels]
                )
                seq_from = " JOIN ".join([seq_from] + fixed_joins)
                seq_where_built = " AND ".join(seq_where)
                select_matches = ", ".join(
                    [
                        f"{u.internal_label}.{self.token}_id"
                        for u, *_ in sqlseq.fixed_tokens
                    ]
                )
                unions.append(
                    f"SELECT {SELECT_PH}, {CARRY_PH}jsonb_build_array({select_matches}) AS disjunction_matches FROM {seq_from} WHERE {seq_where_built}"
                )
            if log_op != "AND":
                continue
            # AND
            from_nested: list[int] = []  # the index of the nested disjuinction CTEs
            conjunction_where: list[str] = []
            conjunction_cross_joins: list[str] = []
            disj_joins: list[str] = []
            conjunction_selects: list[str] = []
            log_args = log_exp.get("args", [])
            for conj in _flatten_coord(log_args, "AND"):
                if not isinstance(conj, dict):
                    continue
                if conj.get("logicalExpression", {}).get("naryOperator") == "OR":
                    nested_disjuncts = conj.get("logicalExpression", {}).get("args", [])
                    nested_disjunction = self.process_disjunction(nested_disjuncts)
                    from_nested.append(
                        len(disjunction_ctes) + len(nested_disjunction) - 1
                    )
                    disjunction_ctes += nested_disjunction
                    continue
                if "unit" in conj:
                    uly = conj["unit"].get("layer", "")
                    ulb = conj["unit"].get("label") or self.r.unique_label(
                        "t", layer=self.token
                    )
                    upo = conj["unit"].get("partOf", [])
                    joins, conds = self._token(conj["unit"], uly, ulb, upo)
                    if not conds:
                        continue
                    joins_values: list[set[str]] = [
                        j for j in joins.values() if j and isinstance(j, set)
                    ]
                    joins_conds: set[str] = set(
                        str(x) for j in joins_values for x in j if str(x).strip()
                    )
                    conjunction_where += [c for c in conds.union(joins_conds)]
                    conjunction_cross_joins += [j for j in joins]
                    conjunction_selects.append(f"{ulb}.{self.token}_id")
                elif "sequence" in conj:
                    seq: Sequence = Sequence(QueryData(), self.conf, conj)
                    sqlseq: SQLSequence = SQLSequence(seq)
                    sqlseq.categorize_members()
                    # if sqlseq.get_first_stream_part_of() != seg_lab:
                    #     continue
                    seq_where = []
                    fixed_where, fixed_joins = sqlseq.where_fixed_members(
                        set(), self.token
                    )
                    if fixed_where:
                        seq_where += fixed_where
                    batch_suffix = _get_batch_suffix(self.batch, self.n_batches)
                    _, _, simple_where = sqlseq.simple_sequences_table(
                        fixed_part_ts="",
                        from_table="{prev_table}",
                        tok=self.token,
                        batch_suffix=batch_suffix,
                        seg=self.segment,
                        schema=self.schema.lower(),
                    )
                    if simple_where:
                        seq_where.append(simple_where)
                    if not seq_where:
                        continue
                    seq_where_built = " AND ".join(seq_where)
                    conjunction_where.append(seq_where_built)
                    disj_joins += [j for j in fixed_joins]
                    bound_tokens = [
                        t.internal_label
                        for t, *_ in sqlseq.fixed_tokens
                        if t.internal_label not in self.r.label_layer
                        or _bound_label(t.internal_label, self.config)
                    ]
                    conjunction_cross_joins += [
                        f"{self.schema}.{token_table} {tlab}" for tlab in bound_tokens
                    ]
                    conjunction_selects += [
                        f"{u.internal_label}.{self.token}_id"
                        for u, *_ in sqlseq.fixed_tokens
                    ]
            disj_joins += [f"disjunction{n}" + " USING ({using})" for n in from_nested]
            conj_from = " CROSS JOIN ".join(["{prev_table}"] + conjunction_cross_joins)
            conj_from = " JOIN ".join([conj_from] + disj_joins)
            conj_where_built = " AND ".join(conjunction_where)
            conj_selects_built = ", ".join(conjunction_selects)
            conj_matches = " || ".join(
                [f"jsonb_build_array({conj_selects_built})"]
                + [f"disjunction{n}.disjunction_matches" for n in from_nested]
            )
            unions.append(
                f"SELECT {SELECT_PH}, {conj_matches} AS disjunction_matches FROM {conj_from} WHERE {conj_where_built}"
            )
        disjunction_ctes.append(unions)
        return disjunction_ctes

    def lift_quantifiers(self, query_obj: dict | list) -> dict | list:
        ret_obj: dict | list = (
            {} if isinstance(query_obj, dict) else [None for _ in range(len(query_obj))]
        )
        for n, k in enumerate(query_obj):
            v = query_obj[k] if isinstance(query_obj, dict) else k
            i = k if isinstance(query_obj, dict) else n
            if isinstance(v, list):
                ret_obj[i] = self.lift_quantifiers(v)
                continue
            elif not isinstance(v, dict):
                ret_obj[i] = v
                continue
            if "quantification" in v:
                quan_obj = cast(dict[str, Any], v["quantification"])
                quantor = quan_obj.get("quantifier", "")
                if quantor.endswith(("EXISTS", "EXIST")):
                    if quantor.startswith(("~", "!", "NOT", "¬")):
                        quantor = "NOT EXISTS"
                    else:
                        quantor = "EXISTS"
                    key_to_lift = next(
                        (x for x in ("unit", "sequence") if x in quan_obj), None
                    )
                    if key_to_lift:
                        v = {x: y for x, y in quan_obj.items() if x == key_to_lift}
                        v[key_to_lift]["quantor"] = quantor
            ret_obj[i] = self.lift_quantifiers(v)
        return ret_obj

    def query(self, recurse: list | None = None) -> tuple[str, str, str]:
        """
        The main entrypoint: produce query SQL as a single string
        """
        self.selects = self.r.selects
        self.joins = self.r.joins
        self.conditions = self.r.conditions

        # print(
        #    "Debug -- data carried over from query:",
        #    self.r.entities,
        #    self.selects,
        #    self.joins,
        #    self.conditions,
        # )

        query_json: QueryPart = self.query_json["query"]

        if not recurse:
            has_segment, main_layer, main_label = self._make_main(query_json)
            self._has_segment = has_segment
            self.main_layer = main_layer
            self.main_label = main_label

        if recurse is None:
            to_iter = query_json
        else:
            to_iter = recurse

        batch_suffix: str = "rest"
        if self.conf.batch[-1].isnumeric():
            e: enumerate[str] = enumerate(reversed(self.conf.batch))
            first_num: int = next(i for i, c in e if not c.isnumeric())
            batch_suffix = self.conf.batch[-first_num:]
        batch_suffix = self._underlang + batch_suffix

        groups: dict[str, list[str]] = {}

        disjunctions: list[list] = []  # disjunctions of tokens/sequences

        # build the conditions of the objects in the query list
        obj: dict[str, Any]
        for obj in self.lift_quantifiers(to_iter):

            # Turn any logical expression into a main constraint
            if "logicalExpression" in obj:
                obj = {"args": [obj]}

            is_sequence = "sequence" in obj
            is_set = "set" in obj
            is_constraint = "constraint" in obj and recurse is None
            is_group = "group" in obj

            if is_constraint:
                log_exp = obj["constraint"].get("logicalExpression", {})
                log_args = log_exp.get("args", [])
                is_disj = log_exp.get("naryOperator") == "OR"
                none_quantified = not any(
                    "quantor" in x.get("unit", x.get("sequence", {})) for x in log_args
                )
                if is_disj and none_quantified:
                    disjunctions.append(log_args)
                else:
                    self.constraint(obj["constraint"])
                continue

            if is_set:
                continue  # sets are already handled in ResultsMaker and included as part of selects
            elif is_group:
                lab = ""
                group: list[str] = []
                for k, v in obj["group"].items():
                    if k == "label":
                        lab = v
                    if k == "members":
                        group = [x.get("reference", "") for x in v]
                if lab and group:
                    groups[lab] = group
                continue

            if "layer" not in obj.get("unit", {}):
                continue
            obj = obj["unit"]
            layer = cast(str, obj["layer"])
            layer_info = cast(JSONObject, self.config["layer"])
            layer_info = cast(JSONObject, layer_info[layer])
            is_meta: bool = (
                cast(str, layer_info.get("contains", "")).lower()
                == self.segment.lower()
            )
            contains_token: bool = (
                cast(str, layer_info.get("contains", "")).lower() == self.token.lower()
            )
            if obj.get("label"):
                label = cast(str, obj["label"])
            else:
                label = f"anonymous_{layer.lower()}_top_{self._n}"
                self._n += 1
            part_of = cast(list[dict[str, str]], obj.get("partOf", []))
            assert not any(
                next(x for x in p.values()) == label for p in part_of
            ), AttributeError(f"An entity cannot be part of itself ('{label}')")
            low = layer.lower()
            is_segment = low == self.segment.lower()
            is_token = low == self.token.lower()
            is_above_segment = _layer_contains(
                cast(dict[str, Any], self.config), layer, self.segment
            )
            is_document = low == self.document.lower()

            layerlang = f"{layer}{self._underlang}".lower()
            llabel = label.lower()
            if not self._backup_table:  # and (is_document or is_segment or is_token):
                self._backup_table = (layerlang, llabel)

            if is_segment or is_document or is_meta or is_above_segment:
                self.segment_level(obj, label, layer)
                continue
            elif contains_token:
                self.char_range_level(obj, label, layer)
                continue

            elif is_token and not is_sequence and not is_set:
                joins, queries = self._token(obj, layer, label, part_of)
                for k, v in joins.items():
                    self.joins[k] = v
                for q in queries:
                    if q.strip():
                        self.conditions.add(q)

            else:  # E.g. time-anchored layer not containing any sublayer
                self.segment_level(obj, label, layer)
                continue

        # Discard any select on a bound label so far
        self.selects = {
            s
            for s in self.selects
            if not _bound_label(self._get_label_as(s), self.query_json)
        }

        # Multiple steps: first SELECT in the fixed_parts table
        selects_in_fixed: set[str] = {s for s in self.selects}
        # Last select potentially *from* the fixed_parts table
        self.selects = {
            f"___lasttable___.{self._get_label_as(s)} as {self._get_label_as(s)}"
            for s in self.selects
        }

        # If sequences require further CTEs, this will be updated
        last_table: str = "fixed_parts"

        # Add any fixed token needed for sequences
        sequence_ranges: dict[str, tuple[str, str, str]] = dict()
        entities: dict[str, list] = {
            self._get_label_as(s).split(".")[-1]: [] for s in self.selects
        }
        entities_set: set = {e for e in entities}
        tok: str = self.token.lower()
        seg_str: str = self.segment.lower()
        for s in self.sqlsequences:
            for t, _, _, _ in s.fixed_tokens:
                lab = t.internal_label
                selects_in_fixed.add(f"{lab}.{tok}_id as {lab}")
                original_label: str = t.obj["unit"].get("label", "")
                if original_label:
                    self.selects.add(f"___lasttable___.{lab} as {original_label}")
                    self.r.entities.add(original_label)
                table: str = tok + batch_suffix
                formed_join: str = f"{self.schema}.{table} {lab}".lower()
                self.joins[formed_join] = self.joins.get(formed_join, None)
            swhere, sleft_joins = s.where_fixed_members(entities_set, tok)

            for w in swhere:
                self.conditions.add(w)
            for lj in sleft_joins:
                join_table, join_conds = lj.split(" ON ")
                self.joins[join_table] = True
                self.conditions.add(join_conds)

            simple_seq, new_labels, simple_where = s.simple_sequences_table(
                fixed_part_ts=",\n".join(
                    [
                        f"{last_table}.{self._get_label_as(s)} AS {self._get_label_as(s)}"
                        for s in sorted(selects_in_fixed)
                    ]
                ),
                from_table=last_table,
                tok=tok,
                batch_suffix=batch_suffix,
                seg=seg_str,
                schema=self.schema.lower(),
            )
            self.conditions.add(simple_where)

            # If this sequence has a user-provided label, select the tokens it contains
            if not s.sequence.anonymous:
                min_ref: str = ""
                max_ref: str = ""
                if s.ctes:
                    # If the first CTE comes first in the sequence, start_id is the main sequence's min token_id
                    if not s.ctes[0].prev_fixed_token:
                        min_ref = f"___lasttable___.start_id"
                    # If the last CTE comes last in the sequence, id is the main sequence's max token_id
                    if not s.ctes[-1].next_fixed_token:
                        max_ref = f"___lasttable___.id"
                if not min_ref:
                    min_ref = f"___lasttable___.{next(t.internal_label for t,_,_,_ in s.fixed_tokens)}"
                if not max_ref:
                    max_ref = f"___lasttable___.{next(t.internal_label for t,_,_,_ in reversed(s.fixed_tokens))}"

                min_label: str = self.r.unique_label(f"min_{s.sequence.label}")
                max_label: str = self.r.unique_label(f"max_{s.sequence.label}")

                s_part_of = s.get_first_stream_part_of()
                sequence_ranges[s.sequence.label] = (
                    f"{min_ref} as {min_label}",
                    f"{max_ref} as {max_label}",
                    s_part_of,
                )

        # Go through all the segments and pick the most constrained one
        # and set the suffixes for the segment tables
        seg_suffixes: dict[str, str] = {}
        n_segment_constraints_max = 0
        n_sequence_length_max = 0
        for lb, (lay, info) in self.r.label_layer.items():
            if lay != self.segment:
                continue
            # Use the full segment table by default, see below for restrictions to current batch
            seg_suffixes[lb] = "0"
            n_segment_constraints = len(info.get("constraints", {}))
            n_sequence_length: int = next(
                (
                    s.sequence.min_length
                    for s in self.sqlsequences
                    if s.get_first_stream_part_of() == lb
                ),
                0,
            )
            if self._table and n_sequence_length < n_sequence_length_max:
                continue
            elif self._table and n_segment_constraints < n_segment_constraints_max:
                continue
            self._table = (
                _get_table(lay, self.config, self.batch, self.lang or ""),
                lb,
            )
            n_segment_constraints_max = n_segment_constraints
            n_sequence_length_max = n_sequence_length
        # Use the current batch suffix for the main / first segment table
        current_batch_suffix: str = _get_batch_suffix(self.batch, self.n_batches)
        if (
            self._table
            and self.r.label_layer[self._table[1]][0].lower() == self.segment.lower()
        ):
            seg_suffixes[self._table[1]] = current_batch_suffix
        elif seg_suffixes:
            seg_suffixes[next(k for k in seg_suffixes.keys())] = current_batch_suffix

        table, label = self.remove_and_get_base(disjunctions)
        from_table = table

        # we remove the selects that are not needed
        selects_in_fixed = {
            i.replace("___seglabel___", label) for i in selects_in_fixed
        }
        self.selects = {
            i.replace("___seglabel___", label)
            for i in self.selects
            if "___seglabel___" in i.lower()
            or any(
                x.endswith(i.lower().split()[-1]) for x in [*self.r.entities, label]
            )  # Keep segment label in case it's needed later on
            or not self.r.entities
        }

        # TODO: report tokens' part_of in their label_layer, then replace token<batch> accordingly
        formed_joins = _joinstring(self.joins)
        if seg_suffixes:
            seg_full_table = f"{self.schema}.{_get_table(self.segment.lower(), self.config, self.batch, self.lang or '')}"
            seg_table_no_schema = (
                _get_mapping(self.segment, self.config, self.batch, self.lang or "")
                .get("relation", self.segment)
                .lower()
            )
            seg_table = f"{self.schema}.{seg_table_no_schema}"
            formed_joins = re.sub(
                rf"CROSS JOIN {seg_full_table} (\S+)",
                lambda x: f"CROSS JOIN {seg_table.removesuffix('<batch>')}{seg_suffixes.get(x[1], current_batch_suffix)} {x[1]}",
                formed_joins,
            )
        join_conditions: set[str] = set()
        for v in self.joins.values():
            if not v:
                continue
            if isinstance(v, str):
                join_conditions.add(v)
            elif isinstance(v, set):
                join_conditions = join_conditions.union(
                    {c for c in v if c and isinstance(c, str)}
                )
        union_conditions: set[str] = join_conditions.union(self.conditions)
        formed_conditions = "\nAND ".join(
            x for x in sorted(union_conditions) if x.strip()
        )
        formed_where = "" if not formed_conditions.strip() else "WHERE"
        formed_conditions = formed_conditions.format(_base_label=label)
        # todo: add group bt and having sections
        group_by = self._get_groupby()
        havings = self._get_havings()

        additional_ctes: str = ""

        unbound_labels: dict[str, str] = {
            lab: lay
            for lab, (lay, _) in self.r.label_layer.items()
            if not _bound_label(lab, self.query_json)
        }
        built_disjunctions = []
        for disjunction in disjunctions:
            disj_ctes: list[str] = [
                " UNION ALL ".join(union_cte)
                for union_cte in self.process_disjunction(disjunction)
            ]
            # Make sure we select what's necessary from fixed_parts
            for n in range(len(disj_ctes)):
                union_cte = disj_ctes[n]
                for lab, lay in unbound_labels.items():
                    found_lab = re.search(rf"\b{lab}\b", union_cte)
                    if not found_lab:
                        continue
                    sel_lab = f"___lasttable___.{lab} AS {lab}".lower()
                    self.selects.add(sel_lab)
                    sel_lab_in_fixed = f"{lab}.{lay}_id AS {lab}".lower()
                    selects_in_fixed.add(sel_lab_in_fixed)
                    union_cte = re.sub(
                        rf"\b{lab}\.{lay}_id", lab, union_cte, flags=re.IGNORECASE
                    )
                    for labref in re.findall(rf"\b{lab}\.[_.a-zA-Z0-9]+", union_cte):
                        # if labref.endswith("_id"):
                        #     continue
                        aname = labref.split(".")[-1]
                        ref_sel_lab = (
                            f"___lasttable___.{lab}_{aname} AS {lab}_{aname}".lower()
                        )
                        self.selects.add(ref_sel_lab)
                        ref_sel_lab_in_fixed = f"{lab}.{aname} AS {lab}_{aname}".lower()
                        selects_in_fixed.add(ref_sel_lab_in_fixed)
                        union_cte = re.sub(
                            rf"\b{labref}\b",
                            f"{lab}_{aname}",
                            union_cte,
                            flags=re.IGNORECASE,
                        )
                        disj_ctes[n] = union_cte
                    disj_ctes[n] = union_cte
            built_disjunctions.append(disj_ctes)

        disjunction_ctes: list[str] = []
        n_disj_cte = 0
        table_suffix: str = (
            self._table[1] if self._table else next(s for s in seg_suffixes)
        )
        using: list[str] = [table_suffix]
        for anchor in ("char_range", "frame_range", "xy_box"):
            if not any(
                sel.lower().endswith(f"as {table_suffix}_{anchor}".lower())
                for sel in selects_in_fixed
            ):
                continue
            using.append(f"{table_suffix}_{anchor}")
        for n_main_disj, disj_ctes in enumerate(built_disjunctions):
            for disj_cte in disj_ctes:
                cte_prev_table = (
                    "fixed_parts" if n_main_disj == 0 else f"disjunction{n_disj_cte-1}"
                )
                cte_selects = ", ".join(
                    s.replace("___lasttable___", cte_prev_table) for s in self.selects
                )
                carry_over: str = (
                    ""
                    if n_main_disj == 0
                    else f"{cte_prev_table}.disjunction_matches || "
                )
                disj_cte_str = disj_cte.format(
                    prev_table=cte_prev_table,
                    selects=cte_selects,
                    carry_over=carry_over,
                    using=", ".join(using),
                )
                disjunction_ctes.append(disj_cte_str)
                additional_ctes += f"disjunction{n_disj_cte} AS ({disj_cte_str}),"
                n_disj_cte += 1
        if built_disjunctions:
            last_table = f"disjunction{n_disj_cte-1}"
            self.selects.add(
                "___lasttable___.disjunction_matches AS disjunction_matches"
            )

        # CTEs: use the traversal strategy
        last_cte: Cte | None = None
        n_cte: int = 0
        for s in self.sqlsequences:
            if not s.ctes:
                continue
            for n, cte in enumerate(s.ctes):
                n_cte += cte.n
                cte.n += n_cte
                state_prev_cte: list[int] = [0]
                if isinstance(last_cte, Cte) and n > 0:
                    state_prev_cte = last_cte.get_final_states()
                transition_table: str = cte.transition()
                additional_selects = [
                    self._get_label_as(slc)
                    for slc in self.selects
                    if self._get_label_as(slc) != s.get_first_stream_part_of()
                ]
                traversal_table: str = cte.traversal(
                    from_table=last_table,
                    state_prev_cte=state_prev_cte,
                    schema=self.schema.lower(),
                    tok=self.token.lower(),
                    batch_suffix=batch_suffix,
                    seg=self.segment.lower(),
                    additional_selects=additional_selects,
                )
                additional_ctes += f"""{transition_table}
                ,
                {traversal_table}
                ,"""
                last_cte = cte
                last_table = f"traversal{cte.n}"

        # If any sequence has a label and needs its range to be returned
        if sequence_ranges:

            # selects_intermediate = {self._get_label_as(s) for s in selects_in_fixed}
            selects_intermediate = {self._get_label_as(s) for s in self.selects}
            gather_selects: str = ",\n".join(
                # sorted({s.replace("___lasttable___", last_table) for s in self.selects})
                sorted(
                    {
                        s.replace("___lasttable___", last_table)
                        for s in selects_intermediate
                    }
                )
            )
            for seqlab, (min_seq, max_seq, seg_lab) in sequence_ranges.items():
                if self.r.entities and seqlab not in self.r.entities:
                    continue
                gather_selects += f",\n{min_seq.replace('___lasttable___', last_table)}"
                gather_selects += f",\n{max_seq.replace('___lasttable___', last_table)}"
                min_label = min_seq.split(" as ")[-1]
                max_label = max_seq.split(" as ")[-1]
                jttable = self.r.unique_label("t", layer=self.token)
                infrom: str = f"{self.conf.schema}.{tok}{batch_suffix} {jttable}"
                inwhere: str = (
                    f"{jttable}.{self.segment.lower()}_id = gather.{seg_lab} AND {jttable}.{tok}_id BETWEEN gather.{min_label}::bigint AND gather.{max_label}::bigint"
                )
                self.selects.add(
                    f"ARRAY(SELECT {jttable}.{tok}_id FROM {infrom} WHERE {inwhere}) AS {seqlab}"
                )

            additional_from: str = last_table
            if last_cte:
                # make sure to reach the last state of the last CTE!
                additional_from = last_cte.get_gather_in(last_table)

            additional_ctes += f"""gather AS (
                SELECT {gather_selects}
                FROM {additional_from}
            )
            ,"""
            last_table = "gather"

        # If there's no sequence range to return, there's no gather table, but we still need to put a constraint on the last state
        elif last_cte:
            last_table = last_cte.get_gather_in(last_table)

        for g, refs in groups.items():
            str_refs: str = ",".join(refs)
            self.selects.add(f"jsonb_build_array({str_refs}) as {g}")

        # Do not select ambiguous references (e.g. because of repeated sequences)
        match_selects: str = ",\n".join(
            sorted(
                {
                    s.replace("___lasttable___", last_table)
                    for s in self.selects
                    if not any(
                        s.split(" as ")[-1] == self._get_label_as(x)
                        for x in self.selects
                        if x != s
                    )
                    and not _bound_label(self._get_label_as(s), self.query_json)
                }
            )
        )

        formed_selects = ",\n".join(sorted(selects_in_fixed))

        out = self.template.format(
            schema=self.conf.schema,
            batch=self.conf.batch,
            table=table,
            from_table=from_table,
            label=label,
            group_by=group_by,
            havings=havings,
            conditions=formed_conditions,
            needed_where=formed_where,
            selects=formed_selects,
            joins=formed_joins,
            # left_joins=formed_left_joins,
            additional_ctes=additional_ctes,
            match_selects=match_selects,
            match_from=last_table,
        )
        return out, label, label

    def _get_groupby(self) -> str:
        """
        Making grouppby right at the end.
        We have self.group_by which we couldd potentially fill
        during query() and then join it or whatever in here
        """
        return ""

    def _get_havings(self) -> str:
        """
        Make having at end of query making
        """
        return ""

    def process_set(self, set_data: dict) -> None:
        res: str = process_set(
            self.conf,
            self.r,
            self._n,
            self.token,
            self.segment,
            self._underlang,
            set_data,
            seg_label=self._get_seg_label(),
            attribute="token",
        )
        if res:
            self.r.selects.add(res)
        return None

    def _get_seg_label(self) -> str:
        if self.has_fts and self._table:
            return self._table[1]
        ll = self.r.label_layer
        assert ll
        return next((k for k, v in ll.items() if v[0] == self.segment), "")

    def disjunction_prefilters(
        self, members: list = [], seg_lab: str = "", op: str = "OR"
    ) -> str:
        ret: str = ""
        for m in members:
            if "unit" in m:
                if not any(seg_lab in x.values() for x in m["unit"].get("partOf", [])):
                    continue
                s: dict = {"sequence": {"members": [m]}}
                unit_pref = Prefilter([s], self.conf, dict(), "")._condition()
                if not unit_pref:
                    continue
                ret = unit_pref if not ret else ret + f" {op} ({unit_pref})"
            elif "sequence" in m:
                seq: Sequence = Sequence(QueryData(), self.conf, m)
                sqlseq: SQLSequence = SQLSequence(seq)
                if sqlseq.get_first_stream_part_of() != seg_lab:
                    continue
                seq_prefs = " AND ".join(sqlseq.prefilters())
                if not seq_prefs:
                    continue
                ret = seq_prefs if not ret else ret + f" {op} ({seq_prefs})"
            elif "logicalExpression" in m:
                log_op = m["logicalExpression"].get("naryOperator")
                log_ar = m["logicalExpression"].get("args", [])
                coord_prefs = self.disjunction_prefilters(log_ar, seg_lab, log_op)
                if not coord_prefs:
                    continue
                ret = coord_prefs if not ret else ret + f" {op} ({coord_prefs})"
        return ret

    def remove_and_get_base(self, disjunctions: list = []) -> tuple[str, str]:
        """
        If we made a join that is equal to the FROM clause, we remove it
        """
        table = ""
        label = ""
        if self._table:
            table, label = self._table
        elif self._backup_table:
            table, label = self._backup_table

        schema_prefix: str = f"{self.schema}."
        base: str = f"{schema_prefix}{table} {label}".lower()
        prefilters: set[str] = {
            p
            for s in self.sqlsequences
            for p in s.prefilters()
            if s.get_first_stream_part_of() == label and p.strip()
        }
        for disjunction in disjunctions:
            prefilters.add(f"({self.disjunction_prefilters(disjunction, label)})")
        if self.has_fts and prefilters:
            batch_suffix = _get_batch_suffix(self.batch, self.n_batches)
            vector_name = f"fts_vector{self._underlang}{batch_suffix}"  # Need better handling of this: add to mapping?
            ps: str = " AND ".join(prefilters)
            new_label = f"fts_vector_{label}"
            old_base_joins: None | bool | list | set = self.joins.get(base, [])
            new_joins: set[str | bool] = set()
            if isinstance(old_base_joins, list) or isinstance(old_base_joins, set):
                new_joins = {x for x in old_base_joins}
            elif isinstance(old_base_joins, bool):
                new_joins = {old_base_joins}
            new_joins.add(
                f"{new_label}.{self.segment}_id = {label}.{self.segment}_id".lower()
            )
            self.joins[base] = new_joins
            table = f"(SELECT {self.config['segment']}_id FROM {self.conf.schema}.{vector_name} vec WHERE {ps})"
            schema_prefix = ""
            label = new_label
        else:
            conds = self.joins.pop(base, None)
            if conds and (isinstance(conds, list) or isinstance(conds, set)):
                for c in conds:
                    self.conditions.add(c)

        return f"{schema_prefix}{table} AS {label}", label

    def constraint(self, obj: dict[str, Any]) -> None:
        """
        Handle top-level constraints only
        """
        conn_obj = _get_constraints(
            cast(JSONObject, [obj]),
            "",
            "",
            self.conf,
            label_layer=self.r.label_layer,
            entities=self.r.entities,
            set_objects=self.r.set_objects,
            n=self._n,
            top_level=True,
        )
        if conn_obj:
            self._n = conn_obj._n + 1
            joins = conn_obj.joins() if conn_obj else {}
            for k, v in joins.items():
                self.joins[k] = v
            cond = conn_obj.conditions() if conn_obj else ""
            if cond:
                self.conditions.add(cond)

    def char_range_level(self, obj: JSONObject, label: str, layer: str) -> None:
        """
        Process an object in the query larger than token unit that directly contains tokens
        """
        if not obj.get("partOf", None):
            return None
        is_negative = obj.get("quantor", "") == "NOT EXISTS"
        if not is_negative:
            select = f"{label}.{layer}_id as {label}"
            self.selects.add(select.lower())
        join: str = f"{self.schema}.{layer}{self._underlang} {label}".lower()
        if join not in self.joins:
            self.joins[join] = None

        constraints = cast(JSONObject, obj.get("constraints", {}))
        conn_obj: Constraints | None = _get_constraints(
            constraints,
            layer,
            label,
            self.conf,
            quantor=cast(str | None, obj.get("quantor", None)),
            label_layer=self.r.label_layer,
            entities=self.r.entities,
            part_of=cast(list[dict[str, str]], obj.get("partOf", [])),
            set_objects=self.r.set_objects,
            n=self._n,
        )
        if conn_obj:
            self._n = conn_obj._n + 1
            joins = conn_obj.joins() if conn_obj else {}
            for k, v in joins.items():
                self.joins[k] = v
            cond = conn_obj.conditions() if conn_obj else ""
            if cond:
                self.conditions.add(cond)

        return None

    def segment_level(self, obj: JSONObject, label: str, layer: str) -> None:
        """
        Process an object in the query larger than token unit
        """
        layer_info = cast(JSONObject, self.config["layer"])
        layer_info = cast(JSONObject, layer_info[layer])
        contains = cast(str, layer_info.get("contains", ""))
        is_meta = bool(contains) and contains != self.token
        is_negative = obj.get("quantor", "") == "NOT EXISTS"
        if not is_meta and not is_negative:
            idx = "_id" if not is_meta else ""
            select = f"{label}.{layer}{idx} as {label}"
            self.selects.add(select.lower())

        table = f"{layer}{self._underlang}"
        if layer.lower() == self.segment.lower():
            table += _get_batch_suffix(self.batch, n_batches=self.n_batches)

        join = f"{self.schema}.{table} {label}".lower()
        if join != self._base and not is_negative:
            self.joins[join] = None
        # if is_meta:
        #     self.handle_meta(label, layer, contains)
        constraints = cast(JSONObject, obj.get("constraints", {}))
        part_of: list[dict[str, str]] = cast(
            list[dict[str, str]], obj.get("partOf", [])
        )
        conn_obj: Constraints | None
        if constraints or part_of:
            conn_obj = _get_constraints(
                constraints,
                layer,
                label,
                self.conf,
                quantor=cast(str | None, obj.get("quantor", None)),
                label_layer=self.r.label_layer,
                entities=self.r.entities,
                part_of=part_of,
                set_objects=self.r.set_objects,
                n=self._n,
            )
            if conn_obj and is_negative:
                self.conditions.add(conn_obj._build_subquery(conn_obj))
            elif conn_obj:
                self._n = conn_obj._n + 1
                joins = conn_obj.joins() if conn_obj else {}
                for k, v in joins.items():
                    self.joins[k] = v
                cond = conn_obj.conditions() if conn_obj else ""
                if cond:
                    self.conditions.add(cond)
        return None

    def handle_meta(self, label: str, layer: str, contains: str) -> None:
        """
        Add conditions relating to metadata queries, above segment level
        """
        seg = self.segment
        segname: str | None
        if (
            contains
            and contains not in {self.token}
            and layer.lower() != "gesture"
            and layer != seg
            and layer != self.document
        ):
            formed = f"{self.conf.schema}.turn_alignment"
            self.joins[formed.lower()] = None
            formed = f"turn_alignment.alignment_id = {label}.alignment_id"
            self.conditions.add(formed.lower())
        ll = self.r.label_layer
        assert ll
        # if self.has_fts:
        #     lab = self._seg_has_char_range()
        #     segname = lab
        # else:
        segname = next((k for k, v in ll.items() if v[0] == seg), None)
        if not segname:
            print("Problem finding segment label -- ignoring ...")
        else:
            formed = f"{label}.char_range && {segname}.char_range"
            self.conditions.add(formed.lower())
        return None

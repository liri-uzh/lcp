import re

from typing import Any, cast

from .constraint import Constraints, _get_constraints, process_set
from .sequence import Cte, SQLSequence
from .typed import JSONObject, Joins, LabelLayer, QueryJSON, QueryPart
from .utils import (
    Config,
    QueryData,
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


class Token:
    def __init__(
        self,
        layer: str,
        part_of: str,
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
        # part_of is now part of get_constraints itself
        # elif self.part_of:
        #     seg = self.segment.lower()
        #     formed: str
        #     if self.label_layer.get(self.part_of, ("",None))[0].lower() == seg:
        #         formed = f"{self.part_of}.{seg}_id = {self.label}.{seg}_id"
        #     else:
        #         formed = f"{self.part_of}.char_range && {self.label}.char_range"
        #     out.add(formed)
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
        _part_of: str,
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
        # part_of = self._get_part_of(cast(str, obj.get("partOf", _part_of)))
        part_of = cast(str, obj.get("partOf", _part_of))
        constraints = cast(JSONObject, obj.get("constraints", []))
        # if self.r.entities and label not in self.r.entities:
        #    return {}, set()
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

    def _get_part_of(self, part_of: str) -> str:
        """
        Return the layer name for the part_of label
        """
        layer: str = self.r.label_layer.get(part_of, ("", None))[0]
        if not self.has_fts:
            return layer
        if layer == self.segment:
            assert self._table is not None
            return self._table[1]
        return layer

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

        obj: dict[str, Any]

        for obj in to_iter:
            # Lift any argument of a quantifier to obj
            if qkey := next((x for x in obj if x.endswith("Quantification")), None):
                quan_obj = cast(dict[str, Any], obj[qkey])
                assert "args" in quan_obj, SyntaxError(
                    "Could not find 'args' in quantifier"
                )
                quantor = quan_obj.get("quantor", "")
                if quantor.endswith(("EXISTS", "EXIST")):
                    if quantor.startswith(("~", "!", "NOT", "¬")):
                        quantor = "NOT EXISTS"
                    else:
                        quantor = "EXISTS"
                    obj = next(a for a in quan_obj["args"])
                    obj["unit"]["quantor"] = quantor

            # Turn any logical expression into a main constraint
            if any(x == "logicalExpression" for x in obj):
                obj = {"args": [obj]}

            is_sequence = "sequence" in obj
            is_set = "set" in obj
            is_constraint = "args" in obj and recurse is None
            is_group = "group" in obj

            if is_constraint:
                self.constraint(obj)
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
            part_of = cast(str, obj.get("partOf", ""))
            assert part_of != label, AttributeError(
                f"An entity cannot be part of itself ('{label}')"
            )
            low = layer.lower()
            is_segment = low == self.segment.lower()
            is_token = low == self.token.lower()
            is_above_segment = _layer_contains(
                cast(dict[str, Any], self.config), layer, self.segment
            )
            is_document = low == self.document.lower()

            layerlang = f"{layer}{self._underlang}".lower()
            llabel = label.lower()
            if not self._backup_table and (is_document or is_segment or is_token):
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

            # If this sequence has a user-provided label, select the tokens it contains
            if not s.sequence.anonymous:
                min: str = (
                    f"___lasttable___.{next(t.internal_label for t,_,_,_ in s.fixed_tokens)}"
                )
                max: str = (
                    f"___lasttable___.{next(t.internal_label for t,_,_,_ in reversed(s.fixed_tokens))}"
                )
                if s.ctes:
                    # If the first CTE comes first in the sequence, start_id is the main sequence's min token_id
                    if not s.ctes[0].prev_fixed_token:
                        min = f"___lasttable___.start_id"
                    # If the last CTE comes last in the sequence, id is the main sequence's max token_id
                    if not s.ctes[-1].next_fixed_token:
                        max = f"___lasttable___.id"

                min_label: str = self.r.unique_label(f"min_{s.sequence.label}")
                max_label: str = self.r.unique_label(f"max_{s.sequence.label}")

                sequence_ranges[s.sequence.label] = (
                    f"{min} as {min_label}",
                    f"{max} as {max_label}",
                    s.part_of,
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
                (s.sequence.min_length for s in self.sqlsequences if s.part_of == lb), 0
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

        table, label = self.remove_and_get_base()
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
        formed_conditions = "\nAND ".join(sorted(union_conditions))
        formed_where = "" if not formed_conditions.strip() else "WHERE"
        formed_conditions = formed_conditions.format(_base_label=label)
        # todo: add group bt and having sections
        group_by = self._get_groupby()
        havings = self._get_havings()

        additional_ctes: str = ""

        # Simple subsequences: create subseq tables that check the series of tokens between two fixed tokens
        for n, s in enumerate(self.sqlsequences):
            simple_seq, new_labels = s.simple_sequences_table(
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
            for new_label in new_labels:
                selects_in_fixed.add(new_label)
            if simple_seq:
                # Update last_table
                last_table = f"subseq{n}"
                additional_ctes += f"""{last_table} AS (
                    {simple_seq}
                )
                ,"""
                # Subsequences do not introduce any selectable entity, so we're find reusing selects_in_fixed for now

        # Simple subsequences: create subseq tables that check the series of tokens between two fixed tokens
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
                traversal_table: str = cte.traversal(
                    from_table=last_table,
                    state_prev_cte=state_prev_cte,
                    schema=self.schema.lower(),
                    tok=self.token.lower(),
                    batch_suffix=batch_suffix,
                    seg=self.segment.lower(),
                )
                additional_ctes += f"""{transition_table}
                ,
                {traversal_table}
                ,"""
                last_cte = cte
                last_table = f"traversal{cte.n}"

        # If any sequence has a label and needs its range to be returned
        if sequence_ranges:

            selects_intermediate = {self._get_label_as(s) for s in selects_in_fixed}
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
                orderby: str = "" if last_cte.no_transition else f" ORDER BY ordercol"
                final_states: str = ",".join(
                    [str(x) for x in last_cte.get_final_states()]
                )
                additional_from = f"(SELECT * FROM {last_table} WHERE {last_table}.state IN ({final_states}){orderby}) {last_table}"

            additional_ctes += f"""gather AS (
                SELECT {gather_selects}
                FROM {additional_from}
            )
            ,"""
            last_table = "gather"

        # If there's no sequence range to return, there's no gather table, but we still need to put a constraint on the last state
        elif last_cte:
            # make sure to reach the last state of the last CTE!
            orderby = "" if last_cte.no_transition else f" ORDER BY ordercol"
            final_states = ",".join([str(x) for x in last_cte.get_final_states()])
            last_table = f"(SELECT * FROM {last_table} WHERE {last_table}.state IN ({final_states}){orderby}) {last_table}"

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

    def remove_and_get_base(self) -> tuple[str, str]:
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
            p for s in self.sqlsequences for p in s.prefilters() if s.part_of == label
        }
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
            obj["args"],
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
        part_of_label: str = cast(str, obj.get("partOf", ""))
        part_of_layer: str = self.r.label_layer.get(part_of_label, ("", None))[0]
        if not part_of_layer:
            return None
        is_negative = obj.get("quantor", "") == "NOT EXISTS"
        if not is_negative:
            select = f"{label}.{layer}_id as {label}"
            self.selects.add(select.lower())
        lab: str = part_of_label
        # if part_of_layer.lower() == self.segment.lower() and self.has_fts:
        #     lab = self._seg_has_char_range()
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
            part_of=lab,
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
        part_of: str = cast(str, obj.get("partOf", ""))
        # part_of_layer = self.r.label_layer.get(part_of, ("", ""))[0]
        # if self.has_fts:
        #     if part_of_layer.lower() == self.segment.lower():
        #         part_of = self._seg_has_char_range()
        #     elif (
        #         layer.lower() == self.segment.lower()
        #         and self._table  # Only use has_char_range if constraint on main segment table (could be another segment)
        #         and label == self._table[1]
        #     ):
        #         label = self._seg_has_char_range()
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

import re

from typing import Any, cast
from uuid import UUID

from .typed import JSONObject, Joins, LabelLayer, QueryType, RefInfo
from .utils import (
    Config,
    _get_underlang,
    _get_mapping,
    _get_table,
    arg_sort_key,
    QueryData,
    _joinstring,
    _is_anchored,
    _layer_contains,
)

from typing import Self

# for (NOT) EXISTS parts of queries
QUANTOR_TEMPLATE = """
{quantor} (SELECT 1 FROM {schema}.{base} {label}
             {joins}
             {conditions}
           )
"""

# callables allowed in dqd
FUNCS = (
    "length",
    "century",
    "decade",
    "year",
    "month",
    "day",
    "position",
    "range",
    "start",
    "end",
)


def _valid_uuid(val: Any) -> bool:
    try:
        UUID(str(val))
        return True
    except ValueError:
        return False


class Constraints:
    def __init__(
        self,
        schema: str,
        layer: str,
        label: str,
        config: Config,
        members: Any,
        conj: str = "AND",
        quantor: str | None = None,
        label_layer: LabelLayer | None = None,
        entities: set[str] | None = None,
        part_of: str | None = None,
        n: int = 1,
        is_set: bool = False,
        set_objects: set[str] | None = None,
        allow_any: bool = True,  # False,
        references: dict[str, list[str]] = {},  # dict of labels + attributes
    ) -> None:
        """
        Model constraints recursively as cross joins and WHERE clauses
        """
        self.schema = schema.lower()
        self.layer = layer
        self.label = label
        self.config = config
        self.quantor = quantor
        self.conj = conj
        self.members = members
        self._is_set = is_set
        self.entities: set[str] | None = entities
        self.part_of: str | None = part_of
        self._n: int = n or 0
        self.label_layer = label_layer
        self.set_objects = set_objects
        self.quantor_template = QUANTOR_TEMPLATE
        self._quantor_label: str | None = None
        self._allow_any: bool = allow_any
        self.references: dict[str, list[str]] = (
            references  # dict of labels + attributes
        )

    def make(self):
        """
        Recursively build all constraints in the tree

        We split instantiating and building so we can apply a patch, the quantor label
        """
        for i in self.members:
            if self._quantor_label:
                i._quantor_label = self._quantor_label
            i.make()

    def __str__(self) -> str:
        return f"Constraints: {len(self.members)} / {self._quantor_label}"

    def _inner_labels(self) -> set[str]:
        inner_labels: set[str] = {self.label}
        for m in self.members:
            if isinstance(m, Constraints):
                inner_labels = inner_labels.union(m._inner_labels())
            else:
                inner_labels.add(m.label)
        return inner_labels

    def _build_subquery(self, member: Self) -> str:
        """
        Helper for quantors
        """
        base = _get_table(
            member.layer,
            self.config.config,
            self.config.batch,
            cast(str, self.config.lang),
        )
        member._quantor_label = self.label
        if isinstance(member, Constraints):
            for m in member.members:
                m._quantor_label = self.label
        member.make()
        not_allowed = f"{self.schema}.{base}".lower()
        joins: Joins = member.joins()
        label_layer = cast(LabelLayer, self.label_layer or dict())
        inner_labels: set[str] = self._inner_labels()
        outer_labels: set[str] = {l for l in label_layer if l not in inner_labels}
        crossjoins = "\n".join(
            f"CROSS JOIN {x}"
            for x in joins
            if not_allowed not in x.lower() and x.split(" ")[-1] not in outer_labels
        )
        conds = member.conditions()
        all_conds = [conds]
        for jcs in joins.values():
            if not isinstance(jcs, set) or not jcs:
                continue
            str_conds = [j for j in jcs if j and isinstance(j, str)]
            if not str_conds:
                continue
            all_conds.append(f"({' AND '.join(str_conds)})")
        conds = "WHERE " + " AND ".join(all_conds)
        template = self.quantor_template.format(
            schema=self.schema,
            base=base,
            quantor=member.quantor,
            label=member.label,
            joins=crossjoins,
            conditions=conds,
        )
        return template

    def conditions(self) -> str:
        """
        Build a single condition string from all constraints recursively
        """
        formed_out: str = self.part_of or ""
        out: dict[str, None] = {}
        for member in self.members:
            if isinstance(member, Constraints) and member.quantor:
                res = self._build_subquery(cast(Self, member))
                if res.strip():
                    out[res] = None
            elif isinstance(member, Constraints) and not member.quantor:
                member.make()
                cons = member.conditions()
                if cons.strip():
                    out[cons] = None
            elif isinstance(member, Constraint):
                # do we need a sublevel here?
                member.make()
                # Constraint instances necessarily connect their conditions with AND
                stripped_conditions = [c for c in member._conditions if c.strip()]
                conjunction = " AND ".join(stripped_conditions)
                if len(stripped_conditions) > 1 and self.conj.upper() != "AND":
                    out[f"({conjunction})"] = None
                elif stripped_conditions:
                    out[conjunction] = None
        if not out:
            return formed_out
        formed_conj: str
        if len(out) == 1:
            formed_conj = list(out)[0]
            if self.conj == "NOT":
                formed_conj = "NOT " + formed_conj
        else:
            formed_conj = "(" + f" {self.conj.upper()} ".join(out) + ")"
        formed_out = f"{formed_out} AND {formed_conj}" if formed_out else formed_conj
        return formed_out

    def joins(self) -> Joins:
        """
        Produce an ordered set of joins needed for this group of constraints

        We use dict keys, with all values as None, as the ordered set
        """
        out: Joins = {}
        for member in self.members:
            if isinstance(member, Constraints) and member.quantor:
                pass
            elif isinstance(member, Constraints) and not member.quantor:
                member.make()
                # todo: does this need nesting?
                for k, v in member.joins().items():
                    if not k.strip():
                        continue
                    if (
                        k in out
                        and v
                        and isinstance(out[k], set)
                        and isinstance(v, set)
                    ):
                        out[k] = cast(set, out[k]).union(v)
                    else:
                        out[k] = v
            elif isinstance(member, Constraint):
                member.make()
                for k, v in member._joins.items():
                    if not k.strip():
                        continue
                    if (
                        k in out
                        and v
                        and isinstance(out[k], set)
                        and isinstance(v, set)
                    ):
                        out[k] = cast(set, out[k]).union(v)
                    else:
                        out[k] = v
        return out


class Constraint:
    def __init__(
        self,
        left: dict[str, Any],
        op: str,
        right: dict[str, Any],
        label: str,
        layer: str,
        conf: Config,
        quantor: str | None = None,
        label_layer: dict | None = None,
        entities: set[str] | None = None,
        n: int = 1,
        is_set: bool = False,
        set_objects: set[str] | None = None,
        order: int | None = None,
        prev_label: str | None = None,
        allow_any: bool = True,  # False,
    ) -> None:
        """
        Model a single simple constraint, like form='word''
        """
        self.left = left
        self.right = right
        self.op = op
        self._layer_info = self._get_layer_info(conf, layer)
        self._attribs = cast(dict[str, Any], self._layer_info.get("attributes", {}))
        # Dependency attributes have an "entity" key in their properties
        self._deps = {
            v.get("name", k): v
            for k, v in self._attribs.items()
            if isinstance(v, dict) and "entity" in v
        }
        self.label = label
        self.quantor = quantor
        self.label_layer = label_layer
        self.conf = conf
        self.is_set_obj = set_objects is not None and self.label in set_objects
        self.config = conf.config
        self.original_layer = layer
        self.layer = self._layer(layer)
        self.schema = conf.schema.lower()
        self.lang = conf.lang
        self.batch = conf.batch.lower()
        self.entities = entities
        self._n = n
        # self.table = f"agent{n}" if self.field.startswith("agent") else self.label
        self.table = self.label
        self._label = ""  # fallback label for anonymous entities
        self.order = order
        self.prev_label = prev_label
        self._joins: Joins = {}
        self._conditions: set[str] = set()
        self._add_text = True
        self._quantor_label: str | None = None
        self._made = False
        self._is_len = False
        self._is_set = is_set
        self._underlang = _get_underlang(self.lang, self.config)
        self._allow_any: bool = allow_any
        self.references: dict[str, list[str]] = {}  # dict of labels + attributes

    @staticmethod
    def _parse_date(date: str | int, filler_month="01", filler_day="01") -> str:
        str_date: str = f"{str(date)}".strip("()")
        if re.match(r"^\d{4}$", str_date):
            str_date = f"{str_date}-{filler_month}-{filler_day}"
        elif re.match(r"^\d{4}-\d{2}$", str_date):
            str_date = f"{str_date}-{filler_day}"
        elif not re.match(r"^\d{4}-\d{2}-\d{2}$", str_date):
            assert False, ValueError(f"Invalid date format: '{str(date)}'")
        str_date = re.sub(rf"-02-(29|3\d)$", "-02-28", str_date)
        str_date = re.sub(rf"-(04|06|09|11)-(3[1-9])$", "-\\1-30", str_date)
        return str_date

    def _add_join_on(self, table: str, constraint: str) -> None:
        """
        Associate one or more WHERE statements with a JOIN statement
        """
        table = table.lower()
        if table in self._joins:
            if self._joins[table] is None:
                self._joins[table] = set()
            assert isinstance(
                self._joins[table], set
            ), "Constraint _joins should be lists"
            cast(set, self._joins[table]).add(constraint)
        else:
            self._joins[table] = {constraint}

    def _get_layer_info(self, conf: Config, layer: str) -> JSONObject:
        """
        todo: remove this once metadata is standardised
        """
        info: dict

        # assert layer in conf.config["layer"], ReferenceError(
        #     f"No entity type named {layer} in this corpus"
        # )
        # info = cast(dict, conf.config["layer"][layer])
        info = cast(dict, conf.config["layer"].get(layer, {}))

        if conf.lang:
            lginfo: dict = cast(
                dict,
                conf.config["layer"]
                .get(f"{layer}@{conf.lang}", {})
                .get("attributes", {}),
            )
            for k, v in lginfo.items():
                info["attributes"][k] = v

        return cast(JSONObject, info)

    def _get_cast(self, field: str, query: Any) -> str:
        """
        Determine whether or not we need to cast to int, float, text or nothing
        """
        typ = ""
        # if isinstance(query, (list, tuple, set)):
        #     query = list(query)[0]
        # if self._query_variable:
        #     return ""
        # if self._is_meta:
        #     met = cast(
        #         dict, self._layer_info.get("meta", self._attribs.get("meta", {}))
        #     )
        #     typ = cast(str, cast(dict, met[self.field]).get("type", ""))
        # else:
        #     met = cast(dict, self._attribs.get(self.field, {}))
        #     typ = cast(str, met.get("type", ""))
        if typ.startswith("int") and isinstance(query, int):
            return "::bigint"
        elif typ.startswith("int") and not isinstance(query, int):
            return "::text"
        elif typ.startswith("float") and isinstance(query, float):
            return "::float"
        elif typ.startswith("float") and not isinstance(query, float):
            return "::text"
        elif _valid_uuid(query):
            return "::uuid"
        return "::text"

    def _layer(self, layer: str) -> str:
        """
        If token table was requested, get batch instead
        """
        if layer == self.config["token"]:
            return self.conf.batch
        return layer

    def get_sql_expr(
        self,
        reference: dict[str, Any],
        prefix: str | None = None,
        attributes: dict[str, Any] = {},
        mapping: dict[str, Any] = {},
    ) -> tuple[str, RefInfo]:
        """
        Parse a reference object and return an SQL-compatible string reference + info about the reference.
        If no_join is False (default), will also add necessary joins
        """
        lab_lay: LabelLayer = cast(
            LabelLayer, (self.label_layer if self.label_layer else {})
        )
        if not prefix:
            prefix = self.label
        layer = lab_lay.get(prefix, lab_lay.get(self.label, (self.layer, None)))[0]
        if not attributes:
            attributes = self._attribs
        if not mapping:
            mapping = _get_mapping(layer, self.config, self.batch, self.lang or "")

        ref = ""
        ref_info: RefInfo = RefInfo(layer=layer, mapping=mapping)
        # function string | regex | math | reference | entity
        if "function" in reference:
            ref, ref_info = self.parse_function(reference["function"])
        elif "string" in reference:
            ref = f"'{reference['string']}'"
            ref_info["type"] = "string"
        elif "regex" in reference:
            rgx = reference["regex"]
            ref = f"'{rgx.get('pattern', '')}'"
            ref_info["type"] = "regex"
            ref_info["meta"] = rgx
        elif "math" in reference:
            ref, ref_info = self.parse_math(reference)
        elif "reference" in reference or "entity" in reference:
            ref, ref_info = self.parse_reference(
                reference, prefix, layer, lab_lay, attributes, mapping
            )
        return (ref, ref_info)

    def make(self) -> None:
        """
        Actually make the joins and the WHERE clause bits
        """
        if self._made:
            return None

        formed_condition: str = ""

        if not self.label:
            self.label = f"{self.layer.lower()}_{str(self._n)}"

        left, left_info = self.get_sql_expr(self.left)
        right, right_info = self.get_sql_expr(self.right)

        left_type = left_info.get("type")
        right_type = right_info.get("type")

        if "id" in (left_type, right_type):
            assert self.op in ("=", "!="), SyntaxError(
                f"References can only be compared for equality (invalid operator '{self.op}')"
            )
            if left_type == right_type:
                formed_condition = f"{left} {self.op} {right}"
            elif left_type == "entity":
                left_layer = left_info.get("layer", self.layer).lower()
                formed_condition = f"{left}.{left_layer}_id {self.op} {right}"
            elif right_type == "entity":
                right_layer = right_info.get("layer", self.layer).lower()
                formed_condition = f"{left} {self.op} {right}.{right_layer}_id"
            else:
                raise TypeError(f"Cannot compare {left} to {right}")

        elif left_type == "entity" and right_type == "entity":
            assert self.op in ("=", "!="), SyntaxError(
                f"References can only be compared for equality (invalid operator '{self.op}')"
            )
            left_layer = left_info.get("layer", self.layer).lower()
            right_layer = right_info.get("layer", self.layer).lower()
            formed_condition = (
                f"{left}.{left_layer}_id {self.op} {right}.{right_layer}_id"
            )

        elif "regex" in (left_type, right_type):
            assert self.op in ("=", "!="), SyntaxError(
                f"Regular expression only accept operator '=' or '!=' (invalid input {self.op})"
            )
            if "string" in (left_type, right_type):
                op = self.op.replace("=", "~")
                meta = cast(dict, {**left_info, **right_info}.get("meta", {}))
                if "caseInsensitive" in meta:
                    op += "*"
                left = f"({left})::text" if left_type == "string" else left
                right = f"({right})::text" if right_type == "string" else right
                formed_condition = f"{left} {op} {right}"
            elif "label" in (left_type, right_type):
                pass

        elif "string" in (left_type, right_type):
            if "label" in (left_type, right_type):
                pass
            elif left_type == right_type:
                formed_condition = f"({left})::text {self.op} ({right})::text"
            else:
                raise TypeError(
                    f"Could not resolve comparison {left} {self.op} {right}"
                )

        elif "number" in (left_type, right_type):
            assert self.op in ("=", "!=", ">=", "<=", ">", "<"), SyntaxError(
                f"Invalid operator {self.op} for numerical comparison ({left} {self.op} {right})"
            )
            left_str = re.sub(r"->([^>]+)$", "->>\\1", left)
            right_str = re.sub(r"->([^>]+)$", "->>\\1", right)
            formed_condition = f"({left_str})::numeric {self.op} ({right_str})::numeric"

        # # Special case: labels
        # left_ref_info = left_ref[1]
        # left_type = left_ref_info.get("type")
        # if left_type == "labels":
        #     assert self.op.lower().endswith("contain"), SyntaxError(
        #         f"Must use 'contain' on labels ({left_ref[0]} + {self.op})"
        #     )
        #     assert self.type in ("string", "regex"), TypeError(
        #         f"Contained labels can only be tested against strings or regexes ({left_ref[0]} + {self.op} + {right_ref[0]})"
        #     )
        #     ref_layer = left_ref_info.get("layer", self.layer)
        #     ref_layer_info = self.config["layer"].get(ref_layer, {})
        #     assert "nlabels" in ref_layer_info, KeyError(
        #         f"Missing 'nlabels' for layer '{ref_layer}' in config"
        #     )
        #     nbit = ref_layer_info["nlabels"]
        #     ref_mapping = left_ref_info.get("mapping", {})
        #     lookup_table = ref_mapping.get("name", "")
        #     inner_op = "~" if self.type == "regex" else "="
        #     dummy_mask = "".join(["0" for _ in range(nbit)])
        #     inner_condition = (
        #         f"(SELECT COALESCE(bit_or(1::bit({nbit})<<bit)::bit({nbit}), b'{dummy_mask}') AS m "
        #         + f"FROM {self.schema}.{lookup_table} WHERE label {inner_op} {right_ref[0]})"
        #     )
        #     # Use label_layer to store the inner conditions query-wide and give them unique labels
        #     if self.label_layer is None:
        #         self.label_layer = {}
        #     if self.label not in self.label_layer:
        #         self.label_layer[self.label] = (self.layer, {})
        #     meta: dict = self.label_layer[self.label][1]
        #     meta["labels inner conditions"] = meta.get("labels inner conditions", {})
        #     comp_str: str = f"{self.op} {self.type} {right_ref[0]}"
        #     n = meta["labels inner conditions"].get(
        #         comp_str, len(meta["labels inner conditions"])
        #     )
        #     meta["labels inner conditions"][comp_str] = n
        #     mask_label = f"{self.label}_mask_{n}"
        #     formed_join_table = f"{inner_condition} {mask_label}"
        #     self._add_join_on(formed_join_table, "")
        #     negated = self.op.lower().startswith(("not", "!"))
        #     op = "=" if negated else ">"
        #     formed_condition = f"{left_ref[0]} & {mask_label}.m {op} 0::bit({nbit})"

        # elif left_type == "date":
        #     right_ref_info = right_ref[1]
        #     assert right_ref_info.get("type") in ("date", "text", "number"), TypeError(
        #         f"Invalid date comparison ({left_ref[0]} {self.op} {right_ref[0]})"
        #     )
        #     q = right_ref[0]
        #     if self.op in (">", "<", ">=", "<=", "=", "!="):
        #         right_ref_no_quotes = right_ref[0].strip("'").strip('"')
        #         lower_date = self._parse_date(right_ref_no_quotes)
        #         upper_date = self._parse_date(
        #             right_ref_no_quotes, filler_month="12", filler_day="31"
        #         )
        #         op = self.op
        #         if op == "=":
        #             op = ">="
        #             q = f"'{lower_date}'::date AND {left_ref[0]}::date <= '{upper_date}'::date"
        #         elif op == "!=":
        #             op = "<"
        #             q = f"'{lower_date}'::date OR {left_ref[0]}::date > '{upper_date}'::date"
        #         elif op in (">", ">="):
        #             q = f"'{upper_date}'::date"
        #         elif op in ("<", "<="):
        #             q = f"'{lower_date}'::date"
        #     formed_condition = f"{left_ref[0]}::date {op} {q}"

        self._joins.pop("", None)
        self._conditions.add(formed_condition)
        self.made = True
        return None

    def parse_reference(
        self,
        reference: dict[str, Any],
        prefix: str,
        layer: str,
        lab_lay: LabelLayer,
        attributes: dict[str, Any],
        mapping: dict[str, Any],
    ) -> tuple[str, RefInfo]:
        ref: str = ""
        ref_info: RefInfo = RefInfo(type="string")
        meta = attributes.get("meta", {})
        deps = {
            v.get("name", k): v
            for k, v in attributes.items()
            if isinstance(v, dict) and "entity" in v
        }
        ref = cast(str, reference.get("reference", reference.get("entity", "")))
        post_dots: list[str] = []
        sub_ref: str = ""
        if "." in ref:
            ref, *post_dots = ref.strip().split(".")
            sub_ref = ".".join(post_dots)
        # Dependency attribute like 'head' or 'dependent'
        if ref in deps:
            assert "." not in ref, SyntaxError(
                f"Cannot reference a sub-attribute ({sub_ref}) on a source/head of a dependency relation ({ref})"
            )
            ref_label = prefix
            layer_table = _get_table(layer, self.config, self.batch, self.lang or "")
            # ref_mapping = mapping.get("attributes", {}).get(ref, {})
            # ref_table = ref_mapping.get("name", layer.lower())
            ref_formed_table = f"{self.schema}.{layer_table} {ref_label}"
            # hack: need a condition here because when inside a sequence,
            # unconditional joins from tokens are ignored in sequence.py#_where_conditions_from_constraints
            # (not sure why, probably to clean out unnecessary joins by sequence processing)
            self._add_join_on(ref_formed_table, "1=1")
            ref = f"{ref_label}.{ref}"
            ref_info["type"] = "id"
        # Attribute-related refs like 'xpos', 'year', 'agent', 'agent.region' or 'ufeat.Degree'
        elif ref in attributes or ref in meta or ref in mapping:
            in_meta = ref not in attributes and ref in meta
            in_mapping = (
                ref not in attributes
                and (not in_meta or "meta" not in attributes)
                and ref in mapping
            )
            # partition-specific attributes are listed in mapping only
            # Handle any necessary mapping first
            current_table = mapping.get("relation")
            # Make sure current partition table is there
            # if current_table:
            #     formed_current_table = f"{self.schema}.{current_table} {prefix}"
            #     self._add_join_on(formed_current_table, "1=1")
            # Add alignment talbe if needed
            alignment_table = (
                self.config["mapping"]["layer"]
                .get(layer, {})
                .get("alignment", {})
                .get("relation")
            )
            # Only add alignment table if attribute in mapping but not in attributes
            if alignment_table and current_table and not in_mapping:
                label_aligned = f"{prefix}_aligned"
                formed_aligned_table = (
                    f"{self.schema}.{alignment_table} {label_aligned}"
                )
                formed_aligned_condition = (
                    f"{prefix}.alignment_id = {label_aligned}.alignment_id"
                )
                self._add_join_on(formed_aligned_table, formed_aligned_condition)
                prefix = label_aligned
            ref_template = meta[ref] if in_meta else attributes[ref]
            ref_type = (
                ref_template.get("type", "string")
                .replace("categorical", "string")
                .replace("text", "string")
            )
            global_attr = ref_template.get("ref")
            # Sub-attribute reference like 'agent.region' or 'ufeat.Degree'
            if post_dots:
                # agent.region
                if global_attr:
                    assert len(post_dots) == 1, SyntaxError(
                        f"No support for nested references yet at {prefix}.{ref}.{sub_ref}"
                    )
                    ref_label = f"{prefix}_{ref}".lower()
                    ref_mapping = mapping.get("attributes", {}).get(ref, {})
                    ref_key = ref_mapping.get("key", ref)
                    ref_table = ref_mapping.get("name", f"global_attributes_{ref}")
                    ref_formed_table = f"{self.schema}.{ref_table.lower()} {ref_label}"
                    ref_formed_condition = (
                        f"{prefix}.{ref_key}_id = {ref_label}.{ref_key}_id"
                    )
                    self._add_join_on(ref_formed_table, ref_formed_condition)
                    ref_attributes = self.config["globalAttributes"][global_attr].get(
                        "keys", {}
                    )
                    ref_type = ref_attributes.get(sub_ref, {}).get("type", "string")
                    ref_type = ref_type.replace("text", "string")
                    # Uncomment once all keys have been reported in the db
                    # assert sub_ref in ref_attributes, ValueError(
                    #     f"Sub-attribute '{sub_ref}' not found on {prefix}.{ref}"
                    # )
                    accessor = "->>" if ref_type == "string" else "->"
                    ref = f"{ref_label}.{ref_key}{accessor}'{sub_ref}'"
                    ref_info = RefInfo(type=ref_type)
                # ufeat.Degree
                elif ref_type in ("dict", "jsonb"):
                    assert len(post_dots) == 1, SyntaxError(
                        f"No support for nested references yet at {prefix}.{ref}.{sub_ref}"
                    )
                    ref_label = f"{prefix}_{ref}"
                    ref_mapping = mapping.get("attributes", {}).get(ref, {})
                    ref_key = ref_mapping.get("key", ref.lower())
                    ref_table = ref_mapping.get("name", ref.lower())
                    ref_formed_table = f"{self.schema}.{ref_table} {ref_label}"
                    ref_formed_condition = (
                        f"{prefix}.{ref_key}_id = {ref_label}.{ref_key}_id"
                    )
                    self._add_join_on(ref_formed_table, ref_formed_condition)
                    ref_type = (
                        attributes.get(ref, {})
                        .get("keys", {})
                        .get(sub_ref, {})
                        .get("type", "string")
                    ).replace("text", "string")
                    accessor = "->>" if ref_type == "string" else "->"
                    ref = f"{ref_label}.{ref_key}{accessor}'{sub_ref}'"
                    ref_info = RefInfo(type=ref_type)
                else:
                    raise TypeError(
                        f"Trying to access sub-attribute '{sub_ref}' on non-dict attribute {prefix}.{ref}"
                    )
            # Simple global attribute reference like 'agent'
            elif global_attr:
                ref = f"{prefix}.{ref}_id"
                ref_info["type"] = "id"
            # Normal attribute reference like 'upos'
            else:
                attr_mapping = mapping.get("attributes", {}).get(ref, {})
                need_to_join = attr_mapping.get("type") == "relation"
                if need_to_join:
                    ref_label = f"{prefix.lower()}_{ref.lower()}"
                    attr_join_table = attr_mapping.get(
                        "name", f"{layer.lower()}_{ref.lower()}"
                    )
                    attr_key = attr_mapping.get("key", ref.lower())
                    formed_ref_table = (
                        f"{self.schema.lower()}.{attr_join_table} {ref_label}"
                    )
                    formed_ref_cond = (
                        f"{ref_label}.{attr_key}_id = {prefix}.{attr_key}_id"
                    )
                    self._add_join_on(formed_ref_table, formed_ref_cond)
                    ref = f"{ref_label}.{attr_key}"
                elif in_meta:
                    accessor = "->>" if ref_type == "string" else "->"
                    ref = f"{prefix}.meta{accessor}'{ref}'"
                else:
                    ref = f"{prefix}.{ref}"
                ref_info["type"] = ref_type
        # Entity reference like t3
        elif ref in lab_lay:
            ref_layer = lab_lay[ref][0]
            ref_mapping = _get_mapping(
                ref_layer, self.config, self.batch, self.lang or ""
            )
            if post_dots:
                return self.get_sql_expr(
                    {"reference": sub_ref}, prefix=ref, mapping=ref_mapping
                )
            else:
                ref_info = RefInfo(type="entity", layer=ref_layer, mapping=ref_mapping)
        else:
            raise ReferenceError(
                f"Could not resolve reference to '{ref}': no entity has that label and {layer} has no attribute of that name"
            )
        return (ref, ref_info)

    def parse_math(
        self,
        math_obj: dict[str, Any],
    ) -> tuple[str, RefInfo]:
        """
        Return (number, {"type": "number"})
        Input is {"math": ...} where ... can be a string number, {"function": ...} or {"operation": ...}
        """
        ref: str = ""
        ref_info: RefInfo = RefInfo(type="number")
        if isinstance(math_obj["math"], str):
            ref = math_obj["math"]
            return (ref, ref_info)
        elif isinstance(math_obj["math"], dict) and "function" in math_obj["math"]:
            return self.parse_function(math_obj["math"]["funciton"])
        operation = math_obj["math"].get("operation", {})
        ref_array: list[str] = ["", operation.get("operator", "+"), ""]
        left = operation.get("left", {"math": "0"})
        right = operation.get("right", {"math": "0"})
        for i in range(2):
            operand = left if i == 0 else right
            operand_ref, operand_info = self.get_sql_expr(cast(dict[str, Any], operand))
            assert (
                operand_info.get("type") == "number"
            ), f"Only numbers can appear in mathematical operations ({operand})"
            ref_array[2 * i] = operand_ref
        ref = " ".join(ref_array)
        return (ref, ref_info)

    def parse_function(
        self,
        fn_obj: dict[str, Any],
    ) -> tuple[str, RefInfo]:
        fn = fn_obj.get("functionName", "")
        assert fn in FUNCS, NotImplementedError(
            f"Function '{fn}' not implemented (yet?)"
        )
        ars = fn_obj.get("arguments", [])
        assert ars, ValueError(f"Arguments of function '{fn}' are missing")
        parsed_ars = [self.get_sql_expr(a) for a in ars]
        ars_str = ",".join([a[0] for a in parsed_ars])
        fn_str = f"{fn}({ars_str})"
        ref_info = RefInfo(type="text")
        if fn == "range":
            first_arg_str, first_arg_info = parsed_ars[0]
            assert first_arg_info.get("type") == "entity", TypeError(
                f"Range only applies to layer annotations (error in '{first_arg_str}')"
            )
            fn_str = (
                f"upper({first_arg_str}.char_range) - lower({first_arg_str}.char_range)"
            )
            ref_info = RefInfo(type="number")
        elif fn == "position":
            first_arg_str, first_arg_info = parsed_ars[0]
            assert first_arg_info.get("type") == "entity", TypeError(
                f"Range only applies to layer annotations (error in '{first_arg_str}')"
            )
            fn_str = f"lower({first_arg_str}.char_range)"
            ref_info = RefInfo(type="number")
        elif fn in ("start", "end"):
            first_arg_str, first_arg_info = parsed_ars[0]
            assert first_arg_info.get("type") == "entity", TypeError(
                f"{fn} only applies to layer annotations (error in '{first_arg_str}')"
            )
            assert _is_anchored(
                self.config, first_arg_info.get("layer", self.layer), "time"
            ), TypeError(
                f"{fn} only applies to time-aligned layer annotations (error in '{first_arg_str})"
            )
            lower_or_upper = "lower" if fn == "start" else "upper"
            fn_str = f"({lower_or_upper}({first_arg_str}.frame_range) / 25.0)"  # time in seconds
            ref_info = RefInfo(type="number")
        return (fn_str, ref_info)

    # def date(self) -> None:
    #     q: str = f"{self._formatted}"
    #     op = self.op
    #     cast = self._cast
    #     labfield = f"{self.label.lower()}.{self.field.lower()}"
    #     if op in (">", "<", ">=", "<=", "=", "!="):
    #         lower_date = self._parse_date(q)
    #         upper_date = self._parse_date(q, filler_month="12", filler_day="31")
    #         cast = "::date"
    #         if op == "=":
    #             op = ">="
    #             q = f"'{lower_date}'::date AND {labfield}{cast} <= '{upper_date}'::date"
    #         elif op == "!=":
    #             op = "<"
    #             q = f"'{lower_date}'::date OR {labfield}{cast} > '{upper_date}'::date"
    #         elif op in (">", ">="):
    #             q = f"'{upper_date}'::date"
    #         elif op in ("<", "<="):
    #             q = f"'{lower_date}'::date"
    #     formed = f"{self.label.lower()}.{self.field.lower()}{cast} {op} {q}"
    #     self._conditions.add(formed)


def _get_constraint(
    constraint: JSONObject,
    layer: str,
    label: str,
    conf: Config,
    quantor: str | None = None,
    n: int = 1,
    order: int | None = None,
    prev_label: str | None = None,
    label_layer: LabelLayer = {},
    entities: set[str] | None = None,
    is_set: bool = False,
    set_objects: set[str] | None = None,
    allow_any: bool = True,  # False,
    top_level: bool = False,
) -> Constraint | Constraints | None:
    """
    Handle a single constraint, or nested constraints
    """

    first_key_in_constraint = next(iter(constraint), "")

    if first_key_in_constraint.endswith("Quantification"):
        obj: dict[str, Any] = cast(dict[str, Any], next(iter(constraint.values())))
        if "quantor" in obj:
            quantor_str: str = obj.get("quantor", "")
            if quantor_str.endswith(("EXIST", "EXISTS")):
                if quantor_str.startswith(("!", "~", "¬", "NOT")):
                    quantor_str = "NOT EXISTS"
                else:
                    quantor_str = "EXISTS"
            quantor = quantor_str
            constraint = obj.get("args", [{}])[0]
            obj_layer = label_layer.get(obj.get("label", ""), [""])[0]
            if _layer_contains(conf.config, layer, obj_layer) or all(
                _is_anchored(conf.config, x, "stream") for x in (layer, obj_layer)
            ):
                part_of = label
            first_key_in_constraint = next(iter(constraint), "")

    unit: dict[str, Any] = cast(dict[str, Any], constraint.get("unit", {}))
    if unit.get("constraints"):
        unit_layer: str = cast(str, unit.get("layer", ""))
        unit_label = unit.get("label", "")
        # unit_label = label
        # # Pass the parent's label if the layer is a dependency relation
        # layer_type = conf.config["layer"].get(unit_layer, {}).get("layerType")
        # if layer_type != "relation":
        #     unit_label = unit.get("label", "")
        # else:
        #     label_layer[label] = (layer, dict())
        part_of = unit.get("partOf", "")
        # Use the parent label as part_of if they are both stream-anchored
        if label != unit_label and (
            _layer_contains(conf.config, layer, unit_layer)
            or all(_is_anchored(conf.config, x, "stream") for x in (layer, unit_layer))
        ):
            part_of = label
        args = (
            cast(JSONObject, unit["constraints"]),
            unit_layer,
            unit_label,
            conf,
            quantor,
            "AND",
            n,
            order,
            prev_label,
            label_layer,
            entities,
            part_of,
            is_set,
            set_objects,
            allow_any,
            top_level,
        )
        return _get_constraints(*args)

    elif first_key_in_constraint == "logicalExpression":
        obj = cast(dict[str, Any], next(iter(constraint.values())))
        # the default operator is AND, and it can be missing
        operator = "AND"
        if "unaryOperator" in obj:
            operator = obj["naryOperator"]
        elif "naryOperator" in obj:
            operator = obj["naryOperator"]

        return _get_constraints(
            obj.get("args", []),
            cast(str, obj.get("layer", layer)),  # todo: which layer is correct?
            cast(str, obj.get("label", label)),
            conf,
            cast(str | None, quantor),
            operator,
            n + 1,
            order,
            prev_label,
            label_layer,
            entities,
            "",  # no part_of here
            is_set,
            set_objects,
            allow_any,
            top_level,
        )

    if not len(constraint):
        if order is None:
            return None
        # This is a hack that needs to be improved to not ignore empty tokens in sequences
        constraint = {
            "comparison": {
                "left": {"string": "_"},
                "operator": "=",
                "right": {"string": "_"},
            }
        }

    comp = cast(dict[str, Any], constraint.get("comparison", {}))

    return Constraint(
        comp.get("left", {}),
        comp.get("comparator", ""),
        comp.get("right", {}),
        label,
        layer,
        conf,
        quantor,
        label_layer,
        entities,
        n,
        is_set,
        set_objects,
        order,
        prev_label,
        allow_any,
    )


def _get_constraints(
    constraints: JSONObject,  # Should be an array of constraints (see cobquec)
    layer: str,
    label: str,
    conf: Config,
    quantor: str | None = None,
    op: str | None = "AND",
    n: int = 1,
    order: int | None = None,
    prev_label: str | None = None,
    label_layer: LabelLayer = {},
    entities: set[str] | None = None,
    part_of: str | None = None,
    is_set: bool = False,
    set_objects: set[str] | None = None,
    allow_any: bool = True,  # False,
    top_level=False,
) -> Constraints | None:
    """
    Create a Constraints object containing all subconstraints

    n is just an ever-incrementing number needed to make unique query names

    order and prev_label are for objects within a sequence

    If allow_any, even constraints belonging to objects not in entities
    will be created.

    top_level is special handling for constraints at base level (tangram4.json)
    """
    # if not constraints and order is None:
    #     return None

    if top_level:
        allow_any = True
        # sorry about this:
        first_unit: dict[str, Any] = next(
            (
                cast(dict[str, Any], cast(JSONObject, i)["unit"])
                for i in cast(
                    list[JSONObject],
                    sorted(
                        cast(list[dict], constraints), key=arg_sort_key
                    ),  # why do we assume the existence of an args key here?
                )
                if "unit" in cast(JSONObject, i)
            ),
            {},
        )
        first_layer = first_unit.get("layer", "")

    results = []
    # op = cast(str, constraints.get("operator", "AND"))

    lab = label or f"constraint_{n}"

    references: dict[str, list[str]] = {}

    if part_of:
        part_of_layer: str = label_layer.get(part_of, ("", None))[0]
        segname = conf.config["segment"].lower()
        is_token = layer.lower() in (conf.config["token"].lower(), conf.batch.lower())
        if part_of == label:
            part_of = ""
        elif (
            is_token and part_of_layer.lower() == segname
        ):  # Use id for token in segment
            part_of = f"{part_of}.{segname}_id = {label}.{segname}_id"
        else:
            references[part_of] = references.get(part_of, []) + ["char_range"]
            references[label] = references.get(label, []) + ["char_range"]
            part_of = f"{part_of}.char_range && {label}.char_range"

    args = cast(list[JSONObject], constraints)
    for arg in sorted(args, key=arg_sort_key):
        arg_label = cast(str, lab if not top_level else arg.get("label", ""))
        tup = _get_constraint(
            arg,
            layer,
            arg_label,
            conf,
            quantor=None,  # quantor is not passed down to single constraints
            n=n,
            order=order,
            prev_label=prev_label,
            label_layer=label_layer,
            entities=entities,
            is_set=is_set,
            set_objects=set_objects,
            allow_any=allow_any,
            top_level=top_level,
        )
        n += 1
        results.append(tup)
    lay: str = layer if not top_level else first_layer
    return Constraints(
        conf.schema,
        lay,
        lab,
        conf,
        results,
        cast(str, op),
        quantor,
        label_layer,
        entities,
        part_of,
        n=n,
        is_set=is_set,
        set_objects=set_objects,
        allow_any=allow_any,
        references=references,
    )


def process_set(
    conf: Config,
    r: QueryData,
    _n: int,
    token: str,
    segment: str,
    _underlang: str | None,
    set_data: dict,
    seg_label: str | None = None,
    attribute="___tokenid___",
    label: str = "",
) -> str:
    batch = conf.batch
    schema = conf.schema
    config = conf.config

    joins: Joins = {}

    conditions: set[str] = set()
    if attribute == "___tokenid___":
        field = cast(str, config["token"]).lower() + "_id"
    elif (
        config["layer"][token]["attributes"].get(attribute, {}).get("type", "")
        == "text"
    ):
        field = attribute + "_id"
    else:
        field = attribute

    if not label:
        label = set_data.get("label", f"unknown_{_n}") + f"_{field}"

    first_unit: dict[str, Any] = next(
        (u["unit"] for u in set_data.get("members", []) if "unit" in u), {}
    )
    from_label = first_unit.get("label", "t")
    lay = first_unit.get("layer", token)
    assert config["layer"][lay].get("layerType") != "relation", TypeError(
        f"Cannot build a set of relational entities ({lay})"
    )

    lang: str = cast(str, _underlang)[1:] if _underlang else ""
    from_table = batch if lay == token else _get_table(lay, config, batch, lang)
    disallowed = f"{schema}.{lay} {from_label}"

    # if "partOf" in first_unit:
    #     part_of_label = first_unit["partOf"]
    #     part_of_layer = r.label_layer.get(part_of_label, [""])[0]
    #     if part_of_label == "___seglabel___":
    #         part_of_layer = segment
    #     if part_of_layer.lower() == segment.lower():
    #         first_unit["partOf"] = seg_label

    conn_obj = _get_constraints(
        first_unit.get("constraints", []),
        first_unit.get("layer", ""),
        from_label,
        conf,
        label_layer=r.label_layer,
        entities=set(),
        part_of=first_unit.get("partOf", None),
        set_objects=r.set_objects,
        n=_n,
        is_set=True,
        top_level=False,
    )
    if conn_obj:
        _n = conn_obj._n + 1
        join = conn_obj.joins() if conn_obj else {}
        for k, v in join.items():
            if disallowed.lower() == k.lower():
                continue
            joins[k] = v
            if not isinstance(v, set):
                continue
            for join_condition in v:
                if not isinstance(join_condition, str):
                    continue
                conditions.add(join_condition)
        cond = conn_obj.conditions() if conn_obj else ""
        if cond:
            conditions.add(cond)

    if config["layer"][lay].get("contains") == config["token"]:
        joins[f"{schema}.{from_table} {from_label}"] = True
        conditions.add(f"{from_label}.char_range && anonymous_set_t.char_range")
        from_table = batch
        from_label = "anonymous_set_t"

    strung_joins = _joinstring(joins)
    strung_conds = "WHERE " + " AND ".join(conditions) if conditions else ""

    formed = f"""
              (SELECT array_agg({from_label}.{field})
              FROM {schema}.{from_table} {from_label}
               {strung_joins} 
               {strung_conds}
              ) AS {label}
    """
    return formed.strip()

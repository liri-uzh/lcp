from typing import Any, Sequence, cast

from .typed import JSON, LabelLayer, QueryPart, JSONObject
from .utils import Config, SUFFIXES, _get_underlang, arg_sort_key, literal_sql

from typing import Self

MATCHES_ALL = {".*", ".+", ".*?", ".?", ".+?"}


class SingleNode:
    """
    Store a query like pos=NOUN , whether it can be prefiltered, and its realisation as prefilter
    """

    def __init__(
        self, field: str, op: str, query: str, is_regex: bool = False, *args, **kwargs
    ) -> None:
        self.field = field
        self.op = op
        self.query = query
        self.is_regex = is_regex
        self.inverse = "!" in op
        self.ignore_diacritics = False
        self.case_sensitive = True
        self.is_listlike, list_regex = self._detect_listlike(query, True, self.is_regex)
        if list_regex:
            self.is_regex = True
        self.is_prefix = _is_prefix(self.query, op=op)

    def as_prefilter(self, col_data: dict[str, str]) -> str:
        """
        Turn node into a prefilter string
        """
        if not self._can_prefilter():
            return ""
        if self.field not in col_data.values():
            return ""
        inv = "!" if self.inverse else ""
        joiner = " | " if not self.inverse else " & "
        fixed = []
        if self.is_listlike:
            search = self.query.strip("()").split("|")
        else:
            search = [self.query]
        for piece in search:
            pref = ""
            for pattern in sorted(SUFFIXES, key=len, reverse=True):
                centerpiece = self.query.lstrip("^").rstrip("$")
                if (
                    centerpiece.isalnum()
                    and self.query.startswith("^")
                    and self.query.endswith("$")
                ):
                    # special case: anchored regular expression with no funny suffix
                    piece = centerpiece
                    break
                if piece.strip().startswith("^") and piece.lstrip("^").isalnum():
                    pref = ":*"
                    piece = piece.lstrip("^")
                    break
                if piece.rstrip().rstrip("$").endswith(pattern):
                    pref = ":*"
                    piece = piece.rstrip().rstrip("$")
                    piece = piece[: -len(pattern)]
                    piece = piece.lstrip().lstrip("^")
                    break
            fixed.append(f"{piece}{pref}")
        idx = next(k for k, v in col_data.items() if v == self.field)
        tokens = [f"{inv}{idx}{s}" for s in fixed]
        if len(tokens) > 1:
            return " (" + joiner.join(tokens) + " ) "
        else:
            return tokens[0]

    def _can_prefilter(self) -> bool:
        """
        Can this node be used as a prefilter?
        """
        if self.op not in ("=", "!="):
            return False
        if self.is_prefix and self.query in MATCHES_ALL:
            return False
        if self.is_regex and not self.is_prefix:
            return False
        # if not self.mini:
        #    return False
        if not self.case_sensitive:
            return False
        if self.ignore_diacritics:
            return False
        return True

    def _detect_listlike(
        self, search: str, case_sensitive: bool, def_regex: bool
    ) -> tuple[bool, bool]:
        """
        Allow both search="x|y|z" and search="(x|y|z)" to be prefiltered,
        but not search="((x,y))" or search="x(y|z)"
        """
        if def_regex:
            return False, False
        if "|" not in search:
            return False, False
        if not case_sensitive:
            return False, False
        if (search.startswith("(") and "(" not in search[1:]) and (
            search.endswith(")") and ")" not in search[:-1]
        ):
            search = search[1:-1]
            return True, False
        elif (search.startswith("(") and "(" in search[1:]) or (
            search.endswith(")") and ")" in search[:-1]
        ):
            return False, True
        return True, False


class Conjuncted:
    """
    A set of constraints held together within an AND/OR expression
    """

    def __init__(self, conj: str | None, items: Sequence[SingleNode | Self]) -> None:
        self.conj = conj
        self.items = items


class Disjunction:
    """
    Sequences units of the same, fixed length
    """

    def __init__(self, units: Sequence[Sequence[SingleNode | Conjuncted]]) -> None:
        self.units = units


class Prefilter:
    """
    A class that can convert query json to a prefilter vector query, or return
    an empty string if a prefilter can't be made from this input
    """

    def __init__(
        self,
        query_json: QueryPart,
        conf: Config,
        label_layer: LabelLayer,
        has_segment: str,
    ) -> None:
        self.query_json = query_json
        self.conf = conf
        self.label_layer = label_layer
        self.has_segment = has_segment
        self.config = conf.config
        self.lang = conf.lang
        self._underlang = _get_underlang(self.lang, self.config)
        self._has_partitions = self.has_partitions()
        self._col_data: dict[str, str] = {}
        col_data = cast(
            dict[str, str] | dict[str, dict[str, str]] | list,
            self.config["mapping"].get("FTSvectorCols", {}),
        )
        if isinstance(self._col_data, list):
            self._col_data = {
                str(ix): name for ix, name in enumerate(col_data, start=1)
            }
        elif self._has_partitions:
            self._col_data = cast(
                dict[str, str],
                cast(dict, col_data).get(cast(str, self.lang), col_data),
            )
        else:
            self._col_data = cast(dict[str, str], col_data)

    def has_partitions(self) -> bool:
        """
        Is this a partitioned corpus like sparcling?
        """
        mapping = cast(JSONObject, self.config["mapping"])
        layers = cast(JSONObject, mapping["layer"])
        _cols = cast(JSONObject, layers[self.config["segment"]])
        return self.lang in cast(JSONObject, _cols.get("partitions", {}))

    def _tsquery(self, query: str) -> str:
        formed_query = literal_sql(query)
        if formed_query.startswith("concat("):
            formed_query += "::tsquery"
        return formed_query

    def _stringify(self, prefilters: list[str]) -> str:
        """
        Build the actual SQL query part
        """
        if not self.config["mapping"].get("hasFTS", True):
            return ""
        if not any(x.strip() for x in prefilters):
            return ""

        conjuncts: list[str] = []
        tok_name = self.config["firstClass"]["token"]
        tok_attrs = self.config["layer"][tok_name].get("attributes", {})
        for ix, name in cast(dict[str, str], self._col_data).items():
            attr_name = name.split()[0]
            if tok_attrs.get(attr_name, {}).get("type") != "text":
                continue
            for pf in prefilters:
                if "|" in pf:
                    continue
                for c in pf.split("&"):
                    stripped_c = c.strip(" ()")
                    if (
                        stripped_c.startswith((str(ix), f"!{ix}"))
                        and stripped_c not in conjuncts
                    ):
                        conjuncts.append(stripped_c)
        formed_prefilters = self._tsquery(" <1> ".join(prefilters))
        stringified = f"vec.vector @@  {formed_prefilters}"
        if len(conjuncts) > 1:
            # Including the single terms aside their sequence makes queries much faster
            cond_conjuncts = [f"vec.vector @@ {self._tsquery(c)}" for c in conjuncts]
            stringified = " AND ".join(cond_conjuncts) + " AND " + stringified
        return stringified

    def initialise(
        self, query_json: QueryPart
    ) -> list[SingleNode | Conjuncted | Disjunction | None]:
        """
        todo: update this for latest query json
        """
        list_nodes: list[SingleNode | Conjuncted | Disjunction | None] = []
        for obj in query_json:
            if not isinstance(obj, dict):
                continue
            if "sequence" not in obj:
                continue
            seq = cast(dict[str, JSON], obj["sequence"])
            members = cast(list[dict[str, JSON]], seq["members"])
            for member in members:
                if "logicalExpression" in member:
                    logic = cast(dict, member["logicalExpression"])
                    assert logic.get("naryOperator") == "OR", RuntimeError(
                        "Cannot build prefix for non-OR matrix logical expression"
                    )
                    log_members = logic.get("args", [])
                    all_unit_or_sequence = all(
                        "unit" in x or "sequence" in x for x in log_members
                    )
                    assert all_unit_or_sequence, RuntimeError(
                        "Cannot build OR prefix if some members are not units or sequences"
                    )
                    units: Sequence[Sequence[SingleNode | Conjuncted]] = []
                    assert all(
                        "unit" in y
                        for x in [lm for lm in log_members if "sequence" in lm]
                        for y in x["sequence"].get("members", [])
                    ), RuntimeError(
                        "Can only build a prefix for disjunctions of sequences that exclusively contain units"
                    )
                    tmp_units = [
                        [
                            self._process_unit(
                                cast(dict, y["unit"]).get("constraints", [])
                            )
                            for y in (
                                x["sequence"].get("members", [])
                                if "sequence" in x
                                else [x]  # single unit
                            )
                        ]
                        for x in log_members
                    ]
                    units = cast(
                        Sequence[Sequence[SingleNode | Conjuncted]],
                        [x for x in tmp_units if x is not None],
                    )
                    list_nodes.append(Disjunction(units))
                    continue
                if "unit" not in member:
                    continue  # TODO: handle nested sequences
                cons = cast(
                    list[dict[str, Any]],
                    cast(dict, member["unit"]).get("constraints", []),
                )
                res = None  # No constraints
                if cons:
                    res = self._process_unit(cons)
                list_nodes.append(res)
        return list_nodes

    def _prefilter_conjuncts(self) -> list[str]:
        first_pass = self.initialise(self.query_json)
        return self._stringify_nodes(first_pass)

    def _condition(self) -> str:
        return self._stringify(self._prefilter_conjuncts())

    def parse_comparison(self, comparison) -> tuple[str, str, str, str]:
        """
        Return (attribute,operator,patter,type) where type can be string, regex or other
        """
        left, right = (comparison["left"], comparison["right"])
        attribute = next(
            (x["reference"] for x in [left, right] if "reference" in x),
            "",
        )
        if not attribute:
            return ("", "", "", "other")
        pattern = ""
        typ = "other"
        if "string" in left:
            pattern = left["string"]
            typ = "string"
        if "string" in right:
            pattern = right["string"]
            typ = "string"
        if "regex" in left:
            pattern = left["regex"]["pattern"]
            # Prefilters are always case-sensitive
            typ = "other" if "caseInsensitive" in left["regex"] else "regex"
        if "regex" in right:
            # Prefilters are always case-sensitive
            pattern = right["regex"]["pattern"]
            typ = "other" if "caseInsensitive" in right["regex"] else "regex"
        return (attribute, comparison["comparator"], pattern, typ)

    def _process_unit(
        self, filt: list[dict[str, Any]]
    ) -> SingleNode | Conjuncted | None:
        """
        Handle unit json object
        """
        if len(filt) > 1:
            result = self._attempt_conjunct(filt, "AND")
            return result
        else:
            if "comparison" in filt[0]:
                attribute, operator, pattern, typ = self.parse_comparison(
                    filt[0]["comparison"]
                )
                if typ == "other":
                    return None
                if _is_prefix(pattern, operator, typ):
                    return SingleNode(attribute, operator, pattern, typ == "regex")
            elif next(iter(filt[0]), "") == "logicalExpression":
                logic: dict[str, Any] = next(iter(filt[0].values()), {})
                operator = logic.get("unaryOperator", logic.get("naryOperator", "AND"))
                result = self._attempt_conjunct(logic.get("args", []), operator)
                return result
        return None

    def _attempt_conjunct(
        self, filt: list[dict[str, Any]], kind: str
    ) -> Conjuncted | None:
        """
        Try to make prefilters from this AND/OR-conjuncted token
        """
        matches: list[SingleNode | Conjuncted] = []

        for arg in sorted(filt, key=arg_sort_key):
            # todo recursive ... how to handle?
            if next(iter(arg), "") == "logicalExpression":
                logic: dict[str, Any] = next(iter(arg.values()), {})
                filt = cast(list[dict[str, Any]], logic.get("args", []))
                result = self._attempt_conjunct(
                    filt, logic.get("unaryOperator", logic.get("naryOperator", "AND"))
                )
                if result:
                    matches.append(result)
                continue
            if "comparison" not in arg:
                continue
            attribute, operator, pattern, typ = self.parse_comparison(arg["comparison"])
            if typ == "other":
                continue
            if _is_prefix(pattern, operator, typ):
                matches.append(SingleNode(attribute, operator, pattern, typ == "regex"))

        # Do not use any prefilter at all for the disjunction if one of the disjuncts could not be used
        if kind == "OR" and len(matches) < len(filt):
            return None

        return Conjuncted(kind, matches) if matches else None

    def _as_string(self, item: Conjuncted | SingleNode) -> str:
        """
        Create a prefilter string with everything but the column-conversion
        """
        if isinstance(item, Conjuncted):
            return " <1> ".join(self._stringify_nodes([item]))
        elif isinstance(item, SingleNode):
            return item.as_prefilter(self._col_data)
        raise NotImplementedError("should not be here")

    def _stringify_nodes(
        self, prefilter: list[Conjuncted | SingleNode | Disjunction | None]
    ) -> list[str]:
        """
        Create the prefilter string from a single item in the defaultdict value
        """
        all_made = []
        for prefilt in prefilter:
            if prefilt is None:
                all_made.append("(!1a|1a)")  # Add a tautology
                continue

            single = []
            if isinstance(prefilt, Disjunction):
                disj = " | ".join(
                    " <1> ".join(
                        self._as_string(u) for u in units if self._as_string(u)
                    )
                    for units in prefilt.units
                )
                all_made.append(f"({disj})")
                continue
            elif isinstance(prefilt, Conjuncted):
                connective = prefilt.conj
                items = prefilt.items
            else:
                connective = None
                items = [prefilt]

            for item in items:
                strung = self._as_string(item)
                if strung:
                    single.append(strung)

            if connective == "AND":
                joined = " & ".join(single)
            elif connective == "OR":
                joined = " | ".join(single)
            else:
                if connective == "NOT":
                    single[0] = "!" + single[0]
                joined = " <1> ".join(single)

            if len(single) > 1:
                joined = f"({joined})"
            all_made.append(joined)

        return all_made

    def _finalise_prefilters(self, prefilters: list[str]) -> str:
        """
        todo: not sure if this remove is needed anymore
        """
        removable = set()
        for ix, s in enumerate(prefilters):
            s = s.strip()
            if any(i != s and s in i and (" " in i or "\n" in i) for i in prefilters):
                removable.add(ix)
        final = set([x for i, x in enumerate(prefilters) if i not in removable])

        return " & ".join(sorted(final))


def _is_prefix(query: str, op: str = "=", typ: str = "string") -> bool:
    """
    Can a query be treated as a prefix in a prefilter? regex like ^a.* for example
    """
    if op not in ("=", "!="):
        return False
    if typ == "string":
        return True
    if query.startswith("^") and query.lstrip("^").rstrip("$").isalnum():
        return True
    for pattern in sorted(SUFFIXES, key=len, reverse=True):
        if not query.rstrip().rstrip("$").endswith(pattern):
            continue
        query = query.rstrip().rstrip("$")
        query = query[: -len(pattern)]
        query = query.lstrip().lstrip("^")
        if not query or any(
            i in query for i in ".^$*+-?[]{}\\/()|"
        ):  # there remain regex characters in the rest of the pattern
            continue
        return True
    return False

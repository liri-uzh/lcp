import json
import re

from dataclasses import dataclass, field
from psycopg import sql
from typing import Any, cast

from .typed import Joins, LabelLayer, QueryType, SQLRef

SUFFIXES = {".*", ".+", ".*?", ".?", ".+?", "."}
LR = "{}"


def unique_label(
    label: str = "anonymous",
    layer="__internal",
    references: LabelLayer | None = None,
    obj: dict = dict({}),
) -> str:
    """
    Return label if not already in references
    otherwise return a unique variation on it
    """
    references = references or {}
    label = label or "anonymous"
    new_label: str = label
    n: int = 1
    while new_label in references:
        n += 1
        new_label = f"{label}{str(n)}"
    references[new_label] = (layer, obj)
    return new_label


def sql_str(template: str, *args, **kwargs) -> str:
    prep_args = [sql.Identifier(a) for a in args]
    return sql.SQL(template).format(*prep_args, **kwargs).as_string()  # type: ignore


class SQLCorpus:
    def __init__(
        self,
        conf: dict,
        schema: str,
        batch: str,
        lang: str,
    ):
        self.refs: dict[tuple[str, str, bool], SQLRef] = {}
        self.conf = conf
        self.schema = schema
        self.batch = batch
        self.lang = lang
        self.used_refs: dict = {}
        self.used_aliases: dict = {}

    def add_ref(
        self,
        key: tuple[str, str, bool],
        entity: str,
        ref: str,
        alias: str,
        joins: dict[str, dict[str, int]],
    ) -> SQLRef:
        self.refs[key] = SQLRef(entity, ref, alias, joins)
        return self.refs[key]

    def layer(self, entity: str, layer: str, pointer: bool = False) -> SQLRef:
        """
        Reference to a layer.
        If pointer is True, ref and alias target the primary key instead of the table.
        """
        key = (entity, "", pointer)
        if key not in self.refs:
            ref = unique_label(entity, layer, self.used_refs)
            layer_table = _get_table(layer, self.conf, self.batch, self.lang).lower()
            table = sql_str("{}.{} {}", self.schema, layer_table, ref)
            joins: dict[str, dict[str, int]] = {table: {}}
            if pointer:
                layer_map = self.conf["mapping"]["layer"].get(layer, {})
                aligned = "alignment" in layer_map and not layer_map["alignment"].get(
                    "indirect"
                )
                id_prefix = "alignment" if aligned else layer.lower()
                ref = sql_str("{}.{}", ref, f"{id_prefix}_id")
            else:
                ref = sql_str("{}", ref)
            alias = unique_label(entity, layer, self.used_aliases)
            self.add_ref(key, entity, ref, alias, joins)
        return self.refs[key]

    def attribute(
        self, entity: str, layer: str, attribute: str, pointer: bool = False
    ) -> SQLRef:
        """
        Reference to an entity's attribute.
        If the attribute uses a lookup table and pointer is True, ref and alias target the foreign key instead of the value.
        """
        key = (entity, attribute, pointer)
        if key in self.refs:
            return self.refs[key]
        used_refs = self.used_refs
        joins: dict[str, dict[str, int]] = {}
        entity_key = (entity, "", False)
        entity_ref: SQLRef
        if entity_key in self.refs:
            entity_ref = self.refs[entity_key]
        else:
            entity_ref = self.layer(entity, layer)
        for k, v in entity_ref.joins.items():
            joins[k] = {**joins.get(k, {}), **v}
        entity_label = entity_ref.ref
        entity_alias = entity_ref.alias
        layer_info = self.conf["layer"][layer]
        info_attributes = layer_info.get("attributes", {})
        layer_mapping = _get_mapping(layer, self.conf, self.batch, self.lang)
        mapping_attributes = layer_mapping.get("attributes", {})
        meta = info_attributes.get("meta", None)
        attr_type = info_attributes.get(attribute, {}).get("type", "categorical")
        rel_table = (
            self.conf["mapping"]["layer"]
            .get(layer, {})
            .get("alignment", {})
            .get("relation")
        )
        if rel_table:
            rel_ent_label = unique_label(f"{entity_alias}_aligned", layer, used_refs)
            table = sql_str("{}.{} {}", self.schema, rel_table, rel_ent_label)
            condition = sql_str(
                f"{entity_label}.alignment_id = {LR}.alignment_id", rel_ent_label
            )
            joins[table] = {**joins.get(table, {}), condition: 1}
            entity_alias = rel_ent_label
            entity_label = sql_str("{}", entity_alias)
        is_glob = info_attributes.get(attribute, {}).get("ref", "") in self.conf.get(
            "globalAttributes", {}
        )
        alias = unique_label(f"{entity_alias}_{attribute}", layer, self.used_aliases)
        ref: str = ""
        if layer_info.get("layerType") == "relation":
            ref = next(
                (
                    attribute
                    for k, v in info_attributes.items()
                    if "entity" in v and v.get("name") == attribute
                ),
                "",
            )
            ref = sql_str(f"{entity_label}.{LR}", ref) if ref else ""
        elif isinstance(meta, dict) and attribute in meta:
            accessor = "->" if attr_type in ("dict", "jsonb") else "->>"
            attr_ph = "{attribute}"
            ref = sql_str(
                f"{entity_label}.{LR}{accessor}{attr_ph}",
                "meta",
                attribute=sql.Literal(attribute),
            )
        elif attr_type in ("categorical", "number", "labels", "image") and not is_glob:
            ref = sql_str(f"{entity_label}.{LR}", attribute)
        if ref:
            return self.add_ref(key, entity, ref, alias, joins)
        ref = unique_label(f"{entity}_{attribute}", layer, used_refs)
        attr_map = mapping_attributes.get(attribute, {})
        rel_key = attr_map.get("key") or attribute
        rel_tab = attr_map.get("name")
        if not rel_tab and not is_glob and attr_type not in ("dict", "jsonb"):
            ref = sql_str(f"{entity_label}.{LR}", attribute)
            return self.add_ref(key, entity, ref, alias, joins)
        rel_tab = rel_tab or (
            f"global_attribute_{attribute}" if is_glob else f"{layer}_{attribute}"
        )
        if pointer:
            ref = entity_alias
            rel_key += "_id"
        else:
            table = sql_str("{}.{} {}", self.schema, rel_tab, ref)
            # rel_alias.rel_key_id = entity.attribute_id
            # e.g. Document_speaker_L.speaker_id = Document.speaker_l_id
            condition = sql_str(
                f"{LR}.{LR} = {entity_label}.{LR}",
                ref,
                f"{rel_key}_id",
                f"{attribute.lower()}_id",
            )
            joins[table] = {**joins.get(table, {}), condition: 1}
        ref = sql_str("{}.{}", ref, rel_key)
        return self.add_ref(key, entity, ref, alias, joins)

    def not_attribute(
        self, entity: str, layer: str, what: str, cast: str = ""
    ) -> SQLRef:
        """
        Column of a layer table that is not an attribute reported in corpus_template.
        """
        key = (entity, what, False)
        entity_ref = self.layer(entity, layer)
        entity_alias = entity_ref.alias
        if key not in self.refs:
            alias = unique_label(f"{entity_alias}_{key[1]}", layer, self.used_aliases)
            ref = sql_str(f"{LR}.{LR}{cast}", entity_alias, key[1])
            self.add_ref(key, entity, ref, alias, entity_ref.joins)
        return self.refs[key]

    def anchor(self, entity: str, layer: str, range: str) -> SQLRef:
        """
        Reference to an anchor. stream -> char_range; time -> frame_range; location -> xy_box
        """
        return self.not_attribute(
            entity,
            layer,
            {"stream": "char_range", "time": "frame_range", "location": "xy_box"}[
                range
            ],
        )


@dataclass
class QueryData:
    """
    Data generated throughout the process of parsing the JSON query
    """

    # the actual results sql string:
    needed_results: str = ""
    # a set of objects needed in the query cte
    entities: set[str] = field(default_factory=set)
    # the metadata about the query that gets given to FE with query results
    meta_json: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # all the select statements in the query cte
    selects: set[str] = field(default_factory=set)
    # joins needed in the query cte
    joins: Joins = field(default_factory=dict)
    # WHERE clauses in the query cte
    conditions: set[str] = field(default_factory=set)
    # a mapping of label to (layer, metadata_about_layer)
    label_layer: LabelLayer = field(default_factory=dict)
    # info about python-side data aggregations to run in callback
    post_processes: dict[int, list[dict]] = field(default_factory=dict)
    manual_track: str = ""
    # the labels of any set in the query
    set_objects: set[str] = field(default_factory=set)
    # the main sequences in the query; note that these aren't hashable, so QueryData cannot be shared across threads
    sqlsequences: list[Any] = field(default_factory=list)
    # all the entity-label-to-attribute references in the query
    all_refs: dict[str, list[str]] = field(default_factory=dict)
    # the SQL interface to get SQL references
    _sql_corpus: SQLCorpus | None = None

    @property
    def sql(self) -> SQLCorpus:
        return self._sql_corpus or SQLCorpus({}, "", "", "")

    def unique_label(
        self,
        label: str = "anonymous",
        layer="__internal",
        references: LabelLayer | None = None,
        obj: dict = dict({}),
    ) -> str:
        return unique_label(label, layer, references or self.label_layer, obj)

    def add_labels(self, query_json: list | dict, references: dict) -> list | dict:
        is_dict = isinstance(query_json, dict)
        new_query_json: list | dict = (
            {} if is_dict else [None for _ in range(len(query_json))]
        )
        key_to_use: None | str = next(
            (l for l in ("unit", "sequence", "set") if l in query_json), None
        )
        if is_dict and key_to_use:
            query_json = cast(dict, query_json)
            layer = query_json[key_to_use].get("layer") or "__internal"
            query_json[key_to_use]["label"] = query_json[key_to_use].get(
                "label"
            ) or self.unique_label(
                layer=layer, references=references, obj=query_json[key_to_use]
            )

        for n, k in enumerate(query_json):
            v = query_json[k] if is_dict else k
            i = k if is_dict else n
            if isinstance(v, (list, dict)):
                v = self.add_labels(v, references)
            new_query_json[i] = v
        return new_query_json


@dataclass
class Config:
    """
    Little object representing current batch and its confguration
    """

    schema: str
    batch: str
    config: dict[str, Any]
    lang: str | None


def _strip_batch(batch: str) -> str:
    """
    Strip batch batch (usually so we can see if it has a language on it)
    """
    batch = batch.rstrip("0123456789")
    if batch.endswith("rest"):
        batch = batch[:-4]
    return batch


def _get_underlang(lang: str | None, config: dict[str, Any]) -> str:
    """
    Get e.g. _en for sparcling, or an empty string for non-partitioned corpora
    """
    underlang = f"_{lang}" if lang else ""
    part_values = config.get("partitions", {}).get("values", [])
    if lang in part_values:
        return underlang
    return ""


def _get_batch_suffix(batch: str, n_batches: int = 2) -> str:
    if batch and n_batches > 1:
        batchsuffix = re.match(r".+?(\d+|rest)$", batch)
        if batchsuffix:
            return batchsuffix.group(1)
    return "0"


def _get_mapping(layer: str, config: Any, batch: str, lang: str) -> dict[str, Any]:
    if layer.lower() == batch.lower():
        layer = config["firstClass"]["token"]
    mapping: dict = config["mapping"]["layer"].get(layer, {})
    if "partitions" in mapping and lang:
        mapping = mapping["partitions"].get(lang, {})
    return mapping


def _get_table(layer: str, config: Any, batch: str, lang: str) -> str:
    table = _get_mapping(layer, config, batch, lang).get("relation", layer)
    # Use batch suffixes if layer == batch (token) or if we're working with segments
    if layer.lower() == batch.lower() or layer.lower() in (
        config["segment"].lower(),
        config["token"].lower(),
    ):
        token_mapping = _get_mapping(config["token"], config, batch, lang)
        n_batches = token_mapping.get("batches", 1)
        batch_suffix: str = _get_batch_suffix(batch, n_batches=n_batches)
        if table.endswith("<batch>"):
            table = table[:-7]
        table += batch_suffix
    return table


def _layer_contains(config: dict[str, Any], parent: str, child: str) -> bool:
    """
    Return whether a parent layer contains a child layer
    """
    child_layer = config["layer"].get(child)
    parent_layer = config["layer"].get(parent)
    if not child_layer or not parent_layer:
        return False
    while parent_layer and (parents_child := parent_layer.get("contains")):
        if parents_child == child:
            return True
        parent_layer = config["layer"].get(parents_child)
    return False


def _is_anchored(config: dict[str, Any], layer: str, anchor: str) -> bool:
    layer_config = config["layer"].get(layer, {})
    if layer_config.get("anchoring", {}).get(anchor):
        return True
    if any(x for x in layer_config.get("anchoring", {}).values()):
        return False  # if *other* anchors are True, this one is False
    child: str = layer_config.get("contains", "")
    if child in config["layer"]:
        return _is_anchored(config, child, anchor)
    return False


def _has_frame_range(config: dict[str, Any]) -> bool:
    for layer in config.get("layer", {}).values:
        if layer.get("anchoring", {}).get("time"):
            return True
    return False


def _bound_label(
    label: str = "",
    query_json: dict[str, Any] = dict(),
    in_scope: bool = False,
) -> bool:
    """
    Look through the query part of the JSON and return False if the label is found in an unbound context
    """
    if not label:
        return False

    query = json.loads(json.dumps(query_json.get("query", [query_json])))
    for obj in query:
        if not isinstance(obj, dict):
            continue
        if obj.get("label") == label:
            return in_scope
        obj = obj.get("constraint", obj)
        if "unit" in obj:
            if obj["unit"].get("label") == label:
                return in_scope
        if "sequence" in obj:
            if obj["sequence"].get("label") == label:
                return in_scope
            reps = _parse_repetition(obj["sequence"].get("repetition", "1"))
            tmp_in_scope = in_scope or (reps != (1, 1))
            for m in obj["sequence"].get("members", []):
                if _bound_label(label, m, tmp_in_scope):
                    return True
        if "logicalExpression" in obj:
            logic = obj["logicalExpression"]
            tmp_in_scope = in_scope or (
                logic.get("naryOperator") == "OR" or logic.get("unaryOperator") == "NOT"
            )
            for a in logic.get("args", []):
                if _bound_label(label, a, tmp_in_scope):
                    return True
        quantor = obj.get("quantification", {}).get("quantor", "")
        # If the quantifier is a NEGATIVE existential (i.e. not EXIST(S))
        if quantor.endswith(("EXIST", "EXISTS")) and quantor not in ("EXIST", "EXISTS"):
            arg = {k: v for k, v in obj.items() if k in ("unit", "sequence", "set")}
            if _bound_label(label, arg, in_scope=True):
                return True

    # Label not found
    return False


def _parse_comparison(
    comparison_object: dict,
) -> tuple[dict[str, Any], str, str, QueryType]:
    left, right, comparator = (
        comparison_object.get(x) for x in ("left", "right", "comparator")
    )
    assert left, KeyError(f"Couldn't find 'left' in comparison ({comparison_object})")
    assert right, KeyError(f"Couldn't find 'right' in comparison ({comparison_object})")
    assert comparator, KeyError(
        f"Couldn't find 'comparator' in comparison ({comparison_object})"
    )

    key = cast(dict[str, Any], left)
    op = cast(str, comparator)
    # op = comparison_object["comparator"]
    # if typ in ("stringComparison", "regexComparison"):
    #     right = cast(str, right)[1:-1]
    # if op in (">=", "<=", ">", "<") and typ != "functionComparison":
    #     typ = "mathComparison"  # Overwrite comparison type
    # return (key, cast(str, op), cast(str, typ), cast(str, right))
    return (key, op, "dummyType", right)


def _label_layer(
    query_json: list | dict[str, Any], depth: int = 0, parent_label: str = ""
) -> LabelLayer:
    """
    Map label to its correct layer, as well as other data:

    {label: (layer, data)}
    """
    out: LabelLayer = {}
    if not isinstance(query_json, (dict, list)):
        return {}
    if isinstance(query_json, list):
        for i in query_json:
            out.update(_label_layer(i, depth=depth + 1, parent_label=parent_label))
    elif isinstance(query_json, dict):
        # todo maybe: does set have members?
        if "set" in query_json:
            if "label" in query_json:
                query_json["_depth"] = depth
                if parent_label and "partOf" not in query_json:
                    query_json["partOf"] = parent_label
                out[query_json["label"]] = (query_json.get("layer", ""), query_json)
            if "label" in query_json["set"]:
                meta = query_json["set"].copy()
                meta["_is_set"] = True
                meta["_depth"] = depth
                if parent_label and "partOf" not in meta:
                    meta["partOf"] = parent_label
                sset = (query_json["set"].get("layer", ""), meta)
                out[query_json["set"]["label"]] = sset
            new_parent_label = query_json.get(
                "partOf", query_json.get("set", {}).get("partOf", parent_label)
            )
            out.update(
                _label_layer(
                    query_json["set"], depth=depth + 1, parent_label=new_parent_label
                )
            )
        elif "group" in query_json:
            gro = query_json["group"]
            if "label" in gro and gro.get("members", []):
                meta = gro.copy()
                meta["_is_group"] = True
                meta["_depth"] = depth
                if parent_label and "partOf" not in meta:
                    meta["partOf"] = parent_label
                sgroup = ("", meta)
                out[gro["label"]] = sgroup

        for i in ["sequence", "members"]:
            if i in query_json:
                part = query_json[i]
                new_parent_label = parent_label
                if isinstance(part, dict) and part.get("label"):
                    part["_depth"] = depth
                    if parent_label and "partOf" not in part:
                        part["partOf"] = parent_label
                    out[part["label"]] = (cast(str, part.get("layer", "")), part)
                    new_parent_label = part.get("partOf", parent_label)
                out.update(
                    _label_layer(part, depth=depth + 1, parent_label=new_parent_label)
                )
        if "label" in query_json and "layer" in query_json:
            query_json["_depth"] = depth
            if parent_label and "partOf" not in query_json:
                query_json["partOf"] = parent_label
            out[query_json["label"]] = (query_json["layer"], query_json)
        for k, v in query_json.items():
            if isinstance(k, (list, dict)):
                out.update(_label_layer(k, depth=depth + 1, parent_label=parent_label))
            if isinstance(v, (list, dict)):
                out.update(_label_layer(v, depth=depth + 1, parent_label=parent_label))
    return out


def _joinstring(joins: Joins) -> str:
    """
    Create a single string of joins from the dict of joins
    """
    strung = [
        f"CROSS JOIN {k}" if not k.startswith("join") else k
        for k, v in joins.items()
        if not (v is True or (isinstance(v, set) and True in v))
        # if v is None
    ]
    last_joins = [
        f"CROSS JOIN {k}" if not k.startswith("join") else k
        for k, v in joins.items()
        if (v is True or (isinstance(v, set) and True in v))
        # if v
    ]
    return "\n".join(strung + last_joins)


def arg_sort_key(d: dict[str, Any] | Any) -> str:
    """
    for use in as sorted(args, key=arg_sort_key), to ensure
    that we always get data in same order and so we can hash
    the resultant SQL query and get the same result

    todo: not sure if all the different value types being handled
    here actually appear in code ... some could be removable
    """
    if not isinstance(d, dict):
        return str(d)
    out: list[str] = []
    for v in d.values():
        if v is None:
            out.append("None")
        elif isinstance(v, (list, tuple, set)):
            for i in v:
                out.append(arg_sort_key(i))
        elif not isinstance(v, dict):
            out.append(str(v))
        else:
            assert isinstance(v, dict)
            out.append(arg_sort_key(v))
    return "".join(out)


def _parse_repetition(repetition: str | dict[str, str]) -> tuple[int, int]:
    if isinstance(repetition, str):
        repetition = {"min": repetition}
    assert "min" in repetition, ValueError(
        "Sequences must define a minimum of repetitions"
    )
    mini: int = int(repetition["min"])
    maxi: int = (
        -1
        if repetition.get("max", "") == "*"
        else int(repetition.get("max", repetition["min"]))
    )
    assert mini > -1, ValueError(
        f"A sequence cannot repeat less than 0 times (encountered min repetition value of {mini})"
    )
    assert maxi < 0 or maxi >= mini, ValueError(
        f"The maximum number of repetitions of a sequence must be greater than its minimum ({maxi} < {mini})"
    )
    return (mini, maxi)


def _flatten_coord(objs: list, operator: str = "OR") -> list:
    """
    Lift all the coordination children of the same type as the current coordination
    and coordinate it at the root level
    """
    ret: list = []
    for o in objs:
        if not isinstance(o, dict):
            ret.append(o)
            continue
        log_op = o.get("logicalExpression", {}).get("operator")
        log_args = o.get("logicalExpression", {}).get("args", [])
        if log_op == operator:
            ret += _flatten_coord(log_args, operator)
            continue
        ret.append(o)
    return ret


def escape_single_quotes(obj: list | dict) -> list | dict:
    is_dict = isinstance(obj, dict)
    ret = {} if is_dict else [1 for _ in range(len(obj))]
    for n, k in enumerate(obj):
        v = obj[k] if is_dict else obj[n]
        if isinstance(v, (dict, list)):
            v = escape_single_quotes(v)
        elif isinstance(v, str):
            v = v.replace("'", "''")
        i = k if is_dict else n
        ret[i] = v  # type: ignore
    return cast(list | dict, ret)

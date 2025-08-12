from typing import Any, cast

import re

from .constraint import _get_constraints, Constraint, Constraints, process_set
from .sequence import SQLSequence
from .sequence_members import Sequence
from .typed import (
    QueryJSON,
    Joins,
    JSONObject,
    ConfigJSON,
    ResultMetadata,
    SQLRef,
    JSON,
    Attribs,
    Details,
    RefInfo,
)
from .utils import (
    Config,
    QueryData,
    SQLCorpus,
    sql_str,
    _flatten_coord,
    _get_table,
    _bound_label,
    _label_layer,
    _get_underlang,
    _is_anchored,
    _parse_comparison,
    _parse_repetition,
)

# TODO: add a count(DISTINCT resX.*) on each plain result table
# this way FE can detect differences and warn user about it
COUNTER = f"""
    res0 AS (SELECT 0::int2 AS rstype,
      jsonb_build_array(count(match_list.*))
       FROM match_list)

"""

ANCHORINGS = ("stream", "time", "location")

LR = "{}"


class ResultsMaker:
    """
    A class to manage the creation of results SQL, data and metadata
    """

    def __init__(
        self, query_json: QueryJSON, conf: Config, all_refs: dict[str, list[str]]
    ) -> None:
        self.conf: Config = conf
        self.config: ConfigJSON = conf.config
        self.schema: str = conf.schema
        self.lang: str = conf.lang or ""
        self.batch: str = conf.batch
        self.segment = cast(str, self.config["segment"])
        self.token = cast(str, self.config["token"])
        self.document = cast(str, self.config["document"])
        self.conf_layer = cast(JSONObject, self.config["layer"])
        self.r = QueryData()
        self.r.all_refs = all_refs
        self.r._sql_corpus = SQLCorpus(self.config, self.schema, self.batch, self.lang)
        tmp_label_layer = _label_layer(query_json.get("query", query_json))
        new_query_json = cast(dict, self.r.add_labels(query_json, tmp_label_layer))
        lifted_quants = cast(list, self.lift_quantifiers(new_query_json["query"]))
        lifted_conjs = self.lift_conjunctions(lifted_quants)
        # Make sure root logicalExpressions are introduced as constraints
        query_json["query"] = [
            {"constraint": x} if "logicalExpression" in x else x for x in lifted_conjs
        ]
        self.query_json = query_json
        self.r.label_layer = _label_layer(self.query_json.get("query", self.query_json))
        self._n = 1
        self._underlang = _get_underlang(self.lang, self.config)

    def lift_conjunctions(self, query_list: list) -> list:
        return [  # lift and flatten conjunctions
            y
            for x in query_list
            for y in (
                _flatten_coord(
                    x["constraint"]["logicalExpression"]["args"], operator="AND"
                )
                if x.get("constraint", {})
                .get("logicalExpression", {})
                .get("naryOperator")
                == "AND"
                else [x]
            )
        ]

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

    def add_query_entities(self, query_json: dict[str, Any]) -> None:
        """
        Look through the query part of the JSON and add entities to the entities list
        """
        query = query_json.get("query", [query_json])
        labels_so_far: set[str] = {e for e in self.r.entities}
        for obj in query:
            if "sequence" in obj:
                seq: Sequence = Sequence(self.r, self.conf, obj)
                sqlseq: SQLSequence = SQLSequence(seq)
                sqlseq.categorize_members()
                for t, _, _, _ in sqlseq.fixed_tokens:
                    original_label: str = cast(str, t.obj["unit"].get("label", ""))
                    if original_label:
                        self.r.entities.add(original_label)
                        if original_label in self.r.label_layer:
                            self.r.label_layer[t.internal_label] = self.r.label_layer[
                                original_label
                            ]
                self.r.sqlsequences.append(sqlseq)
                labels_so_far = labels_so_far.union(
                    {x for x in sqlseq._sequence_references}
                )
                labels_so_far = labels_so_far.union(
                    {x for x in sqlseq._internal_references}
                )
                labels_so_far = labels_so_far.union(
                    {x for x in sqlseq._internal_references.values()}
                )

            elif "logicalExpression" in obj:
                coord = obj["logicalExpression"]
                for arg in coord["args"]:
                    self.add_query_entities(arg)
            elif "unit" in obj:
                unit = obj["unit"]
                layer = obj["unit"].get("layer") or "__internal"
                unit["label"] = unit.get("label") or self.r.unique_label(
                    layer=layer, obj=obj
                )
                if cast(
                    str, unit.get("layer", "")
                ).lower() == self.token.lower() and cast(str, unit.get("label", "")):
                    lab: str = unit["label"].lower()
                    self.r.entities.add(lab)
        return None

    def add_set_objects(self, query_json: dict[str, Any]) -> None:
        """
        Look through the query part of the JSON and add set objects to the objects list
        """
        query = query_json.get("query", [query_json])
        for obj in query:
            if "sequence" in obj:
                seq = obj["sequence"]
                for member in seq["members"]:
                    self.add_set_objects(member)
            elif "set" in obj and cast(str, cast(dict, obj["set"]).get("label", "")):
                self.r.set_objects.add(cast(str, obj["set"]["label"]))
        return None

    def find_set(self, label) -> dict | None:
        for obj in self.query_json["query"]:
            if not isinstance(obj, dict):
                continue
            for k, v in obj.items():
                if not isinstance(v, dict):
                    continue
                if k == "set" and v.get("label") == label:
                    return v
        return None

    def results(self) -> tuple[QueryJSON, QueryData]:
        """
        Build the results section of the postgres query
        """
        # strings = [COUNTER]
        strings = []
        attribs = []

        made: str
        meta: ResultMetadata

        self.add_query_entities(self.query_json)
        self.add_set_objects(self.query_json)

        results = self.query_json.get("results")
        if not results:
            raise ValueError("Results needed in JSON")

        # Check that all entity references are legit
        legal_refs = set("*")
        for obj in self.query_json.get("query", []):
            if "unit" in obj:
                legal_refs.add(cast(dict, obj["unit"]).get("label", ""))
            elif "sequence" in obj:
                sequence: dict[str, Any] = cast(dict[str, Any], obj["sequence"])
                if "repetition" in sequence and _parse_repetition(
                    sequence.get("repetition", "1")
                ) != (1, 1):
                    continue
                legal_refs.add(sequence.get("label", ""))
                members = sequence.get("members", [])
                for m in members:
                    if "unit" in m:
                        legal_refs.add(m["unit"].get("label", ""))
            elif "set" in obj:
                legal_refs.add(cast(dict, obj["set"]).get("label", ""))
                continue

        for result in results:
            if "resultsPlain" in cast(JSONObject, result):
                plain = cast(JSONObject, result["resultsPlain"])
                ents = cast(list[str], plain["entities"])
                for e in ents:
                    assert e in legal_refs, ReferenceError(
                        f"Label {e} cannot be referenced (is not declared or scope-bound)"
                    )
                    self.r.entities.add(e)
                    lay, met = self.r.label_layer.get(e, (None, None))
                    if lay is None and met is None:
                        continue
                    for mem in cast(list, cast(JSONObject, met).get("members", [])):
                        if "label" in mem:
                            self.r.entities.add(mem["label"])

            elif "resultsCollocation" in cast(JSONObject, result):
                coll = cast(JSONObject, result["resultsCollocation"])
                if c := coll.get("center"):
                    assert c in legal_refs, ReferenceError(
                        f"Label {c} cannot be referenced (is not declared or scope-bound)"
                    )
                    self.r.entities.add(cast(str, c).lower())
                # for s in cast(list[str], coll.get("space", [])):
                #    self.r.entities.add(s)
            # elif "resultsAnalysis" in cast(JSONObject, result):
            #     stat = cast(JSONObject, result["resultsAnalysis"])
            #     attr = cast(list[str | dict], stat.get("attributes", []))
            #     for a in attr:
            #         if not isinstance(a, dict) or "attribute" not in a:
            #             continue
            #         lab: str = cast(dict, a)["attribute"].split(".", 1)[0].lower()
            #         assert lab in legal_refs, ReferenceError(
            #             f"Label {lab} cannot be referenced (is not declared or scope-bound)"
            #         )
            #         self.r.entities.add(lab)

        kind: str
        r: JSON

        for i, result in enumerate(results, start=1):
            kind, _r = next((x for x in list(result.items()) if x[0] != "label"), {})
            r = cast(JSONObject, _r)
            # varname = cast(str, r.get("label", f"untitled_{i}"))
            varname = cast(str, result.get("label", f"untitled_{i}"))
            if kind == "resultsPlain":
                context = cast(
                    str,
                    next((x for x in cast(list[str], r.get("context", ["s"]))), "s"),
                )  # list in case of parallel corpus
                # todo: handle 1+ contexts in case of parallel corpus queries
                enti = cast(list[str], r.get("entities", []))
                made, meta = self._kwic(i, varname, context, enti)
            elif kind == "resultsAnalysis":
                made, meta, filter_meta = self.stats(i, varname, r)
                if filter_meta:
                    self.r.post_processes[i] = filter_meta
            elif kind == "resultsCollocation":
                self._add_collocation_selects(r)
                made, meta = self.collocation(i, varname, r)

            strings.append(made)
            attribs.append(meta)

        strings.append(COUNTER)
        self.r.meta_json = {"result_sets": attribs}
        self.r.needed_results = "\n , ".join(strings)
        return self.query_json, self.r

    def _add_collocation_selects(self, result: dict) -> None:
        """
        For collocation query with space, we add the 'space' obj to entities
        so its criteria end up in match_list.

        We do this even when the space object is a set object and otherwise
        not in entities. This might change ... if space is a set, maybe the
        criteria go into the collocation CTE instead of match_list CTE
        """
        # TODO: support a list of references as "space"
        # space = result.get("space", [])
        sql: SQLCorpus = self.r.sql
        space = result.get("space", "")
        feat = cast(str, result.get("attribute", "lemma"))

        if not space:
            center = result["center"]
            if center in self.r.set_objects:
                raise ValueError(f"center cannot be set ({center})")
            else:
                center_ref = sql.layer(center, self.token, pointer=True)
                formed = sql_str(f"{center_ref} AS {LR}", center_ref.alias)
                self.r.selects.add(formed)
                self.r.entities.add(center_ref.alias)
            return None

        # in_entities = False if not space else space[0].lower() in self.r.entities
        layer, _ = self.r.label_layer[space]
        attr_ref = sql.attribute(
            space or result.get("center", ""), layer, feat, pointer=True
        )
        # feat_maybe_id = f"{feat}_id" if need_id and not feat.endswith("_id") else feat
        assert layer == self.token, TypeError("Cannot use a space that is not a token")
        space_ref = sql.layer(space, self.token, pointer=True)
        formed = sql_str(f"{space_ref} AS {LR}", space_ref.alias)
        self._n += 1

        if space not in self.r.set_objects:
            self.r.selects.add(formed)
            self.r.entities.add(space_ref.alias)
            # formed = f"{space}.{feat_maybe_id} AS {space}_{feat_maybe_id}"
            formed = sql_str(f"{attr_ref} AS {LR}", attr_ref.alias)
        # thead.lemma_id AS thead_lemma_id
        else:
            formed = process_set(
                self.conf,
                self.r,
                self._n,
                self.token,
                self.segment,
                self._underlang,
                self.find_set(space) or {},
                seg_label="___seglabel___",
                attribute=feat,
            )

        self.r.selects.add(formed)
        # add entity: thead_lemma_id
        self.r.entities.add(attr_ref.alias)

    def _update_context(self, context: str) -> None:
        """
        Add kwic context joins, selects, needed objects
        """
        lay: str
        lay, _ = self.r.label_layer[context]
        first_class: dict[str, str] = cast(dict[str, str], self.config["firstClass"])
        keys = {first_class[f].lower() for f in {"token", "segment", "document"}}
        err = f"Context not allowed: {lay.lower()} not in {keys}"
        assert lay.lower() in keys, err
        context_ref = self.r.sql.layer(context, lay, pointer=True)
        select = sql_str(f"{context_ref} AS {LR}", context_ref.alias)
        self.r.selects.add(select)
        self.r.entities.add(context_ref.alias)
        return None

    def _process_entity(self, ent: str) -> tuple[list[str], list[Details]]:
        """
        Add kwic metadata and update entities list with requested kwic item
        """
        entities_involved: list[str] = []
        attribs: list[Details] = []
        lay: str
        rest: dict[str, Any]
        lay, rest = self.r.label_layer[ent]

        # sets are simple: just return their name
        if rest.get("_is_set"):
            entities_involved.append(ent)
            attribs.append({"name": ent, "type": "set", "multiple": True})
            return entities_involved, attribs

        # the user might have passed a sequence ...
        members = cast(list, rest.get("members", []))
        # if it is not a sequence or a set:
        if "members" not in rest:
            entities_involved.append(ent)
            mult = False
            typ = self.r.label_layer[ent][0]
            attribs.append({"name": ent, "type": typ, "multiple": mult})
            return entities_involved, attribs

        details: Details = {
            "name": ent,
            "type": "sequence",
            "multiple": True,
            "members": [],
        }

        if rest.get("_is_group"):
            details["type"] = "group"

        for i, mem in enumerate(members):
            if "unit" not in mem:
                continue
            label = cast(str, mem["unit"].get("label", ""))
            if not label:
                # If the token has no label then we don't need to fetch it?
                continue
                # label = f"anonymous_token_from_{ent}_{str(i)}".lower()
                # lay = self.token
            else:
                lay, _ = self.r.label_layer[label]
            if lay == self.token:
                if label not in self.r.set_objects:
                    ent_ref = self.r.sql.layer(label, lay, pointer=True)
                    formed = sql_str(f"{ent_ref} AS {LR}", ent_ref.alias)
                    self.r.selects.add(formed)
                    if label not in self.r.entities:
                        self.r.entities.add(label)
                piece: Details = {"name": label, "type": lay, "multiple": False}
                cast(list, details["members"]).append(piece)
            entities_involved.append(label)

        if all(entities_involved):
            return entities_involved, [details]

        entities_involved = [ent]
        attribs = [{"name": ent, "type": "Token", "multiple": False}]

        return entities_involved, attribs

    def stats(
        self, i: int, varname: str, result: JSONObject
    ) -> tuple[str, ResultMetadata, list[dict[str, Any]]]:
        """
        Process a stats request
        """
        attributes = cast(list[str | dict], result["attributes"])

        functions = cast(list[str], result["functions"])
        filt = cast(JSONObject, result.get("filter", {}))
        made, meta, filter_meta = self._stat_analysis(
            i,
            varname,
            [a for a in attributes if isinstance(a, dict)],
            functions,
            filt,
        )
        return made, meta, filter_meta

    def _kwic(
        self,
        i: int,
        label: str,
        context: str,
        ents: list[str],
    ) -> tuple[str, ResultMetadata]:
        """
        Produce a KWIC query and its JSON metadata
        """
        entout: list[str] = []
        select_extra = ""

        doc_join = ""

        self._update_context(context)
        context_layer = self.r.label_layer[context][0]

        lay: str
        tokens: list[dict] = []

        include_disjunction: bool = False
        if "*" in ents:
            new_ents = [e for e in ents if e != "*"]
            ents = new_ents
            # Tokens in sequences
            for lab, (lay, obj) in cast(dict, self.r.label_layer).items():
                if lay != self.token:
                    continue
                part_of: list[dict[str, str]] = cast(
                    list[dict[str, str]], obj.get("partOf", [])
                )
                if context not in [next(x for x in p.values()) for p in part_of]:
                    continue
                if _bound_label(lab, self.query_json):
                    continue
                is_fixed_token_in_sequence: bool = any(
                    lab in (m.label, m.internal_label)
                    for seq in self.r.sqlsequences
                    for m in seq.get_members()
                )
                if not is_fixed_token_in_sequence:
                    continue
                ents.append(lab)
            # Main tokens
            for u in self.query_json["query"]:
                if not isinstance(u, dict):
                    continue
                if "constraint" in u:
                    constraint = cast(dict, u["constraint"])
                    is_or = (
                        constraint.get("logicalExpression", {}).get("naryOperator")
                        == "OR"
                    )
                    include_disjunction = include_disjunction or (
                        is_or
                        and any(
                            "unit" in x or "sequence" in x and "quantor" not in x
                            for x in cast(
                                list,
                                constraint["logicalExpression"]["args"],
                            )
                        )
                    )
                if "unit" not in u:
                    continue
                part_of = cast(
                    list[dict[str, str]], cast(dict, u["unit"]).get("partOf", [])
                )
                if context not in [next(x for x in p.values()) for p in part_of]:
                    continue
                lab = cast(dict, u["unit"]).get("label")
                if not lab:
                    continue
                ents.append(cast(str, lab))

        for e in ents:
            lay, meta = self.r.label_layer[e]
            # todo: if group, add ARRAY[]
            if e in self.r.set_objects:
                select = process_set(
                    self.conf,
                    self.r,
                    self._n,
                    self.token,
                    self.segment,
                    self._underlang,
                    self.find_set(e) or {},
                    seg_label="___seglabel___",
                    attribute="___tokenid___",
                    label=e,
                )
                # cannot be lowercased because it is a subquery and may have WHERE
                self.r.selects.add(select)
                self.r.entities.add(e)
                continue

            if lay == self.token:
                is_fixed_token_in_sequence = any(
                    m.label == e
                    for seq in self.r.sqlsequences
                    for m in seq.get_members()
                )
                if not is_fixed_token_in_sequence and e not in self.r.set_objects:
                    ent_ref = self.r.sql.layer(e, lay, pointer=True)
                    select = sql_str(f"{ent_ref} AS {LR}", ent_ref.alias)
                    self.r.selects.add(select)
                    self.r.entities.add(ent_ref.alias)

        for e in ents:
            entities_list, attributes = self._process_entity(e)
            conf_layer_info: dict[str, Any] = cast(
                dict[str, Any], self.conf_layer.get(lay, {})
            )
            if (
                isinstance(attributes, list)
                and isinstance(attributes[0], dict)
                and attributes[0].get("type", "") in ("group", "sequence")
            ):
                entout += [cast(dict, attributes[0]).get("name", "")]
                # entout += [f"ARRAY[{', '.join(entities_list)}]"]
            elif conf_layer_info.get("contains", "").lower() == self.token.lower():
                container_lab = self.r.unique_label(
                    f"{e}_container", "_internal", self.r.sql.used_aliases
                )
                cont_tok_ref = self.r.sql.layer(
                    "contained_token", self.token, pointer=True
                )
                cont_tok_stream_ref = self.r.sql.anchor(
                    "contained_token", self.token, "stream"
                )
                ent_lay, _ = self.r.label_layer[e]
                ent_stream_ref = self.r.sql.anchor(e, ent_lay, "stream")
                cont_tok_tab: str = next(x for x in cont_tok_ref.joins)
                select = sql_str(
                    f"""(SELECT array_agg({cont_tok_ref})
FROM {cont_tok_tab}
WHERE {ent_stream_ref} && {cont_tok_stream_ref}
) AS {LR}""",
                    container_lab,
                )
                self.r.selects.add(select)
                self.r.entities.add(container_lab)
                entout += [container_lab]
            else:
                entout += entities_list
            tokens += attributes

        ents_form: str = ", ".join(entout)
        doc_join = ""
        extras: list[str] = []
        frame_ranges: list[dict[str, Any]] = []

        if _is_anchored(self.config, context_layer, "time"):
            out_ref = self.r.sql.anchor(context, context_layer, "time")
            self.r.selects.add(sql_str(f"{out_ref} AS {LR}", out_ref.alias))
            self.r.entities.add(out_ref.alias)
            fr = sql_str(
                "array[lower(match_list.{}), upper(match_list.{})]",
                out_ref.alias,
                out_ref.alias,
            )
            extras.append(fr)
            frame_ranges.append(
                {
                    "name": out_ref.alias,
                    "type": "list[int]",
                    "multiple": True,
                }
            )

        if extras:
            formed = ", ".join(extras)
            select_extra = ", " + formed

        attribs = self._make_attribs(context, context_layer, tokens, frame_ranges)

        if include_disjunction:
            ents_form = (
                "disjunction_matches"
                if not ents_form
                else f"{ents_form}, disjunction_matches"
            )
            attribs[1]["data"].append(
                {"name": "disjunction_matches", "type": "set", "multiple": True}
            )

        out = f"""
            res{i} AS ( SELECT DISTINCT
            {i}::int2 AS rstype,
            jsonb_build_array({context}, jsonb_build_array({ents_form}) {select_extra})
        FROM
            match_list
            {doc_join}
        )
        """
        metadata: ResultMetadata = {
            "attributes": attribs,
            "name": label,
            "type": "plain",
        }
        return out, metadata

    def _get_label_layer(self, name: str) -> None | tuple[str, str]:
        """
        Get a label/layer with layer matching name, or return None
        """
        return next(
            (
                (k, v)
                for k, (v, _) in self.r.label_layer.items()
                if v.lower() == name.lower()
            ),
            None,
        )

    def _make_attribs(
        self,
        context: str,
        context_layer: str,
        tokens: list[dict],
        frame_ranges: list[dict],
    ) -> list[dict]:
        """
        Format kwic metadata for queries
        """

        out: list[dict]

        if not _is_anchored(self.config, context_layer, "time"):
            out = [
                {
                    "name": "identifier",
                    "label": context,
                    "layer": context_layer,
                    "type": "str|int",
                    "multiple": False,
                },
                {
                    "name": "entities",
                    "multiple": True,
                    "data": tokens,
                    "type": "list[dict]",
                },
            ]
            return out

        out = [
            {
                "name": "identifier",
                "label": context,
                "layer": context_layer,
                "type": "str|int",
                "multiple": False,
            },
            {
                "name": "entities",
                "multiple": True,
                "data": tokens,
                "type": "list[dict]",
            },
            # {"name": "document_id", "type": "number", "multiple": False},
            # {"name": "agent", "type": "str", "multiple": False},
            {
                "name": "frame_ranges",
                "type": "list[dict]",
                "multiple": True,
                "data": frame_ranges,
            },
        ]
        return out

    def _process_filters(self, filt: JSONObject) -> tuple[str, list[dict[str, Any]]]:
        """
        Get a where string and metadata for stat filters
        """
        err = "non-simple comparison not supported here yet"
        if not filt:
            return "", []
        out: list[dict[str, Any]] = []
        wheres: set[str] = set()
        comps: list[dict] = cast(
            list[dict], [f.get("comparison") for f in cast(dict, filt)]
        )
        for comp in comps:
            left, comparator, _, right = _parse_comparison(comp)
            left_str = left.get("label")
            right_str = next(x for x in cast(dict, right).values())
            if not left_str or not right_str:
                continue
            wheres.add(" ".join([left_str, comparator, right_str]))
            # wheres.add(f"{entity} {operator.replace('=','~') if type == 'regexComparison' else operator} '{text}'")

        if wheres:
            strung = " WHERE " + " AND ".join(wheres)
        else:
            strung = ""
        return strung, out

    def _stat_analysis(
        self,
        i: int,
        label: str,
        attributes: list[dict[str, Any]],
        functions: list[str],
        filt: JSONObject,
    ) -> tuple[str, ResultMetadata, list[dict[str, Any]]]:
        """
        Produce a frequency table and its JSON metadata
        """
        count_entities: dict[str, str] = {
            x["entity"]: "" for x in attributes if "entity" in x
        }
        assert len(count_entities) < 2, RuntimeError(
            f"Cannot reference more than one entity in the attributes of an analysis {', '.join(count_entities)})"
        )
        counts: list[str] = []
        for func in functions:
            if func.lower().startswith("freq"):
                if not count_entities:
                    counts.append(f"count(*) AS {func.lower()}")
                    continue
                count_entity = next(ce for ce in count_entities)
                counts.append(f"count(DISTINCT {count_entity}) AS {func.lower()}")
                entity_layer, _ = self.r.label_layer[count_entity]
                conf_map = cast(dict, self.config["mapping"])
                token_mapping = conf_map["layer"].get(self.token, {})
                if "partitions" in token_mapping and self.lang:
                    token_mapping = token_mapping["partitions"].get(self.lang, {})
                mapping: dict = conf_map["layer"].get(entity_layer, {})
                if "partitions" in mapping and self.lang:
                    mapping = mapping["partitions"].get(self.lang, {})
                table = _get_table(entity_layer, self.config, self.batch, self.lang)
                el = entity_layer.lower()
                lab_n = 1
                while (el_lab := f"{el[0]}{lab_n}") in self.r.label_layer:
                    lab_n += 1
                count_entities[count_entity] = el_lab
                count_total = (
                    f"""(SELECT count({el_lab})
    FROM {self.schema}.{table} {el_lab}"""
                    + """
    {joins}
    WHERE {wheres}) AS {total_label}"""
                )
                counts.append(count_total)
            else:
                raise NotImplementedError("TODO?")
        if counts:
            jcounts = " , " + " , ".join(counts)
        else:
            jcounts = " "
        funcstr = " , ".join(functions)
        jjoins: list[str] = []
        jwheres: list[str] = []
        jgroups: list[str] = []
        parsed_attributes: list[tuple[str, RefInfo]] = []
        for att in attributes:
            if "entity" in att:
                continue
            constraint: Constraint = Constraint(
                att,
                "=",  # placeholder,
                att,  # placeholder
                "",  # placeholder
                "",  # placeholder
                self.conf,
                "",  # placeholder
                self.r.label_layer,
            )
            # fix = att.replace(".", "_")
            ref, ref_info = constraint.get_sql_expr(att)
            for formed_table, formed_conditions in constraint._joins.items():
                self.r.joins[formed_table] = True
                conds: set = set()
                if isinstance(formed_conditions, set):
                    conds = formed_conditions
                else:
                    conds.add(formed_conditions)
                for c in conds:
                    if not isinstance(c, str):
                        continue
                    self.r.conditions.add(c)
            for condition in constraint._conditions:
                self.r.conditions.add(condition)
            # TODO: use sql here
            alias = (ref_info.get("meta") or {}).get("str", ref)
            alias = re.sub("[^a-zA-Z0-9_]", "_", alias)
            alias = alias.lstrip("_").rstrip("_")
            # The method below does not work for sub-attributes of global attributes
            # if "sql" in ref_info:
            #     alias = cast(SQLRef, ref_info["sql"]).alias
            self.r.selects.add(ref + sql_str(" AS {}", alias))
            self.r.entities.add(alias)
            parsed_attributes.append((alias, ref_info))
            if (
                not count_entities
                or "attribute" not in att
                or "." not in att["attribute"]
            ):
                continue
            entity, entity_lab = next(x for x in count_entities.items())
            entity_layer, _ = self.r.label_layer[entity]
            prefix, *_ = att["attribute"].split(".")
            prefix_layer, _ = self.r.label_layer[prefix]
            anchorings = [
                a
                for a in ANCHORINGS
                if _is_anchored(self.config, prefix_layer, a)
                and _is_anchored(self.config, entity_layer, a)
            ]
            assert anchorings, RuntimeError(
                f"Layer {prefix_layer} ({prefix}) does not share an anchoring with layer {entity_layer} ({entity_lab})"
            )
            # prefix_table = _get_table(prefix_layer, self.config, self.batch, self.lang)
            # join_formed = f"{self.schema}.{prefix_table} {prefix}"
            # if join_formed != f"{self.schema}.{table} {entity_lab}":
            #     jjoins.append(join_formed)
            where_anchors = " OR ".join(
                sql_str("{} && ", self.r.sql.anchor(prefix, prefix_layer, a).alias)
                + self.r.sql.anchor(entity_lab, entity_layer, a).ref
                for a in anchorings
            )
            jwheres.append(where_anchors)
            # self.r.selects.update({f"{prefix}.{a} AS {prefix}_{a}" for a in anchorings})
            jgroups = [
                self.r.sql.anchor(prefix, prefix_layer, a).alias for a in anchorings
            ]
            self.r.entities.update({x for x in jgroups})
        assert parsed_attributes, RuntimeError(
            f"Need at least one *attribute* referenced in the analysis"
        )
        if count_entities:
            count_entity_layer, _ = self.r.label_layer[next(x for x in count_entities)]
            total_label = f"total_{count_entity_layer.lower()}"
            funcstr += f", {total_label}"
            jcounts = jcounts.format(
                joins=" CROSS JOIN " + " CROSS JOIN ".join(jjoins) if jjoins else "",
                wheres=" AND ".join(jwheres),
                total_label=total_label,
            )
        nodes = " , ".join(p for p, _ in parsed_attributes)
        wheres, filter_meta = self._process_filters(filt)
        out = f"""
            res{i} AS ( SELECT
                {i}::int2 AS rstype,
                jsonb_build_array({nodes}, {funcstr})
            FROM
                (
                    SELECT
                        {nodes}
                        {jcounts}
                    FROM
                        match_list
                    GROUP BY {nodes}{', '+','.join(jgroups) if jgroups else ''}
                ) x {wheres} )
        """
        attribs: Attribs = []
        # for att in attributes:
        for attr, info in parsed_attributes:
            # lab, feat = att.split(".", 1)
            # lay = self.r.label_layer[lab][0]
            lab = attr.split(".")[-1]
            lay = info.get("layer", self.r.label_layer.get(lab, ("", None))[0])
            typed = f"{lay}.{lab}"
            attribs.append({"name": attr, "type": typed})
        for func in functions:
            attribs.append({"name": func, "type": "aggregate"})
        if count_entities:
            count_entity_layer, _ = self.r.label_layer[next(x for x in count_entities)]
            attribs.append(
                {"name": f"total_{count_entity_layer.lower()}", "type": "aggregate"}
            )
        meta: ResultMetadata = {
            "attributes": attribs,
            "name": label,
            "type": "analysis",
        }
        return out, meta, filter_meta

    def _space_item(self, item: str) -> tuple[set[str], Joins]:
        """
        Unused method: when collocation space is not in self.r.entities,
        the joins/wheres do not happen in match_list and would need to
        happen in the collocation cte.

        Right now though, we add space to entities. If this changes,
        we use this data to format the joins and wheres inside the collation cte
        """
        if item.lower() in self.r.entities:
            return set(), {}

        wheres: set[str] = set()
        joins: Joins = {}
        lay: str
        rest: dict[str, Any]
        lay, rest = self.r.label_layer[item]
        cons: JSONObject = rest.get("constraints", {})

        if not cons:
            return wheres, joins

        constraints: Constraints | None = _get_constraints(
            cons,
            lay,
            item,
            self.conf,
            self.r.sql,
            n=self._n,
            label_layer=self.r.label_layer,
            entities=self.r.entities,
            part_of=cast(list[dict[str, str]], rest.get("partOf", [])),
            set_objects=self.r.set_objects,
            allow_any=True,
        )

        if constraints is not None:
            self._n = constraints._n + 1
            constraints.make()
            cond = constraints.conditions()
            if cond:
                wheres.add(cond)
            for k, v in constraints.joins().items():
                joins[k] = v

        return wheres, joins

    def _freq_n_table(self) -> str:
        """
        Get the total word count table (it has one column, freq)
        """
        batch: str = self.batch
        if batch.endswith("rest"):
            batch = batch[:-4]
        else:
            batch = batch.rstrip("0123456789")
        return batch + "_n"

    def _freq_table(self) -> str:
        """
        Get freq 'cube' table for collocation data
        """
        batch: str = self.batch
        if batch.endswith("rest"):
            batch = batch[:-4]
        else:
            batch = batch.rstrip("0123456789")
        return batch + "_freq"

    def _other_fields(self, feature: str, freq_table: str) -> str:
        """
        Generate the IS NULL lines for unused fields in collocation queries (uncubing)
        """
        fields: dict[str, int] = {}
        att: str
        data: dict[str, str | bool | dict[str, JSONObject]]
        config: dict[str, Any] = cast(dict[str, Any], self.config)
        layers_config: dict[str, Any] = config["layer"]
        token_info: dict[str, Any] = cast(dict[str, Any], layers_config[self.token])
        for att, data in token_info["attributes"].items():
            field = att
            if att == feature:
                continue
            if data["type"] in ("text", "dict"):
                field = field + "_id"
            fields[field] = 1
        if self.lang:
            for lay, info in layers_config.items():
                named = self.token + "@" + self.lang
                if lay.lower() != named.lower():
                    continue
                for att, data in info["attributes"].items():
                    field = att
                    if att == feature:
                        continue
                    if data["type"] in ("text", "jsonb"):
                        field = field + "_id"
                    fields[field] = 1

        if not fields:
            return ""

        formed = [f"{freq_table}.{a} IS NULL" for a in fields]
        return " WHERE " + " AND ".join(formed)

    @staticmethod
    def _parse_window(window: dict[str, str], center: str | None) -> str:
        """
        Parse the x..y format window into an SQL string
        """
        if not window:
            return ""
        # a, b = window.split("..", 1)
        a, b = (
            cast(str, window.get("leftSpan", "1")).strip(),
            cast(str, window.get("rightSpan", "1")).strip(),
        )
        if "*" in a and "*" in b:
            return ""
        elif "*" not in a and "*" in b:  # *..5
            return f">= {center} + ({a})"
        elif "*" in a and "*" not in b:  # 3..*
            return f"<= {center} + ({b})"
        else:  # 3..4
            return f"BETWEEN {center} + ({a}) AND {center} + ({b})"

    @staticmethod
    def _within_sent(segment_id, seg_name: str = "__seglabel__", **kwargs) -> str:
        """
        If we are limiting the collocation to the sentence, make that condition here

        Right now it is not controllable. Could fail if query doesn't involve segment data maybe?
        """
        return f"AND tx.{segment_id} = match_list.{seg_name}"

    def collocation(
        self,
        i: int,
        label: str,
        result: JSONObject,
    ) -> tuple[str, ResultMetadata]:
        """
        Generate a string query and dict of query metadata

        self is the ResultsMaker object -- all this code could be methods on it,
        but danny put them here because that file is getting large...
        """
        # TODO: support list of references as "space"
        # space = cast(list[str], result.get("space", []))
        space = cast(str, result.get("space", ""))
        center = cast(str | None, result.get("center"))
        assert not (space and center), "Only one of space/center allowed!"
        freq_n = self._freq_n_table()
        freq_table = self._freq_table()
        windowed = self._parse_window(
            cast(
                dict[str, str],
                result.get("window", {"leftSpan": "*", "rightSpan": "*"}),
            ),
            center,
        )
        feat = cast(str, result.get("attribute", "lemma"))
        attribs = cast(JSONObject, self.conf_layer[self.token])["attributes"]
        assert isinstance(attribs, dict)
        att_feat = cast(JSONObject, cast(JSONObject, attribs)[feat])
        is_text = cast(str, att_feat.get("type", "")) == "text"

        seg_lab: str = ""  # the segment label of center's parent

        need_id = feat in attribs and is_text
        feat_maybe_id = f"{feat}_id" if need_id and not feat.endswith("_id") else feat
        space_feat, lany, rbrack = "", "", ""
        if space:
            space_feat = f"{space}_{feat_maybe_id}"
            if space in self.r.set_objects:
                lany = " ANY ( "
                rbrack = " ) "
        elif center and (token_meta := self.r.label_layer.get(center)):
            seg_depth = 999  # start with a ridiculously deep value
            # Use the label of the first segment layer found in label_layer as a fallback
            seg_lab = next(
                (
                    l
                    for l, p in self.r.label_layer.items()
                    if p[0].lower() == self.segment.lower()
                ),
                "",
            )
            # Now go through the chain of center's "partOf"s and choose the highest parent segment
            part_ofs: list[dict[str, str]] = cast(
                list[dict[str, str]], token_meta[1].get("partOf", [])
            )
            while True:
                if not part_ofs:
                    break
                new_part_ofs: list[dict[str, str]] = []
                for part in part_ofs:
                    part_of = next(x for x in part.values())
                    if part_of not in self.r.label_layer:
                        continue
                    parent_meta = self.r.label_layer[part_of]
                    if parent_meta[0].lower() == self.segment.lower():
                        depth = cast(int, parent_meta[1].get("_depth", 999))
                        if depth < seg_depth:
                            seg_lab = part_of
                            seg_depth = depth
                    new_part_ofs += cast(
                        list[dict[str, str]], parent_meta[1].get("partOf", [])
                    )
                part_ofs = new_part_ofs

        token_id = f"{self.token}_id"
        segment_id = f"{self.segment}_id"

        null_fields = self._other_fields(feat, freq_table)
        feat_tab: str = feat
        config: dict[str, dict] = cast(dict[str, dict], self.config)
        mapping: dict[str, Any] = config["mapping"]["layer"].get(self.token, {})
        if mapping:
            attributes: dict[str, Any] = mapping.get("attributes", {})
            if self.lang and (partitions := mapping.get("partitions")):
                attributes = partitions.get(self.lang, {}).get("attributes", {})
            feat_tab = attributes.get(feat, {}).get("name", feat)
        # feat_tab = f"{feat}{self._underlang}"
        within_sent = self._within_sent(segment_id, seg_lab)

        if is_text:
            join_for_text_field = f"JOIN {self.schema}.{feat_tab} ON {feat_tab}.{feat_maybe_id} = x.{feat_maybe_id}"
        else:
            join_for_text_field = ""

        if space:
            if need_id:
                cte = f"""
                    collocates{i} AS (
                        SELECT {feat_tab}.{feat_maybe_id}
                        FROM match_list
                            CROSS JOIN {self.schema}.{feat_tab} {feat_tab}
                        WHERE {feat_tab}.{feat_maybe_id} = {lany}{space_feat}{rbrack}),
                """
            else:
                select_feat = space_feat
                if space in self.r.set_objects:
                    select_feat = f"unnest({space_feat})"
                cte = f"""
                    collocates{i} AS (
                        SELECT {select_feat} AS {feat_maybe_id}
                        FROM match_list),
                """
        else:
            cte = f"""
            collocates{i} AS (
                SELECT tx.{feat_maybe_id}
                FROM match_list
                        JOIN {self.schema}.{self.batch} tx ON tx.{token_id} {windowed}
                    AND tx.{token_id} <> {center}
                    {within_sent}),
            """

        out = f"""
            {cte}
            resXn{i} AS (SELECT count(*) AS freq FROM collocates{i}),
            res{i} AS
                (SELECT {i}::int2 AS rstype,
                    jsonb_build_array({feat}, o, e)
                FROM (SELECT {feat}, o, 1. * x.freq / {freq_n}.freq * resXn{i}.freq AS e
                    FROM (SELECT {feat_maybe_id}, freq, count(*) AS o
                        FROM collocates{i}
                                JOIN {self.schema}.{freq_table} USING ({feat_maybe_id})
                        {null_fields}
                        GROUP BY {feat_maybe_id}, freq) x
                            {join_for_text_field}
                            CROSS JOIN {self.schema}.{freq_n}
                            CROSS JOIN resXn{i}) x)
        """

        meta_attribs: list[dict[str, str]] = [
            {"name": "Text", "type": "str"},
            {"name": "O", "type": "int"},
            {"name": "E", "type": "real"},
        ]

        meta: ResultMetadata = {
            "attributes": meta_attribs,
            "name": label,
            "type": "collocation",
        }
        return out, meta

import json
import traceback

from lark.exceptions import UnexpectedToken
from typing import cast, Any

from .cqp_to_json import full_cqp_to_json
from .dqd_parser import convert
from .textsearch_to_json import textsearch_to_json
from .typed import JSONObject
from .utils import _get_all_attributes, _get_all_labels


def process_refs(
    conf: dict,
    obj: list | dict,
    labels: dict = {},
    recent_layer: str = "",
    recent_label: str = "",
) -> dict[str, set[str]]:
    """
    Check all the unit references in the list/dict (ultimately the JSON query)
    and map all the unit labels to their attribute references
    """
    ret: dict[str, set[str]] = {}
    if isinstance(obj, list):
        for x in obj:
            if not isinstance(x, (dict, list)):
                continue
            for l, l_attrs in process_refs(
                conf,
                x,
                labels=labels,
                recent_layer=recent_layer,
                recent_label=recent_label,
            ).items():
                ret[l] = ret.get(l, set()).union(l_attrs)
        return ret
    if "unit" in obj:
        recent_layer = obj["unit"].get("layer", "")
        recent_label = obj["unit"].get("label", "")
        assert recent_layer in conf["layer"], ReferenceError(
            f"Could not find a layer named '{recent_layer}' in this corpus"
        )
        if obj_l := obj["unit"].get("label"):
            ret[obj_l] = set()
    if "reference" in obj and recent_layer:
        ref = obj["reference"]
        # attrs = conf["layer"].get(recent_layer, {}).get("attributes", {})
        attrs = _get_all_attributes(recent_layer, conf)
        if "." in ref:
            refname, reffield, *_ = ref.split(".")
            attr = attrs.get(refname, {})
            glob_attr = attr.get("ref", "")
            dict_keys = attr.get("keys", {})
            reflayer = labels.get(refname)
            assert refname in attrs or reflayer, ReferenceError(
                f"Invalid reference to '{ref}' under {recent_layer}"
            )
            assert not glob_attr or reffield in conf["globalAttributes"].get(
                glob_attr, {}
            ).get("keys", {}), ReferenceError(
                f"No sub-attribute named '{reffield}' on global attribute '{refname}'"
            )
            assert not reflayer or reffield in _get_all_attributes(
                reflayer, conf
            ), ReferenceError(f"No attribute named '{reffield}' on entity '{refname}'")
            assert not dict_keys or reffield in dict_keys, ReferenceError(
                f"No sub-attribute named '{reffield}' on attribute '{refname}' of layer {recent_layer}"
            )
            if refname and reffield not in (refs := ret.get(refname, set())):
                ret[refname] = refs.union({reffield})
        else:
            assert ref in attrs or ref in labels, ReferenceError(
                f"Could not find an attribute named '{ref}' on layer {recent_layer}"
            )
            if recent_label and ref not in (refs := ret.get(recent_label, set())):
                ret[recent_label] = refs.union({ref})
    if obj.get("attribute", "").count(".") == 1:
        _, aname = obj["attribute"].split(".")
        assert any(
            aname in _get_all_attributes(x, conf) for x in conf["layer"]
        ), ReferenceError(
            f"Could not find an attribute named '{aname}' on any layer ({obj['attribute']})"
        )
        if recent_label and ref not in (refs := ret.get(recent_label, set())):
            ret[recent_label] = refs.union({aname})
    for x in obj.values():
        if not isinstance(x, (dict, list)):
            continue
        for l, l_attrs in process_refs(
            conf, x, labels=labels, recent_layer=recent_layer, recent_label=recent_label
        ).items():
            ret[l] = ret.get(l, set()).union(l_attrs)
    return ret


async def validate(
    query: str = "",
    kind: str = "json",
    **kwargs: dict[str, Any],
) -> JSONObject:
    """
    Validate a JSON/DQD query. This is not an endpoint, it is called by sock.py
    """
    conf: dict[str, Any] = {}
    if kwargs:
        conf = cast(dict[str, Any], kwargs).get("config", {}).get(kwargs.get("corpus"))
    result: JSONObject = {}
    if kind == "json":
        try:
            json_query = json.loads(query)
            result = {
                "kind": "json",
                "valid": True,
                "action": "validate",
                "status": 200,
            }
        except json.JSONDecodeError as e:
            result = {
                "kind": "json",
                "valid": False,
                "action": "validate",
                "error": str(e),
                "status": 400,
            }
    elif kind == "dqd":
        try:
            json_query = convert(query, conf)
            result = {
                "kind": "dqd",
                "valid": True,
                "action": "validate",
                "json": json_query,
                "status": 200,
            }
        except Exception as err:
            tb = traceback.format_exc()
            print("Error during DQD->JSON:", err, tb)
            all_errors: list[JSONObject] = []
            if isinstance(err, UnexpectedToken):
                error = cast(UnexpectedToken, err)
                error_obj = {
                    "end_line": error.line,
                    "end_column": max(error.column - 1, 0),
                    "end_pos": max((error.pos_in_stream or 1) - 1, 0),
                }
                if th := error.token_history:
                    for t in th:
                        val = t.value
                        val_len = len(val)
                        error_obj["start_pos"] = max(
                            error_obj.get("end_pos", 0) - val_len, 0
                        )
                        error_obj["line"] = max(
                            error_obj.get("end_line", 0) - val.count("\n"), 0
                        )
                        error_obj["column"] = max(
                            error_obj.get("end_column", 0) - val_len, 0
                        )
                        error_obj["type"] = t.type
                        error_obj["value"] = val
                        all_errors.append(cast(JSONObject, error_obj))
                else:
                    error_obj["start_pos"] = error_obj.get("end_pos", 0)
                    error_obj["line"] = error_obj.get("end_line", 0)
                    error_obj["column"] = error_obj.get("end_column", 0)
                    all_errors.append(cast(JSONObject, error_obj))
            result = {
                "kind": "dqd",
                "valid": False,
                "action": "validate",
                "error": str(err),
                "errorList": cast(JSONObject, all_errors),
                "status": 400,
                "traceback": tb,
            }
    elif kind == "cqp":
        try:
            json_query = full_cqp_to_json(query, conf)
            # plain text search
            result = {
                "kind": "cqp",
                "valid": True,
                "action": "validate",
                "json": json_query,
                "status": 200,
            }
        except Exception as e:
            result = {
                "kind": "cqp",
                "valid": False,
                "action": "validate",
                "error": str(e),
                "status": 400,
            }
    elif kind == "text":
        try:
            # plain text search
            json_query = textsearch_to_json(query, conf)
            result = {
                "kind": "text",
                "valid": True,
                "action": "validate",
                "json": json_query,
                "status": 200,
            }
        except Exception as e:
            result = {
                "kind": "text",
                "valid": False,
                "action": "validate",
                "error": str(e),
                "status": 400,
            }
    if result.get("valid"):
        try:
            all_labels = _get_all_labels(json_query)
            all_refs = process_refs(conf, json_query, labels=all_labels)
            result["all_refs"] = {k: sorted(v) for k, v in all_refs.items()}  # type: ignore
        except Exception as e:
            result = {
                "kind": kind,
                "valid": False,
                "action": "validate",
                "error": str(e),
                "status": 400,
            }
    return result

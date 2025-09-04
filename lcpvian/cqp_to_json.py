"""
cqp_to_json.py: parse and convert to JSON a CQPWeb Query Language query
as defined in the CQPWeb manual at https://cwb.sourceforge.io/files/CQP_Manual/2.html
"""

from typing import Any
from lark import Lark
from lark.lexer import Token

import os
import re

from .utils import _get_all_labels

PARSER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "parser"))
PARSER_FILES = [os.path.join(PARSER_PATH, f) for f in sorted(os.listdir(PARSER_PATH))]

cqp_grammar_fn: str = next(
    (f for f in PARSER_FILES if re.match(r".*cqp[^/]*\.lark$", f)), ""
)
assert os.path.isfile(
    cqp_grammar_fn
), f"Could not find a valid CQP lark file in the current directory"
cqp_grammar: str = open(cqp_grammar_fn).read()

cqp_parser = Lark(cqp_grammar, parser="earley", start="top")


def get_leaf_value(node: Any) -> str:
    out: str
    try:
        out = node.value
    except:
        out = get_leaf_value(node.children[0])
    return out


def nget(node: Any, prop: str) -> Any:
    out: Any
    try:
        out = next(
            (c for c in node.children if not isinstance(c, Token) and c.data == prop),
            None,
        )
    except:
        out = None
    return out


def process_quantifier(quantifier, range: list[int]) -> list[int]:
    if quantifier:
        r: Any = nget(quantifier, "range")
        if r:
            n_exact: int = int(
                next(
                    (
                        c.value
                        for c in r.children
                        if isinstance(c, Token) and c.type == "RANGE_EXACT"
                    ),
                    -1,
                )
            )
            if n_exact >= 0:
                range = [n_exact, n_exact]
            else:
                min: int = int(
                    next(
                        (
                            c.value
                            for c in r.children
                            if isinstance(c, Token) and c.type == "RANGE_MIN"
                        ),
                        0,
                    )
                )
                max: int = int(
                    next(
                        (
                            c.value
                            for c in r.children
                            if isinstance(c, Token) and c.type == "RANGE_MAX"
                        ),
                        -1,
                    )
                )
                range = [min, max]
        else:
            value: str = get_leaf_value(quantifier)
            if value == "+":
                range[1] = -1
            elif value == "?":
                range[0] = 0
            elif value == "*":
                range[0] = 0
                range[1] = -1
    return range


def process_brackets(node: Any) -> dict:
    section: Any = nget(node, "node_section")
    vp: Any = nget(node, "vp")
    query: Any = nget(node, "query")

    ir = nget(query, "inner_relation")
    if query and ir:
        op: str = "="
        if nget(ir, "not_"):
            op = "!="
        at: str = get_leaf_value(nget(query, "attribute"))
        if at == "word":
            at = "form"  # hack
        value: str = next(c for c in query.children if isinstance(c, Token)).value
        right: dict[str, Any] = {"regex": {"pattern": "^" + value[1:-1] + "$"}}
        if nget(query, "modifier") and get_leaf_value(nget(query, "modifier")) == "%l":
            right = {"string": value[1:-1]}
        return {
            "comparison": {"left": {"reference": at}, "comparator": op, "right": right}
        }

    elif section:
        processed_section: dict
        if nget(section, "not_"):
            processed_section = {
                "logicalExpression": {
                    "unaryOperator": "NOT",
                    "args": [process_brackets(section)],
                }
            }
        else:
            processed_section = process_brackets(section)

        if vp:
            disj: Any = nget(vp, "or_")
            operator: str = "OR" if disj else "AND"
            return {
                "logicalExpression": {
                    "naryOperator": operator,
                    "args": [processed_section, process_brackets(vp)],
                }
            }
        else:
            return processed_section

    return {}


def process_node(node: Any, members: list, conf: dict[str, Any] = {}) -> None:

    token_layer: str = conf.get("firstClass", {}).get("token", "Token")

    token: dict[str, Any] = {"unit": {"layer": token_layer}}
    range: list[int] = [1, 1]
    label: Any = nget(node, "label")
    quantifier: Any = None

    if node.data == "fake_brackets":
        tmp_members: list = []
        disjuncts: list[Any] = [x for x in node.children if x.data != "or_"]
        for d in disjuncts:
            process_node(d, tmp_members, conf)

        if len(tmp_members) == 0:
            return
        disj: dict = {"logicalExpression": {"naryOperator": "OR", "args": tmp_members}}
        members.append(disj)
        return

    elif node.data == "brackets":  # Parentheses

        tmp_members = []
        children_nodes: list[Any] = nget(node, "expr").children
        for cn in children_nodes:
            process_node(cn, tmp_members, conf)

        quantifier = nget(node, "quantifier")
        range = process_quantifier(quantifier, range)

        if len(tmp_members) == 0:
            return
        elif len(tmp_members) == 1 and range == [1, 1]:
            token = tmp_members[0]
            if label:
                token["unit"]["label"] = get_leaf_value(label)
            members.append(token)
            return
        else:
            s: dict = {"sequence": {"members": tmp_members}}
            if label:
                s["sequence"]["label"] = get_leaf_value(label)
            if range != [1, 1]:
                s["sequence"]["repetition"] = {
                    "min": range[0],
                    "max": "*" if range[1] < 0 else str(range[1]),
                }
            members.append(s)
            return

    elif node.data == "node":

        if label:
            token["unit"]["label"] = get_leaf_value(label)

        empty_node: Any = nget(node, "empty_node")
        string_node: Any = nget(node, "string_node")
        bracket_node: Any = nget(node, "bracket_node")

        if string_node:
            comp: str = get_leaf_value(string_node)
            comp = f"^{comp[1:-1]}$"
            token["unit"]["constraints"] = [
                {
                    "comparison": {
                        "left": {"reference": "form"},
                        "comparator": "=",
                        "right": {"regex": {"pattern": comp}},
                    }
                }
            ]
            quantifier = nget(string_node, "quantifier")

        elif empty_node:
            quantifier = nget(empty_node, "quantifier")

        elif bracket_node:
            constraints: dict = process_brackets(bracket_node)
            token["unit"]["constraints"] = [constraints]
            quantifier = nget(bracket_node, "quantifier")

        range = process_quantifier(quantifier, range)

        if range == [1, 1]:
            members.append(token)
        else:
            members.append(
                {
                    "sequence": {
                        "members": [token],
                        "repetition": {
                            "min": str(range[0]),
                            "max": "*" if range[1] == -1 else str(range[1]),
                        },
                    }
                }
            )


def cqp_to_json(cqp: str, conf: dict[str, Any] = {}) -> dict:
    """
    Take a CQP string and generate just the sequence (or single token) part
    """

    cqp_parsed: Any = cqp_parser.parse(cqp)

    members: list = []
    nodes = cqp_parsed.children[0].children  # expr > _

    for n in nodes:
        process_node(n, members, conf=conf)

    out: dict = {}
    if len(members) == 1:
        out = members[0]
    elif len(members) > 1:
        out = {"sequence": {"members": members}}

    return out


def make_part_of(query_json: dict | list, label: str):
    if isinstance(query_json, dict):
        uors = next((x for x in ("unit", "sequence") if x in query_json), "")
        if uors and not query_json[uors].get("partOf"):
            query_json[uors]["partOf"] = [{"partOfStream": label}]

    for x in list(query_json):  # prevent error re. edit during iteration
        v = query_json[x] if isinstance(query_json, dict) else x
        if not isinstance(v, (dict, list)):
            continue
        make_part_of(v, label)


def full_cqp_to_json(cqp: str, conf: dict[str, Any] = {}):
    """
    Take a CQP string and generate the query+result JSON
    """
    query_json = cqp_to_json(cqp, conf)
    all_labels = _get_all_labels(query_json)

    seg_layer: str = conf.get("firstClass", {}).get("segment", "Segment")
    seg_label, counter = "s", 0
    while seg_label in all_labels:
        counter += 1
        seg_label = f"s{counter}"

    make_part_of(query_json, seg_label)

    obj_label: str = next(
        l for l in ("sequence", "logicalExpression", "unit") if l in query_json
    )
    obj: dict = query_json[obj_label]
    rep = obj.get("repetition", {})
    if str(rep.get("min", 1)) != "1" or str(rep.get("max", 1)) != "1":
        obj = {"members": [{"sequence": obj}]}

    label = "*"
    if obj_label in ("sequence", "unit"):
        label = "match"
        obj["label"] = label
        obj["partOf"] = [{"partOfStream": seg_label}]

    res = {
        "label": "matches",
        "resultsPlain": {"context": ["s"], "entities": [label]},
    }

    return {
        "query": [{"unit": {"layer": seg_layer, "label": seg_label}}, {obj_label: obj}],
        "results": [res],
    }

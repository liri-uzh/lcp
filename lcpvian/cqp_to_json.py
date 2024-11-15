from typing import Any

from lark.lexer import Token


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
        comparison_type: str = (
            "stringComparison"
            if nget(query, "modifier")
            and get_leaf_value(nget(query, "modifier")) == "%l"
            else "regexComparison"
        )
        if comparison_type == "regexComparison":
            value = f"/^{value[1:-1]}$/"
        return {
            "comparison": {
                "left": {"entity": at},
                "operator": op,
                comparison_type: value,
            }
        }

    elif section:
        processed_section: dict
        if nget(section, "not_"):
            processed_section = {
                "logicalOpUnary": {
                    "operator": "NOT",
                    "args": [process_brackets(section)],
                }
            }
        else:
            processed_section = process_brackets(section)

        if vp:
            disj: Any = nget(vp, "or_")
            operator: str = "OR" if disj else "AND"
            return {
                "logicalOpNAry": {
                    "operator": operator,
                    "args": [processed_section, process_brackets(vp)],
                }
            }
        else:
            return processed_section

    return {}


def process_node(
    node: Any, members: list, conf: dict[str, Any] = {"token": "Token"}
) -> None:

    token: dict[str, Any] = {"unit": {"layer": conf["token"]}}
    range: list[int] = [1, 1]
    label: Any = nget(node, "label")
    quantifier: Any = None

    if node.data == "brackets":  # Parentheses

        tmp_members: list = []
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
            comp = f"/^{comp[1:-1]}$/"  # replace "s with /s
            token["unit"]["constraints"] = [
                {
                    "comparison": {
                        "left": {"entity": "form"},
                        "operator": "=",
                        "regexComparison": comp,
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


# cqp is a Lark tree
def cqp_to_json(cqp: Any, conf: dict[str, Any] | None = None) -> dict:

    members: list = []
    nodes = cqp.children[0].children  # expr > _

    for n in nodes:
        process_node(n, members)

    out: dict = {}
    if len(members) == 1:
        out = members[0]
    elif len(members) > 1:
        out = {"sequence": {"members": members}}

    return out

import json
import os
import re
import sys

from collections.abc import Iterable
from typing import Any, ClassVar

from lark import Lark
from lark.indenter import Indenter
from lark.lexer import Token

# from .cqp_to_json import cqp_to_json

VALUE_FILTERS: dict = {
    "pattern": lambda p: p[1:-1],  # remove slashes
    "string": lambda p: p[1:-1],  # remove double quotes
    "functionName": lambda p: p.removesuffix("("),  # remove trailing "("
}

PARSER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "parser"))
PARSER_FILES = [os.path.join(PARSER_PATH, f) for f in sorted(os.listdir(PARSER_PATH))]

dqd_grammar_fn: str = next(
    (f for f in PARSER_FILES if re.match(r".*dqd[^/]*\.lark$", f)), ""
)
assert os.path.isfile(
    dqd_grammar_fn
), f"Could not find a valid DQD lark file in the current directory"
dqd_grammar: str = open(dqd_grammar_fn).read()

cqp_grammar_fn: str = next(
    (f for f in PARSER_FILES if re.match(r".*cqp[^/]*\.lark$", f)), ""
)
assert os.path.isfile(
    cqp_grammar_fn
), f"Could not find a valid CQP lark file in the current directory"
cqp_grammar: str = open(cqp_grammar_fn).read()


json_schema_fn: str = next((f for f in PARSER_FILES if f.endswith(".json")), "")
assert os.path.isfile(
    json_schema_fn
), f"Could not find a valid json file in the current directory"
json_schema: dict = json.loads(open(json_schema_fn).read())


class Schema:
    def __init__(self, json_file="cobquec.auto.json"):
        self.skips = {}
        self.renames = {}
        self.schema = {}
        fn = os.path.join(os.path.dirname(__file__), "..", "parser", json_file)
        with open(fn, "r") as input:
            json_string = input.read()
            schema_obj = json.loads(json_string)
            self.skips = schema_obj.pop("skips", {})
            self.renames = schema_obj.pop("renames", {})
            self.schema = schema_obj


class TreeIndenter(Indenter):
    NL_type: str = "_NL"
    INDENT_type: str = "_INDENT"
    DEDENT_type: str = "_DEDENT"
    tab_len: int = 8
    OPEN_PAREN_types: ClassVar[list[str]] = []
    CLOSE_PAREN_types: ClassVar[list[str]] = []
    # this fixes mypy but not sure if it breaks anything:
    always_accept: Iterable[str] = ()


parser = Lark(
    dqd_grammar, parser="earley", start="top", postlex=TreeIndenter(), debug=True
)


def get_specs(name, schema) -> dict:
    specs = schema["$defs"].get(name, {})
    if "$ref" in specs:
        return get_specs(specs["$ref"].removeprefix("#/$defs/"), schema)
    return specs


def dqd_component(component, schema_obj):
    schema = schema_obj.schema
    json_obj = {}
    if isinstance(component, Token):
        return component.value
    key = component.data
    key = re.sub(r"_(.)", lambda m: m[1].upper(), key)
    processed_children = [dqd_component(c, schema_obj) for c in component.children]
    if key in schema_obj.skips:
        # Do any skips necessary
        sk = schema_obj.skips[key]
        processed_children = [
            (
                next(x for x in c.values())
                if isinstance(c, dict) and next(x for x in c) in sk
                else c
            )
            for c in processed_children
        ]
    specs = get_specs(key, schema)
    typ = specs.get("type", "")
    if typ == "array":
        json_obj[key] = processed_children
        # if "properties" not in specs.get("items", {}):
        #     # Skip the key of the children
        #     json_obj[key] = [
        #         (c if c.__class__ is str else next(x for x in c.values()))
        #         for c in processed_children
        #     ]
    elif typ == "object":
        json_obj[key] = {
            next(x for x in c.keys()): next(x for x in c.values())
            for c in processed_children
        }
    elif typ == "string":
        children_strings = [
            (next(x for x in c.values()) if isinstance(c, dict) else c)
            for c in processed_children
        ]
        assert all(
            isinstance(c, str) for c in children_strings
        ), f"Non-string found for {key} ({children_strings})"
        value = "".join(children_strings)  # type: ignore
        json_obj[key] = value
    elif "string" in typ and isinstance(processed_children[0], str):
        json_obj[key] = processed_children[0]
    elif "object" in typ and isinstance(processed_children[0], dict):
        obj = {
            next(x for x in c.keys()): next(x for x in c.values())
            for c in processed_children
        }
        json_obj[key] = obj
        first_entry = next({k: v} for k, v in obj.items())
        properties = specs.get("properties", {})
        if (
            "string" in typ
            and len(obj) == 1
            and next(x for x in first_entry) not in properties
        ):
            value = next(v for v in first_entry.values())
            json_obj[key] = value
    else:
        assert False, f"Type not supported: {typ}"
    # One exception for functionName: remove trailing (
    if key in VALUE_FILTERS:
        json_obj[key] = VALUE_FILTERS[key](json_obj[key])
    if isinstance(json_obj[key], dict) and key in schema_obj.renames:
        # Do any renaming necessary
        rnm = schema_obj.renames[key]
        obj = {rnm.get(k, k): v for k, v in json_obj[key].items()}
        json_obj[key] = obj

    return json_obj


def dqd_to_json(dqd, schema):
    json_obj = {}
    query, results = dqd.children
    assert query.data == "query" and results.data == "results", "Invalid DQD"
    json_obj["query"] = [dqd_component(c, schema) for c in query.children]
    # Skip the "result" key of the results
    json_obj["results"] = [
        next(v for v in dqd_component(c, schema).values()) for c in results.children
    ]
    return json_obj


def convert(dqd_query: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
    data = parser.parse(dqd_query)
    res: dict = dqd_to_json(data, Schema())
    return res


def cmdline() -> None:
    if os.path.isfile(sys.argv[-1]):
        with open(sys.argv[-1], "r") as fo:
            dqd = fo.read()
    else:
        dqd = sys.argv[-1]
    print("Tree:", parser.parse(dqd).pretty())
    print(json.dumps(convert(dqd), indent=4))


if __name__ == "__main__":
    cmdline()

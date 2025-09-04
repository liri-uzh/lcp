"""
cql_to_json.py: parse and convert to JSON a CQL query
as defined by the CLARIN FCS specification:
https://www.clarin.eu/content/federated-content-search-clarin-fcs-technical-details
"""

import os

from lark import Lark, Tree, Token
from typing import cast

test_grammar: str = open(
    os.path.join(os.path.dirname(__file__), "..", "parser", "cql.lark")
).read()

parser = Lark(
    test_grammar,
    parser="earley",
    start="cql_query",
    propagate_positions=True,
    debug=True,
)

IGNORE_RULES = ["prefix_assignment", "modifier"]


def is_rule(node: Tree, rule: str | list[str]) -> bool:
    rules = rule if isinstance(rule, list) else [rule]
    return any(node.data == Token("RULE", r) for r in rules)


class CqlToJson:
    def __init__(self, token: str = "Token", segment: str = "Segment", query: str = ""):
        self.token = token
        self.segment = segment
        self.query = query
        pass

    def unit_form(self, form: str) -> dict:
        return {
            "unit": {
                "partOf": [{"partOfStream": "s"}],
                "layer": self.token,
                "constraints": [
                    {
                        "comparison": {
                            "left": {"reference": "form"},
                            "comparator": "=",
                            "right": {"string": form},
                        }
                    }
                ],
            }
        }

    def sequence(self, text: str) -> dict:
        forms = [t.strip() for t in text.split(" ") if t.strip()]
        return {
            "sequence": {
                "partOf": [{"partOfStream": "s"}],
                "members": [self.unit_form(f) for f in forms],
            }
        }

    def get_term_text(self, term: Tree | Token) -> str:
        query: str = self.query
        if isinstance(term, Token):
            return term.value
        if len(term.children) == 0:
            return query[term.meta.start_pos : term.meta.end_pos]
        if is_rule(cast(Tree, term.children[0]), "identifier"):
            char_string = cast(Tree, term.children[0].children[0])
            term_text = cast(Token, char_string.children[0]).value
            if is_rule(char_string, "char_string1"):
                return term_text
            elif is_rule(char_string, "char_string2"):
                return term_text[1:-1]
        return ""

    def process_node(self, node: Tree) -> dict | list | None:
        query: str = self.query
        if is_rule(node, IGNORE_RULES):
            return None
        if is_rule(node, "cql_query"):
            children = [self.process_node(c) for c in node.children]
            return next(c for c in children if c is not None)
        if is_rule(node, "scoped_clause"):
            if len(node.children) == 3:
                left, op, right = [cast(Tree, x) for x in node.children]
                left_obj = self.process_node(left)
                right_obj = self.process_node(right)
                operator = query[op.meta.start_pos : op.meta.end_pos].upper()
                if operator == "PROX":
                    operator = "AND"
                if operator == "NOT":
                    operator = "AND"
                    right_obj = {
                        "logicalExpression": {"unaryOperator": "NOT", "arg": right_obj}
                    }
                return {
                    "constraint": {
                        "logicalExpression": {
                            "naryOperator": operator,
                            "args": [left_obj, right_obj],
                        }
                    }
                }
            else:
                return self.process_node(node.children[0])
        if is_rule(node, "search_clause"):
            if len(node.children) == 3:
                index, relation, term_right = node.children
                attribute_name = self.get_term_text(index.children[0]).split(".")[-1]
                value_right = self.get_term_text(term_right.children[0])
                comparitor = cast(Tree, relation.children[0])
                operator = "="
                comp_child = cast(Tree, comparitor.children[0])
                if is_rule(comp_child, "comparitor_symbol"):
                    operator = query[
                        comp_child.meta.start_pos : comp_child.meta.end_pos
                    ]
                    operator = (
                        "="
                        if operator == "=="
                        else ("!=" if operator == "<>" else operator)
                    )
                return {
                    "unit": {
                        "layer": "Token",
                        "partOf": [{"partOfStream": "s"}],
                        "constraints": [
                            {
                                "comparison": {
                                    "left": {"reference": attribute_name},
                                    "comparator": operator,
                                    "right": {"string": value_right},
                                }
                            }
                        ],
                    }
                }
            first_child = cast(Tree, node.children[0])
            if is_rule(first_child, "cql_query"):
                return self.process_node(first_child)
            term = first_child.children[0]
            term_text = self.get_term_text(term)
            if " " in term_text:
                return self.sequence(term_text)
            else:
                return self.unit_form(term_text)
        return None

    def convert(self) -> dict:
        members = [
            self.process_node(c)
            for c in parser.parse(self.query).children
            if isinstance(c, Tree)
        ]
        query_list = [{"unit": {"layer": self.segment, "label": "s"}}]
        return {
            "query": query_list + [m for m in members if m],
            "results": [
                {"label": "kwic", "resultsPlain": {"context": ["s"], "entities": ["*"]}}
            ],
        }

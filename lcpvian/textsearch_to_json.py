from typing import Any

import re


def textsearch_to_json(text: str, conf: dict[str, Any] | None = None) -> dict:

    assert len(text.split("\n")) == 1, AssertionError(
        "Not a single-line plain text search"
    )

    forms = re.findall(r"\S+", text)

    segment_layer = (conf or {}).get("firstClass", {}).get("segment", "Segment")
    token_layer = (conf or {}).get("firstClass", {}).get("token", "Token")

    token_attributes = (
        (conf or {}).get("layer", {}).get(token_layer, {}).get("attributes", {})
    )
    assert "form" in token_attributes, ReferenceError(
        "Cannot perform simple text searches on corpora that do not have a 'form' attribute"
    )

    tokens = []
    for f in forms:
        unit = {"unit": {"layer": token_layer}}
        constraint_on_form = {
            "comparison": {
                "left": {"reference": "form"},
                "comparator": "=",
                "right": {"string": f},
            }
        }
        if "lemma" in token_attributes:
            constraint_on_lemma = {
                "comparison": {
                    "left": {"reference": "lemma"},
                    "comparator": "=",
                    "right": {"string": f},
                }
            }
            unit["unit"]["constraints"] = [
                {
                    "logicalExpression": {
                        "naryOperator": "OR",
                        "args": [constraint_on_form, constraint_on_lemma],
                    }
                }
            ]
        else:
            unit["unit"]["constraints"] = [constraint_on_form]
        tokens.append(unit)

    out: dict[str, Any] = {
        "query": [
            {"unit": {"layer": segment_layer, "label": "s"}},
            {
                "sequence": {
                    "partOf": [{"partOfStream": "s"}],
                    "label": "seq",
                    "members": tokens,
                }
            },
        ],
        "results": [
            {
                "label": "matches",
                "resultsPlain": {"context": ["s"], "entities": ["seq"]},
            }
        ],
    }

    return out

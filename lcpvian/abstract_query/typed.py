"""
Nothing but typealiases for common objects
"""

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, TypedDict
from pydantic import JsonValue

QueryType: TypeAlias = str | int | list[str | int] | dict[str, Any]

Attribs: TypeAlias = list[dict[str, str]]


JSON: TypeAlias = JsonValue
JSONObject: TypeAlias = dict[str, JSON]

# modelling the input query json and its components
QueryPart: TypeAlias = list[dict[str, JSON]]
QueryJSON: TypeAlias = dict[str, QueryPart]

# the LabelLayer object maps label names to their associated layer and metadata
LabelLayer: TypeAlias = dict[str, tuple[str, dict[str, JSONObject]]]


@dataclass
class SQLRef:
    """
    Label, tables and conditions to reference a layer or an attribute
    """

    entity: str
    ref: str
    alias: str  # alias to use in SELECT
    joins: dict[str, dict[str, int]]

    def __str__(self):
        return self.ref


# information about a reference in a comparison
class RefInfo(TypedDict, total=False):
    type: str
    layer: str
    mapping: dict | None
    meta: dict | None
    sql: SQLRef | None


# model corpus config data
ConfigJSON: TypeAlias = JSONObject
# model the result metadata returned alongside a query
ResultMetadata: TypeAlias = dict[str, str | Attribs | bool | list[JSONObject]]

# Joins are stored as dict keys, with None as values. If the value is True,
# the join will be put at the end of the list of joins (for performance reasons)
Joins: TypeAlias = dict[str, None | Literal[True] | set]

# a Layer is either None or (label, layer)
Layer: TypeAlias = None | tuple[str, str]
# TGSD is the data for token, gesture, segment and document
TGSD: TypeAlias = tuple[Layer, Layer, Layer, Layer]

# kwic entity details
Details: TypeAlias = dict[str, str | bool | list["Details"]]

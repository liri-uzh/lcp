"""
Model the various parts of the corpus template/corpus config

Code for generating batches is also in here
"""

from typing import Any, Required, NotRequired, Sequence, TypedDict


class Meta(TypedDict, total=False):
    date: str
    name: str
    author: str
    version: int | str | float
    website: NotRequired[str]
    corpusDescription: NotRequired[str | None]
    sample_query: NotRequired[str]


class Attribute(TypedDict, total=False):
    type: str
    nullable: bool
    isGlobal: NotRequired[bool]
    name: NotRequired[str]


class Layer(TypedDict, total=False):
    abstract: bool
    contains: NotRequired[str]
    layerType: str
    attributes: dict[str, Attribute | dict[str, Attribute]]
    anchoring: NotRequired[dict[str, bool]]
    values: NotRequired[list[str]]
    partOf: NotRequired[list[dict[str, str]]]


class FirstClass(TypedDict, total=False):
    segment: Required[str]
    token: Required[str]
    document: Required[str]


class Partitions(TypedDict, total=False):
    values: list[str]


class CorpusTemplate(TypedDict, total=False):
    meta: Meta
    layer: Required[dict[str, Layer]]
    firstClass: Required[FirstClass]
    partitions: NotRequired[Partitions]
    projects: NotRequired[list[str]]
    project: NotRequired[str]
    uploaded: NotRequired[bool]
    schema_name: NotRequired[str]


class CorpusConfig(CorpusTemplate, total=False):
    shortname: NotRequired[str]
    corpus_id: Required[int]
    current_version: Required[int | str | float]
    version_history: str | None
    description: str | None
    schema_path: Required[str]
    token_counts: dict[str, int]
    mapping: Required[dict[str, Any]]
    enabled: bool
    segment: Required[str]
    token: Required[str]
    document: Required[str]
    column_names: list[str]
    sample_query: str
    # doc ids is stored as [job_id, {1: "AKAW"}]
    doc_ids: NotRequired[Sequence[str | dict[str, str]]]
    _batches: NotRequired[dict[str, int]]


def _generate_batches(n_batches: int, basename: str, size: int) -> dict[str, int]:
    """
    We can create batchnames if we know three things:

    total number of batches
    the prefix of the table name
    the total size of the corpus
    """
    batches: dict[str, int] = {}
    if n_batches < 2:
        named = basename.replace("<batch>", "") + "0"
        return {named: size}
    for i in range(1, n_batches):
        if i + 1 == n_batches and n_batches > 1:
            name = "rest"
        else:
            name = str(i)
        batch = basename.replace("<batch>", name)
        size = int(size / 2 if name != "rest" else size)
        batches[batch] = int(size)
    return batches


def _get_batches(config: CorpusConfig) -> dict[str, int]:
    """
    Get a dict of batch_name: size for a given corpus
    """
    batches: dict[str, int] = {}
    counts: dict[str, int] = config.get("token_counts", {})
    try:
        mapping = (
            config.get("mapping", {}).get("layer", {}).get(config.get("token", ""))
        )
    except (KeyError, TypeError):
        return counts
    if not mapping:
        return counts
    if "partitions" in mapping:
        for lang, details in mapping["partitions"].items():
            basename = details["relation"]
            if "<language>" in basename:
                basename = basename.replace("<language>", lang)
            count_key = basename.replace("<batch>", "0").lower()
            size = next(v for k, v in counts.items() if k.lower() == count_key)
            n_batches = details["batches"]
            more = _generate_batches(n_batches, basename, size)
            batches.update(more)
    else:
        n_batches = mapping["batches"]
        name = mapping["relation"]
        count_key = name.replace("<batch>", "0").lower()
        try:
            size = next(v for k, v in counts.items() if k.lower() == count_key)
        except:
            size = sum(v for v in counts.values())
        more = _generate_batches(n_batches, name, size)
        batches.update(more)
    if not batches:
        return counts
    return batches

from typing import Any, cast

import sqlparse  # type: ignore

from .query import QueryMaker
from .results import ResultsMaker
from .typed import QueryJSON
from .utils import Config
from ..validate import process_refs
from ..utils import _get_all_labels

BASE = """
{query}
{results}
{unions};
"""


def unions(query_json: QueryJSON) -> str:
    """
    Make the final part of the SQL, where we UNION ALL the results parts
    """
    size = len(query_json["results"])
    base = " SELECT * FROM res"
    pieces = [base + f"{i} " for i in range(0, size + 1)]
    return "\nUNION ALL\n".join(pieces)


def json_to_sql(
    query_json: QueryJSON,
    schema: str = "corpus",
    batch: str = "token_rest",
    config: QueryJSON = {},
    lang: str | None = None,
) -> tuple[str, QueryJSON, dict[int, Any]]:
    """
    The only public thing exposed by this module.

    It requires a query in JSON format plus configuration stuff
    """
    all_labels = _get_all_labels(query_json)
    all_refs = {
        k: sorted(v)
        for k, v in process_refs(config, query_json, labels=all_labels).items()
    }
    language: str | None = lang.lower() if lang else None
    conf: Config = Config(schema, batch, config, language)
    query_json, result_data = ResultsMaker(query_json, conf, all_refs).results()
    query_part: str
    seg_label: str
    query_part, seg_label, has_char_range = QueryMaker(
        query_json, result_data, conf
    ).query()
    unions_part: str = unions(query_json)
    result = result_data.needed_results
    result = result.replace("__seglabel__", seg_label)

    formatters: dict[str, str] = {
        "query": query_part,
        "results": result,
        "unions": unions_part,
    }

    script = BASE.format(**formatters)
    script = sqlparse.format(
        script, reindent=True, keyword_case="upper", use_space_around_operators=False
    )

    return script, result_data.meta_json, result_data.post_processes

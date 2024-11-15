import json
import traceback

from lark.exceptions import UnexpectedToken
from typing import cast, Any

from .dqd_parser import convert
from .typed import JSONObject


async def validate(
    user: str | None = None,
    room: str | None = None,
    query: str = "",
    query_name: str | None = None,
    **kwargs: dict[str, Any],
) -> JSONObject:
    """
    Validate a JSON/DQD query. This is not an endpoint, it is called by sock.py
    """
    result: JSONObject = {}
    try:
        json.loads(query)
        result = {"kind": "json", "valid": True, "action": "validate", "status": 200}
    except json.JSONDecodeError:
        try:
            conf: dict[str, Any] = {}
            if kwargs:
                conf = (
                    cast(dict[str, Any], kwargs)
                    .get("config", {})
                    .get(kwargs.get("corpus"))
                )
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
                "kind": "dqd?",
                "valid": False,
                "action": "validate",
                "error": str(err),
                "errorList": cast(JSONObject, all_errors),
                "status": 400,
                "traceback": tb,
            }
    return result

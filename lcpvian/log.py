"""
log.py: logging utilities
"""

import logging
import traceback

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar
from uuid import uuid4

R = TypeVar("R")


def logged(f: Callable[..., R]) -> Callable[..., R]:
    """
    Decorator that logs start and end/error of function call
    """

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> R:
        stargs = [str(a) for a in args]
        stkwargs = {str(k): str(v) for k, v in kwargs.items()}
        uu = str(uuid4())
        details = {
            "couplet": uu,
            "event": "called",
            "args": stargs,
            "kwargs": stkwargs,
        }
        logging.info(f"Called: {f.__name__}", extra=details)
        try:
            result = f(*args, **kwargs)
        except Exception as err:
            exc = {"event": "error", "error": str(err), "tb": traceback.format_exc()}
            details.update(exc)
            msg = f"Errored: {f.__name__} threw {type(err).__name__} ({str(err)})"
            logging.error(msg, extra=details)
            raise err
        # if inspect.isawaitable(result)
        #    result = await result
        details.update({"event": "returned"})
        logging.info(
            f"Returned: {type(result).__name__} from {f.__name__}", extra=details
        )
        return result

    return wrapper

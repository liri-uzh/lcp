# tasks/__init__.py
import inspect
import os

from arq.worker import func, Function as ArqFunction

import lcpvian.tasks.configure as configure
import lcpvian.tasks.corpora as corpora
import lcpvian.tasks.document as document
import lcpvian.tasks.export as export
import lcpvian.tasks.exporter_swissdox as exporter_swissdox
import lcpvian.tasks.exporter as exporter
import lcpvian.tasks.query as query
import lcpvian.tasks.store as store
import lcpvian.tasks.upload as upload

QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", 1000))

# List of all async functions found in task modules
_registered_tasks = []

for module in (
    configure,
    corpora,
    document,
    export,
    exporter_swissdox,
    exporter,
    query,
    store,
    upload,
):
    for func_name in dir(module):
        obj = getattr(module, func_name)
        if isinstance(obj, ArqFunction):
            # Object is already prepared: append it already (loop will skip on next line)
            _registered_tasks.append(obj)
        if not inspect.iscoroutinefunction(obj):
            continue
        if obj.__module__ != module.__name__:
            continue
        # Make sure we use the fully qualified name to prevent merged duplicates
        job_func = func(
            obj,
            name=f"{module.__name__}.{obj.__qualname__}",
            keep_result=True,
            timeout=300,  # default arq value
        )
        _registered_tasks.append(job_func)

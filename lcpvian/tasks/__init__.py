# tasks/__init__.py
import inspect

import lcpvian.tasks.configure as configure
import lcpvian.tasks.corpora as corpora
import lcpvian.tasks.document as document
import lcpvian.tasks.export as export
import lcpvian.tasks.exporter_swissdox as exporter_swissdox
import lcpvian.tasks.exporter as exporter
import lcpvian.tasks.query as query
import lcpvian.tasks.store as store
import lcpvian.tasks.upload as upload

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
        if not inspect.iscoroutinefunction(obj):
            continue
        if obj.__module__ != module.__name__:
            continue
        # Make sure we use the fully qualified name to prevent merged duplicates
        obj.__qualname__ = f"{module.__name__}.{obj.__qualname__}"
        _registered_tasks.append(obj)

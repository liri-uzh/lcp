"""
Module that stores custom types used around the backend

TypedDicts for CorpusConfig and CorpusTemplate are in configure.py
"""

import asyncio

from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Mapping, TypeAlias, TypedDict
from uuid import UUID

from aiohttp import web
from rq.job import Job
from pydantic import JsonValue


from .configure import CorpusConfig

# arbitrary json we know nothing about
JSON: TypeAlias = JsonValue

# json when we know it is an object at least
JSONObject: TypeAlias = dict[str, JSON]

# all websocket connections to the app -- {room_id: {(ws_connection, user_id)...}}
Websockets: TypeAlias = defaultdict[str, set[tuple[web.WebSocketResponse, str]]]

# {corpus_id: corpus_config} shared between frontend and backend. keys are numbers cast to string
Config: TypeAlias = dict[str, CorpusConfig]

# corpus id, schema, table, size
Batch: TypeAlias = tuple[int, str, str, int]

# user's search query in JSON format
Query: TypeAlias = dict[str, str | list[JSONObject] | JSONObject]

# what can identify a sentence inside sentence results?
SentKey: TypeAlias = str | UUID | int

# a single token within a sentence
Token: TypeAlias = list[int | str | float]

# an offset, plus list of tokens and possibly annotations. either as tuple or list
# todo: figure out which of these alternatives is needed?
Sentence: TypeAlias = (
    tuple[int, list[Token]]
    | list[int | list[Token] | dict]
    | tuple[int, list[Token], dict]
)

# int = offset, list[Token] = prepared tokens, dict (optional) = annotations
RawSent: TypeAlias = (
    tuple[SentKey, int, list[Token]] | tuple[SentKey, int, list[Token], dict]
)

# the different kinds of sql results in the importer
TableExists: TypeAlias = list[tuple[bool]]
SQLDrops: TypeAlias = list[tuple[str]]
WordCounts: TypeAlias = list[list[tuple[int]]]

# an entry in main.corpus
MainCorpus: TypeAlias = tuple[
    int,  # corpus id
    str,  # name
    str | int | float,  # current version
    str | int | float | None | list[str | int],  # version history
    str | None,  # description
    dict[str, JSON],  # corpus template
    str,  # schema path
    dict[str, int] | None,  # token counts -- todo: remove none when tangram fixed
    dict[str, JSON] | None,  # mapping -- todo: remove none when tangram fixed
    bool,
    str,  # sample_query
    str,  # project_id
]

# what Importer.run_script can return
RunScript: TypeAlias = WordCounts | SQLDrops | TableExists | list[MainCorpus] | None

# the args needed to add an entry to main.corpus
MainCorpusEntry: TypeAlias = dict[str, int | float | str]
# right now MainCorpusEntry/nothing are the only possible params for run_script
Params: TypeAlias = MainCorpusEntry | tuple[()] | dict[str, Any] | None

# Request headers for LAMa  calls
Headers: TypeAlias = Mapping[str, JSON]

# a query to be stored, coming from frontend
UserQuery: TypeAlias = tuple[
    str, dict[str, str | int | list[str | int]], str, str | None, datetime
]

# what redis sends to the listener
RedisMessage: TypeAlias = dict[str, str | bytes | None] | None | str | bytes

# metadata we generate about a query
QueryMeta: TypeAlias = dict[str, list[JSONObject]]

# a group of sentences {sent_id: [offset, sent]}
ResultSents: TypeAlias = dict[SentKey, Sentence]

# kwic, collocation, freqdist data
Analysis: TypeAlias = list[list[str | float | int | list[int]]]

# -1, 0 and 1+ values in the Results object
ResultsValue: TypeAlias = ResultSents | QueryMeta | Analysis

# all the results put together into a single object
Results: TypeAlias = dict[
    int,  # -2 is above-hit data, -1 is sentences, 0 is results metadata, more is kwic/freq/collocates
    ResultsValue,
]

# todo: figure this out -- eternally running background jobs
Task: TypeAlias = asyncio.Task

# params for db_query execute
DBQueryParams: TypeAlias = dict[
    str,
    list[str]
    | list[int]
    | str
    | dict[str, Any]
    | dict[str, list[int] | list[str]]  # sentences job
    | None,
]

# model a query iteration result
Iteration: TypeAlias = tuple[
    Job | None, str | None, dict[str, str | bool | None], list[str]
]

# one of the main endpoint functions like query(), upload()
Endpoint: TypeAlias = Callable[
    [web.Request], Awaitable[web.Response | web.WebSocketResponse | web.FileResponse]
]


class BaseArgs(TypedDict, total=False):
    user: str
    room: str | None


class QueryArgs(BaseArgs):
    """
    The request-specific arguments associated with a corpus query (offset, to_export)
    These are never updated after the request has been submitted
    """

    hash: str
    full: bool
    from_memory: bool
    to_export: Any
    total_results_requested: int
    offset: int


class DocIDArgs(BaseArgs):
    corpus_id: int
    kind: str


class SentJob(BaseArgs, total=False):
    depends_on: str | list[str]
    from_memory: bool
    full: bool
    meta_query: str
    needed: bool
    offset: int
    sentences_query: str
    total_results_requested: int
    to_export: Any


def _make_observable(obj, obs):
    # Pass the parent Observable instance to the observer callback
    new_observer = lambda event, _, *rest: obs._observer(
        f"child:{event}", obs._data, *rest
    )
    if isinstance(obj, list):
        return ObservableList(*obj, observer=new_observer)
    if isinstance(obj, dict):
        return ObservableDict(observer=obs._observer, **obj)
    return obj


def _serialize_observable(obj: Any) -> Any:
    if isinstance(obj, ObservableDict):
        return {k: _serialize_observable(v) for k, v in obj._data.items()}
    if isinstance(obj, ObservableList):
        return [_serialize_observable(d) for d in obj._data]
    if isinstance(obj, dict):
        return {k: _serialize_observable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_observable(d) for d in obj]
    return obj


class ObservableDict:
    """
    Wrapper around a regular dictionary.
    Overrides methods like __setitem__, __delitem__, and update
    to include a call to a notification method (_notify) whenever a change occurs.
    """

    def __init__(self, *args, observer: Callable | None = None, **kwargs):
        self._observer: Callable | None = observer
        new_kwargs = {k: _make_observable(v, self) for k, v in kwargs.items()}
        self._data = dict(*args, **new_kwargs)

    def _serialize(self):
        return _serialize_observable(self)

    def __setitem__(self, key, value):
        value = _make_observable(value, self)
        self._data[key] = value
        if self._observer:
            self._observer("set", self._data, key, value)

    def __delitem__(self, key):
        del self._data[key]
        if self._observer:
            self._observer("set", self._data, key)

    def pop(self, key, default):
        value = self._data.pop(key, default)
        if self._observer:
            self._observer("pop", self._data)
        return value

    def update(self, *args, **kwargs):
        kwargs = {k: _make_observable(v, self) for k, v in kwargs.items()}
        self._data.update(*args, **kwargs)
        if self._observer:
            self._observer("update", self._data)

    def setdefault(self, key, value):
        if key in self._data:
            return self._data[key]
        value = _make_observable(value, self)
        self._data[key] = value
        if self._observer:
            self._observer("setdefault", self._data)
        return value

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return repr(self._data)

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def get(self, name, default=None):
        return self._data.get(name, default)


class ObservableList:
    """
    Wrapper around a regular list.
    Overrides methods like __setitem__, __delitem__, append, insert, remove, pop and clear
    to include a call to a notification method (_notify) whenever a change occurs.
    """

    def __init__(self, *args, observer: Callable | None = None):
        self._observer: Callable | None = observer
        new_args = [_make_observable(a, self) for a in args]
        self._data = list(new_args)

    def _serialize(self):
        return _serialize_observable(self)

    def append(self, item):
        item = _make_observable(item, self)
        self._data.append(item)
        if self._observer:
            self._observer("append", self._data, item)

    def extend(self, iterable):
        iterable = [_make_observable(i, self) for i in iterable]
        self._data.extend(iterable)
        if self._observer:
            self._observer("extend", self._data)

    def insert(self, index, item):
        item = _make_observable(item, self)
        self._data.insert(index, item)
        if self._observer:
            self._observer("insert", self._data, index, item)

    def remove(self, item):
        self._data.remove(item)
        if self._observer:
            self._observer("remove", self._data, item)

    def pop(self, index=-1):
        item = self._data.pop(index)
        if self._observer:
            self._observer("pop", self._data, index, item)
        return item

    def clear(self):
        self._data.clear()
        if self._observer:
            self._observer("clear", self._data)

    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, value):
        value = _make_observable(value, self)
        self._data[index] = value
        if self._observer:
            self._observer("set", self._data, index, value)

    def __delitem__(self, index):
        del self._data[index]
        if self._observer:
            self._observer("delete", self._data, index)

    def __contains__(self, item):
        return item in _serialize_observable(self._data)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return repr(self._data)

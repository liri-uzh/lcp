import json

from hashlib import md5
from redis import Redis
from typing import Any


class RedisDict(dict):
    def __init__(self, redis_client: Redis, redis_key: str):
        self._redis = redis_client
        self._redis_key = redis_key

    def __getattr__(self, name: str):
        # Fetch the entire hash and get the sub-value
        data = self._redis.hget(self._redis_key, name)
        if data is None:
            return None
        try:
            # Deserialize if needed
            ret: Any = json.loads(data)
            if isinstance(ret, dict):
                ret = RedisDict(self._redis, ret.get("key", ""))
            elif isinstance(ret, list):
                ret = RedisList(self._redis, ret[0])
            return ret
        except:
            return data

    def __setattr__(self, name: str, value: Any):
        # Handle internal attributes normally
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            existing: Any = self.__getattr__(name)
            if existing and isinstance(existing, (RedisDict, RedisList)):
                existing.__delete__(pointer_key=self._redis_key)
            if isinstance(value, (RedisDict, RedisList)):
                value = (
                    [value._prefix]
                    if isinstance(value, RedisList)
                    else {"key": value._redis_key}
                )
            elif isinstance(value, (dict, list)):
                new_key = (
                    md5(f"{self._redis_key}::{name}".encode("utf-8")).digest().hex()
                )
                is_list = isinstance(value, list)
                sub_obj: dict | list = (
                    RedisList(self._redis, new_key)
                    if is_list
                    else RedisDict(self._redis, new_key)
                )
                for k in value:
                    v = k if is_list else value[k]
                    if isinstance(sub_obj, RedisList):
                        sub_obj.append(v)
                    else:
                        sub_obj[k] = v
                value = [new_key] if is_list else {"key": new_key}

            if isinstance(value, (dict, list)):
                val_key = value[0] if isinstance(value, list) else value["key"]
                pointers = RedisDict(self._redis, f"{val_key}::pointers")
                pointers[self._redis_key] = 1

            # Serialize the value
            data = json.dumps(value)
            self._redis.hset(self._redis_key, name, data)

    def __bool__(self):
        return len(self.keys()) > 0

    def __contains__(self, key: str) -> bool:
        return key in self.keys()

    def __delete__(self, pointer_key: str = ""):
        pointers = RedisDict(self._redis, f"{self._redis_key}::pointers")
        if pointer_key and pointer_key in pointers:
            del pointers[pointer_key]
        if pointers:
            return
        for k in self.keys():
            val: Any = self.__getattr__(k)
            if not isinstance(val, (RedisDict, RedisList)):
                continue
            val.__delete__(pointer_key=self._redis_key)
        self._redis.delete(self._redis_key)
        self._redis.delete(f"{self._redis_key}::pointers")

    def __delattr__(self, name: str):
        val = self.__getattr__(name)
        if isinstance(val, (RedisDict, RedisList)):
            val.__delete__(pointer_key=self._redis_key)
        self._redis.hdel(self._redis_key, name)

    # Optional: support dict-like access
    def __getitem__(self, key: str):
        return self.__getattr__(key)

    def __setitem__(self, key: str, value: Any):
        self.__setattr__(key, value)

    def __delitem__(self, key: str):
        self.__delattr__(key)

    def keys(self):
        return [x.decode() for x in self._redis.hkeys(self._redis_key)]

    def values(self):
        values: list[Any] = []
        for k in self.keys():
            values.append(self.__getattr__(k))
        return values

    def get(self, key: str, default=None):
        val = self.__getattr__(key)
        if val is None:
            return default
        return val

    def items(self):
        return [(k, self.__getattr__(k)) for k in self.keys()]


class RedisList(list):
    def __init__(self, redis_client: Redis, redis_key_prefix: str):
        self._redis = redis_client
        self._prefix = redis_key_prefix
        self._length_key: str = f"{self._prefix}:length"

        # Initialize length if not exists
        if not self._redis.exists(self._length_key):
            self._redis.set(self._length_key, 0)

    def __len__(self):
        return int(self._redis.get(self._length_key) or 0)

    def __contains__(self, value: Any) -> bool:
        for n in range(len(self)):
            val = self.__getitem__(n)
            if val == value or val is value:
                return True
        return False

    def __bool__(self):
        return len(self) > 0

    def __delete__(self, pointer_key: str = ""):
        pointers = RedisDict(self._redis, f"{self._prefix}::pointers")
        if pointer_key and pointer_key in pointers:
            del pointers[pointer_key]
        if pointers:
            return
        for n in range(len(self)):
            val: Any = self.__getitem__(n)
            self._redis.delete(self._entry_key(n))
            if not isinstance(val, (RedisDict, RedisList)):
                continue
            val.__delete__(pointer_key=self._prefix)
        self._redis.delete(self._length_key)
        self._redis.delete(f"{self._prefix}::pointers")

    def _entry_key(self, index: int):
        return f"{self._prefix}:{index}"

    def __setitem__(self, index: int, value: Any):
        length = len(self)
        if index < 0:
            index = length + index
        if index < 0 or index >= length:
            raise IndexError("list assignment index out of range")
        key = self._entry_key(index)
        existing: Any = self.__getitem__(index)
        if existing and isinstance(existing, (RedisDict, RedisList)):
            existing.__delete__(pointer_key=self._prefix)
        if isinstance(value, (RedisDict, RedisList)):
            value = (
                [value._prefix]
                if isinstance(value, RedisList)
                else {"key": value._redis_key}
            )
        elif isinstance(value, (dict, list)):
            new_key = md5(f"{self._prefix}::{key}".encode("utf-8")).digest().hex()
            is_list = isinstance(value, list)
            sub_obj: dict | list = (
                RedisList(self._redis, new_key)
                if is_list
                else RedisDict(self._redis, new_key)
            )
            for k in value:
                v = k if is_list else value[k]
                if isinstance(sub_obj, RedisList):
                    sub_obj.append(v)
                else:
                    sub_obj[k] = v
            value = [new_key] if is_list else {"key": new_key}

        if isinstance(value, (dict, list)):
            val_key = value[0] if isinstance(value, list) else value["key"]
            pointers = RedisDict(self._redis, f"{val_key}::pointers")
            pointers[self._prefix] = 1

        self._redis.set(key, json.dumps(value))

    def append(self, item: Any):
        # Get current length
        length = len(self)
        # Store new item
        self._redis.set(self._entry_key(length), json.dumps("placeholder"))
        # Increment length
        self._redis.set(self._length_key, length + 1)
        self.__setitem__(length, item)

    def __getitem__(self, index: int):
        length = len(self)
        if index < 0:
            index = length + index
        if index < 0 or index >= length:
            raise IndexError("list index out of range")
        data = self._redis.get(self._entry_key(index))
        if data is None:
            return None
        parsed_data = json.loads(data)
        if isinstance(parsed_data, dict):
            parsed_data = RedisDict(self._redis, parsed_data.get("key", ""))
        elif isinstance(parsed_data, list):
            parsed_data = RedisList(self._redis, parsed_data[0])
        return parsed_data

    def insert(self, index: int, value: Any):
        length = len(self)
        if index < 0:
            index = max(0, length + index)
        if index > length:
            index = length
        # Shift subsequent entries
        for i in range(length - 1, index - 1, -1):
            data: Any = self._redis.get(self._entry_key(i))
            self._redis.set(self._entry_key(i + 1), data)
        # Insert new element
        self.__setitem__(index, value)
        # Update length
        self._redis.set(self._length_key, length + 1)

    def pop(self, index: int = -1):
        length = len(self)
        if index < 0:
            index = length + index
        if index < 0 or index >= length:
            raise IndexError("pop index out of range")
        # Get value to return
        value: Any = self.__getitem__(index)
        # Remove the element
        self._redis.delete(self._entry_key(index))
        # Shift subsequent entries
        for i in range(index + 1, length):
            data: Any = self._redis.get(self._entry_key(i))
            self._redis.set(self._entry_key(i - 1), data)
        # Decrement length
        self._redis.set(self._length_key, length - 1)
        return value

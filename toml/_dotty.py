# inspired by https://github.com/pawelzny/dotty_dict/tree/master

try:
    from collections import Mapping
except ImportError:
    Mapping = dict

try:
    from typing import Any
except ImportError:
    pass


class Dotty:
    """Minimal wrapper around a dict, adding support for `key.key` indexing."""

    SEPARATOR = "."

    def __init__(self, data: dict | None = None):
        """Create a new instance, either empty or around existing data."""

        if data is None:
            data = {}

        if not isinstance(data, Mapping):
            raise ValueError("data has to be a dict(like) object")

        self._data = data
        del data

    def __str__(self):
        return str(self._data)
    
    def __repr__(self):
        return f"<Dotty data={self}, separator='{self.SEPARATOR}'>"

    def _split(self, key: str) -> list[str]:
        return key.split(self.SEPARATOR)

    def __getitem__(self, key: str):
        item = self._data
        for k in self._split(key):
            item = item[k]
            del k

        return item

    def __getattr__(self, key):
        # dont override some dict builtins (eg `items`)
        if hasattr(self._data, key):
            return getattr(self._data, key)
        
        value = self._data[key]
        # wrap on a Dotty to allow: dotty_dict.key.subkey
        if isinstance(value, Mapping):
            value = Dotty(value)

        return value

    def __setitem__(self, key: str, value: Any) -> Mapping:
        def _get_or_create(item: Mapping, k: str):
            if k not in item:
                item[k] = {}

            return item[k]

    
        keys = self._split(key)

        item = self._data
        while len(keys) > 1:
            item = _get_or_create(item, keys.pop(0))

        item[keys.pop()] = value

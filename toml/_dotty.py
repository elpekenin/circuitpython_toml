# inspired by https://github.com/pawelzny/dotty_dict/tree/master

try:
    # types are needed on compyter
    from typing import Any, Optional
except ImportError:
    pass


class Dotty:
    """Minimal wrapper around a dict, adding support for `key.key` indexing."""

    tables: set[str]
    """Stores the tables on this DottyDict."""

    _BASE_DICT: str = "__base__"
    """Special id to return the base dict."""

    def __init__(
        self,
        __data: Optional[dict] = None,
        *,
        fill_tables: bool = False
    ):
        """Create a new instance, either empty or around existing data."""

        if __data is None:
            __data = {}

        if not isinstance(__data, dict):
            raise ValueError("data to be wrapped has to be a dict.")

        self._data = __data

        # set ensures no duplications
        # shouldnt happen anyway, due to _get_or_create's logic
        self.tables = set()

        # _BASE_DICT => items at root of the dict
        self.tables.add(self._BASE_DICT)

        if not fill_tables:
            return

        def _fill(key: str, value: Any):
            """Helper to iterate nested dicts"""

            if isinstance(value, dict):
                self.tables.add(key)

                for k, v in value.items():
                    _fill(f"{key}.{k}", v)

        for k, v in self._data.items():
            _fill(k, v)

    def __str__(self):
        """String just shows the dict inside."""
        return str(self._data)

    def __repr__(self):
        """Repr shows data and tables"""
        return f"<Dotty data={self._data}, tables={self.tables}>"

    @staticmethod
    def split(key: str) -> tuple[list[str], str]:
        """Splits a key into last element and rest of them.

            >>> split("foo")
            >>> [], "foo"

            >>> split("foo.bar")
            >>> ["foo"], "bar"

            >>> split("foo.bar.baz")
            >>> ["foo", "bar"], "baz"
        """

        parts = key.split(".")
        return parts[:-1], parts[-1]

    def __getitem__(self, key: str) -> Any:
        """Syntactic sugar to get a nested item."""

        # special case, return base dict
        if key == self._BASE_DICT:
            return self._data

        keys, last = self.split(key)

        item = self._data
        for k in keys:
            item = item[k]

        return item[last]

    def _get_or_create(self, item: dict, k: str, global_key: str) -> dict:
        """Helper function that creates the nested dict if not present."""

        if k not in item:
            # Add to tables             v get rid of heading dot
            self.tables.add(global_key[1:])

            item[k] = {}

        return item[k]

    def __setitem__(self, key: str, value: Any):
        """Syntactic sugar to set a nested item."""

        if key == self._BASE_DICT:
            raise KeyError(f"Using '{self._BASE_DICT}' as key is not supported")

        keys, last = self.split(key)
        global_key = ""

        item = self._data
        for k in keys:
            global_key += f".{k}"
            item = self._get_or_create(item, k, global_key)

        item[last] = value

    def __getattr__(self, key: str) -> Any:
        """Redirect some methods to dict's builtin ones. Perhaps not too useful."""

        if hasattr(self._data, key):
            return getattr(self._data, key)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{key}'")

    def __eq__(self, __value: object) -> bool:
        klass = self.__class__

        if not isinstance(__value, klass):
            raise ValueError(
                f"Comparation not implemented for {klass} and {type(__value)}"
            )

        return self._data == __value._data

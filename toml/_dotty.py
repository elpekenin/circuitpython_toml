# inspired by https://github.com/pawelzny/dotty_dict/tree/master

try:
    # types are needed on compyter
    from typing import Optional
except ImportError:
    pass


class Dotty:
    """Minimal wrapper around a dict, adding support for `key.key` indexing."""

    _tables: set[str]
    """Stores the tables on this DottyDict."""

    _BASE = object()
    """Special id to return the base dict."""

    __DEFAULT_SEPARATOR = "."

    def __init__(
        self,
        __data: Optional[dict] = None,
        *,
        fill_tables: bool = False,
        separator: str = __DEFAULT_SEPARATOR,
    ):
        """Create a new instance, either empty or around existing data."""

        if __data is None:
            __data = {}

        if not isinstance(__data, dict):
            raise ValueError("data to be wrapped has to be a dict.")

        self._data = __data
        self._separator = separator

        # set ensures no duplications
        # shouldnt happen anyway, due to _get_or_create's logic
        self._tables = set()

        # _BASE => items at root of the dict
        self._tables.add(self._BASE)

        if fill_tables:
            def _fill(key: str, value: object) -> None:
                """Helper to iterate nested dicts"""

                if isinstance(value, dict):
                    self._tables.add(key)

                    for k, v in value.items():
                        _fill(f"{key}{self._separator}{k}", v)

            for k, v in self._data.items():
                _fill(k, v)

    def __str__(self):
        """String just shows the dict inside."""
        return str(self._data)

    @property
    def tables(self) -> list[list[str]]:
        """
        Return a list of "paths" to nested tables.

        e.g. with separator "__" and `self._tables = "nested__table"`
        this will return a two-element list (an entry for each table)
        where each entry will be the list of breadcrumbs:
        [
            ["nested"],
            ["nested", "table"]
        ]
        """

        ret = [self._BASE]
        for table in self._tables:
            if table == self._BASE:
                continue

            ret.append(table.split(self._separator))

        def _order(x):
            """Little helper to sort the tables."""
            return (
                # len cant be -1 on a string, this ensures root elements being first
                -1
                if x == self._BASE
                else len(str(x))
            )

        return sorted(ret, key=_order)

    def __repr__(self):
        """Repr shows data and tables"""
        separator = (
            f", separator={self._separator}"
            if self._separator != self.__DEFAULT_SEPARATOR
            else ""
        )
        tables = self.tables
        tables.remove(self._BASE)
        table_str = (
            f", tables={tables}"
            if tables
            else ""
        )
        return f"<Dotty data={self._data}{separator}{table_str}>"

    def split(self, key: str) -> tuple[list[str], str]:
        """
        Splits a key into last element and rest of them.

        >>> split("foo")
        >>> [], "foo"

        >>> split("foo.bar")
        >>> ["foo"], "bar"

        >>> split("foo.bar.baz")
        >>> ["foo", "bar"], "baz"
        """

        # dont try to split non-str keys
        if not isinstance(key, str):
            return [], key

        parts = key.split(".")
        return parts[:-1], parts[-1]

    def __getitem__(self, __key: object) -> object:
        """Syntactic sugar to get a nested item."""

        # special case, return base dict
        if __key == self._BASE:
            return self._data

        keys, last = self.split(__key)

        table = self._data
        for k in keys:
            table = table[k]

        return table[last]

    def _get_or_create(self, item: dict, k: str, global_key: str) -> dict:
        """Helper function that creates the nested dict if not present."""

        if k not in item and isinstance(item, dict):
            # Add to tables             v get rid of heading separator(s)
            self._tables.add(global_key.lstrip(self._separator))

            item[k] = {}

        return item[k]

    def __setitem__(self, __key: str, __value: object):
        """
        Syntactic sugar to set a nested item.

        Known limitation, setting dicts doesn't update `self.tables`.
        ie, expect issues with code like:
        >>> dotty["foo"] = {"bar": baz}
        """

        keys, last = self.split(__key)
        global_key = ""

        table = self._data
        for k in keys:
            global_key += self._separator + k
            table = self._get_or_create(table, k, global_key)

        table[last] = __value

    # === Main logic of Dotty ends here ===
    # Below this point, it's mainly convenience for some operator/builtins

    def __getattr__(self, __key: str) -> object:
        """
        Redirect some methods to dict's builtin ones. Perhaps not too useful.

        Apparently not too useful on CP
          > https://github.com/elpekenin/circuitpython_toml/issues/4
        """
        if hasattr(self._data, __key):
            return getattr(self._data, __key)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{__key}'")

    def __eq__(self, __value: object) -> bool:
        klass = self.__class__

        if not isinstance(__value, klass):
            raise ValueError(
                f"Comparation not implemented for {klass} and {type(__value)}"
            )

        return self._data == __value._data

    def __contains__(self, __key: object) -> bool:
        try:
            self.__getitem__(__key)
            return True
        except KeyError:
            return False

    def __delitem__(self, __key: object):
        keys, last = self.split(__key)

        parent_table = None
        table = self._data
        for k in keys:
            parent_table = table
            table = table[k]

        # remove item from its table
        del table[last]

        # if table is empty after that, remove it too
        if len(table) == 0:
            if parent_table:
                parent_table.pop(keys[-1])

            self._tables.remove(self._separator.join(keys))

        # if key was a table itself, remove it (and children) from set
        if __key in self._tables:
            self._tables.remove(__key)

            for table in self._tables.copy():
                if (
                    table != self._BASE
                    and table.startswith(f"{__key}{self._separator}")
                ):
                    self._tables.remove(table)

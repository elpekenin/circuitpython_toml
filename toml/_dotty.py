# SPDX-FileCopyrightText: 2024 Pablo Martinez Bernal (elpekenin)
#
# SPDX-License-Identifier: MIT

"""Convenience class around a dict, to allow accessing nested dicts with dotted keys.

Inspired by https://github.com/pawelzny/dotty_dict/tree/master
"""

from __future__ import annotations

import warnings


class Dotty:
    """Minimal wrapper around a dict, adding support for `key.key` indexing."""

    _BASE = object()
    """Special id to return the base dict."""

    def __init__(self, __data: dict | None = None) -> None:
        """Create a new instance, either empty or around existing data."""
        if __data is None:
            __data = {}

        if not isinstance(__data, dict):
            msg = "Data to be wrapped has to be a dict."
            raise TypeError(msg)

        self.data = __data

    def __str__(self) -> str:
        """Represent this instance."""
        return str(self.data)

    def __repr__(self) -> str:
        """Represent this instance."""
        return f"<Dotty data={self.data}>"

    @staticmethod
    def split(key: object) -> tuple[list[str], object]:
        """Split a key into last element and rest of them.

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

        *parts, last = key.split(".")
        return parts, last

    def __getitem__(self, __key: object) -> object:
        """Syntactic sugar to get a nested item."""
        # special case, return base dict
        if __key == self._BASE:
            return self.data

        keys, last = self.split(__key)

        table = self.data
        for k in keys:
            table = table[k]

        return table[last]

    @staticmethod
    def validate_keys(*parts: object) -> None:
        """Warn used about problematic keys."""
        for part in parts:
            if isinstance(part, str) and ("." in part or part == ""):
                msg = (
                    "Empty keys and keys with dots will be added to structure"
                    " correctly, but you will have to read them manually from the"
                    " `Dotty` object."
                )
                warnings.warn(msg)  # noqa: B028  # CircuitPython has no stacklevel
                return

    def get_or_create_dict(self, parts: list[str]) -> dict:
        """Get a nested dict from its "path", create parent(s) if needed."""
        global_key = ""
        table = self.data

        for part in parts:
            if not isinstance(table, dict):
                msg = "Something went wrong on get_or_create_dict. This is not a dict."
                raise TypeError(msg)

            if part not in table:
                global_key += "." + part

                # create new dict
                table[part] = {}

            # update "location"
            table = table[part]

        return table

    def __setitem__(self, __key: str, __value: object) -> None:
        """Syntactic sugar to set a nested item."""
        keys, last = self.split(__key)

        self.validate_keys(last, *keys)
        table = self.get_or_create_dict(keys)

        table[last] = __value

    # === Main logic of Dotty ends here ===
    # Below this point, it's mainly convenience for some operator/builtins

    def __getattr__(self, __key: str) -> object:
        """Redirect some methods to dict's builtin ones. Perhaps not too useful.

        Apparently not too useful on CP
          > https://github.com/elpekenin/circuitpython_toml/issues/4
        """
        if hasattr(self.data, __key):
            return getattr(self.data, __key)

        msg = f"'{self.__class__.__name__}' has no attribute '{__key}'."
        raise AttributeError(msg)

    def __eq__(self, __value: object) -> bool:
        klass = self.__class__

        if not isinstance(__value, klass):
            msg = f"Comparation not implemented for {klass} and {type(__value)}."
            raise TypeError(msg)

        return self.data == __value.data

    def __contains__(self, __key: object) -> bool:
        try:
            self.__getitem__(__key)
        except KeyError:
            return False
        else:
            return True

    def __delitem__(self, __key: object) -> None:
        keys, last = self.split(__key)

        parent_table = None
        table = self.data
        for k in keys:
            parent_table = table
            table = table[k]

        # remove item from its table
        del table[last]

        # if table is empty after that, remove it too
        if len(table) == 0 and parent_table:
            parent_table.pop(keys[-1])

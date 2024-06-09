# SPDX-FileCopyrightText: 2024 Pablo Martinez Bernal (elpekenin)
#
# SPDX-License-Identifier: MIT

"""
Convenience class around a dict, to allow accessing nested dicts with dotted keys.

Inspired by https://github.com/pawelzny/dotty_dict/tree/master
"""

try:
    # types are needed on compyter
    from typing import Optional
except ImportError:
    pass

import warnings


class Dotty:
    """Minimal wrapper around a dict, adding support for `key.key` indexing."""

    _BASE = object()
    """Special id to return the base dict."""

    def __init__(self, __data: Optional[dict] = None):
        """Create a new instance, either empty or around existing data."""

        if __data is None:
            __data = {}

        if not isinstance(__data, dict):
            raise ValueError("data to be wrapped has to be a dict.")

        self.data = __data

    def __str__(self):
        """String just shows the dict inside."""
        return str(self.data)

    def __repr__(self):
        """Repr shows data"""
        return f"<Dotty data={self.data}>"

    @staticmethod
    def split(key: str) -> tuple[list[str], str]:
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

    def get_or_create_dict(self, parts: list[str]) -> dict:
        """
        Helper function to get a nested dict from its "path", creates
        parent(s) if they are not already present.
        """

        global_key = ""
        table = self.data

        warn_dot, warn_empty = False, False
        for part in parts:
            if not isinstance(table, dict):
                raise ValueError(
                    "Something went wrong on get_or_create_dict. This is not a dict."
                )

            if "." in part:
                warn_dot = True

            if part == "":
                warn_empty = True

            if part not in table:
                global_key += "." + part  #

                # create new dict
                table[part] = {}

            # update "location"
            table = table[part]

        if warn_dot:
            warnings.warn(
                "Keys with dots will be added to structure correctly, but you"
                " will have to read them manually from `Dotty._data`"
            )

        if warn_empty:
            warnings.warn(
                "Empty keys will be added to structure correctly, but you"
                " will have to read them manually from `Dotty._data`"
            )

        return table

    def __setitem__(self, __key: str, __value: object):
        """
        Syntactic sugar to set a nested item.
        """

        keys, last = self.split(__key)

        table = self.get_or_create_dict(keys)

        table[last] = __value

    # === Main logic of Dotty ends here ===
    # Below this point, it's mainly convenience for some operator/builtins

    def __getattr__(self, __key: str) -> object:
        """
        Redirect some methods to dict's builtin ones. Perhaps not too useful.

        Apparently not too useful on CP
          > https://github.com/elpekenin/circuitpython_toml/issues/4
        """
        if hasattr(self.data, __key):
            return getattr(self.data, __key)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{__key}'")

    def __eq__(self, __value: object) -> bool:
        klass = self.__class__

        if not isinstance(__value, klass):
            raise ValueError(
                f"Comparation not implemented for {klass} and {type(__value)}"
            )

        return self.data == __value.data

    def __contains__(self, __key: object) -> bool:
        try:
            self.__getitem__(__key)
            return True
        except KeyError:
            return False

    def __delitem__(self, __key: object):
        keys, last = self.split(__key)

        parent_table = None
        table = self.data
        for k in keys:
            parent_table = table
            table = table[k]

        # remove item from its table
        del table[last]

        # if table is empty after that, remove it too
        if len(table) == 0:
            if parent_table:
                parent_table.pop(keys[-1])

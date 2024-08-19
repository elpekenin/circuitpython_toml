# SPDX-FileCopyrightText: 2024 Pablo Martinez Bernal (elpekenin)
#
# SPDX-License-Identifier: MIT

"""Test suite for the library."""

import unittest

import toml
from toml._dotty import Dotty

TEST_FILE = "__test__.toml"


class Syntax(unittest.TestCase):
    """Minimal syntax check rules."""

    CANT_PARSE = "Couldn't parse value"

    def syntax_error(self, file: str, message: str) -> None:
        """Check messages coming from syntax errors."""
        # small incompatibility here
        if hasattr(self, "assertRaisesRegex"):
            with self.assertRaisesRegex(toml.TOMLError, message):
                toml.loads(file)

        else:
            with self.assertRaises(toml.TOMLError) as context_manager:
                toml.loads(file)

            # NOTE: This is for CircuitPython's 3rd party unittest lib, not
            #       the CPython stdlib's one. This attribute does exist.
            self.assertIn(
                message,
                str(context_manager.exception_value),  # type: ignore[attr-defined]
            )

    def test_no_table_nor_assignment(self) -> None:
        """Cant do nothing (if not an empty line)."""
        self.syntax_error("foo", "assignment or table setter")

    def test_table_and_assignment(self) -> None:
        """Can't be table and assignment at the same time."""
        self.syntax_error("[foo=bar]", "assignment and table setter")

    def test_assignment_without_value(self) -> None:
        """No value after equal sign."""
        self.syntax_error("foo = ", "nothing after equal sign")

    def test_extra_quote(self) -> None:
        """Unmatched quotes."""
        self.syntax_error("foo = 'bar''", "String was open but not closed")

    def test_content_after_string(self) -> None:
        """Can't have anything after a string."""
        self.syntax_error("foo = 'bar'baz", self.CANT_PARSE)

    def test_invalid_value(self) -> None:
        """String values must be quoted."""
        self.syntax_error("foo = bar", self.CANT_PARSE)

    def test_bool_casing(self) -> None:
        """Boolean are all-lowercase."""
        self.syntax_error("foo = True", self.CANT_PARSE)

    def test_negative_values(self) -> None:
        """bin, oct and hex numbers can't be negative."""
        self.syntax_error("foo = -0b10", "invalid")
        self.syntax_error("foo = -0o10", "invalid")
        self.syntax_error("foo = -0x10", "invalid")


class Issues(unittest.TestCase):
    """Reported issues that have been solved since."""

    # NOTE: CamelCase according to unittest's naming
    def assertParsedValue(  # noqa: N802
        self,
        file: str,
        expected: dict,
    ) -> None:
        """Check the parsed value(s)."""
        self.assertEqual(toml.loads(file), Dotty(expected))

    def test_3(self) -> None:
        """Empty dict raised exception before this issue got solved."""
        toml.dumps({"y": {}})

    def test_4(self) -> None:
        """There were some missing dunders, making stuff to fail."""
        with open(TEST_FILE) as file:  # noqa: PTH123  # CircuitPython doesn't have pathlib.Path
            data = toml.load(file)

        # __contains__
        self.assertTrue("foo" in data)
        self.assertFalse("__wrong__" in data)

        # __delitem__ (1) removing a table removes its children too
        data = Dotty(
            {"foo": {"bar": {"baz": {"value": 0}}}},
        )
        del data["foo.bar"]

        # keys do not exist
        self.assertNotIn("foo.bar", data)
        self.assertNotIn("foo.bar.baz", data)
        self.assertNotIn("foo.bar.baz.value", data)

        with self.assertRaises(KeyError):
            _ = data["foo.bar.bar.value"]

        # __delitem__ (2) removing single element on table, removes the table
        data = Dotty(
            {"foo": {"bar": 0}},
        )
        del data["foo.bar"]

        with self.assertRaises(KeyError):
            _ = data["foo.bar"]

    def test_5(self) -> None:
        """There was some now-fixed wrong string-related code."""
        self.assertParsedValue(
            """
            [card]
            bg = "tv"
            text = "This is a different card."
            options = [ ["(B)ack", "main"] ]
            """,
            {
                "card": {
                    "bg": "tv",
                    "text": "This is a different card.",
                    "options": [["(B)ack", "main"]],
                },
            },
        )

    def test_6(self) -> None:
        """Table should **not** reset after empty line."""
        self.assertParsedValue(
            """
            [test]
            one = true

            two = true
            """,
            {"test": {"one": True, "two": True}},
        )


class Misc(unittest.TestCase):
    """Miscellaneous tests."""

    def test_dump_and_load(self) -> None:
        """Loading the dump of a TOML retrieves the original data."""
        data = {"foo": "bar", "baz": {"foo": "bar"}}
        self.assertEqual(toml.loads(toml.dumps(data)), Dotty(data))


if __name__ == "__main__":
    unittest.main()

"""
Test suite for the library
"""

import unittest

import toml
from toml._dotty import Dotty

TEST_FILE = "__test__.toml"


class Syntax(unittest.TestCase):
    """Minimal syntax check rules."""

    CANT_PARSE = "Couldn't parse value"

    def syntax_error(self, file: str, message: str):
        """Common logic to check messages coming from syntax errors."""

        # small incompatibility here
        if hasattr(self, "assertRaisesRegex"):
            with self.assertRaisesRegex(toml.TOMLError, message):
                toml.loads(file)

        else:
            with self.assertRaises(toml.TOMLError) as cm:
                toml.loads(file)

            self.assertIn(message, str(cm.exception_value))

    def test_no_table_nor_assignment(self):
        self.syntax_error("foo", "assignment or table setter")

    def test_table_and_assignment(self):
        self.syntax_error("[foo=bar]", "assignment and table setter")

    def test_assignment_without_value(self):
        self.syntax_error("foo = ", "nothing after equal sign")

    def test_extra_quote(self):
        self.syntax_error("foo = 'bar''", "String was open but not closed")

    def test_content_after_string(self):
        self.syntax_error("foo = 'bar'baz", self.CANT_PARSE)

    def test_invalid_value(self):
        """String values must be quoted."""
        self.syntax_error("foo = bar", self.CANT_PARSE)

    def test_bool_casing(self):
        """Boolean are all-lowercase."""
        self.syntax_error("foo = True", self.CANT_PARSE)

    def test_negative_values(self):
        """bin, oct and hex numbers can't be negative."""
        self.syntax_error("foo = -0b10", self.CANT_PARSE)
        self.syntax_error("foo = -0o10", self.CANT_PARSE)
        self.syntax_error("foo = -0x10", self.CANT_PARSE)


class ParseMixin:
    def assertParsedValue(self, file: str, expected: dict):
        """Common logic to check the parsed value(s)."""
        self.assertEqual(toml.loads(file), Dotty(expected))


class Parse(unittest.TestCase, ParseMixin):
    """Values are parsed correctly."""

    def test_comments(self):
        self.assertParsedValue("# foo = bar", {})
        self.assertParsedValue("foo = 'bar'  # baz", {"foo": "bar"})

    def test_strings(self):
        self.assertParsedValue("foo = 'bar'", {"foo": "bar"})
        self.assertParsedValue("foo = '#bar'", {"foo": "#bar"})
        self.assertParsedValue("foo = '0'", {"foo": "0"})  # not an int

    def test_triple_strings(self):
        self.assertParsedValue("foo = '''bar'''", {"foo": "bar"})
        self.assertParsedValue("foo = '''bar'baz'''", {"foo": "bar'baz"})

    def test_numbers(self):
        self.assertParsedValue("foo = 0b10", {"foo": 0b10})
        self.assertParsedValue("foo = 0o34", {"foo": 0o34})
        self.assertParsedValue("foo = 0x34", {"foo": 0x34})
        self.assertParsedValue("foo = 1234", {"foo": 1234})
        self.assertParsedValue("foo = -234", {"foo": -234})
        self.assertParsedValue("foo = 1.34", {"foo": 1.34})
        self.assertParsedValue("foo = -2.4", {"foo": -2.4})

    def test_invalid_numbers(self):
        file = "foo = 0b9"
        message = "invalid"

        # small incompatibility here
        if hasattr(self, "assertRaisesRegex"):
            with self.assertRaisesRegex(ValueError, message):
                toml.loads(file)

        else:
            with self.assertRaises(ValueError) as cm:
                toml.loads(file)

            self.assertIn(message, str(cm.exception_value))

    def test_booleans(self):
        self.assertParsedValue("foo = false", {"foo": False})
        self.assertParsedValue("foo = true", {"foo": True})

    def test_lists(self):
        self.assertParsedValue("foo = []", {"foo": []})
        self.assertParsedValue("foo = [1, 2]", {"foo": [1, 2]})
        self.assertParsedValue("foo = [1, true, []]", {"foo": [1, True, []]})
        self.assertParsedValue("foo = [[1, 2], [1]]", {"foo": [[1, 2], [1]]})
        self.assertParsedValue("foo = [[[]], []]", {"foo": [[[]], []]})

    def test_tables(self):
        self.assertParsedValue(
            """
            foo = 0
            [bar]
            foo = 1
            [baz.baz]
            foo = 2
            """,
            {"foo": 0, "bar": {"foo": 1}, "baz": {"baz": {"foo": 2}}}
        )

    def test_escape_sequences(self):
        """
        We want parser to see the actual backslash, it has to be escaped too.
        """
        self.assertParsedValue("foo = 'bar\\\"baz'", {"foo": "bar\"baz"})
        self.assertParsedValue('foo = """bar\\""""', {"foo": 'bar"'})

    def test_dotted_keys(self):
        """Check that dots on quoted keys are parsed as expected."""
        self.assertParsedValue("foo.bar = 'baz'",   {"foo": {"bar": "baz"}})
        self.assertParsedValue("'foo.bar' = 'baz'", {"foo.bar": "baz"})
        self.assertParsedValue("'foo.bar'.baz = 0", {"foo.bar": {"baz": 0}})
        self.assertParsedValue("'foo.bar.baz' = 0", {"foo.bar.baz": 0})
        self.assertParsedValue("foo.'bar.baz' = 0", {"foo": {"bar.baz": 0}})


class Issues(unittest.TestCase, ParseMixin):
    """Reported issues that have been solved since."""

    def test_3(self):
        """Empty dict raised exception before this issue got solved."""
        toml.dumps({"y": {}})

    def test_4(self):
        """There were some missing dunders, making stuff to fail."""

        with open(TEST_FILE, "r") as f:
            data = toml.load(f)

        # __contains__
        self.assertTrue("foo" in data)
        self.assertFalse("__wrong__" in data)

        # __delitem__ (1) removing a table removes its children too
        data = Dotty(
            {
                "foo": {
                    "bar": {
                        "baz": {
                            "value": 0
                        }
                    }
                }
            },
        )
        del data["foo.bar"]

        # keys do not exist
        self.assertNotIn("foo.bar", data)
        self.assertNotIn("foo.bar.baz", data)
        self.assertNotIn("foo.bar.baz.value", data)

        with self.assertRaises(KeyError):
            data["foo.bar.bar.value"]

        # __delitem__ (2) removing single element on table, removes the table
        data = Dotty(
            {
                "foo": {
                    "bar": 0
                }
            },
        )
        del data["foo.bar"]

        with self.assertRaises(KeyError):
            data["foo.bar"]

    def test_5(self):
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
                    "options": [["(B)ack", "main"]]
                },
            }
        )

    def test_6(self):
        self.assertParsedValue(
            """
            [test]
            one = true

            two = true
            """,
            {"test": {"one": True, "two": True}}
        )


class Misc(unittest.TestCase):
    """Miscellaneous tests."""

    def test_dump_and_load(self):
        """Loading the dump of a TOML retrieves the original data"""

        data = {"foo": "bar", "baz": {"foo": "bar"}}
        self.assertEqual(
            toml.loads(toml.dumps(data)),
            Dotty(data)
        )


if __name__ == "__main__":
    unittest.main()

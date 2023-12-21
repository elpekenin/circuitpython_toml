"""
Small test suite for the library.
"""

try:
    from typing import Optional
except ImportError:
    pass

import toml
from toml._dotty import Dotty

TEST_FILE = "__test__.toml"
CANT_PARSE = "Couldn't parse value"


def underlined_print(msg):
    """Helper to print a header."""
    print(msg)
    print("-" * len(msg))


class TestError(Exception):
    """Custom class for test errors."""


def assertEqual(a, b):
    if a != b:
        raise TestError(f"{a} doesn't match {b}")


def assertTrue(a):
    assertEqual(a, True)


def assertFalse(a):
    assertEqual(a, False)


def assertIn(a, b):
    if a not in b:
        raise TestError(f"{a} is not contained in {b}")


def assertNotIn(a, b):
    if a in b:
        raise TestError(f"{a} is contained in {b}")


class AssertRaises:
    def __init__(
        self,
        *exceptions: list[Exception],
        msg: Optional[str] = None
    ):
        self.exc = exceptions
        self.msg = msg

    def __enter__(self) -> "AssertRaises":
        return self

    def __exit__(self, exc_t: type, exc_v: Exception, _exc_tb):
        # "assertion" failed, just let it raise
        if exc_t == SystemExit:
            return

        # unexpected exc or no expection when expected it
        if exc_t not in self.exc:
            raise TestError(f"Got {exc_t} while expecting {self.exc}")

        # exception message doesnt match the expected one
        if self.msg and self.msg.lower() not in str(exc_v).lower():
            raise TestError(f"Expected '{self.msg}' but got '{exc_v}'")

        return True


class Test:
    """Class to model a test."""

    def __init__(
        self,
        input_: str,
        label: str,
        output: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.input = input_
        self.label = label
        self.output = output
        self.message = message

    def run(self):
        # None or Exception
        expected_exc = (
            toml.TOMLError
            if self.message
            else None
        )

        with AssertRaises(expected_exc, msg=self.message):
            assertEqual(toml.loads(self.input), Dotty(self.output))


TESTS = [
    # minimal syntax checking
    Test(
        "empty_line",
        label="No scope nor equals",
        message="Either an assignment or scope setter",
    ),
    Test(
        "[3=2]",
        label="Scope and equals",
        message="Assignment and scope setter at the same time",
    ),
    Test("foo = ", label="Equals without value", message="Nothing after equal sign"),
    # valid string
    Test("foo = 'bar''", label="Extra quote", message="Malformed string"),
    Test("foo = 'bar'bad", label="Content after string", message=CANT_PARSE),
    Test("var = foo", label="Invalid value", message=CANT_PARSE),
    # bool casing
    Test("foo = True", label="Py-like boolean", message=CANT_PARSE),
    # for some reason, only negative floats and integers are supported
    Test("var = -0b10", label="Negative bin", message=CANT_PARSE),
    Test("var = -0o10", label="Negative oct", message=CANT_PARSE),
    Test("var = -0x10", label="Negative hex", message=CANT_PARSE),
    # ------------------------------------------------------------
    # parsing simple values
    Test("# var = foo", label="Standalone comment", output={}),
    Test("var = 'foo' # comment", label="Inline comment", output={"var": "foo"}),
    Test("var = '#foo'", label="String with #", output={"var": "#foo"}),
    Test("var = 'foo\"quote'", label="Quote in string", output={"var": 'foo"quote'}),
    Test("var = 'foo'", label="String", output={"var": "foo"}),
    Test("var =  '3'", label="String not casted", output={"var": "3"}),
    Test("var = 3", label="Positive int", output={"var": 3}),
    Test("var = -42", label="Negative int", output={"var": -42}),
    Test("var = 6.9", label="Positive float", output={"var": 6.9}),
    Test("var = 0x10", label="Positive hex", output={"var": 0x10}),
    Test("var = true", label="boolean", output={"var": True}),
    Test("var = [3, 2]", label="basic list", output={"var": [3, 2]}),
    # complex parsing, many types, with nested lists
    Test(
        """
        var = 'string'

        [numbers]
        integer = [1, -1]
        float = [1.1, -1.1]
        literals = [0b10, 0o10, 0x10]

        [bool]
        both = [true, false]

        [list.nesting]
        nested_and_empty = [[], [[]]]
        """,
        label="Everything",
        output={
            "var": "string",
            "numbers": {
                "integer": [1, -1],
                "literals": [0b10, 0o10, 0x10],
                "float": [1.1, -1.1],
            },
            "bool": {
                "both": [True, False],
            },
            "list": {"nesting": {"nested_and_empty": [[], [[]]]}},
        },
    ),
]


max_len = max(map(lambda x: len(x.label), TESTS))

underlined_print("Parsing")
for test in TESTS:
    padding = " " * (max_len - len(test.label))
    print(f"{padding}{test.label} >> ", end="")

    test.run()

    print("OK")


# =====

print()
underlined_print("Others")

# ensure dumping and reading end up with same data structure
# we cant use dump, as we -probably- have a read-only filesystem
print("dumps + loads == original")
data = {"foo": "bar", "nested": {"foo": "bar"}}
assertEqual(toml.loads(toml.dumps(data)), Dotty(data))


# Lets check that empty dicts dont break things
# https://github.com/elpekenin/circuitpython_toml/issues/3
print("dumping empty dict")
toml.dumps({"y": {}})


print("load from str")
from_str = toml.load(TEST_FILE)


print("load from file")
with open(TEST_FILE, "r") as f:
    from_file = toml.load(f)


print("from str == from file")
assertEqual(from_str, from_file)


print("wrong type")
with AssertRaises(toml.TOMLError, msg="Not a file?"):
    toml.load(42)

print("wrong mode")
with AssertRaises(toml.TOMLError, msg="File open in wrong mode?"):
    with open(TEST_FILE, "a") as f:
        toml.load(f)

# Lets check manually implemented dunders
# https://github.com/elpekenin/circuitpython_toml/issues/4
print("__contains__")
data = toml.load(TEST_FILE)
assertTrue("foo" in data)
assertFalse("__wrong__" in data)

print("__delitem__")
# ======
# case 1
# ======
# deleting a table causes its child to be deleted too
data = Dotty(
    {
        "nested": {
            "foo": {
                "bar": {
                    "baz": {
                        "value": 42
                    }
                }
            }
        }
    },
    fill_tables=True
)
del data["nested.foo"]

# target table deleted
assertNotIn("nested.foo", data)
assertNotIn("nested.foo.bar", data.tables)
# child table deleted
assertNotIn("nested.foo.bar.baz", data)
assertNotIn("nested.foo.bar.baz", data.tables)
# child item deleted
assertNotIn("nested.foo.bar.baz.value", data)
with AssertRaises(KeyError):
    data["nested.foo.bar.bar.value"]

# ======
# case 2
# ======
# deleting the only element on a table deletes the table itself
data = Dotty(
    {
        "nested": {
            "value": 42
        }
    },
    fill_tables=True
)
del data["nested.value"]

# --- item deleted
with AssertRaises(KeyError):
    data["nested.value"]

# --- would-be-empty table deleted
assertNotIn("nested", data.tables)

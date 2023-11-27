"""
Small test suite for the library.
"""

try:
    from typing import Optional
except ImportError:
    pass

import toml
from toml._dotty import Dotty


def underlined_print(msg):
    """Helper to print a header."""
    print(msg)
    print("-" * len(msg))


class TestError(Exception):
    """Custom class for test errors."""

    pass


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

    def __enter__(self) -> tuple[str, Dotty]:
        return self.input, Dotty(self.output)

    def __exit__(self, exc_t: type, exc_v: Exception, _exc_tb):
        # "assertion" failed, just let it raise
        if exc_t == SystemExit:
            return

        # None or Exception
        expected_exc = toml.TOMLError if self.message else None

        # unexpected exc or no expection when expected it
        if exc_t != expected_exc:
            raise TestError(f"Expected {expected_exc} but got {exc_t}")

        # exception message doesnt match the expected one
        if self.message and self.message.lower() not in str(exc_v).lower():
            raise TestError(f"Expected '{self.message}' but got '{exc_v}'")

        return True


CANT_PARSE = "Couldn't parse value"

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

    with test as (input_, expected):
        output: Dotty = toml.loads(input_)

        if output != expected:
            print(f"ERROR: Expected {expected} but got {output}")
            exit(1)

    print("OK")

print()
underlined_print("Others")

# Ensure dumping and reading end up with same data structure
# we cant use dump, as we -probably- have a read-only filesystem
print("dumps + loads == original")
data = {"foo": "bar", "nested": {"foo": "bar"}}
if toml.loads(toml.dumps(data)) != Dotty(data):
    raise TestError("Data doesn't match")

# https://github.com/elpekenin/circuitpython_toml/issues/3
# Lets check that empty dicts dont break things
print("dumping empty dict")
toml.dumps({"y": {}})

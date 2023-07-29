try: 
    from typing import Optional
except ImportError:
    pass

import toml
from toml._dotty import Dotty

class TestError(Exception):
    """Custom class for test errors."""
    pass


class Test:
    """Class to model a test."""
    def __init__(
            self,
            input_: str,
            output: Optional[str] = None,
            message: Optional[str] = None
        ):
        self.input = input_
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


TESTS = [
    ########################
    # Detect syntax errors #
    ########################

    # valid scope xor assignment
    Test("empty_line", message="Either an assignment or scope setter"),
    Test("[3=2]", message="Assignment and scope setter at the same time"),
    Test("foo = ", message="Nothing after equal sign"),

    # valid string
    Test("foo = 'bar''", message="Malformed string"),
    Test("foo = 'bar'bad", message="Content after closing the string"),

    ##################
    # Parsing values #
    ##################

    # comments
    Test("# var = foo", output={}),
    Test("var = foo # comment", output={"var": "foo"}),

    # escaping comment in string
    Test("var = '#foo'", output={"var": "#foo"}),

    # quote in string
    Test("var = 'foo\"quote'", output={"var": "foo\"quote"}),

    # no-quotes as string
    Test("var = foo", output={"var": "foo"}),

    # quoted string
    Test("var = 'foo'", output={"var": "foo"}),

    # quoted string doesnt get casted
    Test("var =  '3'", output={"var": '3'}),

    # numbers
    Test("var = 3", output={"var": 3}),
    Test("var = -42", output={"var": -42}),
    Test("var = 6.9", output={"var": 6.9}),
    Test("var = 0x10", output={"var": 0x10}),

    # bool
    Test("var = true", output={"var": True}),

    # list
    Test("var = [3, 2]", output={"var": [3, 2]}),
    Test("var = [True, false, 3, -4.6]", output={"var": [True, False, 3, -4.6]}),
]


max_len = max(map(lambda x: len(x.input), TESTS))

msg = "Running tests..."
print(msg)
print("-" * len(msg))

for test in TESTS:
    padding = " " * (max_len - len(test.input))
    print(f"{padding}{test.input} >> ", end="")

    with test as (input_, expected):
        output: Dotty = toml.loads(input_)

        if output != expected:
            print(f"ERROR: Expected {expected} but got {output}")
            exit(1)

    print("OK")

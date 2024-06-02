try:
    # types are needed on compyter
    from typing import Any, Optional
except ImportError:
    pass

import warnings
from io import StringIO

from ._dotty import Dotty

# TODO?: Move key warnings to Dotty's logic


class TOMLError(Exception):
    """Custom class for errors."""


class Tokens:
    """Different strings with "special" meaning."""

    OPENING_BRACKET = "["
    CLOSING_BRACKET = "]"
    QUOTE = "'"
    DQUOTE = '"'
    TRIPLE_QUOTE = "'''"
    TRIPLE_DQUOTE = '"""'
    EQUAL_SIGN = "="
    COMMENT = "#"
    COMMA = ","
    BACKSLASH = "\\"

    # triple has to be first, as regular quotes would match too
    # thus, this also needs to be a list, to maintain order
    QUOTES = [
        TRIPLE_QUOTE,
        TRIPLE_DQUOTE,
        QUOTE,
        DQUOTE,
    ]

    ALL = {
        OPENING_BRACKET,
        CLOSING_BRACKET,
        QUOTE,
        DQUOTE,
        TRIPLE_QUOTE,
        TRIPLE_DQUOTE,
        EQUAL_SIGN,
        COMMENT,
        COMMA,
        BACKSLASH,
    }


class ParsedLine:
    """Cleanup raw line's content and find tokens on it."""

    line: str
    """Clean line (strip()'ed and comments removed)."""

    tokens: dict[str, list[int]]
    """Mapping from tokens to the position(s) where they are found on the line."""

    def __str__(self) -> str:
        return f"line={self.line!r}, tokens={self.tokens!r}"

    __repr__ = __str__

    def __init__(self, __line: str):
        self.line = ""
        self.tokens = {t: [] for t in Tokens.ALL}

        quote_token = None

        stripped = __line.strip()
        length = len(stripped)

        i = 0
        while i < length:
            char = stripped[i]

            # upon finding a comment (not in a string), quit
            if (
                char == Tokens.COMMENT
                and quote_token is None
            ):
                # clean trailing spaces
                self.line = self.line.rstrip()
                return

            token, string, offset = Parser.string(stripped[i:])
            if string:
                self.tokens[token].append(i)
                self.tokens[token].append(i + offset)

                i += offset
                self.line += string

                continue

            i += 1
            self.line += char

            # store tokens' positions
            if char in Tokens.ALL:
                self.tokens[char].append(len(self.line) - 1)

        # clean trailing spaces
        self.line = self.line.rstrip()

    def is_empty(self) -> bool:
        """Whether this line contains anything."""
        return not bool(self.line)

    def key_value(self) -> tuple[str, str]:
        """Get the key and value on this line (ie: split on equal sign)."""

        assert len(self.tokens[Tokens.EQUAL_SIGN]), "How did we end up on key_value with len(EQUAL) != 1"

        split_at = self.tokens[Tokens.EQUAL_SIGN][0]
        key = self.line[:split_at].strip()
        value = self.line[split_at + 1 :].strip()

        return key, value


class Parser:
    """Get Python values out of strings."""

    @classmethod
    def string(cls, __value: str) -> tuple[str, str, int]:
        """
        Find the next **quoted** string in the input,
        return it and how much the cursor has been moved.

        Eg:
        >>> string("'''hello'world'''")
        >>> Tokens.TRIPLE_QUOTE, "hello'world", 17
        """

        quote_token = None
        string = ""
        i = 0

        for token in Tokens.QUOTES:
            sliced = __value[i : i+len(token)]
            if sliced == token:
                # opening quote
                if quote_token is None:
                    # store the string delimiter
                    quote_token = token

                    # the "clean" line should store single
                    # quotes, not triple, thus append just current char
                    string += token[0]

                    # store this token
                    i += len(token)

                    break

        # quote token not found, just exit
        else:
            return quote_token, string, i

        # TODO: Handle escape sequences
        length = len(__value)
        while i < length:
            char = __value[i]

            # TODO: Better handling of this
            if char == Tokens.BACKSLASH:
                # blindly add the next char
                string += __value[i + 1]

                # and jump over it
                i += 2
                continue

            # closing quote
            sliced = __value[i : i+len(quote_token)]
            if sliced == quote_token:
                string += quote_token[0]

                i += len(quote_token)

                return quote_token, string, i

            i += 1
            string += char

        # if we get down here, check that we did not had not found an opening
        if quote_token is not None:
            raise TOMLError("String was open but not closed.")

    @classmethod
    def key(cls, __key: str) -> list[str]:
        """
        Sanitize keys with quotes, giving the "path" to it.
        """

        # Note: The "__" here is Parser._SEPARATOR
        #         input | output
        #         ------|-------
        #       foo.bar | ["foo", "bar"]
        #     "foo.bar" | ["foo.bar"]
        # "foo.bar.baz" | ["foo.bar.baz"]
        # "foo.bar".baz | ["foo.bar", "baz"]

        parts = [None]
        length = len(__key)

        i = 0
        while i < length:
            _, string, offset = Parser.string(__key[i:])
            if string:
                i += offset
                # NOTE: string is quoted, eg from a """hello"world"""
                #       we get "hello\"world", stip head and trail quotes
                #       but dont use .replace() as we might remove actual info
                parts.append(string[1:-1])
                continue

            char = __key[i]
            if char == ".":
                parts.append(None)
            else:
                # do not add whitespace chars
                if not char.isspace():
                    # if last part is empty (None), replace it
                    if parts[-1] is None:
                        parts[-1] = ""

                    parts[-1] += char

            i += 1

        # remove the (potential) empty strings that got added
        clean = []
        warn_dot, warn_empty = False, False
        for part in parts:
            if part is None:
                continue

            if "." in part:
                warn_dot = True

            if part == "":
                warn_empty = True

            clean.append(part)

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

        return clean

    @classmethod
    def value(cls, __value: str, __line_info: Optional[ParsedLine] = None) -> Any:
        """
        (Try) Convert a string into a Python value.

        Note: __line_info is only used when parsing lists
        """

        # quoted string, has to be first, to prevent casting it
        if Syntax.is_quoted(__value):
            # remove quotes
            return __value[1:-1]

        # integer
        if __value.isdigit():
            return int(__value)

        # float
        if (
            __value.count(".") == 1
            # if replacing a single dot with 0 yields a number, this was a float
            and __value.replace(".", "0", 1).isdigit()
        ):
            return float(__value)

        # bin/octal/hex literal
        if __value[0] == "0":
            specifier = __value[1].lower()
            base = {"b": 2, "o": 8, "x": 16}.get(specifier, 0)
            return int(__value, base)

        # positive prefix, aka do nothing
        if __value[0] == "+":
            return cls.value(__value[1:])

        # negative numbers
        if __value[0] == "-":
            # spec does not allow negative numbers with base prefix
            if __value[1:3] not in ("0b", "0o", "0x"):
                return -cls.value(__value[1:])

        # bool
        if __value in {"true", "false"}:
            return __value.lower() == "true"

        # array
        if Syntax.is_in_brackets(__value):
            if __line_info is None:
                raise TOMLError("How did we end on array parsing without line info?")

            opening = __line_info.tokens[Tokens.OPENING_BRACKET]
            closing = __line_info.tokens[Tokens.CLOSING_BRACKET]

            if len(opening) != len(closing):
                raise TOMLError("Mismatched brackets.")

            value, _ = cls.list(__line_info.line, opening[0] + 1)
            return value

        # couldn't parse, raise Exception
        raise TOMLError(
            f"Couldn't parse value: `{__value}` (Hint, remember to wrap strings in quotes)"
        )

    @classmethod
    def list(cls, __line: str, __start: int) -> tuple[list[Any], int]:
        """
        Helper to parse a list.
        Returns parsed list + where next element starts
        """

        pos = __start
        text = ""
        elements = []
        while pos < len(__line):
            char = __line[pos]
            pos += 1

            # early stop when current list ends
            if char == Tokens.CLOSING_BRACKET:
                _text = text.strip()
                if _text:
                    elements.append(cls.value(_text))
                return elements, pos

            # parse list and update current position
            elif char == Tokens.OPENING_BRACKET:
                text = ""
                value, pos = cls.list(__line, pos)
                if value is not None:
                    elements.append(value)

            # parse the element we have collected so far
            elif char == Tokens.COMMA:
                _text = text.strip()
                if _text:
                    elements.append(cls.value(_text))
                text = ""

            # collect another char
            else:
                text += char

        # how do we get here?
        return elements, pos

    @classmethod
    def toml(cls, __toml: str) -> Dotty:
        """
        Parse a whole TOML string.
        """

        table_name = []
        data = Dotty()

        lines = __toml.replace("\r", "").split("\n")
        for i, raw_line in enumerate(lines, 1):
            parsed_line = ParsedLine(raw_line)

            # empty line => nothing to be done
            if parsed_line.is_empty():
                continue

            message = Syntax.check(parsed_line)
            if message:
                raise TOMLError(f"{message} in line {i}")

            # at this point, line should have content and correct syntax, this code can be rather dumb
            # we can't strip or anything like that tho, indexes would be broken

            # equal sign => assignment expresion
            if Syntax.is_assignment(parsed_line):
                key, value = parsed_line.key_value()

                *parts, last = cls.key(key)
                parts = table_name + parts

                table = data._create(parts)
                table[last] = cls.value(value, parsed_line)

            # no equal sign => table assignment, ie: [table]
            else:
                # remove "[" and "]", handle quotes/dots
                table_name = cls.key(parsed_line.line[1:-1])

        return data


class Syntax:
    """Tiny helpers for syntax."""

    @staticmethod
    def check(__parsed: ParsedLine) -> Optional[str]:
        """Run some checks."""

        #######################
        # Table or assignment #
        #######################
        is_assignment = Syntax.is_assignment(__parsed)
        is_table_setter = Syntax.is_in_brackets(__parsed.line)

        if not is_assignment and not is_table_setter:
            return "Line has to contain either an assignment or table setter"

        if is_assignment and is_table_setter:
            return "Line cant be an assignment and table setter at the same time"

        ##############
        # Assignment #
        ##############
        if is_assignment and not len(__parsed.line) > (__parsed.tokens[Tokens.EQUAL_SIGN][0] + 1):
            return "Invalid assignment, nothing after equal sign"

        # If we got here, everything was correct
        # Empty string => No exception raised
        return ""


    @staticmethod
    def is_quoted(__val: str) -> bool:
        """Check if a string is quoted."""
        return __val[0] == __val[-1] and __val[0] in Tokens.QUOTES

    @staticmethod
    def is_assignment(__parsed: ParsedLine) -> bool:
        """Whether this line contains an assignment."""
        return bool(__parsed.tokens[Tokens.EQUAL_SIGN])

    @staticmethod
    def is_in_brackets(__val: str) -> bool:
        return (
            __val[0] == Tokens.OPENING_BRACKET
            and __val[-1] == Tokens.CLOSING_BRACKET
        )


##############
# Public API #
##############
def loads(__str: str) -> Dotty:
    """Parse TOML from a string."""
    return Parser.toml(__str)


def load(__file: "File") -> Dotty:
    """Parse TOML from a file-like."""
    return loads(__file.read())


def dumps(__data: Dotty | dict) -> str:
    """Write a (dotty) dict as TOML into a string."""

    if not isinstance(__data, (Dotty, dict)):
        raise TOMLError("dumping is only implemented for dict-like objects")

    # enclose on a dict, to easily find the "tables" on it
    if isinstance(__data, dict):
        __data = Dotty(__data, fill_tables=True)

    def _order(x):
        """Little helper to sort the tables."""
        return (
            # len cant be -1 on a string, this ensures root elements being first
            -1
            if x == __data._BASE
            else len(x)
        )

    out = StringIO()
    for table_name in sorted(__data.tables, key=_order):
        table: dict = __data[table_name]

        # special case for tables without direct childs (ie: only nested ones)
        # skip them
        if all(map(lambda x: isinstance(x, dict), table.values())):
            continue

        # special case for items at root of the dict
        if table_name != __data._BASE:
            # apparently an empty string is a valid name...
            if table_name == "":
                table_name = '""'
            out.write(f"[{table_name}]\n")

        for key, value in table.items():
            # will be handled by another iteration
            if isinstance(value, dict):
                continue

            # enclose string in quotes to prevent casting it when reading
            if isinstance(value, str):
                value = f'"{value}"'

            # if key contains a dot, quote it to maintain the data format
            # if empty, make a string with quotes on it, to achieve the same
            if "." in key or key == "":
                key = f'"{key}"'

            out.write(f"{key}={value}\n")

        # empty line for readability
        out.write("\n")

    return out.getvalue()


def dump(__data: Dotty | dict, __file: "File"):
    """Write a (dotty) dict as TOML into a file."""
    __file.write(dumps(__data))


__all__ = [
    "TOMLError",
    "loads",
    "load",
    "dumps",
    "dump",
]

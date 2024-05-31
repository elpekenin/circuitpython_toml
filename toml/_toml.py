try:
    # types are needed on compyter
    from typing import Any, Optional
except ImportError:
    pass

from io import StringIO
from ._dotty import Dotty


class TOMLError(Exception):
    """Custom class for errors."""


class Tokens:
    OPENING_BRACKET = "["
    CLOSING_BRACKET = "]"
    SINGLE_QUOTE = "'"
    DOUBLE_QUOTE = '"'
    EQUAL_SIGN = "="
    COMMENT = "#"
    COMMA = ","

    QUOTES = {
        SINGLE_QUOTE,
        DOUBLE_QUOTE,
    }

    ALL = {
        OPENING_BRACKET,
        CLOSING_BRACKET,
        SINGLE_QUOTE,
        DOUBLE_QUOTE,
        EQUAL_SIGN,
        COMMA,
    }


class LineInfo:
    """Cleanup raw line's content and find tokens on it."""

    line: str
    """Clean line (strip()'ed and comments removed)."""

    tokens: dict
    """Mapping from tokens to the position(s) where they are found on the line."""

    assignment: int = -1
    """Position of the equal sign, -1 if none."""

    had_comment: bool = False
    """Whether the line contained a comment."""

    def __init__(self, __line: str):
        self.line = ""
        self.tokens = {t: [] for t in Tokens.ALL}

        in_quotes = False
        quote_token = None
        for i, char in enumerate(__line.lstrip()):
            # upon finding a comment (not in a quoted string), quit
            if char == Tokens.COMMENT and not in_quotes:
                # clean trailing spaces
                self.line = self.line.rstrip()
                self.had_comment = True
                return

            # add current char to "clean" string
            self.line += char

            if char in Tokens.QUOTES:
                # opening quote
                if not quote_token:
                    in_quotes = True
                    quote_token = char
                    self.tokens[char].append(i)
                    continue

                # closing quote
                elif char == quote_token:
                    in_quotes = False
                    quote_token = None
                    self.tokens[char].append(i)
                    continue

            # no token data to be stored if we are in a string
            if in_quotes:
                continue

            # metadata about tokens
            if char in Tokens.ALL:
                self.tokens[char].append(i)

                # assignment location
                if char == Tokens.EQUAL_SIGN and self.assignment == -1:
                    self.assignment = i

        # clean trailing spaces
        self.line = self.line.rstrip()


class SyntaxChecker:
    """Some basic syntax rules based on the tokens found."""

    @staticmethod
    def check(info: LineInfo) -> Optional[str]:
        """Run some checks."""

        #################
        # String checks #
        #################

        single = len(info.tokens[Tokens.SINGLE_QUOTE])
        double = len(info.tokens[Tokens.DOUBLE_QUOTE])

        # every openning quote should be closed too
        if single % 2 != 0 or double % 2 != 0:
            return "Malformed string, check out your quotes"

        #######################
        # Table or assignment #
        #######################
        is_assignment = info.assignment != -1
        is_table_setter = (
            info.line[0] == Tokens.OPENING_BRACKET
            and info.line[-1] == Tokens.CLOSING_BRACKET
        )

        if not (is_assignment or is_table_setter):
            return "Line has to contain either an assignment or table setter"

        if is_assignment and is_table_setter:
            return "Line cant be an assignment and table setter at the same time"

        ##############
        # Assignment #
        ##############
        if is_assignment and not len(info.line) > (info.assignment + 1):
            return "Invalid assignment, nothing after equal sign"

        # If we got here, everything was correct
        # Empty string => No exception raised
        return ""


class Parser:
    """Extract information from a TOML."""

    data: Dotty
    """Dotty dict where the information from the TOML is stored."""

    _table: str
    """Current table ([table], [another.table]) of the parser."""

    def __init__(self, __text: str):
        """Parse incoming TOML."""

        self.data = Dotty()
        self._table = ""

        lines = __text.replace("\r", "").split("\n")
        for i, line in enumerate(lines, 1):
            # TODO: Remove comments before processing the line
            self._parse_line(i, line)

    def _parse_value(self, __value: str, __line_info: Optional[LineInfo] = None) -> Any:
        """
        (Try) Convert a string into a value.

        Note: __line_info is only used when parsing lists
        """

        # quoted string, has to be first, to prevent casting it
        if __value[0] in Tokens.QUOTES and __value[0] == __value[-1]:
            return __value[1:-1]

        # integer
        if __value.isdigit():
            return int(__value)

        # negative integer
        if __value[0] == "-" and __value[1:].isdigit():
            return -int(__value[1:])

        # float
        if (
            __value.count(".") == 1
            # if replacing a single dot with 0 yields a number, this was a float
            and __value.replace(".", "0", 1).isdigit()
        ):
            return float(__value)

        # negative float
        if (
            __value.count(".") == 1
            and __value[0] == "-"
            and __value[1:].replace(".", "0", 1).isdigit()
        ):
            return -float(__value[1:])

        # bin/octal/hex literal
        if __value[0] == "0":
            specifier = __value[1].lower()
            base = {"b": 2, "o": 8, "x": 16}.get(specifier, 0)
            return int(__value, base)

        # bool
        if __value in {"true", "false"}:
            return __value.lower() == "true"

        # array
        if (
            __value[0] == Tokens.OPENING_BRACKET
            and __value[-1] == Tokens.CLOSING_BRACKET
        ):
            if __line_info is None:
                raise TOMLError("How did we end on array parsing without line info?")

            opening = __line_info.tokens[Tokens.OPENING_BRACKET]
            closing = __line_info.tokens[Tokens.CLOSING_BRACKET]

            if len(opening) != len(closing):
                raise TOMLError("Mismatched brackets.")

            value, _ = self._parse_list(__line_info.line, opening[0] + 1)
            return value

        # couldn't parse, raise Exception
        raise TOMLError(
            f"Couldn't parse value: `{__value}` (Hint, remember to wrap strings in quotes)"
        )

    def _parse_assignment(self, __line_info: LineInfo) -> None:
        split_at = __line_info.tokens[Tokens.EQUAL_SIGN][0]
        _key = __line_info.line[:split_at].strip()
        _value = __line_info.line[split_at + 1 :].strip()

        key = f"{self._table}.{_key}" if self._table else _key
        self.data[key] = self._parse_value(_value, __line_info)

    def _parse_list(self, __line: str, __start: int) -> tuple[list[Any], int]:
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
                    elements.append(self._parse_value(_text))
                return elements, pos

            # parse list and update current position
            elif char == Tokens.OPENING_BRACKET:
                text = ""
                value, pos = self._parse_list(__line, pos)
                if value is not None:
                    elements.append(value)

            # parse the element we have collected so far
            elif char == Tokens.COMMA:
                _text = text.strip()
                if _text:
                    elements.append(self._parse_value(_text))
                text = ""

            # collect another char
            else:
                text += char

        # how do we get here?
        return elements, pos

    def _parse_line(self, __i: int, __line: str) -> None:
        """Extract information from a line and add it to the Dotty."""

        # get information about this line
        info = LineInfo(__line)

        # empty line => nothing to be done
        if not info.line:
            return

        message = SyntaxChecker.check(info)
        if message:
            raise TOMLError(f"{message} in line {__i}")

        # at this point, line should have content and correct syntax, this code can be rather dumb
        # we can't strip or anything like that tho, indexes would be broken

        # equal sign => assignment expresion
        if Tokens.EQUAL_SIGN in info.line:
            self._parse_assignment(info)

        # no equal sign => table assignment, ie: [table]
        else:
            # remove "[" and "]"
            self._table = info.line[1:-1]


##############
# Public API #
##############
def loads(__str: str) -> Dotty:
    """Parse TOML from a string."""
    return Parser(__str).data


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
        table = __data[table_name]

        # special case for tables without direct childs (ie: only nested ones)
        # skip them
        if all(map(lambda x: isinstance(x, dict), table.values())):
            continue

        # special case for items at root of the dict
        if table_name != __data._BASE:
            out.write(f"[{table_name}]\n")

        for key, value in table.items():
            # will be handled by another iteration
            if isinstance(value, dict):
                continue

            # enclose string in quotes to prevent casting it when reading
            # actually, TOML enforces the use of quotes, while this lib does not
            if isinstance(value, str):
                value = f'"{value}"'

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

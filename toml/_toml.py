try:
    # types are needed on compyter
    from typing import Any, Optional
except ImportError:
    pass

from ._dotty import Dotty


class TOMLError(Exception):
    """Custom class for errors."""
    pass


class Tokens:
    OPENING_BRACKET = "["
    CLOSING_BRACKET = "]"
    SINGLE_QUOTE = "'"
    DOUBLE_QUOTE = "\""
    EQUAL_SIGN = "="
    COMMENT = "#"

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
    }


class LineInfo:
    """Cleanup raw line's content and find tokens on it."""

    line: str
    """Clean line (strip()'ed and comments removed)."""

    tokens: dict
    """Mapping from tokens to the position(s) where they are found on the line."""

    open_quote: int = -1
    """Position of the first " or ' found, -1 if none."""

    close_quote: int = -1
    """Position of the closing " or ', -1 if none."""

    assignment: int = -1
    """Position of the equal sign, -1 if none."""

    had_comment: bool = False
    """Whether the line contained a comment."""

    def __init__(self, __line: str):
        self.line = ""
        self.tokens = {t: [] for t in Tokens.ALL}

        in_quotes = False
        for i, char in enumerate(__line.lstrip()):
            # upon finding a comment (not in a quoted string), quit
            if (
                char == Tokens.COMMENT
                and not in_quotes
            ):
                # clean trailing spaces
                self.line = self.line.rstrip()
                self.had_comment = True
                return

            # add current char to "clean" string
            self.line += char

            # keep track of opening quote
            if (
                char in Tokens.QUOTES
                and self.open_quote == -1
            ):
                in_quotes = True
                self.open_quote = i

            # ... and where it ends
            if (
                in_quotes
                and i != self.open_quote
                and char == __line[self.open_quote]
            ):
                in_quotes = False
                self.close_quote = i

            # no token data to be stored if we are in a string
            if in_quotes:
                continue

            # metadata about tokens
            if char in Tokens.ALL:
                self.tokens[char].append(i)

                # assignment location
                if (
                    char == Tokens.EQUAL_SIGN
                    and self.assignment == -1
                ):
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

        # smallest (but not -1) index
        quoted = info.open_quote != -1

        # there can only be 2 delimiting quotes (open and close), but an arbritrary amount of the other one 
        if quoted and info.line.count(info.line[info.open_quote]) != 2:
            return "Malformed string, check out your quotes"

        if quoted and len(info.line) > (info.close_quote + 1):
            return "Cant have content after closing the string"

        #######################
        # Scope or assignment #
        #######################
        is_assignment = info.assignment != -1
        is_scope_setter = (
            info.line[0] == Tokens.OPENING_BRACKET
            and info.line[-1] == Tokens.CLOSING_BRACKET
        ) 

        if not (is_assignment or is_scope_setter):
            return (
                "Line has to contain either "
                "an assignment or scope setter"
            )

        if is_assignment and is_scope_setter:
            return (
                "Line cant be an assignment and "
                "scope setter at the same time"
            )

        ##############
        # Assignment #
        ##############
        if (
            is_assignment and
            not len(info.line) > (info.assignment + 1)
        ):
            return "Invalid assignment, nothing after equal sign"

        # If we got here, everything was correct
        # Empty string => No exception raised
        return ""


class Parser:
    """Extract information from a TOML."""

    data: Dotty
    """Dotty dict where the information from the TOML is stored."""

    _scope: str
    """Current scope ([scope], [another.scope]) of the parser."""

    _ignore_exc: bool
    """Whether TOMLError's are ignored."""

    def __init__(self, __text: str, *, ignore_exc: bool = True):
        """Parse incoming TOML."""

        self.data = Dotty()
        self._scope = "" 
        self._ignore_exc = ignore_exc

        lines = __text.replace("\r", "").split("\n")
        for i, line in enumerate(lines, 1):
            # TODO: Remove comments before processing the line
            self._parse_line(i, line)

    def _parse_value(self, __value: str) -> Any:
        """
        (Try) Convert a string into another type.
        
        >>> _parse_value("foo")
        >>> "foo"

        >>> _parse_value("3")
        >>> 3

        >>> _parse_value("-42")
        >>> -42

        >>> _parse_value("6.9")
        >>> 6.9

        >>> _parse_value("0x10")
        >>> 16

        >>> _parse_value("true")
        >>> True

        >>> _parse_value("FaLse")
        >>> False

        >>> _parse_value("[3, 2]")
        >>> [3, 2]

        """

        # quoted string, has to be first, to prevent casting it
        if (
            __value[0] in Tokens.QUOTES
            and __value[0] == __value[-1]
        ):
            return __value[1:-1]

        # integer
        if __value.isdigit():
            return int(__value)

        # negative integer
        if __value[0] == "-" and __value[1:].isdigit():
            return -int(__value[1:])

        # bin/octal/hex literal
        if __value[0] == "0":
            specifier = __value[1].lower()
            base = {
                "b": 2,
                "o": 8,
                "x": 16
            }.get(specifier, 0)
            return int(__value, base)
        
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

        # bool
        if __value.lower() in {"true", "false"}:
            return __value.lower() == "true"

        # array
        if (
            __value[0] == Tokens.OPENING_BRACKET
            and __value[-1] == Tokens.CLOSING_BRACKET
        ):
            return [
                self._parse_value(v.strip())
                for v in __value[1:-1].split(",")
            ]

        # couldn't parse, return as is (str)
        return __value

    def _add_item(self, __key: str, __value: str) -> None:
        key = f"{self._scope}.{__key}" if self._scope else __key
        self.data[key] = self._parse_value(__value)

    def _parse_line(self, __i: int, __line: str) -> None:
        """Extract information from a line and add it to the Dotty."""

        # get information about this line
        info = LineInfo(__line)

        # empty line clears scope
        if not info.line:
            # lines with comments dont clear scope, empty ones do
            if not info.had_comment:
                self._scope = ""
            return
        
        message = SyntaxChecker.check(info)
        if message and not self._ignore_exc:
            raise TOMLError(f"{message} in line {__i}")
        
        # at this point, line should have content and correct syntax, this code can be rather dumb
        # we can't strip or anything like that tho, indexes would be broken

        # equal sign => assignment expresion
        if Tokens.EQUAL_SIGN in info.line:
            split_at = info.tokens[Tokens.EQUAL_SIGN][0]

            key = info.line[:split_at].strip()
            value = info.line[split_at+1:].strip()

            self._add_item(key, value)

        # no equal sign => scope assignment, ie: [scope]
        else:
            # remove "[" and "]"
            scope = info.line[1:-1]
            self._scope = scope

##############
# Public API #
##############
def loads(__str: str, *, ignore_exc: bool = False) -> Dotty:
    """Parse TOML from a string."""
    return Parser(__str, ignore_exc=ignore_exc).data


def load(__file: "Path", *, ignore_exc: bool = False) -> Dotty:
    """Parse TOML from a file-like."""
    with open(__file, "r") as f:
        return loads(f.read(), ignore_exc=ignore_exc)


def dump(__data: Dotty | dict, __file: "Path"):
    """Write a (dotty) dict as TOML into a file."""

    if not isinstance(__data, (Dotty, dict)):
        raise TOMLError("dumping is only implemented for dict-like objects")

    # enclose on a dict, to easily find the "tables" on it
    if isinstance(__data, dict):
        __data = Dotty(__data, fill_tables=True)

    def _order(x):
        """Little helper to sort the tables."""
        return (
            # len cant be -1 on a string, this ensures root elements being first
            -1 if x == __data._BASE_DICT
            else len(x)
        )

    with open(__file, "w") as f:
        for table_name in sorted(__data.tables, key=_order):
            table = __data[table_name]

            # special case for tables without direct childs (ie: only nested ones)
            # skip them
            if all(map(lambda x: isinstance(x, dict), table.values())):
                continue

            # special case for items at root of the dict
            if table_name != __data._BASE_DICT:
                f.write(f"[{table_name}]\n")

            for key, value in table.items():
                # will be handled by another iteration
                if isinstance(value, dict):
                    continue

                # enclose string in quotes to prevent casting it when reading
                # actually, TOML enforces the use of quotes, while this lib does not
                if isinstance(value, str):
                    value = f"\"{value}\""

                f.write(f"{key}={value}\n")

            # empty line to reset scope + readability
            f.write("\n")


def dumps(__str: str, __file: "Path"):
    # parse it into a dict, and dump it
    dump(loads(__str), __file)


__all__ = [
    "TOMLError",
    "loads",
    "load",
    "dumps",
    "dump",
]
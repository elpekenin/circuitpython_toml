# SPDX-FileCopyrightText: 2024 Pablo Martinez Bernal (elpekenin)
#
# SPDX-License-Identifier: MIT

"""
Logic to parse a TOML file/string into a data structure. This structure
is a custom class (Dotty) around a regular dict, adding some convenience.
"""

try:
    # types are needed on computer (CPython)
    from typing import Any, Optional, Union
except ImportError:
    pass

import warnings
from io import StringIO

from ._dotty import Dotty


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

    @staticmethod
    def escaped_char(string: str) -> tuple[str, int]:
        """
        From TOML's documentation
        https://github.com/toml-lang/toml/blob/main/toml.md#string

        Returns replacement and how much to update the pointer.
        """

        replacements = {
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "f": "\f",
            "r": "\r",
            "e": 0x1B,  # "\e" is not a thing
            '"': '"',
            "\\": "\\",
        }

        escaped = string[0]

        replacement = replacements.get(escaped, None)
        if replacement is not None:
            return replacement, 1

        for specifier, width in (
            ("u", 8),
            ("u", 4),
            ("x", 2),
        ):
            if escaped != specifier:
                continue

            try:
                char = chr(int(string[1 : 1 + width], 16))
            except ValueError:
                continue

            return char, 1 + width

        # TODO: should this raise instead?
        warnings.warn(f"Unknown/invalid escape sequence '\\{escaped}'")
        return "\\" + escaped, 1


class ParsedLine:
    """Cleanup raw line's content and find tokens on it."""

    line: str
    """Clean line (strip()'ed and comments removed)."""

    tokens: dict[str, list[int]]
    """Mapping from tokens to the position(s) where they are found on the line."""

    def __str__(self) -> str:
        return f"line={self.line!r}, tokens={self.tokens!r}"

    __repr__ = __str__

    def __init__(self, line: str):
        self.line = ""
        self.tokens = {t: [] for t in Tokens.ALL}

        keep_escape = False

        stripped = line.strip()
        length = len(stripped)

        i = 0
        while i < length:
            char = stripped[i]

            # dont parse strings if we have an array
            # the array-parsing logic will take care of that later
            # and we dont want to do it twice
            token, string, offset = Parser.string(stripped[i:], keep_escape=keep_escape)
            if string:
                self.tokens[token].append(i)
                self.tokens[token].append(i + offset)

                i += offset
                self.line += string

                continue

            # upon finding a comment quit
            if char == Tokens.COMMENT:
                # clean trailing spaces
                self.line = self.line.rstrip()
                return

            i += 1
            self.line += char

            # store tokens' positions
            if char in Tokens.ALL:
                if char == Tokens.OPENING_BRACKET:
                    keep_escape = True

                self.tokens[char].append(len(self.line) - 1)

        # clean trailing spaces
        self.line = self.line.rstrip()

    def is_empty(self) -> bool:
        """Whether this line contains anything."""
        return not bool(self.line)

    def key_value(self) -> tuple[str, str]:
        """Get the key and value on this line (ie: split on equal sign)."""

        assert len(
            self.tokens[Tokens.EQUAL_SIGN]
        ), "How did we end up on key_value with len(EQUAL) != 1"

        split_at = self.tokens[Tokens.EQUAL_SIGN][0]
        key = self.line[:split_at].strip()
        value = self.line[split_at + 1 :].strip()

        return key, value


class Parser:
    """Get Python values out of strings."""

    @classmethod
    def string(cls, value: str, *, keep_escape: bool = False) -> tuple[str, str, int]:
        """
        Find the next **quoted** string in the input,
        return it and how much the cursor has been moved.

        Eg:
        >>> string("'''hello'world'''")
        >>> Tokens.TRIPLE_QUOTE, "hello'world", 17

        Keeping escape sequences is only used when we get into a list when
        initially scanning the raw line, because the code to parse list will
        also parse the string, and if we really interpret it twice, code breaks.
        """

        quote_token = None
        string = ""
        i = 0

        for token in Tokens.QUOTES:
            sliced = value[i : i + len(token)]
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

        length = len(value)
        while i < length:
            char = value[i]

            if char == Tokens.BACKSLASH:
                i += 1  # backslash itself

                replacement, offset = Tokens.escaped_char(value[i:])

                if keep_escape:
                    string += "\\" + value[i : i + offset]
                else:
                    string += replacement
                i += offset

                continue

            # closing quote
            sliced = value[i : i + len(quote_token)]
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
    def key(cls, key: str) -> list[str]:
        """
        Sanitize keys with quotes, giving the "path" to it.
        """

        #         input | output
        #         ------|-------
        #       foo.bar | ["foo", "bar"]
        #     "foo.bar" | ["foo.bar"]
        # "foo.bar.baz" | ["foo.bar.baz"]
        # "foo.bar".baz | ["foo.bar", "baz"]

        parts = [None]
        length = len(key)

        i = 0
        while i < length:
            _, string, offset = Parser.string(key[i:])
            if string:
                i += offset
                # NOTE: string is quoted, eg from a """hello"world"""
                #       we get "hello\"world", stip head and trail quotes
                #       but dont use .replace() as we might remove actual info
                parts.append(string[1:-1])
                continue

            char = key[i]
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
        return [part for part in parts if part is not None]

    @classmethod
    def try_int(cls, string: str) -> Optional[int]:
        """Try and convert a string into an integer."""

        if string.isdigit():
            return int(string)

        if string[0] == "0":
            # looks like a float to me :P
            if string[1] == ".":
                return None  # return cls.try_float(string) ??

            base = {
                "b": 2,
                "o": 8,
                "x": 16,
            }.get(string[1], None)

            if base is None:
                raise TOMLError("Invalid number.")

            return int(string, base)

        return None

    @classmethod
    def try_float(cls, string: str) -> Optional[float]:
        """Try and convert a string into an floating point number."""

        literals = {"inf": float("inf"), "nan": float("nan")}

        maybe_literal = literals.get(string, None)
        if maybe_literal is not None:
            return maybe_literal

        if (
            string.count(".") == 1
            # if replacing a single dot with 0 yields a number, this was a float
            and string.replace(".", "0").isdigit()
        ):
            if string[0] == ".":
                raise TOMLError("Leading point is invalid.")

            if string[-1] == ".":
                raise TOMLError("Trailing point is invalid.")

            return float(string)

        return None

    @classmethod
    def try_number(cls, string: str) -> Optional[Union[int, float]]:
        """Try and convert a string into a number."""

        # numbers with underscores
        if string[0] == "_":
            raise TOMLError("Leading underscore is invalid.")

        if string[-1] == "_":
            raise TOMLError("Trailing underscore is invalid.")

        if "__" in string:
            raise TOMLError("Double underscore is invalid.")

        if "_" in string:
            if "._" in string or "_." in string:
                raise TOMLError("Underscore next to point is invalid.")

            maybe_number = cls.try_number(string.replace("_", ""))
            if maybe_number is not None:
                return maybe_number

        # positive/negative sign
        if string[0] in ("+", "-"):
            if string[0] == string[1]:
                raise TOMLError("Double sign is invalid.")

            if string[1:3] in ("0b", "0o", "0x"):
                raise TOMLError("Sign + specifier is invalid.")

            maybe_number = cls.try_number(string[1:])
            if maybe_number is not None:
                multiplier = -1 if string[0] == "-" else 1
                return multiplier * cls.try_number(string[1:])

        maybe_number = cls.try_int(string)
        if maybe_number is not None:
            return maybe_number

        maybe_number = cls.try_float(string)
        if maybe_number is not None:
            return maybe_number

        return None

    @classmethod
    def try_bool(cls, string: str) -> Optional[bool]:
        """Try and parse a literal value."""

        literals = {
            "true": True,
            "false": False,
        }

        return literals.get(string, None)

    @classmethod
    def value(cls, string: str, line_info: Optional[ParsedLine] = None) -> Any:
        """
        (Try) Convert a string into a Python value.

        Note: line_info is only used when parsing lists
        """

        # quoted string, has to be first, to prevent casting it
        if Syntax.is_quoted(string):
            # remove quotes
            return string[1:-1]

        maybe_number = cls.try_number(string)
        if maybe_number is not None:
            return maybe_number

        maybe_bool = cls.try_bool(string)
        if maybe_bool is not None:
            return maybe_bool

        # array
        if Syntax.is_in_brackets(string):
            if line_info is None:
                raise TOMLError("How did we end on array parsing without line info?")

            start = line_info.tokens[Tokens.OPENING_BRACKET][0]
            value, _ = cls.list(line_info.line, start + 1)
            return value

        # couldn't parse, raise Exception
        raise TOMLError(
            f"Couldn't parse value: '{string}' (Hint, remember to wrap strings in quotes)"
        )

    @classmethod
    def list(cls, line: str, start: int) -> tuple[list[Any], int]:
        """
        Helper to parse a list.
        Returns parsed list + where next element starts
        """

        i = start
        collected = ""
        elements = []
        parsed_since_last_comma = False

        while i < len(line):
            char = line[i]

            # handle strings
            _, string, offset = cls.string(line[i:])
            if string:
                elements.append(string[1:-1])

                i += offset
                parsed_since_last_comma = True

            # stop when current list ends
            elif char == Tokens.CLOSING_BRACKET:
                stripped = collected.strip()
                if stripped:
                    elements.append(cls.value(stripped))

                return elements, i + 1

            # parse list and update current position
            elif char == Tokens.OPENING_BRACKET:
                value, new_pos = cls.list(line, i + 1)
                elements.append(value)

                i = new_pos
                collected = ""
                parsed_since_last_comma = True

            # parse the element we had collected
            elif char == Tokens.COMMA:
                stripped = collected.strip()
                if stripped:
                    elements.append(cls.value(stripped))
                elif not parsed_since_last_comma:
                    raise TOMLError("Malformed array, check out your commas.")

                i += 1
                collected = ""
                parsed_since_last_comma = False

            # collect another char
            else:
                i += 1
                collected += char

        # how do we get here?
        return elements, i

    @classmethod
    def toml(cls, raw_file: str) -> Dotty:
        """
        Parse a whole TOML string.
        """

        table_name = []
        data = Dotty()

        for raw_line in raw_file.replace("\r\n", "\n").split("\n"):
            #             null    lf     us      del     bs
            for char in ("\x00", "\r", "\x1F", "\x7F", "\x08"):
                if char in raw_line:
                    raise TOMLError(f"Invalid control sequence {char!r} found.")

            parsed_line = ParsedLine(raw_line)

            # empty line => nothing to be done
            if parsed_line.is_empty():
                continue

            Syntax.check_or_raise(parsed_line)

            # at this point, line should have content and correct syntax, code can be dumb(ish)
            # we can't strip or anything like that tho, indexes would be broken

            # equal sign => assignment expresion
            if Syntax.is_assignment(parsed_line):
                key, value = parsed_line.key_value()

                *parts, last = cls.key(key)
                parts = table_name + parts

                table = data.get_or_create_dict(parts)
                table[last] = cls.value(value, parsed_line)

            # no equal sign => table assignment, ie: [table]
            else:
                # remove "[" and "]", handle quotes/dots
                table_name = cls.key(parsed_line.line[1:-1])
                data.get_or_create_dict(table_name)

        return data


class Syntax:
    """Tiny helpers for syntax."""

    @staticmethod
    def check_or_raise(parsed: ParsedLine) -> Optional[str]:
        """Run some checks."""

        is_assignment = Syntax.is_assignment(parsed)
        is_table_setter = Syntax.is_in_brackets(parsed.line)

        if not is_assignment and not is_table_setter:
            raise TOMLError("Line has to contain either an assignment or table setter.")

        if is_assignment:
            if is_table_setter:
                raise TOMLError("Line cant be an assignment and table setter.")

            equal_sign = parsed.tokens[Tokens.EQUAL_SIGN][0]
            if is_assignment and not len(parsed.line) > equal_sign + 1:
                raise TOMLError("Invalid assignment, nothing after equal sign.")

        opening = parsed.tokens[Tokens.OPENING_BRACKET]
        closing = parsed.tokens[Tokens.CLOSING_BRACKET]
        if len(opening) != len(closing):
            raise TOMLError("Mismatched brackets.")

    @staticmethod
    def is_quoted(value: str) -> bool:
        """Check if a string is quoted."""
        return value[0] == value[-1] and value[0] in Tokens.QUOTES

    @staticmethod
    def is_assignment(parsed: ParsedLine) -> bool:
        """Whether this line contains an assignment."""
        return bool(parsed.tokens[Tokens.EQUAL_SIGN])

    @staticmethod
    def is_in_brackets(value: str) -> bool:
        """Whether string starts with an opening bracket and ends with a closing one."""
        return (
            value[0] == Tokens.OPENING_BRACKET and value[-1] == Tokens.CLOSING_BRACKET
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
        raise TOMLError("dumping is only implemented for dict-like objects.")

    # enclose on a dict, to easily find the "tables" on it
    if isinstance(__data, Dotty):
        __data = __data.data

    def order(key_value):
        """Custom function to dump basic keys before nested tables."""

        key, value = key_value
        return 1000 if isinstance(value, dict) else len(key)

    def dump_table(buffer: StringIO, table: dict, key_parts: list[str]) -> StringIO:
        """Helper to iterate the tree. Returns the buffer for convenience."""

        for key, value in sorted(table.items(), key=order):
            if "." in key or key == "":
                # quote it, for valid value
                key = repr(key)

            if isinstance(value, dict):
                # update global key
                key_parts.append(key)

                # write table header
                table_name = ".".join(key_parts)
                if table_name:
                    # newline before, for readability
                    buffer.write(f"\n[{table_name}]\n")

                # handle child
                dump_table(buffer, value, key_parts)

                # undo addition
                key_parts.pop()

            else:
                if isinstance(value, str):
                    # quote it, for valid value
                    value = repr(value)

                buffer.write(f"{key} = {value}\n")

        return buffer

    # get going from base table
    return dump_table(StringIO(), __data, []).getvalue()


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

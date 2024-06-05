try:
    # types are needed on compyter
    from typing import Any, Optional
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

        REPLACEMENTS = {
            "b": "\b",
            "t": "\t",
            "n": "\n",
            "f": "\f",
            "r": "\r",
            "e": 0x1B,  # "\e" is not a thing
            "\"": "\"",
            "\\": "\\",
        }

        escaped = string[0]

        replacement = REPLACEMENTS.get(escaped)
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

        warnings.warn(rf"Unknown/invalid escape sequence '\{escaped}'")
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

    def __init__(self, __line: str):
        self.line = ""
        self.tokens = {t: [] for t in Tokens.ALL}

        keep_escape = False

        stripped = __line.strip()
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

        assert len(self.tokens[Tokens.EQUAL_SIGN]), "How did we end up on key_value with len(EQUAL) != 1"

        split_at = self.tokens[Tokens.EQUAL_SIGN][0]
        key = self.line[:split_at].strip()
        value = self.line[split_at + 1 :].strip()

        return key, value


class Parser:
    """Get Python values out of strings."""

    @classmethod
    def string(
        cls,
        __value: str,
        *,
        keep_escape: bool = False
    ) -> tuple[str, str, int]:
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

        length = len(__value)
        while i < length:
            char = __value[i]

            if char == Tokens.BACKSLASH:
                i += 1  # backslash itself

                replacement, offset = Tokens.escaped_char(__value[i:])

                if keep_escape:
                    string += "\\" + __value[i : i+offset]
                else:
                    string += replacement
                i += offset

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
        return [part for part in parts if part is not None]

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
            base = {"b": 2, "o": 8, "x": 16}.get(__value[1])
            if base is None:
                raise TOMLError("Invalid number.")

            return int(__value, base)

        # positive prefix, aka do nothing
        if __value[0] == "+":
            if __value[1] == "+":
                raise TOMLError("Double sign is invalid.")

            if __value[1:3] in ("0b", "0o", "0x"):
                raise TOMLError("Sign + specifier is invalid.")

            return cls.value(__value[1:])

        # handle exponents here, avoid issue with 0e<something> numbers

        # negative numbers
        if __value[0] == "-":
            if __value[1] == "-":
                raise TOMLError("Double sign is invalid.")

            # spec does not allow negative numbers with base prefix
            if __value[1:3] not in ("0b", "0o", "0x"):
                return -cls.value(__value[1:])

        # numbers with underscores
        replaced = __value.replace("_", "")
        if replaced.isdigit():
            return int(__value)

        if replaced.count(".")  == 1 and replaced.replace(".", "0").isdigit():
            return float(__value)

        # bool
        if __value in {"true", "false"}:
            return __value == "true"

        # infinite and not a number
        if __value in {"inf", "nan"}:
            return float(__value)

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
            f"Couldn't parse value: '{__value}' (Hint, remember to wrap strings in quotes)"
        )

    @classmethod
    def list(cls, __line: str, __start: int) -> tuple[list[Any], int]:
        """
        Helper to parse a list.
        Returns parsed list + where next element starts
        """

        i = __start
        collected = ""
        elements = []
        parsed_since_last_comma = False

        while i < len(__line):
            char = __line[i]

            # handle strings
            _, string, offset = cls.string(__line[i:])
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
                value, new_pos = cls.list(__line, i + 1)
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
    def toml(cls, __toml: str) -> Dotty:
        """
        Parse a whole TOML string.
        """

        table_name = []
        data = Dotty()

        for raw_line in __toml.replace("\r\n", "\n").split("\n"):
            #             null    lf     us      del     bs
            for char in ("\x00", "\r", "\x1F", "\x7F", "\x08"):
                if char in raw_line:
                    raise TOMLError(
                        f"Invalid control sequence {char!r} found."
                    )

            parsed_line = ParsedLine(raw_line)

            # empty line => nothing to be done
            if parsed_line.is_empty():
                continue

            Syntax.check_or_raise(parsed_line)

            # at this point, line should have content and correct syntax, this code can be rather dumb
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
    def check_or_raise(__parsed: ParsedLine) -> Optional[str]:
        """Run some checks."""

        is_assignment = Syntax.is_assignment(__parsed)
        is_table_setter = Syntax.is_in_brackets(__parsed.line)

        if not is_assignment and not is_table_setter:
            raise TOMLError(
                "Line has to contain either an assignment or table setter."
            )

        if is_assignment:
            if is_table_setter:
                raise TOMLError(
                    "Line cant be an assignment and table setter."
                )

            equal_sign = __parsed.tokens[Tokens.EQUAL_SIGN][0]
            if is_assignment and not len(__parsed.line) > equal_sign  + 1:
                raise TOMLError("Invalid assignment, nothing after equal sign.")

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
        raise TOMLError("dumping is only implemented for dict-like objects.")

    # enclose on a dict, to easily find the "tables" on it
    if isinstance(__data, Dotty):
        __data = __data._data

    def order(kv):
        """Custom function to dump basic keys before nested tables."""

        k, v = kv
        return (
            1000
            if isinstance(v, dict)
            else len(k)
        )

    def dump_table(
        buffer: StringIO,
        table: dict,
        key_parts: list[str]
    ) -> StringIO:
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

from ._dotty import Dotty

class TOMLError(Exception):
    """Errors detected while parsing, others are for sure missed."""

    def __init__(self, message):
        self.message = f"Invalid TOML: {message}"
        super().__init__(self.message)


class Quotes:
    """Solve the question: Are we in a string?."""
    # TODO: Support for triple quotes?

    single: bool
    """Whether we are in a string delimited by '."""

    double: bool
    '''Whether we are in a string delimited by ".'''

    def __init__(self):
        self.single = False
        self.double = False

    def __bool__(self):
        """Returns whether we are in a string."""
        return self.single == self.double == True
    
    def update(self, char: chr):
        """Update after fetching a char."""
        if char == "'":
            self.single = not self.single
        
        elif char == '"':
            self.double = not self.double


def parse_helper(func):
    """Wrapper to prevent duplication of the 'in string?' logic."""

    def wrapper(self: TOMLParser, line: str):
        quotes = Quotes() 

        for i, c in enumerate(line):
            quotes.update(c)

            # we are in a string
            if quotes:
                continue

            # functions can output whether they are finished
            # return False, _ => keep iterating
            # return True, out => return out
            finished, output = func(line, c, i)

            if finished:
                return output

        # fallback, return line unchange
        return line

    return wrapper


class TOMLParser:
    """Class for parsing a TOML file."""

    _scope: str = ""
    """Current scope ([scope], [another.scope]) of the parser."""

    def __str__(self) -> self:
        return f"{self.__class__.__name__}"
    
    def __repr__(self) -> str:
        return f"<{self}>"

    def remove_comments(self, line: str) -> str:
        """Remove comment from a line, takes into account strings, but not triple quotation ones."""

        @parse_helper
        def remove_comments_impl(line: str, c: chr, i: int) -> str:

            if c == "#":
                return True, line[:i].strip()

            return False, None

        return remove_comments_impl(self, line)
    
    def parse_assignment(self, line: str) -> tuple[str, str]:
        """Parse a key = value line, and return both of those."""

        @parse_helper
        def parse_assignment_impl(line: str, c: chr, i: int) -> str:

            if c == "=":
                key = line[:i].strip()
                value = line[i+1:].strip()
                return True, (key, value)

            return False, (None, None)

        output = parse_assignment_impl(self, line)
        if isinstance(output, str):
            raise TOMLError(f"This is not an assignment: '{line}'")

        return output[:2]

    def is_empty(self, line: str) -> bool:
        """Returns whether the line is empty."""
        return not line.strip()
    
    def scope(self, line: str) -> bool:
        """Returns whether this line was setting up a scope."""
        if line[0] == "[" and line[-1] == "]":
            self._scope = line[1:-1]
            return True

        return False


    def parse_string(self, value: str) -> tuple[bool, str]:
        """Check if a value starts and ends with same quote mark, and only has 2 of them."""

        if value[0] in ['"', "'"]:
            if value.count(value[0]) != 2 or value[0] != value[-1]:
                TOMLError(f"Malformed string: {value}")

            return True, value[1:-1]

        return False, value

    def parse_bool(self, value: str) -> tuple[bool, bool]:
        _value = value.strip().lower()

        if _value == "true":
            del _value
            return True, True

        if _value == "false":
            del _value
            return True, False

        return False, value

    def parse_int(self, value: str) -> tuple[bool, int]:
        if value.isdigit():
            return True, int(value)
        
        # negative
        if value[0] == "-" and value[1:].isdigit():
            return True, -int(value[1:])

        return False, value
    
    def parse_list(self, value: str) -> tuple[bool, list[Any]]:
        if value[0] == "[" and value[-1] == "]":
            items = value[1:-1].split(",")
            return True, [self.parse_value(item.strip()) for item in items]

        return False, value

    def parse_value(self, value: str):
        # string has to be first, to prevent casting it to something else
        for type_ in ["string", "bool", "int", "list", ]:
            parsed, value = getattr(self, f"parse_{type_}")(value)
            if parsed:
                del parsed
                return value

        print(f"Couldn't parse: {value}")
        return value

    def load(self, text: str) -> Dotty:
        data = Dotty()

        for _line in text.replace("\r\n", "\n").splitlines():
            line = self.remove_comments(_line)
            
            if self.is_empty(line):
                self._scope = ""
                del line
                continue

            if self.scope(line):
                del line
                continue

            key, value = self.parse_assignment(line)
            # convert to number, bool, etc
            value = self.parse_value(value)
            key = f"{self._scope}.{key}" if self._scope else key
            data[key] = value
            del line, key, value
        return data

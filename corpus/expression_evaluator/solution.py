_OPERATORS = {"+", "-", "*", "/"}


def _tokenize(text):
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char.isdigit():
            start = index
            while index < len(text) and text[index].isdigit():
                index += 1
            tokens.append(("number", int(text[start:index])))
        elif char in _OPERATORS or char in "()":
            tokens.append((char, char))
            index += 1
        else:
            raise ValueError("invalid character %r" % (char,))
    return tokens


class _Parser:
    def __init__(self, tokens):
        self._tokens = tokens
        self._pos = 0

    def peek(self):
        if self._pos < len(self._tokens):
            return self._tokens[self._pos][0]
        return None

    def take(self):
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def parse_expression(self):
        value = self.parse_term()
        while self.peek() in ("+", "-"):
            operator = self.take()[0]
            right = self.parse_term()
            value = value + right if operator == "+" else value - right
        return value

    def parse_term(self):
        value = self.parse_factor()
        while self.peek() in ("*", "/"):
            operator = self.take()[0]
            right = self.parse_factor()
            value = value * right if operator == "*" else value / right
        return value

    def parse_factor(self):
        token = self.peek()
        if token == "-":
            self.take()
            return -self.parse_factor()
        if token == "+":
            self.take()
            return self.parse_factor()
        if token == "(":
            self.take()
            value = self.parse_expression()
            if self.peek() != ")":
                raise ValueError("unbalanced parentheses")
            self.take()
            return value
        if token == "number":
            return self.take()[1]
        raise ValueError("unexpected token")


def evaluate(expr):
    tokens = _tokenize(expr)
    if not tokens:
        raise ValueError("empty expression")
    parser = _Parser(tokens)
    value = parser.parse_expression()
    if parser.peek() is not None:
        raise ValueError("unexpected trailing token")
    return value

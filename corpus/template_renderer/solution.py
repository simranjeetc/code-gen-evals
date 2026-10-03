def _is_name_char(char):
    return char.isalnum() or char == "_"


def render(template, values):
    out = []
    index = 0
    length = len(template)

    while index < length:
        char = template[index]
        if char == "{":
            if index + 1 < length and template[index + 1] == "{":
                out.append("{")
                index += 2
                continue
            end = template.find("}", index + 1)
            if end == -1:
                raise ValueError("unterminated placeholder")
            name = template[index + 1:end]
            if not name or not all(_is_name_char(c) for c in name):
                raise ValueError("invalid placeholder: %r" % (name,))
            if name not in values:
                raise KeyError(name)
            out.append(str(values[name]))
            index = end + 1
        elif char == "}":
            if index + 1 < length and template[index + 1] == "}":
                out.append("}")
                index += 2
                continue
            raise ValueError("unmatched closing brace")
        else:
            out.append(char)
            index += 1

    return "".join(out)

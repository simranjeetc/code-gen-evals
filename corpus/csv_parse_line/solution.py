def csv_parse_line(line):
    fields = []
    current = []
    in_quotes = False
    index = 0
    length = len(line)

    while index < length:
        char = line[index]
        if in_quotes:
            if char == '"':
                if index + 1 < length and line[index + 1] == '"':
                    current.append('"')
                    index += 2
                    continue
                in_quotes = False
                index += 1
                continue
            current.append(char)
        else:
            if char == '"' and not current:
                in_quotes = True
            elif char == ",":
                fields.append("".join(current))
                current = []
            else:
                current.append(char)
        index += 1

    fields.append("".join(current))
    return fields

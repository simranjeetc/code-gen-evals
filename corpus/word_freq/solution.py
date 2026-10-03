_STRIP = ".,!?;:\"'()[]"


def word_freq(text):
    counts = {}
    for token in text.split():
        word = token.lower().strip(_STRIP)
        if not word:
            continue
        counts[word] = counts.get(word, 0) + 1
    return counts

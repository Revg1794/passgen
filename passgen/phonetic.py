"""Spelling passwords out loud.

Reading `PixelPonyFringeHymnGrain41=` to someone over the phone character by
character is where generated passwords go to die. This renders one as NATO
spelling alphabet words instead.

Case is carried by the case of the word itself - ALPHA is a capital A, alpha is
a lowercase one - which is unambiguous on paper and easy to say out loud
("capital alpha"). Chunks are split at capital letters, so the CamelCase word
boundaries passgen already generates become natural pauses when dictating.
"""

NATO = {
    "a": "alpha", "b": "bravo", "c": "charlie", "d": "delta", "e": "echo",
    "f": "foxtrot", "g": "golf", "h": "hotel", "i": "india", "j": "juliett",
    "k": "kilo", "l": "lima", "m": "mike", "n": "november", "o": "oscar",
    "p": "papa", "q": "quebec", "r": "romeo", "s": "sierra", "t": "tango",
    "u": "uniform", "v": "victor", "w": "whiskey", "x": "x-ray",
    "y": "yankee", "z": "zulu",
}

DIGITS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}

# Named rather than described, so both ends of the call say the same thing.
SYMBOLS = {
    "!": "exclamation", "?": "question", "#": "hash", "$": "dollar",
    "%": "percent", "&": "ampersand", "*": "asterisk", "+": "plus",
    "=": "equals", "-": "dash", "_": "underscore", ".": "dot",
    " ": "space", "@": "at", "/": "slash", "\\": "backslash",
    "(": "open-bracket", ")": "close-bracket", "[": "open-square",
    "]": "close-square", "{": "open-brace", "}": "close-brace",
    ":": "colon", ";": "semicolon", "'": "apostrophe", '"': "quote",
    ",": "comma", "<": "less-than", ">": "greater-than", "|": "pipe",
    "~": "tilde", "`": "backtick", "^": "caret",
}


def say(character):
    """The spoken form of a single character."""
    lowered = character.lower()
    if lowered in NATO:
        word = NATO[lowered]
        return word.upper() if character.isupper() else word
    if character in DIGITS:
        return DIGITS[character]
    return SYMBOLS.get(character, f"'{character}'")


def chunks(password):
    """Split into speakable groups, breaking before each capital letter."""
    groups = []
    current = ""
    for character in password:
        if character.isupper() and current:
            groups.append(current)
            current = ""
        current += character
    if current:
        groups.append(current)
    return groups


def spell(password, separator="  /  "):
    """Render a password as spoken words, grouped at capital letters."""
    return separator.join(" ".join(say(c) for c in group)
                          for group in chunks(password))


LEGEND = "CAPITALS are uppercase letters, lowercase are lowercase"

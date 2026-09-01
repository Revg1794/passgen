"""House defaults from a config file, so policy is configuration not code.

The shipped defaults are opinionated - no separators, and a capital, a number
and a symbol in every password - because that is what most corporate password
policies demand. Anyone whose policy differs should not have to edit source to
change it, which is what this is for.

INI rather than TOML deliberately: `tomllib` only arrived in Python 3.11, and
passgen supports 3.8. `configparser` is in every version, and the settings here
are flat key/value pairs that gain nothing from a richer format.

Search order, first file wins:

    1. the path given to --config
    2. ./passgen.conf, in the current directory
    3. the per-user config directory:
         Windows  %APPDATA%\\passgen\\passgen.conf
         macOS    ~/Library/Application Support/passgen/passgen.conf
         Linux    $XDG_CONFIG_HOME/passgen/passgen.conf, or ~/.config/...

Precedence overall is: an explicit command-line flag beats a profile's defaults,
which beat this file, which beats the built-in defaults. A profile wins over the
config file on purpose - naming `-p msa` is a deliberate request to target that
platform, and a stray `words = 7` in a config file should not quietly produce
passwords too long for it.
"""

import configparser
import os
import sys

FILENAME = "passgen.conf"
SECTION = "defaults"

# Only these may be set from a file, with the type each is parsed as. Anything
# else is a typo worth reporting rather than silently ignoring.
SETTINGS = {
    "profile": str,
    "mode": str,
    "sep": str,
    "require": str,
    "words": int,
    "syllables": int,
    "digits": int,
    "count": int,
    "capitalize": bool,
    "symbol": bool,
    "leaked_list": str,
    "banned_list": str,
}


def user_config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return os.path.join(base, "passgen")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/passgen")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "passgen")


def candidates(explicit=None):
    if explicit:
        return [explicit]
    return [os.path.join(os.getcwd(), FILENAME),
            os.path.join(user_config_dir(), FILENAME)]


def find(explicit=None):
    """The config file that will be used, or None."""
    for path in candidates(explicit):
        if os.path.isfile(path):
            return path
    return None


def load(explicit=None):
    """Return (settings dict, path used). Raises ValueError on a bad file."""
    path = find(explicit)
    if path is None:
        if explicit:
            raise ValueError(f"config file not found: {explicit}")
        return {}, None

    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error as err:
        raise ValueError(f"{path}: {err}") from err

    if not parser.has_section(SECTION):
        raise ValueError(f"{path}: missing a [{SECTION}] section")

    settings = {}
    for key, raw in parser.items(SECTION):
        key = key.replace("-", "_")
        if key not in SETTINGS:
            raise ValueError(
                f"{path}: unknown setting {key!r}; valid settings are "
                + ", ".join(sorted(SETTINGS)))
        kind = SETTINGS[key]
        try:
            if kind is bool:
                settings[key] = parser.getboolean(SECTION, key)
            elif kind is int:
                settings[key] = int(raw)
            else:
                settings[key] = raw.strip()
        except ValueError as err:
            raise ValueError(f"{path}: {key} = {raw!r} is not valid: {err}") from err
    return settings, path


EXAMPLE = """\
# passgen house defaults. Every setting is optional; anything not listed here
# keeps passgen's built-in default, and any command-line flag overrides both.
#
# Put this file next to passgen as passgen.conf, or in your per-user config
# directory (on Windows: %APPDATA%\\passgen\\passgen.conf).

[defaults]
# Which platform to target when none is given on the command line.
# profile = entra

# Password shape.
# words = 5
# mode = words
# sep = none
# digits = 2
# capitalize = true
# symbol = true

# Character categories every password must contain. Empty to drop the rule.
# require = upper,number,symbol

# How many to print at once.
# count = 5

# Always check against these, so you cannot forget to.
# leaked_list = C:/Projects/passgen/leaked.idx
# banned_list = C:/Projects/passgen/my-terms.local.txt
"""

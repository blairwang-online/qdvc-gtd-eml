"""
Configuration: loads config.yml, holds shared constants (colours, folder names,
metadata schema), and normalises the my_own_accounts list.
"""

import os

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# config.yml lives next to the top-level scripts (the parent of this package).
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yml"
)

# Defaults — overridden by matching keys in config.yml if present.
DEFAULTS = {
    "working_directory": os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gtd-eml"
    ),                         # root holding the 5 folders + metadata.csv
    "max_filename_chars": 60,  # max length of generated filename (incl. ".eml")
    "archive_report_n": 10,    # number of most recent archive files to report
    "green_max_days": 2,       # days < this -> green
    "yellow_max_days": 14,     # days < this (and >= green) -> yellow; else red
    "max_subject_chars": 72,   # truncate displayed subjects longer than this
    "my_own_accounts": [],     # list of {email_address, display_name, colour}
    "force_colour": False,     # always emit colour (e.g. when piping to `less -R`)
}

# ANSI colour codes used for report lines.
COLOURS = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "reset": "\033[0m",
}

INPUT_DIR = "01-input"
TRIAGE_DIR = "02-triage"
ACTIONABLE_DIR = "03-actionable"
REFERENCE_DIR = "04-reference"
ARCHIVE_DIR = "05-archive"

ALL_DIRS = [INPUT_DIR, TRIAGE_DIR, ACTIONABLE_DIR, REFERENCE_DIR, ARCHIVE_DIR]
METADATA_FILE = "metadata.csv"
METADATA_HEADERS = ["eml_filename", "general_notes", "project", "next_action", "message_ref", "flags"]


def load_config(config_path=CONFIG_FILE):
    """
    Load settings from config.yml, falling back to DEFAULTS for any key not
    present. my_own_accounts is normalised to a list of dicts with lower-cased
    email_address plus display_name and colour.

    Example (config.yml has my_own_accounts with one entry):
        load_config("/path/config.yml")["my_own_accounts"]
        # -> [{"email_address": "james@x.com",
        #      "display_name": "Work account", "colour": "yellow"}]
    """
    cfg = dict(DEFAULTS)
    if os.path.isfile(config_path):
        if yaml is None:
            raise RuntimeError(
                "config.yml found but PyYAML is not installed. "
                "Install it with: pip install pyyaml"
            )
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for key in cfg:
            if key in data and data[key] is not None:
                cfg[key] = data[key]

    cfg["my_own_accounts"] = normalise_accounts(cfg.get("my_own_accounts"))
    return cfg


def normalise_accounts(accounts):
    """
    Normalise the my_own_accounts list: lower-case email addresses, supply a
    fallback display_name, and validate the colour against COLOURS.

    Example:
        normalise_accounts([{"email_address": "ME@X.com"}])
        # -> [{"email_address": "me@x.com", "display_name": "me@x.com",
        #      "colour": "cyan"}]
    """
    result = []
    for entry in accounts or []:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email_address") or "").strip().lower()
        if not email:
            continue
        colour = (entry.get("colour") or "cyan").strip().lower()
        if colour not in COLOURS:
            colour = "cyan"
        result.append({
            "email_address": email,
            "display_name": (entry.get("display_name") or email).strip(),
            "colour": colour,
        })
    return result


def should_use_colour(cfg, stream):
    """
    Decide whether to emit ANSI colour, applying this precedence (highest
    first):
        1. NO_COLOR env var set (to anything)        -> never colour
        2. FORCE_COLOR env var set to a truthy value  -> always colour
        3. force_colour: true in config.yml           -> always colour
        4. otherwise                                   -> colour iff stream is a TTY

    NO_COLOR and FORCE_COLOR follow the conventions documented at
    https://no-color.org and https://force-color.org . A FORCE_COLOR value of
    "0", "false", "no", or "off" (case-insensitive) is treated as NOT forcing.

    Example:
        should_use_colour({"force_colour": False}, sys.stdout)  # -> True if a TTY
        should_use_colour({"force_colour": True}, piped_stream)  # -> True
    """
    if "NO_COLOR" in os.environ:
        return False

    force_env = os.environ.get("FORCE_COLOR")
    if force_env is not None and force_env.strip().lower() not in ("0", "false", "no", "off", ""):
        return True

    if cfg.get("force_colour"):
        return True

    return bool(getattr(stream, "isatty", lambda: False)())

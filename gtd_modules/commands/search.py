"""
`search` subcommand: find report entries matching a literal, case-insensitive
string and print them with the match highlighted.
"""

import sys

from .. import config as cfg_mod
from .. import fs
from ..metadata import load_metadata, sync_metadata
from ..report import search_report


def cmd_search(argv):
    """
    `gtd.py search <text>` — search the full `gtd.py list` report for <text>
    and print the email entries that match. All the words after `search` are
    joined back into a single query (with single spaces), so the match is on the
    literal string — spaces, `#`, and `@` included — not on separate words. The
    search is case-insensitive.

    Read-only: it reconciles metadata.csv with what's on disk (so flags and
    next_action are current) but does NOT ingest 01-input or move anything.

    Example:
        cmd_search(["project", "pudding"])  # -> entries containing "project pudding"
        cmd_search(["#quick"])              # -> entries containing "#quick"
        cmd_search(["jane@example.com"])    # -> entries with that address
    """
    if not argv:
        print("usage: gtd.py search <text>", file=sys.stderr)
        return 2

    query = " ".join(argv)
    if not query.strip():
        print("usage: gtd.py search <text>", file=sys.stderr)
        return 2

    cfg = cfg_mod.load_config()
    base_dir = cfg["working_directory"]
    colour_enabled = cfg_mod.should_use_colour(cfg, sys.stdout)
    colour_cfg = (cfg["green_max_days"], cfg["yellow_max_days"], colour_enabled)

    fs.ensure_folders(base_dir)
    sync_metadata(base_dir)
    metadata = load_metadata(base_dir)
    search_report(base_dir, query, colour_cfg,
                  accounts=cfg["my_own_accounts"],
                  max_subject=cfg["max_subject_chars"],
                  metadata=metadata)
    return 0

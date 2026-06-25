"""
`stats` subcommand: show how many .eml files each workflow folder holds.
"""

import sys

from .. import config as cfg_mod
from .. import fs


def cmd_stats(argv):
    """
    `gtd.py stats` — print each workflow folder and how many .eml files it holds,
    plus a total.

    Example:
        cmd_stats([])
        # === file counts ===
        #   01-input         0
        #   02-triage        3
        #   ...
        #   total            7
    """
    if argv:
        print("usage: gtd.py stats", file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    fs.ensure_folders(base_dir)

    width = max(len(f) for f in cfg_mod.ALL_DIRS)
    total = 0
    print("=== file counts ===")
    for folder in cfg_mod.ALL_DIRS:
        n = len(fs.list_eml_files(base_dir, folder))
        total += n
        print(f"  {folder.ljust(width)}   {n:>4}")
    print(f"  {'total'.ljust(width)}   {total:>4}")
    return 0

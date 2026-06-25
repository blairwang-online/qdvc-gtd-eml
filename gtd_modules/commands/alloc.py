"""
`alloc` subcommand: move an email from wherever it is filed to another folder.
"""

import os
import sys

from .. import config as cfg_mod
from .. import fs


def cmd_alloc(argv):
    """
    `gtd.py alloc <file.eml> <destination>` — find where an email is currently
    filed and move it to the destination folder. Destination accepts a short
    alias (actionable, delegated, reference, archive, triage, input) or the full
    folder name (e.g. 04-delegated).

    Example:
        cmd_alloc(["2026-06-03-x.eml", "delegated"])
        # -> moves the file to 04-delegated, prints confirmation, returns 0
    """
    if len(argv) != 2:
        print("usage: gtd.py alloc <file.eml> <destination>", file=sys.stderr)
        print("       destinations: " + ", ".join(cfg_mod.FOLDERS_BY_ALIAS),
              file=sys.stderr)
        return 2

    filename, destination = argv
    dest_folder = fs.resolve_folder(destination)
    if dest_folder is None:
        print(f"error: unknown destination '{destination}'", file=sys.stderr)
        print("       choose one of: " + ", ".join(cfg_mod.FOLDERS_BY_ALIAS),
              file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    src_path = fs.find_eml(base_dir, filename)
    if src_path is None:
        print(f"error: '{filename}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1

    src_folder = os.path.basename(os.path.dirname(src_path))
    if src_folder == dest_folder:
        print(f"'{os.path.basename(src_path)}' is already in {dest_folder}; nothing to do.")
        return 0

    try:
        fs.move_eml(src_path, base_dir, dest_folder)
    except FileExistsError:
        print(f"error: a file named '{os.path.basename(src_path)}' already exists "
              f"in {dest_folder}", file=sys.stderr)
        return 1

    print(f"Moved {os.path.basename(src_path)}: {src_folder} -> {dest_folder}")
    return 0

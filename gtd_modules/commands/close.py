"""
`close` subcommand: archive an email and record which email closed it.
"""

import os
import sys

from .. import config as cfg_mod
from .. import fs
from .. import metadata as meta_mod


def cmd_close(argv):
    """
    `gtd.py close <file.eml> with <other.eml>` — archive an email and record
    what closed it. Checks the email is not already in 06-archive (refusing if
    it is), moves it there, and sets its metadata next_action to
    "Closed with <other.eml>".

    The literal word "with" between the two filenames is optional; both .eml
    extensions are optional. <other.eml> must itself exist somewhere in the
    workflow; if it does not, the command errors immediately and nothing is
    moved or modified. The canonical on-disk name of <other.eml> is what gets
    recorded.

    Example:
        cmd_close(["abcde.eml", "with", "xyz.eml"])
        # -> moves abcde.eml to 06-archive, sets next_action, returns 0
    """
    # Accept "<file> with <other>" or "<file> <other>".
    if len(argv) == 3 and argv[1].lower() == "with":
        filename, other = argv[0], argv[2]
    elif len(argv) == 2:
        filename, other = argv[0], argv[1]
    else:
        print("usage: gtd.py close <file.eml> with <other.eml>", file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    src_path = fs.find_eml(base_dir, filename)
    if src_path is None:
        print(f"error: '{filename}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1

    # The email we are closing WITH must actually exist; verify before moving or
    # touching any metadata so a typo leaves everything untouched.
    other_path = fs.find_eml(base_dir, other)
    if other_path is None:
        print(f"error: '{other}' not found in any GTD folder under {base_dir}; "
              f"nothing was changed", file=sys.stderr)
        return 1
    other = os.path.basename(other_path)

    canonical = os.path.basename(src_path)
    src_folder = os.path.basename(os.path.dirname(src_path))
    if src_folder == cfg_mod.ARCHIVE_DIR:
        print(f"error: '{canonical}' is already in {cfg_mod.ARCHIVE_DIR}; "
              f"refusing to close it again", file=sys.stderr)
        return 1

    try:
        fs.move_eml(src_path, base_dir, cfg_mod.ARCHIVE_DIR)
    except FileExistsError:
        print(f"error: a file named '{canonical}' already exists "
              f"in {cfg_mod.ARCHIVE_DIR}", file=sys.stderr)
        return 1

    meta_mod.set_metadata_value(base_dir, canonical, "next_action",
                                f"Closed with {other}")
    print(f"Closed {canonical}: {src_folder} -> {cfg_mod.ARCHIVE_DIR} "
          f"(closed with {other})")
    return 0

"""
`pin` / `unpin` subcommands: add or remove the "pinned" flag on an email.
Both share the `_toggle_flag` helper that does the locate-then-modify work.
"""

import os
import sys

from .. import config as cfg_mod
from .. import fs
from .. import metadata as meta_mod


def cmd_pin(argv):
    """
    `gtd.py pin <file.eml>` — add the "pinned" flag to an email's metadata
    flags field. A no-op (reported as such) if it is already pinned.

    Example:
        cmd_pin(["2026-06-03-x.eml"])  # -> adds "pinned", returns 0
    """
    return _toggle_flag(argv, "pin", "pinned", add=True)


def cmd_unpin(argv):
    """
    `gtd.py unpin <file.eml>` — remove the "pinned" flag from an email's
    metadata flags field. A no-op (reported as such) if it is not pinned.

    Example:
        cmd_unpin(["2026-06-03-x.eml"])  # -> removes "pinned", returns 0
    """
    return _toggle_flag(argv, "unpin", "pinned", add=False)


def _toggle_flag(argv, verb, flag, add):
    """
    Shared implementation for `pin`/`unpin`: locate the email, then add or
    remove `flag` from its metadata flags field. Returns a process exit code.

    Example:
        _toggle_flag(["x.eml"], "pin", "pinned", add=True)  # -> 0
    """
    if len(argv) != 1:
        print(f"usage: gtd.py {verb} <file.eml>", file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    path = fs.find_eml(base_dir, argv[0])
    if path is None:
        print(f"error: '{argv[0]}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1
    canonical = os.path.basename(path)

    if add:
        changed = meta_mod.add_flag(base_dir, canonical, flag)
        if changed:
            print(f"{canonical}: added flag '{flag}'")
        else:
            print(f"{canonical}: already has flag '{flag}'; nothing to do.")
    else:
        changed = meta_mod.remove_flag(base_dir, canonical, flag)
        if changed:
            print(f"{canonical}: removed flag '{flag}'")
        else:
            print(f"{canonical}: does not have flag '{flag}'; nothing to do.")
    return 0

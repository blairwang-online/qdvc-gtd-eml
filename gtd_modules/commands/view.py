"""
`view` subcommand: locate one email and print a markdown-friendly preview.
"""

import sys

from .. import config as cfg_mod
from .. import fs
from ..emailutil import read_eml_message
from ..preview import render


def cmd_view(argv):
    """
    `gtd.py view <file.eml>` — locate one email across all folders and print a
    markdown-friendly preview (headers, attachments, body). The ".eml"
    extension is optional.

    Example:
        cmd_view(["2026-06-03-project-pudding.eml"])  # -> prints preview, 0
    """
    if len(argv) != 1:
        print("usage: gtd.py view <file.eml>", file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    path = fs.find_eml(base_dir, argv[0])
    if path is None:
        print(f"error: '{argv[0]}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1

    render(read_eml_message(path), path)
    return 0

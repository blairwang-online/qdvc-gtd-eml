"""
`list` subcommand: ingest new input, sync metadata, print the status report.
"""

import sys

from .. import config as cfg_mod
from .. import fs
from ..ingest import ingest_input_files
from ..metadata import load_metadata, sync_metadata
from ..report import print_report


def cmd_list(argv):
    """
    `gtd.py list [folder]` — ingest any new input files, sync metadata, and
    print the colour-coded status report. With no argument the full report is
    shown; with a folder name/alias (e.g. `actionable`, `delegated`,
    `05-reference`) only that segment is printed.

    Example:
        cmd_list([])              # -> prints the full report, returns 0
        cmd_list(["actionable"])  # -> prints just the actionable segment
    """
    only = None
    if len(argv) > 1:
        print("usage: gtd.py list [folder]", file=sys.stderr)
        return 2
    if argv:
        only = fs.resolve_folder(argv[0])
        if only is None:
            print(f"error: unknown folder '{argv[0]}'", file=sys.stderr)
            print("       choose one of: " + ", ".join(cfg_mod.FOLDERS_BY_ALIAS),
                  file=sys.stderr)
            return 2

    cfg = cfg_mod.load_config()
    base_dir = cfg["working_directory"]
    colour_enabled = cfg_mod.should_use_colour(cfg, sys.stdout)
    colour_cfg = (cfg["green_max_days"], cfg["yellow_max_days"], colour_enabled)

    fs.ensure_folders(base_dir)

    moved = ingest_input_files(base_dir, cfg["max_filename_chars"])
    new_refs = {}
    if moved:
        print("Ingested from 01-input -> 02-triage:")
        for old_name, new_name, message_ref in moved:
            tag = f"   (ref {message_ref})" if message_ref else ""
            print(f"   {old_name}  ->  {new_name}{tag}")
            if message_ref:
                new_refs[new_name] = {"message_ref": message_ref}
    else:
        print("No new files in 01-input.")

    sync_metadata(base_dir, new_values=new_refs)
    metadata = load_metadata(base_dir)
    print_report(base_dir, cfg["archive_report_n"], colour_cfg,
                 accounts=cfg["my_own_accounts"],
                 max_subject=cfg["max_subject_chars"],
                 metadata=metadata, only=only)
    return 0

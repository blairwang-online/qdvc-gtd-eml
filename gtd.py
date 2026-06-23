#!/usr/bin/env python3
"""
GTD (Getting Things Done) workflow based on EML email files.

Folder structure (relative to working_directory, set in config.yml):
    01-input       <- you manually drop new .eml files here
    02-triage      <- script renames + moves new files here
    03-actionable  <- you move files here
    04-delegated   <- you move files here
    05-reference   <- you move files here
    06-archive     <- you move files here

Run the script to:
    1. Ingest & rename new files from 01-input into 02-triage.
    2. Produce a report on triage / actionable / reference / recent archive.
    3. Ensure metadata.csv exists & is in sync with current .eml files.

Implementation lives in the gtd_modules package; this file just wires it
together.
"""

import sys

from gtd_modules import config as cfg_mod
from gtd_modules.fs import ensure_folders
from gtd_modules.ingest import ingest_input_files
from gtd_modules.metadata import load_metadata, sync_metadata
from gtd_modules.report import print_report


def main():
    """
    Orchestrate: load config -> ensure folders -> ingest -> sync metadata -> report.

    Example:
        main()  # run as `python gtd.py`
    """
    cfg = cfg_mod.load_config()
    base_dir = cfg["working_directory"]
    colour_enabled = cfg_mod.should_use_colour(cfg, sys.stdout)
    colour_cfg = (cfg["green_max_days"], cfg["yellow_max_days"], colour_enabled)

    ensure_folders(base_dir)

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
                 metadata=metadata)


if __name__ == "__main__":
    main()

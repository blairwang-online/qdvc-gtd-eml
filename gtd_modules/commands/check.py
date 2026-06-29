"""
`metadata_check` subcommand: reconcile metadata.csv with the files on disk and
report dangling references.

This runs the same `sync_metadata()` the `list` workflow uses (so rows are
created for any EML files not yet tracked, and rows for vanished files are
dropped), then flags two kinds of stale reference:

  * rows whose ``eml_filename`` no longer exists in any workflow folder, and
  * rows whose ``next_action`` mentions an ``*.eml`` filename that does not
    exist anywhere in the workflow.

The first list is what `sync_metadata` is about to prune; reporting it lets a
maintainer notice (and recover from) an unexpected disappearance before the row
is gone. The second catches `next_action` notes like "Closed with <other.eml>"
left pointing at a file that has since been renamed or deleted.
"""

import re
import sys

from .. import config as cfg_mod
from .. import fs
from .. import metadata as meta_mod

# An EML filename inside free text: any run of non-whitespace characters that
# ends in a literal ".eml" (case-insensitive). Per the spec, a filename is "any
# sequence of characters unbroken by spaces, followed by '.eml'".
_EML_IN_TEXT = re.compile(r"\S+\.eml", re.IGNORECASE)


def cmd_metadata_check(argv):
    """
    `gtd.py metadata_check` — reconcile metadata.csv and report dangling refs.

    1. Reconciles metadata.csv with the files on disk (creates rows for any new
       EML files, drops rows for files that have vanished) via sync_metadata().
    2. Reports rows whose eml_filename does not exist in any folder (these are
       the rows the reconcile just pruned).
    3. Reports rows whose next_action references an "*.eml" filename that does
       not exist anywhere in the workflow.

    Read-only on the .eml files themselves: it never ingests 01-input or moves
    anything. Returns 0 when nothing dangling is found, 1 when at least one
    missing-file or dangling-reference issue is reported.

    Example:
        cmd_metadata_check([])
        # === metadata_check ===
        #   metadata.csv reconciled with files on disk.
        #   ...
    """
    if argv:
        print("usage: gtd.py metadata_check", file=sys.stderr)
        return 2

    base_dir = cfg_mod.load_config()["working_directory"]
    fs.ensure_folders(base_dir)

    # Read the CSV as it stands BEFORE reconciling, so we can report rows whose
    # eml_filename has vanished (sync_metadata is about to drop them).
    rows_before = meta_mod.load_metadata(base_dir)
    on_disk = fs.all_existing_filenames(base_dir)

    missing_files = sorted(name for name in rows_before if name not in on_disk)

    # Rows whose next_action points at an .eml filename that does not exist.
    dangling_refs = []  # (eml_filename, referenced_filename)
    for name in sorted(rows_before):
        next_action = rows_before[name].get("next_action", "") or ""
        for ref in _EML_IN_TEXT.findall(next_action):
            if ref not in on_disk:
                dangling_refs.append((name, ref))

    # Step 1: create rows for untracked files (and prune vanished ones).
    meta_mod.sync_metadata(base_dir)

    print("=== metadata_check ===")
    print("  metadata.csv reconciled with files on disk "
          "(new files added, vanished files removed).")

    if missing_files:
        print(f"\n  rows whose eml_filename no longer exists ({len(missing_files)}):")
        for name in missing_files:
            print(f"    {name}")
    else:
        print("\n  no rows reference a missing eml_filename.")

    if dangling_refs:
        print(f"\n  next_action references to missing .eml files "
              f"({len(dangling_refs)}):")
        for name, ref in dangling_refs:
            print(f"    {name}: next_action -> {ref}")
    else:
        print("\n  no next_action references a missing .eml file.")

    return 1 if (missing_files or dangling_refs) else 0

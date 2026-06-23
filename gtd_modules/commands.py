"""
Subcommand implementations for the `gtd.py` CLI: list, view, alloc, help.
Each returns a process exit code (0 = success).

`gtd.py` itself is just an argument dispatcher; the real work lives here.
"""

import os
import sys

from . import config as cfg_mod
from . import fs
from . import metadata as meta_mod
from .emailutil import read_eml_message
from .ingest import ingest_input_files
from .metadata import load_metadata, sync_metadata
from .preview import render
from .report import print_report


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


def cmd_metadata(argv):
    """
    `gtd.py metadata <file.eml> get <field>` — print a stored metadata value.
    `gtd.py metadata <file.eml> set <field> [=] <value>` — write a value.

    Editable fields: general_notes, project, next_action, flags. Readable also
    includes message_ref. The ".eml" extension is optional. The "=" between
    field and value is optional, and the value may be quoted or span multiple
    shell words (they are rejoined with spaces).

    Examples:
        cmd_metadata(["x.eml", "get", "next_action"])
        cmd_metadata(["x.eml", "set", "next_action", "=", "Do something"])
    """
    if len(argv) < 3:
        print('usage: gtd.py metadata <file.eml> get <field>', file=sys.stderr)
        print('       gtd.py metadata <file.eml> set <field> [=] <value>', file=sys.stderr)
        return 2

    filename, action = argv[0], argv[1]
    field = argv[2]
    rest = argv[3:]

    base_dir = cfg_mod.load_config()["working_directory"]

    # Resolve to the canonical on-disk filename so the metadata key matches and
    # the extension is optional.
    path = fs.find_eml(base_dir, filename)
    if path is None:
        print(f"error: '{filename}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1
    canonical = os.path.basename(path)

    if action == "get":
        if rest:
            print("usage: gtd.py metadata <file.eml> get <field>", file=sys.stderr)
            return 2
        try:
            value = meta_mod.get_metadata_value(base_dir, canonical, field)
        except KeyError:
            print(f"error: unknown field '{field}'", file=sys.stderr)
            print("       readable fields: " + ", ".join(meta_mod.READABLE_FIELDS),
                  file=sys.stderr)
            return 2
        if value is None:
            # No row yet (e.g. metadata.csv not built). Treat as empty.
            value = ""
        print(value)
        return 0

    if action == "set":
        # Allow an optional leading "=" token, and rejoin the remaining words
        # into the value (the shell has already removed any quotes).
        if rest and rest[0] == "=":
            rest = rest[1:]
        value = " ".join(rest)
        try:
            meta_mod.set_metadata_value(base_dir, canonical, field, value)
        except KeyError:
            print(f"error: field '{field}' is not editable", file=sys.stderr)
            print("       editable fields: " + ", ".join(meta_mod.EDITABLE_FIELDS),
                  file=sys.stderr)
            return 2
        except FileNotFoundError:
            print(f"error: '{canonical}' is not in the workflow", file=sys.stderr)
            return 1
        print(f"{canonical}: {field} = {value!r}")
        return 0

    print(f"error: unknown action '{action}' (expected 'get' or 'set')", file=sys.stderr)
    return 2


HELP_TEXT = """\
gtd.py — a Getting Things Done workflow over .eml files

USAGE
    gtd.py <command> [arguments]

COMMANDS
    list [folder]
        Ingest any new emails from 01-input, then print the status report
        (colour-coded by age). With no argument, every folder is shown. Give a
        folder name or alias to show just that segment:
            actionable | delegated | reference | archive | triage | input
        Pipe it through a pager to scroll:
            FORCE_COLOR=1 python3 gtd.py list | less -R
            python3 gtd.py list actionable

    stats
        Show each workflow folder and how many emails it currently holds,
        plus a total:
            python3 gtd.py stats

    view <file.eml>
        Preview a single email — headers, attachments, and body (base64 is
        decoded automatically). The .eml extension is optional. Output is
        markdown-friendly:
            python3 gtd.py view 2026-06-03-project-pudding.eml
            python3 gtd.py view 2026-06-03-project-pudding | glow -

    alloc <file.eml> <destination>
        Find where an email is currently filed and move it to another folder.
        Destination is a short name or the full folder name:
            actionable | delegated | reference | archive | triage | input
        Examples:
            python3 gtd.py alloc 2026-06-03-project-pudding.eml delegated
            python3 gtd.py alloc 2026-06-03-project-pudding.eml 06-archive

    metadata <file.eml> get <field>
    metadata <file.eml> set <field> [=] <value>
        Read or write a metadata.csv field for an email. Editable fields:
        general_notes, project, next_action, flags (message_ref is read-only).
        Examples:
            python3 gtd.py metadata 2026-06-03-project-pudding.eml get next_action
            python3 gtd.py metadata 2026-06-03-project-pudding.eml set next_action = "Reply by Fri"
            python3 gtd.py metadata 2026-06-03-project-pudding.eml set flags pinned

    help
        Show this overview.

CONFIGURATION
    Settings are read from config.yml next to this script (working_directory,
    colour thresholds, my_own_accounts, etc.). See README.md / MAINTENANCE.md.
"""


def cmd_help(argv):
    """
    `gtd.py help` — print the overview of available commands.

    Example:
        cmd_help([])  # -> prints HELP_TEXT, returns 0
    """
    print(HELP_TEXT, end="")
    return 0

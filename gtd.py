#!/usr/bin/env python3
"""
GTD (Getting Things Done) workflow over EML email files.

Folder structure (relative to working_directory, set in config.yml):
    01-input       <- you manually drop new .eml files here
    02-triage      <- `list` renames + moves new files here
    03-actionable  <- you file emails here (via `alloc` or by hand)
    04-delegated   <- you file emails here
    05-reference   <- you file emails here
    06-archive     <- you file emails here

Commands (run `gtd.py help` for details):
    gtd.py list [folder]              ingest new input + print the status report
    gtd.py export <format> [out]      export all tracked emails to a data format
    gtd.py search <text>              find report entries matching <text>
    gtd.py stats                      show how many emails are in each folder
    gtd.py view <file.eml>            preview a single email
    gtd.py alloc <file.eml> <dest>    move an email to another folder
    gtd.py close <file.eml> with <other.eml>   archive + record what closed it
    gtd.py pin <file.eml>             add the "pinned" flag
    gtd.py unpin <file.eml>           remove the "pinned" flag
    gtd.py metadata <file.eml> ...    get/set a metadata.csv field
    gtd.py metadata_check             reconcile metadata.csv + report dangling refs
    gtd.py help                       show the command overview

Implementation lives in the gtd_modules package; this file just dispatches.
"""

import os
import sys

from gtd_modules import commands

# Map subcommand name -> handler. Each handler takes the remaining argv list
# and returns an exit code.
COMMANDS = {
    "list": commands.cmd_list,
    "export": commands.cmd_export,
    "search": commands.cmd_search,
    "stats": commands.cmd_stats,
    "view": commands.cmd_view,
    "alloc": commands.cmd_alloc,
    "close": commands.cmd_close,
    "pin": commands.cmd_pin,
    "unpin": commands.cmd_unpin,
    "metadata": commands.cmd_metadata,
    "metadata_check": commands.cmd_metadata_check,
    "help": commands.cmd_help,
}


def main(argv):
    """
    Dispatch to the requested subcommand.

    Example:
        main(["list"])                      # -> runs the report, returns 0
        main(["view", "2026-06-03-x.eml"])  # -> previews one email
    """
    if not argv:
        commands.cmd_help([])
        return 2

    name, rest = argv[0], argv[1:]
    if name in ("-h", "--help"):
        return commands.cmd_help([])

    handler = COMMANDS.get(name)
    if handler is None:
        print(f"gtd.py: unknown command '{name}'\n", file=sys.stderr)
        commands.cmd_help([])
        return 2

    return handler(rest)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        # Reader (e.g. `less` quit early, or `head`) closed the pipe; exit quietly.
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)

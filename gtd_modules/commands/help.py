"""
`help` subcommand: print the command overview. Holds the canonical HELP_TEXT
shown by `gtd.py help`, `gtd.py` with no args, and unknown-command errors.
"""

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

    export <format> [output-file]
        Export every tracked email (the same set `list` reports on: triage,
        actionable, delegated, reference, archive) to another data format.
        Read-only: it reconciles metadata.csv but does not ingest 01-input or
        move anything. Available formats:
            masterdetail_yaml   one YAML (.yml) document conforming to the
                                master-detail viewer SPEC (a sequence of items,
                                one per email, each with a `title` heading)
        With no output file, masterdetail_yaml writes
        <working_directory>/export-masterdetail.yml; give a path to write
        elsewhere (a ".yml" extension is appended if omitted). Examples:
            python3 gtd.py export masterdetail_yaml
            python3 gtd.py export masterdetail_yaml ~/gtd-export.yml

    stats
        Show each workflow folder and how many emails it currently holds,
        plus a total:
            python3 gtd.py stats

    search <text>
        Search the full report (what `gtd.py list` prints) for <text> and show
        the matching email entries, with the matched text highlighted. The words
        after `search` are joined into a single query, so the match is on the
        literal string — spaces, "#", and "@" included — not on separate words;
        matching is case-insensitive. Read-only: does not ingest 01-input or
        move anything. Examples:
            python3 gtd.py search project pudding
            python3 gtd.py search "#quick"
            python3 gtd.py search jane@example.com

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

    metadata_check
        Reconcile metadata.csv with the .eml files on disk, then report stale
        references. Creates rows for any EML files not yet tracked and drops
        rows for files that have vanished (the same sync `list` performs), then
        reports: (1) rows whose eml_filename no longer exists, and (2) rows
        whose next_action mentions an "*.eml" filename that does not exist
        anywhere in the workflow. Read-only on the emails themselves: it does
        not ingest 01-input or move anything. Exits 1 if anything dangling is
        found, 0 otherwise:
            python3 gtd.py metadata_check

    close <file.eml> with <other.eml>
        Archive an email and record what closed it. Refuses if the email is
        already in 06-archive; otherwise moves it there and sets its next_action
        to "Closed with <other.eml>". The word "with" is optional, as are the
        .eml extensions. <other.eml> must itself exist in the workflow; if it
        does not, the command errors immediately and nothing is moved or changed.
        Examples:
            python3 gtd.py close 2026-06-03-project-pudding.eml with 2026-06-10-reply.eml
            python3 gtd.py close 2026-06-03-project-pudding 2026-06-10-reply

    pin <file.eml>
    unpin <file.eml>
        Add or remove the "pinned" flag in an email's metadata flags field:
            python3 gtd.py pin 2026-06-03-project-pudding.eml
            python3 gtd.py unpin 2026-06-03-project-pudding.eml

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

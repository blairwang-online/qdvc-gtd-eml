"""
Status reporting: building and printing the colour-coded per-folder report
(date/elapsed, subject, filename, correspondents, own-account label, next
action) used by gtd.py.
"""

import os
import re
from datetime import datetime, timezone

from . import config, emailutil, fs


def colour_for_days(elapsed, green_max, yellow_max):
    """
    Return the ANSI colour name for a given elapsed-day count: green if
    days < green_max, else yellow if days < yellow_max, else red.

    Example:
        colour_for_days(1, 2, 14)   # -> "green"
        colour_for_days(5, 2, 14)   # -> "yellow"
        colour_for_days(30, 2, 14)  # -> "red"
    """
    if elapsed < green_max:
        return "green"
    if elapsed < yellow_max:
        return "yellow"
    return "red"


def colourize(text, colour_name, enabled=True):
    """
    Wrap text in ANSI colour codes for the named colour. If disabled (e.g. when
    output is not a TTY), return the text unchanged.

    For multi-line text, the colour code is re-applied at the START of every
    line (and reset at the end of every line). This is necessary because pagers
    like `less -R` and many terminals reset SGR colour state at each newline, so
    a single leading code would only colour the first line.

    Example:
        colourize("hi", "green")          # -> "\\033[32mhi\\033[0m"
        colourize("a\\nb", "green")        # -> "\\033[32ma\\033[0m\\n\\033[32mb\\033[0m"
        colourize("hi", "green", False)   # -> "hi"
    """
    if not enabled or colour_name not in config.COLOURS:
        return text
    start = config.COLOURS[colour_name]
    reset = config.COLOURS["reset"]
    return "\n".join(f"{start}{line}{reset}" for line in text.split("\n"))


def truncate(text, max_chars):
    """
    Truncate text to max_chars, appending a single-character ellipsis (…) if
    cut. A non-positive max_chars disables truncation.

    Example:
        truncate("a very long subject line", 10)  # -> "a very lo…"
        truncate("short", 10)                      # -> "short"
    """
    if max_chars and max_chars > 0 and len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "\u2026"
    return text


def parse_flags(raw):
    """
    Parse the metadata `flags` cell into a lower-cased set of tokens. Tokens may
    be separated by commas and/or whitespace.

    Example:
        parse_flags("pinned")              # -> {"pinned"}
        parse_flags("pinned, urgent")      # -> {"pinned", "urgent"}
        parse_flags("")                    # -> set()
    """
    if not raw:
        return set()
    return {tok.lower() for tok in re.split(r"[,\s]+", raw.strip()) if tok}


def file_report_line(base_dir, folder, filename, exclude=None,
                     max_subject=0, next_action=None, accounts=None,
                     colour_enabled=True, flags=None, today=None):
    """
    Build the report content for one file. Correspondents are prefixed with
    "With: " and capped at 3 (plus a "+ N more" line). Trailing lines (the
    matched own-account, then a PINNED marker, then the next_action) are
    returned SEPARATELY from the age-coloured body so they render distinctly:
    the account and PINNED use their own colour; the next_action is uncoloured.
    The account label comes first; the tree-style indicators (PINNED, next)
    follow it.

    `flags` is the parsed flag set (see parse_flags); when it contains "pinned"
    a "└─ PINNED" marker is emitted (after the account label, before next).

    Returns (body_block, trailing_lines, date_dt, elapsed), where trailing_lines
    is a list of already-formatted strings (possibly empty), e.g.:
        ["                    [Work account]",
         "                    └─ PINNED",
         "                    └─ next: Reply to Jane"]

    Example:
        file_report_line("/home/me/gtd", "02-triage", "x.eml",
                         next_action="Reply", accounts=accts, flags={"pinned"})
        # -> ("2026-06-03  (20d)   Subject\\n...With: Jane <jane@x.com>",
        #     ["                    [Work account]",
        #      "                    └─ PINNED",
        #      "                    └─ next: Reply"], date_dt, 20)
    """
    if today is None:
        today = datetime.now(timezone.utc)
    flags = flags or set()

    account_emails = [a["email_address"] for a in (accounts or [])]
    exclude = list(exclude or []) + account_emails

    path = os.path.join(base_dir, folder, filename)
    message = emailutil.read_eml_message(path)
    date_dt = emailutil.get_email_date(message)
    subject = emailutil.get_email_subject(message) or "(no subject)"
    subject = truncate(subject, max_subject)
    correspondents = emailutil.get_email_correspondents(message, exclude=exclude)
    own_account = emailutil.match_own_account(message, accounts)

    date_str = date_dt.strftime("%Y-%m-%d")
    elapsed = (today.date() - date_dt.date()).days
    elapsed_str = f"({elapsed}d)".rjust(6)  # right-align up to "(9999d)"-ish

    indent = " " * len(f"{date_str} {elapsed_str}   ")
    rows = [f"{date_str} {elapsed_str}   {subject}", f"{indent}{filename}"]
    if correspondents:
        shown = correspondents[:3]
        rows.extend(f"{indent}With: {c}" for c in shown)
        remaining = len(correspondents) - len(shown)
        if remaining > 0:
            rows.append(f"{indent}      + {remaining} more")
    else:
        rows.append(f"{indent}With: (no correspondents)")

    trailing = []
    if own_account:
        label = colourize(f"[{own_account['display_name']}]",
                          own_account["colour"], colour_enabled)
        trailing.append(f"{indent}{label}")
    if "pinned" in flags:
        marker = colourize(f"\u2514\u2500 PINNED", "magenta", colour_enabled)
        trailing.append(f"{indent}{marker}")
    if next_action and next_action.strip():
        trailing.append(f"{indent}\u2514\u2500 next: {next_action.strip()}")

    return "\n".join(rows), trailing, date_dt, elapsed


def report_folder(base_dir, folder, colour_cfg, exclude=None, limit=None,
                  max_subject=0, metadata=None, show_next_action=False,
                  accounts=None):
    """
    Print a report block for a folder, colour-coding each entry by elapsed days.
    If limit is set, show only the most recent `limit` files (by email date).
    `colour_cfg` is (green_max, yellow_max, enabled); `exclude` is a list of
    correspondent addresses to omit; `max_subject` truncates subjects;
    `metadata` is the dict from load_metadata; `show_next_action` toggles the
    next_action branch line (off for the archive); `accounts` is the
    my_own_accounts list used to label which account received each email.

    Entries flagged "pinned" in metadata float to the top of their section
    (and are never dropped by the archive `limit`).

    Example:
        report_folder("/home/me/gtd", "03-actionable", (2, 14, True),
                      metadata=meta, show_next_action=True, accounts=accts)
        # -> prints colour-coded actionable entries with account + next-action
    """
    green_max, yellow_max, enabled = colour_cfg
    metadata = metadata or {}
    files = fs.list_eml_files(base_dir, folder)
    entries = []
    for name in files:
        meta = metadata.get(name, {})
        flags = parse_flags(meta.get("flags", ""))
        pinned = "pinned" in flags
        try:
            na = meta.get("next_action", "") if show_next_action else None
            body, trailing, date_dt, elapsed = file_report_line(
                base_dir, folder, name, exclude=exclude,
                max_subject=max_subject, next_action=na,
                accounts=accounts, colour_enabled=enabled, flags=flags)
            body = colourize(body, colour_for_days(elapsed, green_max, yellow_max), enabled)
            block = "\n".join([body] + trailing)
            entries.append((pinned, date_dt, block))
        except Exception as e:
            entries.append((pinned, datetime.min.replace(tzinfo=timezone.utc),
                            f"!! could not read {name}: {e}"))

    entries.sort(key=lambda t: t[1])  # oldest -> newest
    if limit is not None:
        # Keep the most recent `limit`, but never drop pinned entries.
        recent = entries[-limit:]
        pinned_extra = [e for e in entries[:-limit] if e[0]]
        entries = pinned_extra + recent

    # Float pinned entries to the top of the section (stable: preserves the
    # date order established above within each group).
    entries.sort(key=lambda t: not t[0])

    print(f"\n=== {folder} ({len(files)} file{'s' if len(files) != 1 else ''}) ===")
    if not entries:
        print("   (empty)")
    for _, _, block in entries:
        print(block)


def print_report(base_dir, archive_n, colour_cfg, accounts=None,
                 max_subject=0, metadata=None, only=None):
    """
    Print the GTD status report. next_action lines are shown for
    triage/actionable/delegated/reference but NOT for the archive. The matched
    own-account label is shown in every segment.

    `only`, if given, is a single canonical folder name (e.g. "03-actionable");
    just that folder is printed. When showing a single folder the archive
    `limit` is not applied (you asked for that folder specifically, so show it
    all); in the full report the archive is still capped at archive_n.

    Example:
        print_report("/home/me/gtd", 10, (2, 14, True), accounts=accts,
                     max_subject=72, metadata=meta)
        # -> prints all segments
        print_report(..., only="03-actionable")
        # -> prints just the actionable segment
    """
    common = dict(accounts=accounts, max_subject=max_subject, metadata=metadata)

    # (folder, show_next_action, limit_in_full_report)
    segments = [
        (config.TRIAGE_DIR, True, None),
        (config.ACTIONABLE_DIR, True, None),
        (config.DELEGATED_DIR, True, None),
        (config.REFERENCE_DIR, True, None),
        (config.ARCHIVE_DIR, False, archive_n),
    ]

    for folder, show_next_action, limit in segments:
        if only is not None and folder != only:
            continue
        # A specifically-requested single folder is shown in full (no limit).
        effective_limit = None if only is not None else limit
        report_folder(base_dir, folder, colour_cfg,
                      show_next_action=show_next_action,
                      limit=effective_limit, **common)

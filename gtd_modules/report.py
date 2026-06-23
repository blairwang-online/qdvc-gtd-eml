"""
Status reporting: building and printing the colour-coded per-folder report
(date/elapsed, subject, filename, correspondents, own-account label, next
action) used by gtd.py.
"""

import os
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

    Example:
        colourize("hi", "green")        # -> "\\033[32mhi\\033[0m"
        colourize("hi", "green", False) # -> "hi"
    """
    if not enabled or colour_name not in config.COLOURS:
        return text
    return f"{config.COLOURS[colour_name]}{text}{config.COLOURS['reset']}"


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


def file_report_line(base_dir, folder, filename, exclude=None,
                     max_subject=0, next_action=None, accounts=None,
                     colour_enabled=True, today=None):
    """
    Build the report content for one file. Correspondents are prefixed with
    "With: " and capped at 3 (plus a "+ N more" line). Trailing lines (the
    matched own-account, then the next_action) are returned SEPARATELY from the
    age-coloured body so they render distinctly: the account uses its own
    configured colour; the next_action is uncoloured.

    Returns (body_block, trailing_lines, date_dt, elapsed), where trailing_lines
    is a list of already-formatted strings (possibly empty), e.g.:
        ["                    [Work account]",
         "                    └─ next: Reply to Jane"]

    Example:
        file_report_line("/home/me/gtd", "02-triage", "x.eml",
                         next_action="Reply", accounts=accts)
        # -> ("2026-06-03  (20d)   Subject\\n...With: Jane <jane@x.com>",
        #     ["                    [Work account]",
        #      "                    └─ next: Reply"], date_dt, 20)
    """
    if today is None:
        today = datetime.now(timezone.utc)

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

    Example:
        report_folder("/home/me/gtd", "03-actionable", (2, 14, True),
                      metadata=meta, show_next_action=True, accounts=accts)
        # -> prints colour-coded actionable entries with account + next-action
    """
    green_max, yellow_max, enabled = colour_cfg
    metadata = metadata or {}
    files = fs.list_eml_files(base_dir, folder)
    lines = []
    for name in files:
        try:
            na = metadata.get(name, {}).get("next_action", "") if show_next_action else None
            body, trailing, date_dt, elapsed = file_report_line(
                base_dir, folder, name, exclude=exclude,
                max_subject=max_subject, next_action=na,
                accounts=accounts, colour_enabled=enabled)
            body = colourize(body, colour_for_days(elapsed, green_max, yellow_max), enabled)
            block = "\n".join([body] + trailing)
            lines.append((date_dt, block))
        except Exception as e:
            lines.append((datetime.min.replace(tzinfo=timezone.utc),
                          f"!! could not read {name}: {e}"))

    lines.sort(key=lambda t: t[0])  # oldest -> newest
    if limit is not None:
        lines = lines[-limit:]

    print(f"\n=== {folder} ({len(files)} file{'s' if len(files) != 1 else ''}) ===")
    if not lines:
        print("   (empty)")
    for _, block in lines:
        print(block)


def print_report(base_dir, archive_n, colour_cfg, accounts=None,
                 max_subject=0, metadata=None):
    """
    Print the full GTD status report across the relevant folders. next_action
    lines are shown for triage/actionable/reference but NOT for the archive. The
    matched own-account label is shown in every segment.

    Example:
        print_report("/home/me/gtd", 10, (2, 14, True), accounts=accts,
                     max_subject=72, metadata=meta)
        # -> prints triage, actionable, reference, last-10 archive blocks
    """
    common = dict(accounts=accounts, max_subject=max_subject, metadata=metadata)
    report_folder(base_dir, config.TRIAGE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, config.ACTIONABLE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, config.REFERENCE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, config.ARCHIVE_DIR, colour_cfg, show_next_action=False,
                  limit=archive_n, **common)

#!/usr/bin/env python3
"""
GTD (Getting Things Done) workflow based on EML email files.

Folder structure (relative to working_directory, set in config.yml):
    01-input       <- you manually drop new .eml files here
    02-triage      <- script renames + moves new files here
    03-actionable  <- you move files here
    04-reference   <- you move files here
    05-archive     <- you move files here

Run the script to:
    1. Ingest & rename new files from 01-input into 02-triage.
    2. Produce a report on triage / actionable / reference / recent archive.
    3. Ensure metadata.csv exists & is in sync with current .eml files.
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone
from email import message_from_binary_file
from email.utils import parsedate_to_datetime

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Settings live in config.yml alongside this script.
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config.yml"
)

# Defaults — overridden by matching keys in config.yml if present.
DEFAULTS = {
    "working_directory": os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "gtd-eml"
    ),                         # root holding the 5 folders + metadata.csv
    "max_filename_chars": 60,  # max length of generated filename (incl. ".eml")
    "archive_report_n": 10,    # number of most recent archive files to report
    "green_max_days": 2,       # days < this -> green
    "yellow_max_days": 14,     # days < this (and >= green) -> yellow; else red
    "max_subject_chars": 72,   # truncate displayed subjects longer than this
    "my_own_accounts": [],     # list of {email_address, display_name, colour}
}

# ANSI colour codes used for report lines.
COLOURS = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "reset": "\033[0m",
}

INPUT_DIR = "01-input"
TRIAGE_DIR = "02-triage"
ACTIONABLE_DIR = "03-actionable"
REFERENCE_DIR = "04-reference"
ARCHIVE_DIR = "05-archive"

ALL_DIRS = [INPUT_DIR, TRIAGE_DIR, ACTIONABLE_DIR, REFERENCE_DIR, ARCHIVE_DIR]
METADATA_FILE = "metadata.csv"
METADATA_HEADERS = ["eml_filename", "general_notes", "project", "next_action", "message_ref"]


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_config(config_path=CONFIG_FILE):
    """
    Load settings from config.yml, falling back to DEFAULTS for any key not
    present. my_own_accounts is normalised to a list of dicts with lower-cased
    email_address plus display_name and colour.

    Example (config.yml has my_own_accounts with one entry):
        load_config("/path/config.yml")["my_own_accounts"]
        # -> [{"email_address": "james@x.com",
        #      "display_name": "Work account", "colour": "yellow"}]
    """
    cfg = dict(DEFAULTS)
    if os.path.isfile(config_path):
        if yaml is None:
            raise RuntimeError(
                "config.yml found but PyYAML is not installed. "
                "Install it with: pip install pyyaml"
            )
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for key in cfg:
            if key in data and data[key] is not None:
                cfg[key] = data[key]

    cfg["my_own_accounts"] = normalise_accounts(cfg.get("my_own_accounts"))
    return cfg


def normalise_accounts(accounts):
    """
    Normalise the my_own_accounts list: lower-case email addresses, supply a
    fallback display_name, and validate the colour against COLOURS.

    Example:
        normalise_accounts([{"email_address": "ME@X.com"}])
        # -> [{"email_address": "me@x.com", "display_name": "me@x.com",
        #      "colour": "cyan"}]
    """
    result = []
    for entry in accounts or []:
        if not isinstance(entry, dict):
            continue
        email = (entry.get("email_address") or "").strip().lower()
        if not email:
            continue
        colour = (entry.get("colour") or "cyan").strip().lower()
        if colour not in COLOURS:
            colour = "cyan"
        result.append({
            "email_address": email,
            "display_name": (entry.get("display_name") or email).strip(),
            "colour": colour,
        })
    return result


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #
def ensure_folders(base_dir):
    """
    Create the 5 GTD folders if they don't exist.

    Example:
        ensure_folders("/home/me/gtd")
        # -> creates /home/me/gtd/01-input, .../02-triage, ... if missing
    """
    for folder in ALL_DIRS:
        os.makedirs(os.path.join(base_dir, folder), exist_ok=True)


def list_eml_files(base_dir, folder):
    """
    Return a sorted list of .eml filenames (not full paths) in a given folder.

    Example:
        list_eml_files("/home/me/gtd", "02-triage")
        # -> ["2026-06-12-meeting-minutes.eml", "2026-06-13-update.eml"]
    """
    folder_path = os.path.join(base_dir, folder)
    if not os.path.isdir(folder_path):
        return []
    return sorted(
        f for f in os.listdir(folder_path)
        if f.lower().endswith(".eml")
        and os.path.isfile(os.path.join(folder_path, f))
    )


def all_existing_filenames(base_dir):
    """
    Return a set of every .eml filename present across all 5 folders.

    Example:
        all_existing_filenames("/home/me/gtd")
        # -> {"2026-06-12-meeting.eml", "2026-06-13-update.eml"}
    """
    names = set()
    for folder in ALL_DIRS:
        names.update(list_eml_files(base_dir, folder))
    return names


# --------------------------------------------------------------------------- #
# EML parsing helpers
# --------------------------------------------------------------------------- #
def read_eml_message(eml_path):
    """
    Parse an .eml file into an email.message.Message object.

    Example:
        read_eml_message("/home/me/gtd/01-input/foo.eml")
        # -> <email.message.Message object>
    """
    with open(eml_path, "rb") as f:
        return message_from_binary_file(f)


def get_email_subject(message):
    """
    Extract the (decoded) subject line from an email Message.

    Example:
        get_email_subject(msg)  # Subject: "Meeting Minutes - Project Pudding"
        # -> "Meeting Minutes - Project Pudding"
    """
    raw = message.get("Subject", "") or ""
    from email.header import decode_header, make_header
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


def get_email_date(message):
    """
    Extract the email's Date header as a timezone-aware datetime.
    Falls back to the current time if the header is missing/unparseable.

    Example:
        get_email_date(msg)  # Date: "Wed, 03 Jun 2026 09:15:00 +0000"
        # -> datetime(2026, 6, 3, 9, 15, tzinfo=...)
    """
    raw = message.get("Date", "")
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass
    return datetime.now(timezone.utc)


def get_email_correspondents(message, exclude=None):
    """
    Return a de-duplicated, order-preserving list of correspondent display
    names/addresses drawn from the From, To, and Cc headers (decoded). Any
    correspondent whose email address (case-insensitive) is in `exclude` is
    omitted.

    Example:
        get_email_correspondents(msg, exclude=["bob@y.com"])
        # From: "Jane Doe <jane@x.com>", To: "bob@y.com"
        # -> ["Jane Doe <jane@x.com>"]
    """
    from email.header import decode_header, make_header
    from email.utils import getaddresses

    exclude_set = {e.lower() for e in (exclude or [])}

    raw_values = []
    for header in ("From", "To", "Cc"):
        raw_values.extend(message.get_all(header, []))

    people = []
    for name, addr in getaddresses(raw_values):
        if addr and addr.lower() in exclude_set:
            continue
        try:
            name = str(make_header(decode_header(name))).strip()
        except Exception:
            name = name.strip()
        if name and addr:
            entry = f"{name} <{addr}>"
        else:
            entry = name or addr
        if entry and entry not in people:
            people.append(entry)
    return people


def match_own_account(message, accounts):
    """
    Return the first configured own-account (dict) whose email_address appears
    in the To, Cc, From, or Bcc headers, or None. Header order of preference:
    To, Cc, Bcc, From (i.e. prefer the account that received the mail).

    Example:
        match_own_account(msg, [{"email_address": "me@x.com",
                                  "display_name": "Work", "colour": "yellow"}])
        # To: "me@x.com" -> {"email_address": "me@x.com", ...}
    """
    from email.utils import getaddresses

    if not accounts:
        return None
    by_email = {a["email_address"]: a for a in accounts}
    for header in ("To", "Cc", "Bcc", "From"):
        for _, addr in getaddresses(message.get_all(header, [])):
            if addr and addr.lower() in by_email:
                return by_email[addr.lower()]
    return None


def get_email_body_text(message):
    """
    Return the email's text body as a single string, decoding base64 /
    quoted-printable transparently. Prefers text/plain; falls back to the raw
    text of a text/html part. Returns "" if no text body is found.

    Example:
        get_email_body_text(msg)  # base64 body "SGk=" -> "Hi"
    """
    def decode_part(part):
        payload = part.get_payload(decode=True)  # handles base64 / QP
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, TypeError):
            return payload.decode("utf-8", errors="replace")

    if not message.is_multipart():
        return decode_part(message)

    plain, html = None, None
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in disposition:
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and plain is None:
            plain = decode_part(part)
        elif ctype == "text/html" and html is None:
            html = decode_part(part)

    if plain and plain.strip():
        return plain
    return html or ""


# Matches e.g. "Message ref. 8FKnj9Tx8d" — case-insensitive, with flexible
# spacing/punctuation after "ref". The nanoid uses the default nanoid alphabet
# (A-Za-z0-9_-). Length 6-32 keeps it from grabbing unrelated long tokens.
MESSAGE_REF_RE = re.compile(
    r"message\s+ref\.?\s*[:\-]?\s*([A-Za-z0-9_-]{6,32})",
    re.IGNORECASE,
)


def find_message_ref(message):
    """
    Return the FIRST message-ref nanoid found in the email body, or None.
    In a thread with several refs (quoted replies), the earliest occurrence in
    the body text is treated as authoritative.

    Example:
        find_message_ref(msg)  # body contains "Message ref. 8FKnj9Tx8d"
        # -> "8FKnj9Tx8d"
    """
    body = get_email_body_text(message)
    if not body:
        return None
    match = MESSAGE_REF_RE.search(body)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# Filename generation
# --------------------------------------------------------------------------- #
def slugify(text):
    """
    Convert arbitrary text into a lowercase dash-separated slug containing
    only [a-z0-9-].

    Example:
        slugify("Meeting Minutes - Project Pudding!")
        # -> "meeting-minutes-project-pudding"
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)   # non-alnum -> dash
    text = re.sub(r"-{2,}", "-", text)        # collapse repeats
    return text.strip("-")


def build_base_filename(date_dt, subject, max_chars, message_ref=None):
    """
    Build a "yyyy-mm-dd-brief-description[-ref-<nanoid>]" base name (no
    extension), truncated so that base + ".eml" fits within max_chars. When a
    message_ref is given, the "-ref-<nanoid>" suffix is preserved intact and
    the subject slug is truncated to make room.

    Example:
        build_base_filename(datetime(2026,6,12), "Meeting Minutes", 40)
        # -> "2026-06-12-meeting-minutes"
        build_base_filename(datetime(2026,6,12), "Meeting Minutes", 40, "8FKnj9Tx8d")
        # -> "2026-06-12-meeting-ref-8FKnj9Tx8d"
    """
    date_str = date_dt.strftime("%Y-%m-%d")
    slug = slugify(subject) or "no-subject"

    ref_suffix = f"-ref-{message_ref}" if message_ref else ""
    max_base = max_chars - len(".eml")

    # Reserve space for the date prefix and the (protected) ref suffix; the
    # subject slug gets whatever remains.
    available_for_slug = max_base - len(date_str) - len("-") - len(ref_suffix)
    if available_for_slug < 0:
        # Pathological: ref alone overflows. Keep date + ref, drop the slug.
        base = f"{date_str}{ref_suffix}"
        return base[:max_base].rstrip("-")

    if len(slug) > available_for_slug:
        slug = slug[:available_for_slug].rstrip("-")

    base = f"{date_str}-{slug}{ref_suffix}" if slug else f"{date_str}{ref_suffix}"
    return base.strip("-")


def unique_filename(base, existing, max_chars):
    """
    Given a base name (no extension) and a set of existing filenames,
    return a unique "<base>.eml". Appends "-N" before the extension on
    collision, keeping the total within max_chars.

    Example:
        unique_filename("2026-06-12-meeting", {"2026-06-12-meeting.eml"}, 60)
        # -> "2026-06-12-meeting-2.eml"
    """
    candidate = f"{base}.eml"
    if candidate not in existing:
        return candidate

    n = 2
    while True:
        suffix = f"-{n}"
        max_base = max_chars - len(".eml") - len(suffix)
        trimmed = base[:max_base].rstrip("-") if len(base) > max_base else base
        candidate = f"{trimmed}{suffix}.eml"
        if candidate not in existing:
            return candidate
        n += 1


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
def ingest_input_files(base_dir, max_chars):
    """
    Rename every .eml in 01-input per the naming convention and move it to
    02-triage. Detects a "Message ref. <nanoid>" in each body and appends
    "-ref-<nanoid>" to the filename. Returns a list of
    (old_name, new_name, message_ref) tuples (message_ref is "" if none found).

    Example:
        ingest_input_files("/home/me/gtd", 60)
        # -> [("inbox123.eml", "2026-06-12-meeting-ref-8FKnj9Tx8d.eml", "8FKnj9Tx8d")]
    """
    moved = []
    existing = all_existing_filenames(base_dir)
    input_path = os.path.join(base_dir, INPUT_DIR)
    triage_path = os.path.join(base_dir, TRIAGE_DIR)

    for old_name in list_eml_files(base_dir, INPUT_DIR):
        old_path = os.path.join(input_path, old_name)
        message = read_eml_message(old_path)
        date_dt = get_email_date(message)
        subject = get_email_subject(message)
        message_ref = find_message_ref(message)

        base = build_base_filename(date_dt, subject, max_chars, message_ref=message_ref)
        new_name = unique_filename(base, existing, max_chars)
        existing.add(new_name)

        os.rename(old_path, os.path.join(triage_path, new_name))
        moved.append((old_name, new_name, message_ref or ""))

    return moved


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def colour_for_days(elapsed, green_max, yellow_max):
    """
    Return the ANSI colour name for a given elapsed-day count:
    green if days < green_max, else yellow if days < yellow_max, else red.

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
    if not enabled or colour_name not in COLOURS:
        return text
    return f"{COLOURS[colour_name]}{text}{COLOURS['reset']}"


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
    "With: ". Trailing lines (the matched own-account, then the next_action) are
    returned SEPARATELY from the age-coloured body so they render distinctly:
    the account uses its own configured colour; the next_action is uncoloured.

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
    message = read_eml_message(path)
    date_dt = get_email_date(message)
    subject = get_email_subject(message) or "(no subject)"
    subject = truncate(subject, max_subject)
    correspondents = get_email_correspondents(message, exclude=exclude)
    own_account = match_own_account(message, accounts)

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
    files = list_eml_files(base_dir, folder)
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
    lines are shown for triage/actionable/reference but NOT for the archive.
    The matched own-account label is shown in every segment.

    Example:
        print_report("/home/me/gtd", 10, (2, 14, True), accounts=accts,
                     max_subject=72, metadata=meta)
        # -> prints triage, actionable, reference, last-10 archive blocks
    """
    common = dict(accounts=accounts, max_subject=max_subject, metadata=metadata)
    report_folder(base_dir, TRIAGE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, ACTIONABLE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, REFERENCE_DIR, colour_cfg, show_next_action=True, **common)
    report_folder(base_dir, ARCHIVE_DIR, colour_cfg, show_next_action=False,
                  limit=archive_n, **common)


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def load_metadata(base_dir):
    """
    Read metadata.csv into a dict keyed by eml_filename. Returns {} if the
    file doesn't exist.

    Example:
        load_metadata("/home/me/gtd")
        # -> {"2026-06-03-x.eml": {"general_notes": "", "project": "Pudding",
        #                          "next_action": "Reply to Jane"}}
    """
    meta_path = os.path.join(base_dir, METADATA_FILE)
    rows = {}
    if os.path.isfile(meta_path):
        with open(meta_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row.get("eml_filename", "")
                if key:
                    rows[key] = {h: row.get(h, "") for h in METADATA_HEADERS if h != "eml_filename"}
    return rows


def sync_metadata(base_dir, new_values=None):
    """
    Ensure metadata.csv exists at the root and has one row per current .eml
    file (across all folders). Preserves existing column values (notes,
    project, next_action, message_ref); adds blank rows for new files; drops
    rows for files that no longer exist.

    `new_values` optionally seeds columns for freshly-ingested files, e.g.
    {"2026-06-03-x.eml": {"message_ref": "8FKnj9Tx8d"}}. Seeds only apply to
    files not already present in the CSV (no retroactive overwrite).

    Example:
        sync_metadata("/home/me/gtd", {"x.eml": {"message_ref": "8FKnj9Tx8d"}})
        # -> writes/updates /home/me/gtd/metadata.csv
    """
    meta_path = os.path.join(base_dir, METADATA_FILE)
    current = all_existing_filenames(base_dir)
    existing_rows = load_metadata(base_dir)
    new_values = new_values or {}
    blank = {h: "" for h in METADATA_HEADERS if h != "eml_filename"}

    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_HEADERS)
        writer.writeheader()
        for name in sorted(current):
            if name in existing_rows:
                prev = existing_rows[name]
            else:
                prev = dict(blank)
                prev.update(new_values.get(name, {}))  # seed new files only
            row = {"eml_filename": name}
            row.update({h: prev.get(h, "") for h in METADATA_HEADERS if h != "eml_filename"})
            writer.writerow(row)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    """
    Orchestrate: load config -> ensure folders -> ingest -> sync metadata -> report.

    Example:
        main()  # run as `python gtd.py`
    """
    cfg = load_config()
    base_dir = cfg["working_directory"]
    colour_enabled = sys.stdout.isatty()
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

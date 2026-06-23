#!/usr/bin/env python3
"""
GTD (Getting Things Done) workflow based on EML email files.

Folder structure (relative to BASE_DIR):
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

import configparser
import csv
import os
import re
import sys
from datetime import datetime, timezone
from email import message_from_binary_file
from email.utils import parsedate_to_datetime

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# The INI file lives alongside this script and is named "<script>.ini".
INI_FILE = os.path.abspath(__file__) + ".ini"  # e.g. /path/gtd.py.ini

# Defaults — overridden by [settings] in gtd.py.ini if present there.
DEFAULTS = {
    "working_directory": os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "gtd-eml"
    ),                         # root holding the 5 folders + metadata.csv
    "max_filename_chars": 60,  # max length of generated filename (incl. ".eml")
    "archive_report_n": 10,    # number of most recent archive files to report
    "green_max_days": 2,       # days < this -> green
    "yellow_max_days": 14,     # days < this (and >= green) -> yellow; else red
}

# ANSI colour codes used for report lines.
COLOURS = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "reset": "\033[0m",
}

INPUT_DIR = "01-input"
TRIAGE_DIR = "02-triage"
ACTIONABLE_DIR = "03-actionable"
REFERENCE_DIR = "04-reference"
ARCHIVE_DIR = "05-archive"

ALL_DIRS = [INPUT_DIR, TRIAGE_DIR, ACTIONABLE_DIR, REFERENCE_DIR, ARCHIVE_DIR]
METADATA_FILE = "metadata.csv"
METADATA_HEADERS = ["eml_filename", "general_notes", "project"]


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_config(ini_path=INI_FILE):
    """
    Load settings from a [settings] section in the INI file, falling back to
    DEFAULTS for any key not present. Integer keys are coerced to int.

    Example (gtd.py.ini contains working_directory = "/data" and green_max_days = 1):
        load_config("/path/gtd.py.ini")
        # -> {"working_directory": "/data", "max_filename_chars": 60,
        #     "archive_report_n": 10, "green_max_days": 1, "yellow_max_days": 14}
    """
    cfg = dict(DEFAULTS)
    parser = configparser.ConfigParser()
    if os.path.isfile(ini_path):
        parser.read(ini_path, encoding="utf-8")
        if parser.has_section("settings"):
            section = parser["settings"]
            for key in cfg:
                if key in section:
                    raw = section[key].strip().strip('"').strip("'")
                    if isinstance(DEFAULTS[key], int):
                        cfg[key] = int(raw)
                    else:
                        cfg[key] = raw
    return cfg


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


def get_email_correspondents(message):
    """
    Return a de-duplicated, order-preserving list of correspondent display
    names/addresses drawn from the From, To, and Cc headers (decoded).

    Example:
        get_email_correspondents(msg)
        # From: "Jane Doe <jane@x.com>", To: "bob@y.com"
        # -> ["Jane Doe <jane@x.com>", "bob@y.com"]
    """
    from email.header import decode_header, make_header
    from email.utils import getaddresses

    raw_values = []
    for header in ("From", "To", "Cc"):
        raw_values.extend(message.get_all(header, []))

    people = []
    for name, addr in getaddresses(raw_values):
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


def build_base_filename(date_dt, subject, max_chars):
    """
    Build a "yyyy-mm-dd-brief-description" base name (no extension),
    truncated so that base + ".eml" fits within max_chars.

    Example:
        build_base_filename(datetime(2026,6,12), "Meeting Minutes", 40)
        # -> "2026-06-12-meeting-minutes"
    """
    date_str = date_dt.strftime("%Y-%m-%d")
    slug = slugify(subject) or "no-subject"
    base = f"{date_str}-{slug}"

    ext_len = len(".eml")
    max_base = max_chars - ext_len
    if len(base) > max_base:
        base = base[:max_base].rstrip("-")
    return base


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
    02-triage. Returns a list of (old_name, new_name) tuples.

    Example:
        ingest_input_files("/home/me/gtd", 60)
        # -> [("inbox123.eml", "2026-06-12-meeting-minutes.eml")]
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

        base = build_base_filename(date_dt, subject, max_chars)
        new_name = unique_filename(base, existing, max_chars)
        existing.add(new_name)

        os.rename(old_path, os.path.join(triage_path, new_name))
        moved.append((old_name, new_name))

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


def file_report_line(base_dir, folder, filename, today=None):
    """
    Build a multi-line report block for one file:
        <date> (<elapsed>d)   <subject>
                              <filename>
                              <correspondent1>; <correspondent2>; ...

    Returns (block_text, date_dt, elapsed).

    Example:
        file_report_line("/home/me/gtd", "02-triage", "2026-06-03-x.eml")
        # -> ("2026-06-03  (20d)   Meeting Minutes\\n"
        #     "                    2026-06-03-x.eml\\n"
        #     "                    Jane <jane@x.com>; bob@y.com", date_dt, 20)
    """
    if today is None:
        today = datetime.now(timezone.utc)

    path = os.path.join(base_dir, folder, filename)
    message = read_eml_message(path)
    date_dt = get_email_date(message)
    subject = get_email_subject(message) or "(no subject)"
    correspondents = get_email_correspondents(message)

    date_str = date_dt.strftime("%Y-%m-%d")
    elapsed = (today.date() - date_dt.date()).days
    elapsed_str = f"({elapsed}d)".rjust(6)  # right-align up to "(9999d)"-ish

    indent = " " * len(f"{date_str} {elapsed_str}   ")
    people = "; ".join(correspondents) if correspondents else "(no correspondents)"

    block = (
        f"{date_str} {elapsed_str}   {subject}\n"
        f"{indent}{filename}\n"
        f"{indent}{people}"
    )
    return block, date_dt, elapsed


def report_folder(base_dir, folder, colour_cfg, limit=None):
    """
    Print a report block for a folder, colour-coding each line by elapsed days.
    If limit is set, show only the most recent `limit` files (by email date).
    `colour_cfg` is (green_max, yellow_max, enabled).

    Example:
        report_folder("/home/me/gtd", "05-archive", (2, 14, True), limit=10)
        # -> prints up to 10 most-recent, colour-coded archive lines
    """
    green_max, yellow_max, enabled = colour_cfg
    files = list_eml_files(base_dir, folder)
    lines = []
    for name in files:
        try:
            line, date_dt, elapsed = file_report_line(base_dir, folder, name)
            line = colourize(line, colour_for_days(elapsed, green_max, yellow_max), enabled)
            lines.append((date_dt, line))
        except Exception as e:
            lines.append((datetime.min.replace(tzinfo=timezone.utc),
                          f"!! could not read {name}: {e}"))

    lines.sort(key=lambda t: t[0])  # oldest -> newest
    if limit is not None:
        lines = lines[-limit:]

    print(f"\n=== {folder} ({len(files)} file{'s' if len(files) != 1 else ''}) ===")
    if not lines:
        print("   (empty)")
    for _, line in lines:
        print(line)


def print_report(base_dir, archive_n, colour_cfg):
    """
    Print the full GTD status report across the relevant folders.

    Example:
        print_report("/home/me/gtd", 10, (2, 14, True))
        # -> prints triage, actionable, reference, last-10 archive blocks
    """
    report_folder(base_dir, TRIAGE_DIR, colour_cfg)
    report_folder(base_dir, ACTIONABLE_DIR, colour_cfg)
    report_folder(base_dir, REFERENCE_DIR, colour_cfg)
    report_folder(base_dir, ARCHIVE_DIR, colour_cfg, limit=archive_n)


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def sync_metadata(base_dir):
    """
    Ensure metadata.csv exists at the root and has one row per current .eml
    file (across all folders). Preserves existing notes/project values; adds
    blank rows for new files; drops rows for files that no longer exist.

    Example:
        sync_metadata("/home/me/gtd")
        # -> writes/updates /home/me/gtd/metadata.csv
    """
    meta_path = os.path.join(base_dir, METADATA_FILE)
    current = all_existing_filenames(base_dir)

    existing_rows = {}
    if os.path.isfile(meta_path):
        with open(meta_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_rows[row.get("eml_filename", "")] = {
                    "general_notes": row.get("general_notes", ""),
                    "project": row.get("project", ""),
                }

    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_HEADERS)
        writer.writeheader()
        for name in sorted(current):
            prev = existing_rows.get(name, {"general_notes": "", "project": ""})
            writer.writerow({
                "eml_filename": name,
                "general_notes": prev["general_notes"],
                "project": prev["project"],
            })


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
    if moved:
        print("Ingested from 01-input -> 02-triage:")
        for old_name, new_name in moved:
            print(f"   {old_name}  ->  {new_name}")
    else:
        print("No new files in 01-input.")

    sync_metadata(base_dir)
    print_report(base_dir, cfg["archive_report_n"], colour_cfg)


if __name__ == "__main__":
    main()

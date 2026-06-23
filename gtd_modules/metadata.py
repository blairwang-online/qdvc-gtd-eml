"""
metadata.csv handling: read it into a dict and keep it in sync with the EML
files currently present across all folders.
"""

import csv
import os

from . import config, fs

# Columns a user may read/write via `gtd.py metadata`. eml_filename is the key
# (not editable here); message_ref is derived at ingestion and left read-only to
# avoid desyncing it from the actual filename suffix.
EDITABLE_FIELDS = ["general_notes", "project", "next_action", "flags"]
READABLE_FIELDS = [h for h in config.METADATA_HEADERS if h != "eml_filename"]


def load_metadata(base_dir):
    """
    Read metadata.csv into a dict keyed by eml_filename. Returns {} if the file
    doesn't exist.

    Example:
        load_metadata("/home/me/gtd")
        # -> {"2026-06-03-x.eml": {"general_notes": "", "project": "Pudding",
        #                          "next_action": "Reply to Jane", "message_ref": ""}}
    """
    meta_path = os.path.join(base_dir, config.METADATA_FILE)
    rows = {}
    if os.path.isfile(meta_path):
        with open(meta_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row.get("eml_filename", "")
                if key:
                    rows[key] = {h: row.get(h, "")
                                 for h in config.METADATA_HEADERS if h != "eml_filename"}
    return rows


def sync_metadata(base_dir, new_values=None):
    """
    Ensure metadata.csv exists at the root and has one row per current .eml file
    (across all folders). Preserves existing column values (notes, project,
    next_action, message_ref); adds blank rows for new files; drops rows for
    files that no longer exist.

    `new_values` optionally seeds columns for freshly-ingested files, e.g.
    {"2026-06-03-x.eml": {"message_ref": "8FKnj9Tx8d"}}. Seeds only apply to
    files not already present in the CSV (no retroactive overwrite).

    Example:
        sync_metadata("/home/me/gtd", {"x.eml": {"message_ref": "8FKnj9Tx8d"}})
        # -> writes/updates /home/me/gtd/metadata.csv
    """
    meta_path = os.path.join(base_dir, config.METADATA_FILE)
    current = fs.all_existing_filenames(base_dir)
    existing_rows = load_metadata(base_dir)
    new_values = new_values or {}
    blank = {h: "" for h in config.METADATA_HEADERS if h != "eml_filename"}

    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.METADATA_HEADERS)
        writer.writeheader()
        for name in sorted(current):
            if name in existing_rows:
                prev = existing_rows[name]
            else:
                prev = dict(blank)
                prev.update(new_values.get(name, {}))  # seed new files only
            row = {"eml_filename": name}
            row.update({h: prev.get(h, "")
                        for h in config.METADATA_HEADERS if h != "eml_filename"})
            writer.writerow(row)


def get_metadata_value(base_dir, filename, field):
    """
    Return the stored value of `field` for `filename`, or None if the file has
    no metadata row. Raises KeyError if the field name is not a known column.

    Example:
        get_metadata_value("/g", "2026-06-03-x.eml", "next_action")
        # -> "Reply to Jane"
    """
    if field not in READABLE_FIELDS:
        raise KeyError(field)
    row = load_metadata(base_dir).get(filename)
    if row is None:
        return None
    return row.get(field, "")


def set_metadata_value(base_dir, filename, field, value):
    """
    Set `field` to `value` for `filename` and rewrite metadata.csv. Performs a
    full sync first (so any new/removed EML files are reconciled) and preserves
    every other field. Raises KeyError for an unknown/uneditable field, and
    FileNotFoundError if `filename` is not present anywhere in the workflow.

    Example:
        set_metadata_value("/g", "2026-06-03-x.eml", "next_action", "Do it")
        # -> writes the value, returns None
    """
    if field not in EDITABLE_FIELDS:
        raise KeyError(field)
    if filename not in fs.all_existing_filenames(base_dir):
        raise FileNotFoundError(filename)

    # Reconcile the CSV with what's on disk, then apply the single edit on top.
    sync_metadata(base_dir)
    rows = load_metadata(base_dir)
    rows.setdefault(filename, {h: "" for h in READABLE_FIELDS})[field] = value

    meta_path = os.path.join(base_dir, config.METADATA_FILE)
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.METADATA_HEADERS)
        writer.writeheader()
        for name in sorted(rows):
            row = {"eml_filename": name}
            row.update({h: rows[name].get(h, "") for h in READABLE_FIELDS})
            writer.writerow(row)

"""
Data export: turn the emails currently in the workflow into other data formats.

The first (and currently only) format is `masterdetail_yaml`: a single YAML
(.yml) document that conforms to the master-detail viewer SPEC
(https://github.com/blairwang-online/qdvc-masterdetail-viewer/blob/main/SPEC.md).
That spec requires the document to be a top-level *sequence* of items, where each
item is a mapping carrying a reserved `title` field (the heading) plus arbitrary
other fields. We emit one item per email, in the same order the report walks the
folders (triage → actionable → delegated → reference → archive), oldest → newest
within each folder, so an export mirrors what `gtd list` shows.

Scalars are stringified the SPEC's way at serialization time — in particular the
email date is written as a plain ISO 8601 string (not a YAML native date) so no
language-specific temporal form can leak into a downstream renderer (SPEC §7.1).
"""

import os

from . import config, emailutil, fs
from .report import parse_flags

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

# The folders to export, in report order (triage first, archive last). 01-input
# is deliberately excluded: those files have not been ingested/renamed yet, so
# they are not part of the tracked dataset `gtd list` reports on.
EXPORT_FOLDERS = [
    config.TRIAGE_DIR,
    config.ACTIONABLE_DIR,
    config.DELEGATED_DIR,
    config.REFERENCE_DIR,
    config.ARCHIVE_DIR,
]


def build_item(base_dir, folder, filename, metadata=None, accounts=None):
    """
    Build one master-detail item (an ordered dict) for a single email. The
    reserved `title` is the email subject; the remaining fields are inserted in
    a stable, human-sensible order. Empty/absent fields are omitted entirely so
    the exported document stays uncluttered (SPEC allows any field set; there
    are no required fields beyond `title`).

    `metadata` is the dict from metadata.load_metadata (keyed by filename);
    `accounts` is the my_own_accounts list used to label the receiving account.

    Example:
        build_item("/home/me/gtd", "03-actionable", "2026-06-03-x.eml",
                   metadata=meta, accounts=accts)
        # -> {"title": "Project Pudding", "folder": "03-actionable",
        #     "date": "2026-06-03", "filename": "2026-06-03-x.eml",
        #     "correspondents": ["Jane Doe <jane@x.com>"],
        #     "project": "Pudding", "next_action": "Reply to Jane"}
    """
    metadata = metadata or {}
    meta = metadata.get(filename, {})

    path = os.path.join(base_dir, folder, filename)
    message = emailutil.read_eml_message(path)
    subject = emailutil.get_email_subject(message) or "(no subject)"
    date_dt = emailutil.get_email_date(message)
    correspondents = emailutil.get_email_correspondents(
        message, exclude=[a["email_address"] for a in (accounts or [])])
    own_account = emailutil.match_own_account(message, accounts)
    attachments = emailutil.list_attachments(message)

    # Insertion order is preserved on output (SPEC §3.4), so build the mapping in
    # the order we want the detail view to read. `title` must come first.
    item = {"title": subject, "folder": folder}
    # Plain ISO 8601 date string, NOT a native date, per SPEC §7.1.
    item["date"] = date_dt.strftime("%Y-%m-%d")
    item["filename"] = filename
    if correspondents:
        item["correspondents"] = correspondents
    if own_account:
        item["received_by"] = own_account["display_name"]
    if attachments:
        item["attachments"] = attachments

    # Annotations from metadata.csv — include each only when it carries a value.
    for field in ("project", "next_action", "general_notes", "message_ref"):
        value = (meta.get(field) or "").strip()
        if value:
            item[field] = value
    flags = sorted(parse_flags(meta.get("flags", "")))
    if flags:
        item["flags"] = flags

    return item


def build_export(base_dir, metadata=None, accounts=None):
    """
    Build the full master-detail document: a list of items (one per email)
    across all exported folders, in report order (triage → actionable →
    delegated → reference → archive; oldest → newest within each folder, by
    email date). An email that cannot be read is skipped with a placeholder
    item so a single bad file never aborts the whole export.

    Example:
        build_export("/home/me/gtd", metadata=meta, accounts=accts)
        # -> [{"title": "...", ...}, {"title": "...", ...}, ...]
    """
    items = []
    for folder in EXPORT_FOLDERS:
        names = fs.list_eml_files(base_dir, folder)
        dated = []
        for name in names:
            try:
                path = os.path.join(base_dir, folder, name)
                date_dt = emailutil.get_email_date(
                    emailutil.read_eml_message(path))
                dated.append((date_dt, name))
            except Exception:
                # Unreadable: sort it to the front so it is still emitted.
                dated.append((None, name))
        # oldest -> newest; unreadable (None date) first.
        dated.sort(key=lambda t: (t[0] is not None, t[0]))
        for _, name in dated:
            try:
                items.append(build_item(base_dir, folder, name,
                                         metadata=metadata, accounts=accounts))
            except Exception as e:
                items.append({"title": f"(could not read {name})",
                              "folder": folder, "filename": name,
                              "error": str(e)})
    return items


def dump_masterdetail_yaml(items, out_path):
    """
    Serialise the master-detail item list to a YAML (.yml) file conforming to
    the viewer SPEC: a top-level block sequence of mappings, keys in insertion
    order (sort_keys=False), Unicode preserved. All scalars have already been
    stringified per SPEC §7.1 in build_item, so PyYAML never sees a native date.
    Returns the number of items written.

    Example:
        dump_masterdetail_yaml(items, "/home/me/gtd/export-masterdetail.yml")
        # -> writes the file, returns len(items)
    """
    if yaml is None:
        raise RuntimeError(
            "export to YAML needs PyYAML, which is not installed. "
            "Install it with: pip install pyyaml"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(items, f, sort_keys=False, allow_unicode=True,
                       default_flow_style=False)
    return len(items)

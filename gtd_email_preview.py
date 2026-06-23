#!/usr/bin/env python3
"""
gtd_email_preview.py — preview a single EML file from the GTD workflow.

Usage:
    gtd_email_preview.py 2026-06-03-project-pudding.eml
    gtd_email_preview.py 2026-06-03-project-pudding.eml | less -R

Locates the file across the 5 GTD folders (based on working_directory in
gtd.py.ini), prints the key headers, lists any attachments, and renders the
text body (decoding base64 / quoted-printable as needed).
"""

import configparser
import os
import re
import sys
from email import message_from_binary_file
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime

# --------------------------------------------------------------------------- #
# Configuration (kept consistent with gtd.py)
# --------------------------------------------------------------------------- #
# gtd.py reads its settings from "gtd.py.ini"; we read the same file so the two
# tools share one working_directory.
COMPANION_INI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gtd.py.ini"
)
DEFAULT_WORKING_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gtd-eml"
)
GTD_FOLDERS = ["01-input", "02-triage", "03-actionable", "04-reference", "05-archive"]


def load_working_directory(ini_path=COMPANION_INI):
    """
    Read working_directory from the [settings] section of gtd.py.ini, falling
    back to the default if absent.

    Example:
        load_working_directory("/path/gtd.py.ini")
        # -> "/home/james/gtd-eml-data"
    """
    parser = configparser.ConfigParser()
    if os.path.isfile(ini_path):
        parser.read(ini_path, encoding="utf-8")
        if parser.has_section("settings") and "working_directory" in parser["settings"]:
            raw = parser["settings"]["working_directory"].strip().strip('"').strip("'")
            if raw:
                return raw
    return DEFAULT_WORKING_DIRECTORY


def find_eml(base_dir, filename):
    """
    Search the 5 GTD folders for an .eml file and return its full path, or None.
    A ".eml" extension is appended if the user omitted it.

    Example:
        find_eml("/home/me/gtd-eml", "2026-06-03-project-pudding.eml")
        # -> "/home/me/gtd-eml/03-actionable/2026-06-03-project-pudding.eml"
    """
    if not filename.lower().endswith(".eml"):
        filename += ".eml"
    for folder in GTD_FOLDERS:
        candidate = os.path.join(base_dir, folder, filename)
        if os.path.isfile(candidate):
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Header helpers
# --------------------------------------------------------------------------- #
def decode_mime(raw):
    """
    Decode a possibly MIME-encoded header value into a plain string.

    Example:
        decode_mime("=?utf-8?q?Z=C3=B6e?=")  # -> "Zöe"
    """
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw.strip()


def format_addresses(message, header):
    """
    Return a decoded, comma-joined string of all addresses in a header (handles
    repeated headers and grouped lists). Empty string if the header is absent.

    Example:
        format_addresses(msg, "To")
        # To: "Bob <bob@x.com>, carol@y.com"
        # -> "Bob <bob@x.com>, carol@y.com"
    """
    raw_values = message.get_all(header, [])
    if not raw_values:
        return ""
    parts = []
    for name, addr in getaddresses(raw_values):
        name = decode_mime(name)
        if name and addr:
            parts.append(f"{name} <{addr}>")
        elif addr:
            parts.append(addr)
        elif name:
            parts.append(name)
    return ", ".join(parts)


def format_date(message):
    """
    Return the Date header reformatted as "YYYY-MM-DD HH:MM" (local-ish, as
    given), or the raw value if it can't be parsed, or "" if absent.

    Example:
        format_date(msg)  # Date: "Wed, 03 Jun 2026 09:15:00 +0000"
        # -> "2026-06-03 09:15"
    """
    raw = message.get("Date", "")
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return raw.strip()


# --------------------------------------------------------------------------- #
# Body / attachment helpers
# --------------------------------------------------------------------------- #
def is_attachment(part):
    """
    Decide whether a MIME part is an attachment (vs inline body).

    Example:
        is_attachment(part)  # Content-Disposition: attachment; filename=...
        # -> True
    """
    disposition = (part.get("Content-Disposition") or "").lower()
    if "attachment" in disposition:
        return True
    # A named part that isn't plain/html body text counts as an attachment.
    if part.get_filename():
        return True
    return False


def list_attachments(message):
    """
    Return decoded filenames of all attachment parts.

    Example:
        list_attachments(msg)  # -> ["report.pdf", "image.png"]
    """
    names = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            if is_attachment(part):
                fname = part.get_filename()
                names.append(decode_mime(fname) if fname else "(unnamed attachment)")
    return names


def decode_part_text(part):
    """
    Decode a single MIME part's payload to text, honouring its transfer
    encoding (base64, quoted-printable, etc.) and declared charset.

    Example:
        decode_part_text(part)  # base64 payload "SGk=" -> "Hi"
    """
    payload = part.get_payload(decode=True)  # handles base64 / quoted-printable
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def strip_html(html):
    """
    Crudely convert HTML to readable plain text (used only when no text/plain
    part exists).

    Example:
        strip_html("<p>Hi <b>Jane</b></p>")  # -> "Hi Jane"
    """
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse excess blank lines and decode a few common entities.
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                    ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(ent, ch)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_body(message):
    """
    Return the best plain-text body: prefer text/plain, else convert text/html.
    Decodes base64/quoted-printable transparently. For non-multipart messages,
    decodes the single payload directly.

    Example:
        extract_body(msg)  # -> "Hi Jane,\\n\\nThanks for the update..."
    """
    if not message.is_multipart():
        text = decode_part_text(message)
        if message.get_content_type() == "text/html":
            return strip_html(text)
        return text

    plain, html = None, None
    for part in message.walk():
        if part.is_multipart() or is_attachment(part):
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and plain is None:
            plain = decode_part_text(part)
        elif ctype == "text/html" and html is None:
            html = decode_part_text(part)

    if plain is not None and plain.strip():
        return plain
    if html is not None and html.strip():
        return strip_html(html)
    return ""


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(message, path):
    """
    Print the formatted preview (headers, attachments, body) to stdout.

    Example:
        render(msg, "/home/me/gtd-eml/02-triage/x.eml")
        # -> prints "From: ...", "Date: ...", ..., body
    """
    folder = os.path.basename(os.path.dirname(path))
    print(f"# {os.path.basename(path)}   [{folder}]")
    print()
    print("```")

    always_show = {"From", "Date", "Subject"}
    for label, header in (("From", "From"), ("Date", None),
                          ("To", "To"), ("CC", "Cc"), ("BCC", "Bcc"),
                          ("Subject", "Subject")):
        if label == "Date":
            value = format_date(message)
        elif header == "Subject":
            value = decode_mime(message.get("Subject", ""))
        else:
            value = format_addresses(message, header)
        if not value and label not in always_show:
            continue
        print(f"{label + ':':<8} {value}")

    attachments = list_attachments(message)
    if attachments:
        joiner = "\n" + " " * 9
        print(f"{'Attached:':<8} " + joiner.join(attachments))

    print("```")
    print()
    body = extract_body(message)
    print(body if body.strip() else "(no text body)")


def main(argv):
    """
    Entry point: validate args, locate the file, render it.

    Example:
        main(["2026-06-03-project-pudding.eml"])  # -> prints preview, returns 0
    """
    if len(argv) != 1:
        print("usage: gtd_email_preview.py <filename.eml>", file=sys.stderr)
        return 2

    base_dir = load_working_directory()
    path = find_eml(base_dir, argv[0])
    if path is None:
        print(f"error: '{argv[0]}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1

    with open(path, "rb") as f:
        message = message_from_binary_file(f)
    render(message, path)
    return 0


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

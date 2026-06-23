"""
Single-message preview rendering for gtd_email_preview.py: a markdown-friendly
layout (H1 title, fenced header block, body) suitable for piping into `glow`
or `less`.
"""

import os

from . import emailutil


def render(message, path):
    """
    Print the formatted preview (headers, attachments, body) to stdout. Output
    is markdown-friendly: an H1 title, a fenced code block of headers, then the
    body as plain markdown.

    Example:
        render(msg, "/home/me/gtd-eml/02-triage/x.eml")
        # -> prints "# x.eml ...", fenced headers, then the body
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
            value = emailutil.format_date(message)
        elif header == "Subject":
            value = emailutil.get_email_subject(message)
        else:
            value = emailutil.format_addresses(message, header)
        if not value and label not in always_show:
            continue
        print(f"{label + ':':<8} {value}")

    attachments = emailutil.list_attachments(message)
    if attachments:
        joiner = "\n" + " " * 9
        print(f"{'Attached:':<8} " + joiner.join(attachments))

    print("```")
    print()
    body = emailutil.get_email_body_text(message, render_html=True)
    print(body if body.strip() else "(no text body)")

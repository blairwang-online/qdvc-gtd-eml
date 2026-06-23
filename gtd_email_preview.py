#!/usr/bin/env python3
"""
gtd_email_preview.py — preview a single EML file from the GTD workflow.

Usage:
    gtd_email_preview.py 2026-06-03-project-pudding.eml
    gtd_email_preview.py 2026-06-03-project-pudding.eml | less
    gtd_email_preview.py 2026-06-03-project-pudding.eml | glow -

Locates the file across the 5 GTD folders (based on working_directory in
config.yml), prints the key headers, lists any attachments, and renders the
text body (decoding base64 / quoted-printable as needed). Output is
markdown-friendly.

Implementation lives in the gtd_modules package; this file just wires it
together.
"""

import os
import sys

from gtd_modules.config import load_config
from gtd_modules.emailutil import read_eml_message
from gtd_modules.fs import find_eml
from gtd_modules.preview import render


def main(argv):
    """
    Entry point: validate args, locate the file, render it.

    Example:
        main(["2026-06-03-project-pudding.eml"])  # -> prints preview, returns 0
    """
    if len(argv) != 1:
        print("usage: gtd_email_preview.py <filename.eml>", file=sys.stderr)
        return 2

    base_dir = load_config()["working_directory"]
    path = find_eml(base_dir, argv[0])
    if path is None:
        print(f"error: '{argv[0]}' not found in any GTD folder under {base_dir}",
              file=sys.stderr)
        return 1

    render(read_eml_message(path), path)
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

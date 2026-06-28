"""
`export` subcommand: export the tracked emails to another data format. The only
format implemented so far is `masterdetail_yaml`, which writes a single YAML
(.yml) file conforming to the master-detail viewer SPEC.
"""

import os
import sys

from .. import config as cfg_mod
from .. import export as export_mod
from .. import fs
from ..metadata import load_metadata, sync_metadata

# format name -> (file extension, default output basename, builder/dumper).
# Adding a new format is: write a dump_* in export.py and register it here.
FORMATS = {
    "masterdetail_yaml": {
        "ext": ".yml",
        "default_basename": "export-masterdetail",
        "dump": export_mod.dump_masterdetail_yaml,
    },
}


def cmd_export(argv):
    """
    `gtd.py export <format> [output-file]` — export all tracked emails (the same
    set `gtd.py list` reports on: triage, actionable, delegated, reference,
    archive) to another data format.

    Currently the only format is `masterdetail_yaml`, which writes a single
    YAML document conforming to the master-detail viewer SPEC. With no output
    file, it writes `<working_directory>/export-masterdetail.yml`; give a path
    to write elsewhere (a `.yml` extension is appended if you omit one).

    Read-only with respect to the workflow: it reconciles `metadata.csv` with
    what is on disk (so projects, next actions, flags are current) but does NOT
    ingest `01-input` or move any email.

    Example:
        cmd_export(["masterdetail_yaml"])               # -> writes the default .yml
        cmd_export(["masterdetail_yaml", "out.yml"])    # -> writes ./out.yml
    """
    if not argv:
        print("usage: gtd.py export <format> [output-file]", file=sys.stderr)
        print("       formats: " + ", ".join(sorted(FORMATS)), file=sys.stderr)
        return 2
    if len(argv) > 2:
        print("usage: gtd.py export <format> [output-file]", file=sys.stderr)
        return 2

    fmt_name = argv[0]
    fmt = FORMATS.get(fmt_name)
    if fmt is None:
        print(f"error: unknown export format '{fmt_name}'", file=sys.stderr)
        print("       choose one of: " + ", ".join(sorted(FORMATS)),
              file=sys.stderr)
        return 2

    cfg = cfg_mod.load_config()
    base_dir = cfg["working_directory"]

    if len(argv) == 2:
        out_path = argv[1]
        if not out_path.lower().endswith(fmt["ext"]):
            out_path += fmt["ext"]
    else:
        out_path = os.path.join(base_dir,
                                fmt["default_basename"] + fmt["ext"])

    fs.ensure_folders(base_dir)
    sync_metadata(base_dir)
    metadata = load_metadata(base_dir)

    items = export_mod.build_export(base_dir, metadata=metadata,
                                    accounts=cfg["my_own_accounts"])
    try:
        n = fmt["dump"](items, out_path)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Exported {n} email{'s' if n != 1 else ''} "
          f"({fmt_name}) -> {out_path}")
    return 0

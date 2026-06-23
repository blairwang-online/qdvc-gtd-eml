# qdvc-gtd-eml

A **quick-and-dirty vibe-coded ("QDVC")** command-line toolkit for running a [Getting Things Done](https://gettingthingsdone.com/)
workflow over plain `.eml` email files. Export emails you want to act on, drop
them in a folder, and let the tool file and track them.

## How it works

You export emails as `.eml` files into `01-input/`. Running `gtd.py`:

- **renames** each new file to `yyyy-mm-dd-brief-description.eml` (derived from
  the date and subject), then moves it to `02-triage/`;
- prints a **status report** of what's in each folder, colour-coded by age, with
  correspondents and your next action.

You then manually move each triaged file into `03-actionable/`, `04-reference/`,
or `05-archive/`. Annotations (notes, project, next action) live in a
`metadata.csv` the tool keeps in sync.

```
01-input  →  02-triage  →  03-actionable
                        ↘  04-reference
                        ↘  05-archive
```

## Usage

```bash
python gtd.py                              # ingest new files + print the report
python gtd_email_preview.py <file.eml>     # preview one email (headers + body)
```

Page through a long report with colours and scrolling:

```bash
FORCE_COLOR=1 python gtd.py | less -R
```

The preview is markdown-friendly, so it also pipes nicely into
[`glow`](https://github.com/charmbracelet/glow).

## Configuration

Settings live in `config.yml` next to the scripts:

```yaml
working_directory: "/home/james/gtd-eml-data"   # where the folders + metadata.csv live
archive_report_n: 10            # how many recent archive items to show
green_max_days: 2               # report colour thresholds (age in days)
yellow_max_days: 14
my_own_accounts:                # your addresses: excluded from "correspondents",
  - email_address: james.smith@example.com   # and labelled when they receive mail
    display_name: "Work account"
    colour: yellow
```

Every key is optional and has a sensible default.

## Requirements

- Python 3.8+
- [PyYAML](https://pypi.org/project/PyYAML/) (`pip install pyyaml`) — only if you
  use a `config.yml`

## Maintainers

See [MAINTENANCE.md](MAINTENANCE.md) for the module layout, dependency graph, and
the conventions to preserve when editing.

## Acknowledgements

This codebase was vibe-coded with assistance from Claude Opus 4.8 High. The full
conversation behind it is preserved in
[vibe-coding/2026-06-23-conversation-with-claude.md](vibe-coding/2026-06-23-conversation-with-claude.md).

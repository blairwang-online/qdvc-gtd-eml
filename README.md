# qdvc-gtd-eml

A **quick-and-dirty vibe-coded ("QDVC")** command-line toolkit for running a [Getting Things Done](https://gettingthingsdone.com/)
workflow over plain `.eml` email files. Export emails you want to act on, drop
them in a folder, and let the tool file and track them.

## How it works

You export emails as `.eml` files into `01-input/`. Running `gtd.py list`:

- **renames** each new file to `yyyy-mm-dd-brief-description.eml` (derived from
  the date and subject), then moves it to `02-triage/`;
- prints a **status report** of what's in each folder, colour-coded by age, with
  correspondents and your next action.

You then file each triaged email into `03-actionable/`, `04-delegated/`,
`05-reference/`, or `06-archive/` — either by hand or with `gtd.py alloc`.
Annotations (notes, project, next action) live in a `metadata.csv` the tool
keeps in sync.

```
01-input  →  02-triage  →  03-actionable
                        ↘  04-delegated
                        ↘  05-reference
                        ↘  06-archive
```

## Usage

```bash
python gtd.py list                       # ingest new files + print the report
python gtd.py list <folder>              # show just one folder (e.g. actionable)
python gtd.py stats                      # count emails in each folder
python gtd.py view <file.eml>            # preview one email (headers + body)
python gtd.py alloc <file.eml> <dest>    # move an email to another folder
python gtd.py metadata <file.eml> ...    # get/set a metadata.csv field
python gtd.py help                       # full command overview
```

`alloc`'s destination is a short name (`actionable`, `delegated`, `reference`,
`archive`, `triage`, `input`) or the full folder name (e.g. `04-delegated`).

`metadata` reads or writes one field for an email:

```bash
python gtd.py metadata <file.eml> get next_action
python gtd.py metadata <file.eml> set next_action = "Reply by Friday"
```

Editable fields: `general_notes`, `project`, `next_action`, `flags`
(`message_ref` is read-only).

Page through a long report with colours and scrolling:

```bash
FORCE_COLOR=1 python gtd.py list | less -R
```

`view` output is markdown-friendly, so it also pipes nicely into
[`glow`](https://github.com/charmbracelet/glow):

```bash
python gtd.py view <file.eml> | glow -
```

## Shell completion

If you use **zsh with [oh-my-zsh](https://ohmyz.sh/)**, there's a Tab-completion
script for the `gtd` command (subcommands, `.eml` filenames, metadata fields,
and `alloc` destinations). See
[`misc/shell_completion.md`](misc/shell_completion.md) for setup.

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
[`vibe-coding/2026-06-23-conversation-with-claude.md`](vibe-coding/2026-06-23-conversation-with-claude.md).

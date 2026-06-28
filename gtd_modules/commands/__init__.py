"""
Subcommand implementations for the `gtd.py` CLI, one module per command:

    list.py      -> cmd_list
    export.py    -> cmd_export
    stats.py     -> cmd_stats
    view.py      -> cmd_view
    alloc.py     -> cmd_alloc
    search.py    -> cmd_search
    close.py     -> cmd_close
    pin.py       -> cmd_pin, cmd_unpin (+ the shared _toggle_flag helper)
    metadata.py  -> cmd_metadata
    help.py      -> cmd_help (+ HELP_TEXT)

Each handler takes the post-command argv list and returns a process exit code
(0 = success). This package re-exports every handler (and HELP_TEXT) at the top
level, so callers can keep using `from gtd_modules import commands` and then
`commands.cmd_list`, `commands.HELP_TEXT`, etc. `gtd.py` itself is just an
argument dispatcher; the real work lives in these modules.
"""

from .alloc import cmd_alloc
from .close import cmd_close
from .export import cmd_export
from .help import HELP_TEXT, cmd_help
from .list import cmd_list
from .metadata import cmd_metadata
from .pin import cmd_pin, cmd_unpin
from .search import cmd_search
from .stats import cmd_stats
from .view import cmd_view

__all__ = [
    "cmd_list",
    "cmd_export",
    "cmd_stats",
    "cmd_view",
    "cmd_alloc",
    "cmd_search",
    "cmd_close",
    "cmd_pin",
    "cmd_unpin",
    "cmd_metadata",
    "cmd_help",
    "HELP_TEXT",
]

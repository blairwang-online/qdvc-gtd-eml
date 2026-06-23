#!/usr/bin/env bash
#
# gtd — convenience wrapper around gtd.py and gtd_email_preview.py
#
# Subcommands:
#   gtd list            Show the status report, paged with colour:
#                         FORCE_COLOR=1 python3 .../gtd.py | less -R
#   gtd view <file.eml> Preview a single email:
#                         python3 .../gtd_email_preview.py <file.eml>
#
# Installation:
#   Place this script next to gtd.py and gtd_email_preview.py (it locates them
#   relative to its own path), make it executable (chmod +x gtd), and either put
#   its directory on PATH or alias it from ~/.zshrc, e.g.:
#       alias gtd="/path/to/gtd"
#
set -euo pipefail

# Directory containing this script (and, by assumption, the two Python files),
# resolving symlinks so an aliased/symlinked `gtd` still finds them.
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

GTD_PY="$SCRIPT_DIR/gtd.py"
PREVIEW_PY="$SCRIPT_DIR/gtd_email_preview.py"

# Python interpreter: honour $PYTHON if set, else python3.
PYTHON="${PYTHON:-python3}"

usage() {
    cat >&2 <<EOF
usage: gtd <command> [args]

commands:
  list                 Show the status report, paged with colour (| less -R)
  view <file.eml>      Preview a single email

examples:
  gtd list
  gtd view 2026-06-03-project-pudding.eml
EOF
}

# Fail early with a clear message if a required script is missing.
require_file() {
    if [ ! -f "$1" ]; then
        echo "gtd: cannot find $(basename "$1") at $1" >&2
        echo "gtd: this wrapper must sit next to gtd.py and gtd_email_preview.py" >&2
        exit 1
    fi
}

cmd="${1:-}"
case "$cmd" in
    list)
        shift
        require_file "$GTD_PY"
        # FORCE_COLOR keeps colour on through the pipe; -R lets less render it.
        # -F: don't page if it fits on one screen; -X: leave output on screen.
        FORCE_COLOR=1 "$PYTHON" "$GTD_PY" "$@" | less -RFX
        ;;
    view)
        shift
        if [ $# -eq 0 ]; then
            echo "gtd: 'view' needs a filename, e.g. gtd view 2026-06-03-foo.eml" >&2
            exit 2
        fi
        require_file "$PREVIEW_PY"
        "$PYTHON" "$PREVIEW_PY" "$@"
        ;;
    -h|--help|help|"")
        usage
        [ -z "$cmd" ] && exit 2 || exit 0
        ;;
    *)
        echo "gtd: unknown command '$cmd'" >&2
        usage
        exit 2
        ;;
esac

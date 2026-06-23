# Shell completion setup (`gtd`) — zsh + oh-my-zsh

This folder contains `_gtd`, a zsh completion script for the `gtd` command. Once
installed, pressing <kbd>Tab</kbd> completes subcommands, `.eml` filenames,
metadata field names, and `alloc` destinations:

```
gtd me<Tab>            → gtd metadata
gtd metadata <Tab>     → lists your .eml files
gtd alloc foo.eml <Tab>→ actionable delegated reference archive triage input
```

These instructions assume **zsh with oh-my-zsh**.

---

## 1. Make `gtd` a shell function (not an alias)

This is the step that actually makes completion work. zsh expands *aliases*
before completing, so an `alias gtd=...` is completed as `python3` / `gtd.py`
and the completion script is ignored. A **function** is its own command word, so
completion sees `gtd` and uses `_gtd`.

In `~/.zshrc`, remove any existing alias:

```zsh
# DELETE this line if present:
# alias gtd="python3 /path/to/gtd.py"
```

and add a function in its place (point the path at your actual `gtd.py`):

```zsh
gtd() { python3 /path/to/gtd.py "$@" }
```

> If you'd rather keep an alias, you instead need `setopt complete_aliases` in
> `~/.zshrc` — but that's global and changes completion behaviour for *all* your
> aliases, so the function is the cleaner choice.

---

## 2. Install the completion file

oh-my-zsh automatically adds `~/.oh-my-zsh/custom/completions` to `fpath`
*before* it initialises completions, so dropping `_gtd` there is all that's
needed — no extra `fpath`/`compinit` lines.

From this folder:

```zsh
mkdir -p ~/.oh-my-zsh/custom/completions
cp misc/_gtd ~/.oh-my-zsh/custom/completions/_gtd
```

The file **must** be named exactly `_gtd` (leading underscore, no extension).

---

## 3. Clear the completion cache and restart

oh-my-zsh caches the completion index in `~/.zcompdump`, so a freshly added file
won't be picked up until that's refreshed:

```zsh
rm -f ~/.zcompdump*
exec zsh
```

---

## 4. Verify

```zsh
print ${_comps[gtd]}
```

- Prints `_gtd` → installed correctly. Try `gtd me<Tab>`.
- Prints nothing → see Troubleshooting below.

---

## How it finds your emails

For filename completion (`gtd view <Tab>`, `gtd alloc <Tab>`,
`gtd metadata <Tab>`), `_gtd` locates your `gtd.py` from the `gtd` function (or
alias) definition, reads `working_directory` out of the adjacent `config.yml`,
and lists the `.eml` files across the workflow folders. Subcommand completion
(`gtd me<Tab>`) works regardless of any of that.

---

## Troubleshooting

**`print ${_comps[gtd]}` prints nothing.**
The file isn't being loaded. Confirm it's at
`~/.oh-my-zsh/custom/completions/_gtd` (exact name), then
`rm -f ~/.zcompdump* && exec zsh`. If you keep oh-my-zsh's completions in a
non-default `$ZSH_CUSTOM`, use `$ZSH_CUSTOM/completions` instead.

**`print ${_comps[gtd]}` prints `_gtd`, but `gtd <Tab>` does nothing / lists
plain files.**
`gtd` is still an alias, so it's being expanded before completion. Check with
`type gtd` — it should say "gtd is a shell function". If it says "alias",
revisit Step 1 (and remember to `exec zsh`).

**A "zsh compinit: insecure directories" warning appears.**
Fix the permissions oh-my-zsh is complaining about:

```zsh
compaudit | xargs chmod g-w,o-w
```

**Diagnose what completion is actually doing.**
Type `gtd me` then press <kbd>Ctrl-X</kbd> <kbd>h</kbd>. The reported context
should mention `:complete:gtd:` — if it mentions `gtd.py` or `python3`, `gtd` is
still being treated as an alias (Step 1).

# Contributing

Everything needed to make a change to this repository and have it accepted by its own
checks.

## Setup

```bash
yay -S ruff
helper/hooks/enable
```

`helper/hooks/enable` arms the pre-commit gate for your clone. Git keeps hook configuration
out of version control on purpose — cloning a repository must never run code its author
chose — so a fresh clone starts with the gate off and nothing says so. `install.py` runs
this for you; a clone made only to edit needs the command.

## The Gate

Two checks run on every commit and refuse it if either fails:

```bash
ruff check .                    # lint and type-annotation enforcement
python helper/gendocs.py        # regenerate the marker blocks in the docs
python helper/gendocs.py --check   # ...or just fail if they are stale
```

`gendocs.py` does more than regenerate: it refuses to run while a structural rule is
broken — a non-widget under `configuration/qtile/widgets/`, a module named in
`docs/dependencies.md` that does not resolve, an import with no Arch package recorded. The
error names the offending file and what to do about it.

Both run against the working tree rather than the staged snapshot, because qtile loads its
configuration live from this tree: a clean tree is the property worth defending, not a clean
diff. `git commit --no-verify` bypasses them for one commit.

This is a git hook rather than a CI workflow by choice. The working copy *is* the running
desktop, so the moment worth catching a broken tree is before the commit, on the machine —
not minutes later in a hosted runner. It also keeps the checks runnable with nothing but a
clone and `ruff`.

Lint configuration lives in `pyproject.toml`, which holds tool configuration and nothing
else. Prefer fixing a finding to suppressing it; where a rule genuinely cannot be satisfied,
add a per-file entry under `[tool.ruff.lint.per-file-ignores]` with the reason, rather than
an inline `# noqa`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org): `type(scope): summary`, where
the scope is the component touched.

```
fix(qtile/audio): reopen the stream after a device disappears
refactor(helper): one module per patched application
docs: one word for the palette
```

Explain in the body why the change is right, not what the diff already shows.

## Where the Conventions Live

Each component documents its own, next to the code it governs:

| Adding a… | Read |
|---|---|
| qtile widget | [configuration/qtile/widgets/README.md](configuration/qtile/widgets/README.md) |
| per-app patcher | [helper/README.md](helper/README.md) |
| document | [docs/style.md](docs/style.md) |

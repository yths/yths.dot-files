# Tests

The pure logic: functions that take values and return values, with no X server, no Redis, no
sound card and no filesystem beyond a temporary directory. That is most of what this
repository gets wrong, and all of what can be checked without a running desktop.

```bash
pytest                    # from the repository root
pytest tests/test_state.py -v
```

`helper/hooks/pre-commit` runs them alongside `ruff` and `gendocs.py`, so a commit that
breaks one is refused.

## What Is Covered

One file per module under test, named for it. Every test here guards a defect that actually
occurred — the glyph ramp that skipped a block, the state key rename that would have
silently stopped the theme switch, the monitor average that divided by zero and truncated
`~/.Xresources` on the way. The comment above each names the failure it prevents, because a
test whose purpose is not obvious gets deleted the first time it is inconvenient.

## What Is Not

Anything needing a desktop: widget rendering, the patchers' file output, the installer's
symlinks, plymouth's images. Those were verified in the session that wrote them, by scripts
that compared old and new output and were then thrown away. Bringing them here means
fixtures for a home directory, a Redis and a palette — worth doing, and a larger job than
this.

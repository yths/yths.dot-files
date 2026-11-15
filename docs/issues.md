# Issues

Open work only. An item is deleted when it is done; the commit that closes it says how, and
`git log -- docs/issues.md` keeps every entry that was ever here.

## Themes

- [ ] `yths.themes` still writes `palette.pkl`
    - (2026-11-15) bundles here now carry `palette.json`: unpickling a file another tool drops
      into `assets/` runs whatever code it holds, so the pickle was a trust boundary rather
      than the trusted local artifact the `S301` suppression claimed. The generator's export
      and its contract test have to switch to `palette.json` too; until then, each fresh export
      converts with `python helper/convert_palette.py assets/<name>`, which refuses any pickle
      holding more than plain data.

- [ ] `yths.themes` does not emit the `symbols` and `strings` blocks
    - (2026-09-19) the bundle manifest gained two optional keys, and the generator writes
      neither, so every exported bundle currently falls back to the ASCII vocabulary. That is
      the designed behaviour rather than a break — a bundle that omits both gets a desktop
      that renders without a Nerd Font — but it means a generated theme cannot yet ship its
      own icons the way the tracked `assets/default/` does.
    - (2026-09-19) `docs/notes.md` says a schema change lands in both repositories at once,
      and this is the half that did not. The contract to mirror is in `docs/symbols.md`:
      the key vocabulary is closed, values are a string or a ramp of a declared length, and
      an override is partial. `helper/symbols.py` holds the list; `gendocs.py` already
      refuses a bundle here that overrides a key nothing declares, so the generator emitting
      an unknown key fails the gate on this side rather than silently doing nothing.
    - (2026-10-04) the same holds for `bluetooth_devices`, the optional MAC-to-icon map the
      bar's bluetooth widget reads (`docs/config-schema.md`). It is per-user data rather than
      design, so the generator may reasonably leave it to whoever owns the devices — but the
      contract should say so on both sides.

## Configurations

- [ ] Delete the legacy `state` translation in `configuration/qtile/shared/state.py`
    - (2026-08-29) `state.mode` became `state.theme_mode`, and `audio_mode`'s `"auto"` became
      `"automatic"`. `LEGACY_STATE_KEYS` and `LEGACY_MODE_VALUES` translate an older
      `~/.config/config.json` on read and the next write persists the new form. Remove both,
      and the note in `docs/config-schema.md`, once no machine runs a file written before.

- [ ] The lock screen's password field reads as a graphics artefact
    - (2026-11-13) this concerns the field's appearance while entering a password, not stale
      text after a message transition. The renderer patch fixes the latter while preserving
      the existing 32-character cursor feedback.
    - (2026-09-26) `XSECURELOCK_PASSWORD_PROMPT=cursor` draws a 32-character row of
      underscores with a cursor jumping around inside it. Underscores are contiguous glyphs, so
      the row is an unbroken line at any size, and on 4K — doubly so on HDMI-0, downscaled 2:1
      by `.xinitrc` — it reads as a solid grey bar rather than as a text field.
    - (2026-09-26) not fixable by configuration: the 32 is hardcoded in xsecurelock's
      `auth_x11`, which exposes no width option. The levers are a different prompt mode,
      a patched build, or accepting it. `time` is the interesting alternative — upstream calls
      it the most secure mode, it keeps the keystroke feedback `cursor` was chosen for, and it
      is short enough not to form a bar — but it is a bare epoch timestamp, which is its own
      kind of odd. Left to a decision rather than changed unilaterally.

- [ ] The `inhibit-bridge` tray icon does not render (needs a `dbus-fast` fix)
    - (2026-09-08) the bridge itself works: it holds `org.freedesktop.ScreenSaver` and opens a matching logind idle inhibitor for each inhibit taken, verified end to end with `systemd-inhibit --list`. Only the indicator is missing.
    - (2026-09-08) qtile reads `IconPixmap`, `AttentionIconPixmap` and `OverlayIconPixmap` from every StatusNotifier item. `inhibit-bridge` implements the first and answers the other two with a D-Bus error carrying no message body; `dbus_fast.errors.DBusError._from_message` reads `msg.body[0]` unconditionally and raises `IndexError`, which qtile reports as "Error starting StatusNotifierItem" and drops the item.
    - (2026-09-08) an error reply with no body is legal D-Bus, so the fix belongs in `dbus-fast`. qtile catching a non-`DBusError` around the optional icons would also do it. Nothing in this repository can close it.

- [ ] The VSCode light template is an export of classic Light+, not Light Modern
    - (2026-10-04) both templates come from the classic themes, while the patcher pins the
      Modern ones underneath. Light+ drew the activity bar dark in light mode, now worked
      around by letting the base theme decide `activityBar.*`. Re-exporting both templates
      from the Modern themes — with this repository's colour customisations switched off,
      or they end up in the export — would remove the workaround and the vintage mismatch.
- [ ] The rofi theme fails to parse when loaded on its own
    - (2026-10-04) `rofi -dump-theme -theme configuration/rofi/theme.rasi` reports "unexpected
      invalid property name, expecting end of file". Loaded through `config.rasi`'s
      `@theme`, the normal path, it parses, so nothing visible breaks — but `rofi -theme`
      is the obvious way to preview it.


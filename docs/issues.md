# Issues

Open work only. An item is deleted when it is done; the commit that closes it says how, and
`git log -- docs/issues.md` keeps every entry that was ever here.

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

- [ ] `yths.themes` still holds the twenty-one-token vocabulary
    - (2026-11-23) the palette gained `surface`, `surface_variant` and `foreground_muted`,
      which chromalytica writes and `helper/palette_tokens.py` names. `ColorToken` in
      yths.themes lists the previous twenty-one, and its contract test reads this
      repository's `assets/default/palette.json`, so it fails until the enum carries the
      three. A bundle it exports without them still installs, on stand-ins.
    - (2026-11-23) `assets/default/` is such a bundle: its three newest greys are the
      stand-ins, written into the file. Regenerating it from chromalytica replaces them, and
      needs its four wallpapers redrawn for the new background.

- [ ] The VSCode light template is an export of classic Light+, not Light Modern
    - (2026-10-04) both templates come from the classic themes, while the patcher pins the
      Modern ones underneath. Light+ drew the activity bar dark in light mode, now worked
      around by letting the base theme decide `activityBar.*`. Re-exporting both templates
      from the Modern themes — with this repository's colour customisations switched off,
      or they end up in the export — would remove the workaround and the vintage mismatch.

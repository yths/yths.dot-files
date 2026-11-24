"""Capture the README's screenshots from the real programs, in a session of their own.

The screenshots are of qtile, kitty, tmux, vim, qutebrowser, rofi, dunst, the login screen and
the lock prompt as this repository configures them -- but not of anyone's desktop. A copy of
the tracked tree is installed into a scratch home, the shipped theme is applied to it by
``install.py`` and ``patch_configurations.py`` themselves, and the programs run on a virtual
display inside a sandbox with staged content: a sample project, two local pages, invented
readings in the bar. What a capture shows is therefore the configuration and nothing that
was on a screen.

A copy, not this clone, because installing is symlinking: the patchers write into the
repository they are run from, so applying the shipped theme from here would retheme the
machine it runs on. The sandbox is what keeps the rest apart -- its own process, network and
host namespaces, so the theme switch the capture performs signals only the staged programs,
the bar's store is a private one, and the prompt names an account and a host that do not
exist.

    python helper/capture_tour.py              # every screenshot
    python helper/capture_tour.py --only boot  # one capture; repeatable
    python helper/capture_tour.py --dry-run    # the sandbox commands, nothing run

Nothing here needs root, the boot splash included. plymouthd insists on being root and on
finding its theme under ``/usr/share``; the sandbox gives it both -- the caller's own account
under the name root, and the rendered theme mounted where the daemon looks -- so the splash
is drawn by the real daemon without anything being installed, and the machine's own boot
theme is neither read nor touched.
"""

import argparse
import contextlib
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from typing import Any

import list_tour
from utils import logger, read_setup

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The account and the machine the staged session believes it is. Both appear in the shell
#: prompt and in tmux's status line, which is why neither is the real one.
SANDBOX_USER = "tour"
SANDBOX_HOST = "dot-files"
SANDBOX_HOME = f"/home/{SANDBOX_USER}"
SANDBOX_REPOSITORY = f"{SANDBOX_HOME}/repositories/yths.dot-files"
SANDBOX_OUTPUT = f"{SANDBOX_HOME}/output"
SANDBOX_RUNTIME = f"{SANDBOX_HOME}/.runtime"

#: Where the staged session's store listens. Fixed, because the sandbox has a network of its
#: own and nothing else can be on the port.
STORE_PORT = 6379

#: The name the boot splash is rendered under. Not the name an install gives it, so that a
#: capture can never be mistaken for, or collide with, the theme a machine boots with.
BOOT_THEME = "dot-files-tour"
BOOT_THEME_ROOT = "/usr/share/plymouth/themes"

#: What systemd asks when it unlocks a disk at boot, for a volume named as docs/os-build.md
#: names it.
UNLOCK_PROMPT = "Please enter passphrase for disk root (cryptroot):"

#: The staged project and pages, as the session sees them.
PROJECT = f"{SANDBOX_HOME}/project"
PAGES = f"{SANDBOX_HOME}/pages"

#: Two displays of one resolution and different sizes: a laptop panel and a desktop monitor.
#: The same pixels over more millimetres is what gives the second a smaller scaling factor,
#: so the pair shows each bar scaled to its own display. (name, width, height, mm, mm, primary)
PANEL = ("eDP-1", 1920, 1080, 309, 174, True)
EXTERNAL = ("HDMI-1", 1920, 1080, 527, 296, False)

#: One reading per bar cell, in the shape yths.backend-service publishes it. Invented, and
#: chosen to draw every cell without drawing attention: nothing urgent, no tunnel, no place.
#: ``location`` carries no ``timezone`` on purpose -- that is the field that makes the bar
#: move the system clock.
STREAMS: dict[str, dict[str, Any]] = {
    "audio": {"muted": False, "volume": 60, "active_sink": "speakers"},
    "backlight": {"devices": {"intel_backlight": {"brightness": 549, "max_brightness": 1515}}},
    "bluetooth": {"headphones": {"capacity": "80"}},
    "broadcast": {"obs": False, "streaming": False},
    "claude_usage": {
        "available": True,
        "limits": [
            {"kind": "session", "percent": 38, "resets_in": 7200},
            {"kind": "weekly_all", "percent": 21, "resets_in": 302400},
        ],
    },
    "location": {"sunrise": "07:41:12", "sunset": "16:28:05", "vpn": False},
    "power_supply": {
        "grid": True,
        "batteries": {
            "BAT0": {
                "capacity": "84", "status": "Charging", "energy_now_wh": 44.1,
                "energy_full_wh": 52.5, "health": 100.0, "cycle_count": 12, "power_w": 18.4,
                "seconds_left": 1500, "charge_start_threshold": 75, "charge_end_threshold": 90,
            },
        },
        "tlp": {"enabled": True, "profile": "balanced/BAL", "power_source": "AC"},
    },
    "updates": {"outstanding_updates": 3},
    "vpn": {"connected": False},
}


def session_environment() -> dict[str, str]:
    """The staged session's whole environment, built up rather than inherited.

    Nothing is copied from the caller's: a ``DISPLAY``, a bus address or a runtime directory
    that leaked through is how a staged program ends up opening in the real session, or the
    theme switch ends up signalling the real one.
    """
    return {
        "HOME": SANDBOX_HOME,
        "USER": SANDBOX_USER,
        "LOGNAME": SANDBOX_USER,
        "HOSTNAME": SANDBOX_HOST,
        "SHELL": "/bin/bash",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        # The shims stand in for the four programs that reach past a session: see helper/tour.
        "PATH": f"{SANDBOX_REPOSITORY}/helper/tour/shims:/usr/bin",
        "XDG_CONFIG_HOME": f"{SANDBOX_HOME}/.config",
        "XDG_CACHE_HOME": f"{SANDBOX_HOME}/.cache",
        "XDG_DATA_HOME": f"{SANDBOX_HOME}/.local/share",
        "XDG_STATE_HOME": f"{SANDBOX_HOME}/.local/state",
        "XDG_RUNTIME_DIR": SANDBOX_RUNTIME,
        "TMUX_TMPDIR": SANDBOX_RUNTIME,
        "BACKEND_REDIS_HOST": "127.0.0.1",
        "BACKEND_REDIS_PORT": str(STORE_PORT),
        "BACKEND_REDIS_DB": "1",
        # A virtual display has no GPU, and a sandbox cannot nest the browser's own.
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "QTWEBENGINE_DISABLE_SANDBOX": "1",
        "QT_QPA_PLATFORM": "xcb",
    }


def tracked_files() -> list[str]:
    """Every file that is part of this repository as it stands: tracked, or new and not ignored.

    Asked of git rather than walked, for the reason ``utils.tracked_bundles`` gives: the
    working tree also holds a personal theme bundle and every file the patchers generated
    for this machine, and neither belongs in a capture of what the repository ships.
    """
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [name for name in listing.split("\0") if name]


def build_scratch(scratch: pathlib.Path) -> pathlib.Path:
    """Lay out the scratch home under ``scratch`` and copy the repository into it.

    Returns the home directory. Symlinks are copied as links, so the ones the installer is
    about to point somewhere keep pointing into the copy.
    """
    home = scratch / "home"
    repository = home / "repositories" / "yths.dot-files"
    for name in tracked_files():
        source = REPO_ROOT / name
        if not source.is_symlink() and not source.exists():
            continue  # deleted in the working tree, still in the index
        destination = repository / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
    for directory in ("output", ".runtime", "boot-theme"):
        (home / directory).mkdir(mode=0o700)
    # The account the prompt shows: the caller's ids under the staged name.
    (scratch / "passwd").write_text(
        f"{SANDBOX_USER}:x:{os.getuid()}:{os.getgid()}:{SANDBOX_USER}:{SANDBOX_HOME}:/bin/bash\n"
        "root:x:0:0:root:/root:/usr/bin/nologin\n"
    )
    (scratch / "group").write_text(f"{SANDBOX_USER}:x:{os.getgid()}:\nroot:x:0:\n")
    return home


def sandbox_command(
    scratch: pathlib.Path, command: list[str], *, as_root: bool = False
) -> list[str]:
    """``command`` as an argv that runs it inside the sandbox built on ``scratch``.

    Its own process namespace, so ``killall dunst`` and the signals a theme switch sends reach
    the staged programs only; its own network, so the store and the X server are private and
    nothing is fetched; its own host name. The system is mounted read-only and ``/run`` is
    empty, which puts the system bus -- and with it ``timedatectl`` and logind -- out of reach.
    ``/dev`` is a bare one: no consoles, no framebuffer, no graphics card.

    ``as_root`` is for the boot splash. It maps the caller to uid 0 inside the sandbox --
    which grants nothing outside it -- and mounts an empty theme directory over plymouth's,
    holding only the staged theme. The daemon then finds what it insists on, and cannot find
    the theme this machine boots with.
    """
    argv = [
        "bwrap", "--die-with-parent", "--new-session",
        "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-net",
        "--hostname", SANDBOX_HOST,
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/bin", "/sbin",
        "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--ro-bind", str(scratch / "passwd"), "/etc/passwd",
        "--ro-bind", str(scratch / "group"), "/etc/group",
        "--ro-bind", "/sys", "/sys",
        "--ro-bind-try", "/opt", "/opt",
        "--ro-bind-try", "/var/cache/fontconfig", "/var/cache/fontconfig",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/run",
        "--tmpfs", "/tmp",  # noqa: S108 -- a mount point for an empty one, not a file in the real one
        "--bind", str(scratch / "home"), SANDBOX_HOME,
        "--chdir", SANDBOX_HOME,
        "--clearenv",
    ]
    if as_root:
        argv += [
            "--unshare-user", "--uid", "0", "--gid", "0",
            "--tmpfs", BOOT_THEME_ROOT,
            "--bind", str(scratch / "home" / "boot-theme"), f"{BOOT_THEME_ROOT}/{BOOT_THEME}",
            "--tmpfs", "/var",
        ]
    for name, value in session_environment().items():
        argv += ["--setenv", name, value]
    return [*argv, "--", *command]


# ------------------------------------------------------------------- inside the sandbox


class StageError(RuntimeError):
    """Something the capture waits for did not happen."""


def wait_for(probe: Callable[[], Any], what: str, timeout: float = 40.0) -> Any:
    """Poll ``probe`` until it returns something truthy, and return that.

    A probe that raises is one that is not ready yet -- a socket not created, a window not
    mapped -- so the exception is kept only to explain a timeout.
    """
    deadline = time.monotonic() + timeout
    failure: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = probe()
        except Exception as error:  # noqa: BLE001 -- see the docstring
            failure, result = error, None
        if result:
            return result
        time.sleep(0.25)
    raise StageError(f"Timed out waiting for {what}" + (f": {failure!r}" if failure else "."))


def run(*argv: str, check: bool = True, **options: Any) -> subprocess.CompletedProcess:
    """Run one staged command to completion."""
    return subprocess.run(list(argv), check=check, **options)


class Stage:
    """The programs of one capture, and the display they draw on.

    Everything started here is stopped by ``close``, so each phase begins on an empty display
    rather than on whatever the previous one left mapped.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.processes: list[subprocess.Popen] = []
        self.logs = pathlib.Path(SANDBOX_HOME) / "logs"
        self.logs.mkdir(exist_ok=True)
        read_end, write_end = os.pipe()
        self.spawn(
            "Xvfb", "-displayfd", str(write_end), "-screen", "0", f"{width}x{height}x24",
            "-nolisten", "tcp", "-ac", "-noreset", pass_fds=[write_end],
        )
        os.close(write_end)
        with os.fdopen(read_end) as handle:
            os.environ["DISPLAY"] = f":{handle.readline().strip()}"
        # What a session's startup does: services the bus starts on demand -- dunst is one --
        # have to be told which display to open.
        run("dbus-update-activation-environment", "DISPLAY")

    def spawn(self, *argv: str, **options: Any) -> subprocess.Popen:
        """Start a program that stays up for the phase, logging to a file named for it."""
        log = (self.logs / f"{pathlib.Path(argv[0]).name}.log").open("ab")
        process = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **options
        )
        self.processes.append(process)
        return process

    def shoot(
        self, name: str, geometry: tuple[int, int, int, int] | None = None,
        size: tuple[int, int] | None = None,
    ) -> None:
        """Capture the display, or the ``(x, y, width, height)`` part of it, as ``name``.webp.

        The same ``maim`` call the screenshot bindings make, then encoded as WebP: a desktop
        over a photograph is two megabytes as PNG and a seventh of that this way.
        """
        import PIL.Image  # noqa: PLC0415 -- needed here only, and not by --dry-run

        png = self.logs / f"{name}.png"
        command = ["maim", "--hidecursor"]
        if geometry is not None:
            x, y, width, height = geometry
            command += ["--geometry", f"{width}x{height}+{x}+{y}"]
        run(*command, str(png))
        with PIL.Image.open(png) as image:
            frame = image.convert("RGB")
            if size is not None:
                frame = frame.resize(size, PIL.Image.Resampling.LANCZOS)
            frame.save(pathlib.Path(SANDBOX_OUTPUT) / f"{name}.webp", "WEBP", quality=88, method=6)
        logger.info(f"Captured {name}.")

    def close(self) -> None:
        """Stop everything this phase started, the display last."""
        run("tmux", "kill-server", check=False, capture_output=True)
        for name in ("qutebrowser", "kitty", "rofi", "dunst", "qtile"):
            run("pkill", "-x", name, check=False)
        for process in reversed(self.processes):
            process.terminate()
        for process in self.processes:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=10)
            if process.poll() is None:
                process.kill()
        os.environ.pop("DISPLAY", None)


def start_store() -> subprocess.Popen:
    """Start the private store the bar reads, and fill it with ``STREAMS``."""
    import redis  # noqa: PLC0415 -- needed inside the sandbox only

    process = subprocess.Popen(
        ["valkey-server", "--port", str(STORE_PORT), "--bind", "127.0.0.1", "--save", "",
         "--appendonly", "no", "--dir", SANDBOX_RUNTIME, "--daemonize", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(host="127.0.0.1", port=STORE_PORT, db=1)
    wait_for(client.ping, "the store")
    for stream, measurement in STREAMS.items():
        client.xadd(stream, {"measurement": json.dumps(measurement)})
    return process


def configuration_path() -> str:
    return os.path.join(SANDBOX_HOME, ".config", "config.json")


def install() -> None:
    """Install the copy into the scratch home, with the installer itself.

    It needs a display to detect a monitor from; the answer to its one question is no,
    because the capture collects no credentials.
    """
    run(
        sys.executable, f"{SANDBOX_REPOSITORY}/install.py", "--theme",
        read_setup()["desktop"]["theme"], input=b"n\n",
    )


def stage_state(monitors: tuple[tuple, ...], theme: str) -> None:
    """Record ``monitors`` and ``theme`` in the staged configuration.

    The monitors are written in the shape detection gives them, by the function that gives
    it, so the scaling the bar draws at is the one a display of that size would get. The mode
    is manual so the bar leaves the theme where the capture put it.
    """
    import screeninfo  # noqa: PLC0415 -- needed inside the sandbox only
    import shared.monitors  # noqa: PLC0415
    import shared.state  # noqa: PLC0415

    configuration = shared.state.read_state(configuration_path())
    configuration["monitors"] = {
        name: shared.monitors._monitor(screeninfo.Monitor(
            x=0, y=0, width=width, height=height, width_mm=width_mm, height_mm=height_mm,
            name=name, is_primary=primary,
        ))
        for name, width, height, width_mm, height_mm, primary in monitors
    }
    configuration["state"].update(theme=theme, theme_mode="manual")
    shared.state.write_state(configuration, configuration_path())


def patch(*, reload: bool) -> None:
    """Apply the staged theme with the patchers themselves.

    With ``reload`` this is the theme switch exactly as the bar runs it: dunst is killed,
    tmux, kitty and qutebrowser are told, qtile restarts. Inside the sandbox those reach the
    staged programs and no others.
    """
    argv = [sys.executable, f"{SANDBOX_REPOSITORY}/helper/patch_configurations.py"]
    run(*argv, *([] if reload else ["--no-reload"]), check=False)


def qtile_client() -> Any:
    """A command client for the staged qtile, once it answers."""
    from libqtile.command.client import InteractiveCommandClient  # noqa: PLC0415

    def connect() -> Any:
        client = InteractiveCommandClient()
        client.status()
        return client

    return wait_for(connect, "qtile")


def window(client: Any, wm_class: str) -> dict[str, Any] | None:
    """The first managed window of ``wm_class``, as qtile describes it."""
    for candidate in client.windows():
        if wm_class in (candidate.get("wm_class") or []):
            return candidate
    return None


def geometry(client: Any, wm_class: str) -> tuple[int, int, int, int]:
    """Where a window is on the display: ``(x, y, width, height)``."""
    found = wait_for(lambda: window(client, wm_class), f"a {wm_class} window")
    return found["x"], found["y"], found["width"], found["height"]


def tmux(*argv: str) -> None:
    run("tmux", *argv)


def stage_home() -> None:
    """Fill the staged home with what the installer does not: an account's and a person's.

    The login profile every new account is given, which is what makes a login shell -- the
    kind tmux starts -- read ``.bashrc`` at all. The browser's note that its first-run pages
    have been seen. And the sample project, as a repository with one commit and one edit
    after it, so the prompt and ``git status`` have something to say.
    """
    home = pathlib.Path(SANDBOX_HOME)
    (home / ".bash_profile").write_text("[[ -f ~/.bashrc ]] && . ~/.bashrc\n")
    state = home / ".local" / "share" / "qutebrowser" / "state"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("[general]\nquickstart-done = 1\nsession-warning-shown = 1\n")
    # An empty keyring that needs no password. The editor asks the desktop's keyring for a
    # place to keep sign-in secrets on its first start, and a keyring that does not exist yet
    # answers by asking for a password to create one -- over the window being photographed.
    keyrings = home / ".local" / "share" / "keyrings"
    keyrings.mkdir(parents=True, exist_ok=True)
    (keyrings / "default").write_text("staged")
    (keyrings / "staged.keyring").write_text(
        "[keyring]\ndisplay-name=staged\nctime=0\nmtime=0\nlock-on-idle=false\nlock-after=false\n"
    )

    source = pathlib.Path(SANDBOX_REPOSITORY) / "helper" / "tour"
    shutil.copytree(source / "project", PROJECT)
    shutil.copytree(source / "pages", PAGES)
    identity = ["-c", f"user.name={SANDBOX_USER}", "-c", f"user.email={SANDBOX_USER}@{SANDBOX_HOST}"]
    run("git", "-C", PROJECT, "init", "--quiet", "--initial-branch", "main")
    run("git", "-C", PROJECT, "add", ".")
    run("git", "-C", PROJECT, *identity, "commit", "--quiet", "-m", "feat: trace an orbit")
    with open(os.path.join(PROJECT, "notes.md"), "a", encoding="utf-8") as handle:
        handle.write("- compare against a fixed-step integrator\n")


def start_session(stage: Stage, *arguments: str) -> Any:
    """Start the staged desktop the way ``.xinitrc`` does, and return a client for it.

    The X resources first: they carry the DPI the patchers computed for the staged monitor,
    and the terminal, the launcher and the notifications all size their text from it.
    """
    run("xrdb", "-merge", os.path.join(SANDBOX_HOME, ".Xresources"))
    stage.spawn("qtile", "start", *arguments)
    return qtile_client()


def stage_terminal(client: Any) -> None:
    """Open the terminal with its own binding and fill it: two shells side by side, in tmux.

    ``.bashrc`` starts tmux and starship; what is typed here is only what a person would
    type into them.
    """
    client.simulate_keypress(["mod4"], "Return")
    geometry(client, "kitty")
    wait_for(
        lambda: run("tmux", "has-session", "-t", SANDBOX_HOST, check=False,
                    capture_output=True).returncode == 0,
        "the tmux session",
    )
    time.sleep(2)
    tmux("send-keys", "-t", SANDBOX_HOST, f"cd {PROJECT} && clear", "Enter")
    tmux("send-keys", "-t", SANDBOX_HOST, "git --no-pager diff", "Enter")
    tmux("split-window", "-t", SANDBOX_HOST, "-h", "-c", PROJECT)
    time.sleep(2)
    tmux("send-keys", "-t", SANDBOX_HOST, "clear && ls -l && python orbit.py", "Enter")
    time.sleep(2)


def stage_browser(client: Any) -> None:
    """Open the browser on the two staged pages, the first one in front.

    Without the session the previous capture's browser saved on exit, which would be
    restored beside them.
    """
    shutil.rmtree(os.path.join(SANDBOX_HOME, ".local", "share", "qutebrowser", "sessions"),
                  ignore_errors=True)
    client.spawn(["qutebrowser", f"file://{PAGES}/index.html", f"file://{PAGES}/palette.html"])
    geometry(client, "qutebrowser")
    time.sleep(6)
    run("qutebrowser", ":tab-focus 1", check=False)
    time.sleep(1)


def type_text(text: str) -> None:
    """Press the keys that spell ``text``, as a keyboard would, into whatever has the focus.

    For the two places a person types into something that takes no commands: the launcher's
    filter and the boot splash's passphrase field.
    """
    import xcffib  # noqa: PLC0415 -- needed inside the sandbox only
    import xcffib.xproto  # noqa: PLC0415
    import xcffib.xtest  # noqa: PLC0415

    key_press, key_release = 2, 3  # the X protocol's event codes
    connection = xcffib.connect()
    setup = connection.get_setup()
    first, count = setup.min_keycode, setup.max_keycode - setup.min_keycode + 1
    mapping = connection.core.GetKeyboardMapping(first, count).reply()
    width = mapping.keysyms_per_keycode
    # Unshifted symbols only; a lower-case letter's keysym is its code point.
    keycodes = {mapping.keysyms[index * width]: first + index for index in reversed(range(count))}
    fake = connection(xcffib.xtest.key)
    for character in text:
        for event in (key_press, key_release):
            fake.FakeInput(event, keycodes[ord(character)], 0, setup.roots[0].root, 0, 0, 0)
        connection.flush()
        time.sleep(0.05)
    connection.disconnect()


def notify(*, critical: bool) -> None:
    """Send one staged notification through the notification service, as any program would."""
    if critical:
        run("notify-send", "-u", "critical", "Battery", "12% left - plug in the charger")
    else:
        run("notify-send", "-u", "normal", "Patching", "All configurations reloaded ...")
    time.sleep(1.5)


def capture_desktop(theme: str) -> None:
    """The single-monitor desktop in ``theme``, and in dark the applications one by one."""
    stage = Stage(PANEL[1], PANEL[2])
    try:
        stage_state((PANEL,), theme)
        patch(reload=False)
        client = start_session(stage)
        stage_terminal(client)
        stage_browser(client)
        stage.shoot(f"desktop-{theme}")
        if theme != "dark":
            return

        stage.shoot("terminal", geometry(client, "kitty"))

        run("qutebrowser", ":hint", check=False)
        time.sleep(1.5)
        stage.shoot("browser", geometry(client, "qutebrowser"))
        run("qutebrowser", ":mode-leave", check=False)

        client.simulate_keypress(["mod4"], "r")
        time.sleep(2.5)
        type_text("kit")
        time.sleep(1)
        stage.shoot("launcher", size=(1280, 720))
        run("pkill", "-x", "rofi", check=False)
        time.sleep(1)

        # Last, because the notifications lie over the top of every window.
        notify(critical=False)
        notify(critical=True)
        stage.shoot("notification", (0, 0, stage.width * 2 // 3, stage.height // 3))
    finally:
        stage.close()


def capture_dual() -> None:
    """Two monitors side by side, a window on each, the second one focused."""
    stage = Stage(PANEL[1] + EXTERNAL[1], max(PANEL[2], EXTERNAL[2]))
    try:
        stage_state((PANEL, EXTERNAL), "dark")
        patch(reload=False)
        client = start_session(
            stage, "-c", f"{SANDBOX_REPOSITORY}/helper/tour/dual_monitor_config.py"
        )
        stage_terminal(client)
        client.to_screen(1)
        stage_browser(client)
        stage.shoot("desktop-dual", size=(stage.width * 2 // 3, stage.height * 2 // 3))
    finally:
        stage.close()


def capture_editor() -> None:
    """Visual Studio Code on the sample project, in the colours matched for it."""
    stage = Stage(PANEL[1], PANEL[2])
    try:
        stage_state((PANEL,), "dark")
        patch(reload=False)
        client = start_session(stage)
        client.spawn([
            "code", "--no-sandbox", "--disable-gpu", "--new-window", "--disable-workspace-trust",
            "--skip-welcome", "--skip-release-notes", "--disable-updates", "--disable-telemetry",
            "--password-store=basic",
            PROJECT, "--goto", f"{PROJECT}/orbit.py:20",
        ])
        geometry(client, "com.microsoft.vscode")
        time.sleep(15)
        stage.shoot("editor", size=(1280, 720))
    finally:
        stage.close()


def capture_login() -> None:
    """The login screen's own page, in its preview mode, filling the display.

    Served over HTTP because the mock LightDM the preview mode loads is addressed from the
    server root. The browser is a plain one with no configuration, so nothing of the staged
    desktop's -- its dark mode least of all -- is applied to the page.
    """
    stage = Stage(PANEL[1], PANEL[2])
    try:
        stage_state((PANEL,), "dark")
        patch(reload=False)
        themes = f"{SANDBOX_REPOSITORY}/configuration/web-greeter/themes"
        stage.spawn(sys.executable, "-m", "http.server", "--bind", "127.0.0.1", "8765",
                    "--directory", themes)
        time.sleep(1)
        stage.spawn(
            "qutebrowser", "--temp-basedir", "--qt-arg", "qwindowgeometry",
            f"{stage.width}x{stage.height}+0+0", "-s", "statusbar.show", "never",
            "-s", "tabs.show", "never", "http://127.0.0.1:8765/standard/?preview=1",
        )
        time.sleep(10)
        stage.shoot("login", size=(1280, 720))
    finally:
        stage.close()


def capture_lock() -> None:
    """The lock prompt, drawn by the locker's own dialog without locking anything.

    xsecurelock is two programs: one that grabs the screen and covers it with a window in
    the lock's background colour, and one that draws the prompt in a window inside that one.
    Only the second runs here, handed a pair of windows made the way the first makes its own,
    and asking a stand-in for the password instead of PAM. So there is no grab to be stuck
    behind, and no failed attempt is ever counted against an account.
    """
    import xcffib  # noqa: PLC0415 -- needed inside the sandbox only
    import xcffib.xproto  # noqa: PLC0415

    stage = Stage(PANEL[1], PANEL[2])
    try:
        stage_state((PANEL,), "dark")
        patch(reload=False)
        settings = run(
            "sh", "-c", f". {SANDBOX_HOME}/.config/lock/environment && env",
            capture_output=True, text=True,
        ).stdout
        environment = dict(os.environ)
        environment.update(
            line.split("=", 1) for line in settings.splitlines() if line.startswith("XSECURELOCK_")
        )
        run("xrdb", "-merge", os.path.join(SANDBOX_HOME, ".Xresources"))
        connection = xcffib.connect()
        screen = connection.get_setup().roots[0]
        background = int(environment["XSECURELOCK_BACKGROUND_COLOR"].lstrip("#"), 16)
        cover, prompt = connection.generate_id(), connection.generate_id()
        for identifier, parent in ((cover, screen.root), (prompt, cover)):
            connection.core.CreateWindow(
                screen.root_depth, identifier, parent, 0, 0, stage.width, stage.height, 0,
                xcffib.xproto.WindowClass.InputOutput, screen.root_visual,
                xcffib.xproto.CW.BackPixel | xcffib.xproto.CW.OverrideRedirect,
                [background, 1],
            )
            connection.core.MapWindow(identifier)
        connection.flush()
        environment.update(
            XSCREENSAVER_WINDOW=str(prompt),
            XSECURELOCK_AUTHPROTO=f"{SANDBOX_REPOSITORY}/helper/tour/authproto_stub",
            XSECURELOCK_BURNIN_MITIGATION="0",
        )
        dialog = subprocess.Popen(
            ["/usr/lib/xsecurelock/auth_x11_feedback"], env=environment, stdin=subprocess.PIPE,
        )
        stage.processes.append(dialog)
        time.sleep(2)
        dialog.stdin.write(b"staged")  # what a person would have typed; it goes nowhere
        dialog.stdin.flush()
        time.sleep(1.5)
        stage.shoot("lock", size=(1280, 720))
    finally:
        stage.close()


def capture_boot() -> None:
    """The boot splash and its passphrase prompt, drawn by plymouthd itself.

    The theme is rendered by the patcher's own two stages, from the copy -- whose wallpaper
    link the installer pointed at the shipped bundle -- and under a name of its own. The
    daemon is given that name on the kernel command line it is told to pretend it booted
    with, which is the override plymouth provides; ``plymouthd.conf`` is not consulted.
    The frames are discarded unless the daemon's log -- which it writes as it quits -- names
    that theme as the one it loaded, so a fallback is never kept in its place.
    """
    import patch_plymouth  # noqa: PLC0415 -- needed inside the sandbox only

    with open(configuration_path(), encoding="utf-8") as handle:
        configuration = json.load(handle)
    staged = patch_plymouth.stage_theme(patch_plymouth.THEME_SOURCE)
    try:
        patch_plymouth.render_theme(
            configuration, staged, patch_plymouth.PALETTE_VARIANT, BOOT_THEME
        )
        shutil.copytree(staged, f"{BOOT_THEME_ROOT}/{BOOT_THEME}", dirs_exist_ok=True)
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    stage = Stage(PANEL[1], PANEL[2])
    log = stage.logs / "plymouthd-debug.log"
    frames = ("boot-splash", "boot-passphrase")
    verified = False
    try:
        stage.spawn(
            "plymouthd", "--no-daemon", "--mode=boot", "--no-boot-log", "--debug",
            f"--debug-file={log}", f"--pid-file={SANDBOX_RUNTIME}/plymouthd.pid",
            f"--kernel-command-line=quiet splash plymouth.splash={BOOT_THEME}",
        )
        daemon = stage.processes[-1]
        wait_for(lambda: run("plymouth", "--ping", check=False).returncode == 0, "plymouthd")
        run("plymouth", "show-splash")
        time.sleep(4)
        stage.shoot(frames[0], size=(1280, 720))

        stage.spawn("plymouth", "ask-for-password", "--prompt", UNLOCK_PROMPT)
        time.sleep(2)
        type_text("staged")
        time.sleep(1)
        stage.shoot(frames[1], size=(1280, 720))

        run("plymouth", "quit", check=False)
        daemon.wait(timeout=20)
        loaded = f"Loading boot splash theme '{BOOT_THEME_ROOT}//{BOOT_THEME}/"
        if loaded not in log.read_text(encoding="utf-8", errors="replace"):
            raise StageError(f"plymouthd did not load the {BOOT_THEME} theme; see {log}.")
        verified = True
    finally:
        if not verified:
            for frame in frames:
                pathlib.Path(SANDBOX_OUTPUT, f"{frame}.webp").unlink(missing_ok=True)
        stage.close()


#: Each capture, by the name ``--only`` selects it with, in the order a boot shows them.
CAPTURES: dict[str, Callable[[], None]] = {
    "boot": capture_boot,
    "login": capture_login,
    "dark": lambda: capture_desktop("dark"),
    "light": lambda: capture_desktop("light"),
    "dual": capture_dual,
    "editor": capture_editor,
    "lock": capture_lock,
}

#: The captures that run with the sandbox's own root: see ``sandbox_command``.
ROOT_CAPTURES = frozenset({"boot"})


def capture(names: list[str]) -> int:
    """Inside the sandbox: install the copy if it is not yet, then take each named capture."""
    sys.path.insert(0, f"{SANDBOX_REPOSITORY}/configuration/qtile")
    store = start_store()
    try:
        if not os.path.exists(configuration_path()):
            bootstrap = Stage(PANEL[1], PANEL[2])
            try:
                install()
            finally:
                bootstrap.close()
            stage_home()
        for name in names:
            CAPTURES[name]()
    finally:
        store.terminate()
    return 0


# ------------------------------------------------------------------ outside the sandbox


def collect(home: pathlib.Path) -> list[str]:
    """Move what the sandbox captured into ``docs/preview``. Returns the file names."""
    known = {shot.file for shot in list_tour.SHOTS}
    captured = sorted(path.name for path in (home / "output").glob("*.webp") if path.name in known)
    list_tour.PREVIEW_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name in captured:
        shutil.copyfile(home / "output" / name, list_tour.PREVIEW_DIRECTORY / name)
    return captured


def inner_command(names: list[str]) -> list[str]:
    """This script as it is run inside the sandbox, from the copy, for ``names``.

    Under a session bus of its own: dunst is started by one on demand, and ``gsettings``
    writes through one -- into the scratch home, since that is where this one keeps its state.
    """
    return [
        "dbus-run-session", "--", sys.executable,
        f"{SANDBOX_REPOSITORY}/helper/capture_tour.py", "--inside",
        *[argument for name in names for argument in ("--only", name)],
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--only", action="append", choices=sorted(CAPTURES), metavar="CAPTURE",
        help=f"take only this capture; repeatable. One of: {', '.join(sorted(CAPTURES))}",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the sandbox command and the staged environment, and run nothing",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="leave the scratch home behind, with every program's log, and say where",
    )
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    names = arguments.only or list(CAPTURES)

    if arguments.inside:
        return capture(names)

    # Two runs at most: the desktop as the staged account, the boot splash as the sandbox's
    # root. The first installs the copy and the second finds it installed.
    runs = [
        (as_root, [name for name in names if (name in ROOT_CAPTURES) == as_root])
        for as_root in (False, True)
    ]
    commands = [
        (as_root, inner_command(selected)) for as_root, selected in runs if selected
    ]
    if arguments.dry_run:
        for as_root, command in commands:
            print(shlex.join(sandbox_command(pathlib.Path("<scratch>"), command, as_root=as_root)))
        return 0

    scratch = pathlib.Path(tempfile.mkdtemp(prefix="dot-files-tour-"))
    try:
        home = build_scratch(scratch)
        failed = 0
        for as_root, command in commands:
            result = subprocess.run(
                sandbox_command(scratch, command, as_root=as_root), check=False
            )
            failed = failed or result.returncode
        captured = collect(home)
        if captured:
            list_tour.record(captured)
        logger.info(f"Captured {len(captured)} screenshots into {list_tour.PREVIEW_DIRECTORY}.")
        return failed
    finally:
        if arguments.keep:
            logger.info(f"The scratch home is kept at {scratch}.")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

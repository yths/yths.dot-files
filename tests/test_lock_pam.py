"""The lock screen's PAM stack: the one file here that can stop a screen unlocking.

xsecurelock draws only what the PAM conversation gives it, and Arch's `system-auth` answers a
wrong password with nothing -- pam_unix fails silently and pam_faillock's `authfail` dies at
once -- so the screen showed an empty field and no reason. `configuration/lock/pam/` adds a
`pam_echo` on the failure path.

The risk is not the echo, it is the arithmetic around it. PAM jumps are counted in lines, so
inserting one moves every target that skips past it, and getting that wrong does not merely
lose the message: with `system-auth`'s original counts, a *correct* password is denied. These
tests pin both branches by substituting `pam_permit` and `pam_deny` for `pam_unix` -- which is
how the success path can be checked at all without a real password.

Each runs in a bubblewrap sandbox with a fake `/etc/pam.d`, so nothing here reads or writes
the stack the rest of the system logs in through.
"""

import hashlib
import pathlib
import re
import shutil
import subprocess

import patch_lock
import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
PAM_FILE = REPO / "configuration/lock/pam/xsecurelock.pam"
PKGBUILD = REPO / "configuration/lock/pam/PKGBUILD"

#: A PAM client, built once per session. There is no pamtester in the Arch repositories and no
#: Python binding installed, and the whole point is to observe the conversation rather than the
#: exit status, so this asks libpam directly.
PROBE = r"""
#include <security/pam_appl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char *pw;
static int conv(int n, const struct pam_message **m, struct pam_response **r, void *d) {
    (void)d;
    *r = calloc((size_t)n, sizeof(struct pam_response));
    if (!*r) return PAM_BUF_ERR;
    for (int i = 0; i < n; i++) {
        if (m[i]->msg_style == PAM_ERROR_MSG || m[i]->msg_style == PAM_TEXT_INFO)
            printf("MSG:%s\n", m[i]->msg ? m[i]->msg : "");
        else (*r)[i].resp = strdup(pw);
    }
    return PAM_SUCCESS;
}
int main(int argc, char **argv) {
    if (argc < 4) return 2;
    pw = argv[3];
    struct pam_conv c = {conv, NULL};
    pam_handle_t *h = NULL;
    if (pam_start(argv[1], argv[2], &c, &h) != PAM_SUCCESS) return 3;
    int rc = pam_authenticate(h, 0);
    printf("RC:%d\n", rc);
    pam_end(h, rc);
    return rc == PAM_SUCCESS ? 0 : 1;
}
"""

requires_sandbox = pytest.mark.skipif(
    not (shutil.which("bwrap") and shutil.which("gcc")
         and pathlib.Path("/usr/include/security/pam_appl.h").is_file()),
    reason="needs bwrap, gcc and the PAM headers to exercise a stack without touching /etc",
)


@pytest.fixture(scope="module")
def probe(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    directory = tmp_path_factory.mktemp("pamprobe")
    source = directory / "probe.c"
    source.write_text(PROBE)
    binary = directory / "probe"
    subprocess.run(["gcc", "-o", str(binary), str(source), "-lpam"], check=True)
    return binary


def _run(probe: pathlib.Path, directory: pathlib.Path, service: str) -> tuple[int, list[str]]:
    """Authenticate against a stack in `directory`, seeing nothing of the real /etc/pam.d."""
    faillock = directory / "faillock"
    faillock.mkdir(exist_ok=True)
    result = subprocess.run(
        ["bwrap", "--dev-bind", "/", "/", "--bind", str(directory), "/etc/pam.d",
         "--bind", str(faillock), "/run/faillock",
         str(probe), service, "nobody", "irrelevant"],
        capture_output=True, text=True, check=False,
    )
    messages = [line[4:] for line in result.stdout.splitlines() if line.startswith("MSG:")]
    codes = [int(line[3:]) for line in result.stdout.splitlines() if line.startswith("RC:")]
    return (codes[0] if codes else -1), messages


def _stack(directory: pathlib.Path, name: str, module: str, counts: bool = True) -> None:
    """The real auth stack with `module` standing in for pam_unix.

    Only the account/password/session includes are dropped -- they pull in the real
    system-auth, which is not in the sandbox. Every auth line, and so every jump target,
    is the shipped one.
    """
    text = PAM_FILE.read_text()
    text = re.sub(r"^(account|password|session)\s+include.*$", "", text, flags=re.M)
    text = text.replace("pam_unix.so          try_first_pass nullok", f"{module}.so")
    if not counts:  # system-auth's original counts, as if the echo had been inserted blindly
        text = text.replace("success=3", "success=2").replace("success=2 default=bad",
                                                              "success=1 default=bad")
    (directory / name).write_text(text)
    (directory / "other").write_text("#%PAM-1.0\nauth required pam_deny.so\n")


# The whole reason the stack is forked from system-auth rather than edited into it.
def test_the_shipped_stack_leaves_system_auth_alone() -> None:
    text = PAM_FILE.read_text()
    assert "system-auth" in text, "the account/password/session phases should be included"
    for phase in ("account", "password", "session"):
        assert re.search(rf"^{phase}\s+include\s+system-auth", text, re.M), phase
    # It must not be an `@include`, which would pull system-auth's auth stack back in and run
    # pam_unix twice.
    assert "@include" not in text


@requires_sandbox
def test_a_correct_password_is_accepted_and_says_nothing(
    probe: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The dangerous direction: a stack that denies a correct password locks you out."""
    _stack(tmp_path, "candidate", "pam_permit")
    code, messages = _run(probe, tmp_path, "candidate")
    assert code == 0, f"a correct password was refused ({code}); this would lock the screen"
    assert messages == [], f"success should be silent, got {messages}"


@requires_sandbox
def test_a_wrong_password_is_refused_and_says_so(
    probe: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The defect this closes: the screen had nothing to draw, so it drew nothing."""
    _stack(tmp_path, "candidate", "pam_deny")
    code, messages = _run(probe, tmp_path, "candidate")
    assert code != 0
    assert any("password" in message.lower() for message in messages), (
        f"a failure has to carry a message for xsecurelock to draw, got {messages}"
    )


# Proof that the two tests above have power. Inserting the echo without moving the jump targets
# is the obvious mistake, and it does not lose the message -- it denies a correct password.
@requires_sandbox
def test_the_original_jump_counts_would_deny_a_correct_password(
    probe: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    _stack(tmp_path, "candidate", "pam_permit", counts=False)
    code, _ = _run(probe, tmp_path, "candidate")
    assert code != 0, (
        "system-auth's original counts accepted a correct password with the echo inserted, "
        "so the tests above no longer prove the arithmetic"
    )


# ------------------------------------------------------------------------------ the package


def test_the_pkgbuild_checksum_matches_the_file_it_ships() -> None:
    """Editing the stack without updating the checksum makes makepkg refuse to build."""
    digest = hashlib.sha256(PAM_FILE.read_bytes()).hexdigest()
    assert digest in PKGBUILD.read_text(), "run `updpkgsums` in configuration/lock/pam"


def test_the_package_owns_the_file_rather_than_copying_it() -> None:
    """`backup=` is what makes an update leave a .pacnew instead of replacing the stack."""
    text = PKGBUILD.read_text()
    assert "backup=('etc/pam.d/xsecurelock')" in text
    assert "install -Dm644" in text and "/etc/pam.d/xsecurelock" in text


# Naming a service with no file in /etc/pam.d is worse than the silence it fixes: PAM falls
# through to /etc/pam.d/other, which on Arch denies everything.
def test_the_environment_names_the_service_only_when_it_is_installed() -> None:
    assert patch_lock.pam_service() == {} or pathlib.Path(patch_lock.PAM_SERVICE_PATH).exists()
    source = pathlib.Path(REPO / "helper/patch_lock.py").read_text()
    assert "os.path.exists(PAM_SERVICE_PATH)" in source, "the guard is the whole safety here"

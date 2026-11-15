"""Install the polkit rule that lets the system timezone follow the machine's location.

The bar's sunrise/sunset cell sets the timezone with ``timedatectl`` when the geolocated zone
changes, and systemd's default policy asks an administrator for that every time -- a prompt a
bar cell cannot answer. ``configuration/timezone/50-dot-files-timezone.rules`` grants that
one action, and nothing else, to ``wheel`` members in an active local session. Installing it
under ``/etc/polkit-1/rules.d/`` needs root, so this is a system patcher: ``install.py
--system`` runs it after asking for root once, or on its own::

    python helper/patch_timezone.py --install

See ``configuration/timezone/README.md``.
"""

import argparse
import os
import subprocess
import sys
from typing import Any

from utils import REPOSITORY_ROOT, logger, root_prefix

RULE_NAME = "50-dot-files-timezone.rules"
RULE_SOURCE = os.path.join(REPOSITORY_ROOT, "configuration", "timezone", RULE_NAME)
RULES_DIRECTORY = "/etc/polkit-1/rules.d"


def install_rule(prefix: list[str]) -> bool:
    """Copy the rule into place as root. polkitd watches the directory, so no restart."""
    result = subprocess.run(
        [*prefix, "install", "-D", "-m", "644", RULE_SOURCE,
         os.path.join(RULES_DIRECTORY, RULE_NAME)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        logger.warning(f"Could not install the timezone rule: {result.stderr.strip()}")
        return False
    logger.info(f"Installed {RULE_NAME}; the timezone now follows the machine's location.")
    return True


def install_system(_configuration: dict[str, Any], *, prompt: bool = False) -> bool:
    """The system patchers' common entry point. Returns whether the rule is installed."""
    prefix = root_prefix(prompt=prompt)
    if prefix is None:
        logger.warning("No way to run as root; the timezone rule was not installed.")
        return False
    return install_rule(prefix)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", action="store_true", help="install the rule (needs root)")
    arguments = parser.parse_args()
    if not arguments.install:
        parser.print_help()
        return 0
    return 0 if install_system({}, prompt=True) else 1


if __name__ == "__main__":
    sys.exit(main())

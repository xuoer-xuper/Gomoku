"""Best-effort Windows Firewall exception so guests can join."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading

from gomoku.config import DEFAULT_PORT

logger = logging.getLogger(__name__)

_RULE_NAME = "Gomoku LAN"
_CREATE_NO_WINDOW = 0x08000000


def allow_inbound(port: int = DEFAULT_PORT) -> None:
    """Allow this executable and the room TCP port through the firewall.

    Lab PCs often silently block inbound SYN, which shows up on the guest
    as WinError 10061. Adding the rule needs elevation; failures are
    ignored and the UI still explains what to click.
    """
    if sys.platform != "win32":
        return
    thread = threading.Thread(
        target=_allow_inbound_sync,
        args=(port,),
        name="gomoku-firewall",
        daemon=True,
    )
    thread.start()


def _allow_inbound_sync(port: int) -> None:
    exe = sys.executable
    try:
        _netsh(
            [
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={_RULE_NAME}",
                "dir=in",
                "action=allow",
                f"program={exe}",
                "enable=yes",
                "profile=any",
            ]
        )
        end = port + 16
        _netsh(
            [
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={_RULE_NAME} TCP",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}-{end}",
                "enable=yes",
                "profile=any",
            ]
        )
        _netsh(
            [
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={_RULE_NAME} UDP",
                "dir=in",
                "action=allow",
                "protocol=UDP",
                f"localport={port}-{end}",
                "enable=yes",
                "profile=any",
            ]
        )
    except OSError as exc:
        logger.info("firewall rule not added: %s", exc)


def _netsh(args: list[str]) -> None:
    creationflags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(
        ["netsh", *args],
        capture_output=True,
        timeout=2,
        check=False,
        creationflags=creationflags,
    )

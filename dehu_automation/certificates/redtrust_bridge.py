import os
import subprocess
import sys

from utils.logger import get_logger

logger = get_logger()


def select_certificate(certificate_name: str, timeout_seconds: int = 90, mode: str = "full") -> bool:
    """Invoke redtrust_window_inspect.py in a subprocess with live logs."""

    logger.info(
        "RedTrust bridge: starting certificate selection for '%s' (mode=%s)",
        certificate_name,
        mode,
    )

    script_path = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "redtrust_window_inspect.py",
        )
    )

    if not os.path.isfile(script_path):
        logger.error("RedTrust bridge: script not found at %s", script_path)
        return False

    valid_modes = {"search", "diagnose", "full"}
    action = mode if mode in valid_modes else "full"
    command = [sys.executable, "-u", script_path, action, certificate_name]

    logger.info("RedTrust bridge: launching subprocess %s", command)

    try:
        proc = subprocess.run(
            command,
            timeout=timeout_seconds,
            check=False,
        )

        logger.info("RedTrust bridge: subprocess finished with return code %d", proc.returncode)
        if proc.returncode != 0:
            logger.error("RedTrust bridge: subprocess failed")
            return False

        return True
    except subprocess.TimeoutExpired:
        logger.error("RedTrust bridge: subprocess timeout after %ss", timeout_seconds)
        return False
    except Exception as exc:
        logger.exception("RedTrust bridge: unexpected error while running subprocess: %s", exc)
        return False

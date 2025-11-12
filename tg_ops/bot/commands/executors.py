"""Command executors."""

import asyncio
import logging
import shlex

# from telegram import Update
# from telegram.constants import ParseMode
from typing import Tuple

logger = logging.getLogger(__name__)


class ShellService:
    """Service for executing shell commands safely."""

    async def execute(self, command: str) -> Tuple[int, str, str]:
        """Run a shell command and return (return_code, stdout, stderr)."""
        try:
            logger.debug(f"Executing: {command}")
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            stdout_dec = stdout.decode("utf-8", errors="replace").strip()
            stderr_dec = stderr.decode("utf-8", errors="replace").strip()
            return_code = process.returncode or 0

            return return_code, stdout_dec, stderr_dec

        except Exception as e:
            logger.exception(f"Shell execution failed for '{command}': {e}")
            return -1, "", str(e)

    async def is_service_active(self, service_name: str) -> bool:
        """Check if a systemd service is active (injection safe)."""
        safe_name = shlex.quote(service_name)
        command = f"systemctl is-active {safe_name}"
        code, _, _ = await self.execute(command)
        return code == 0

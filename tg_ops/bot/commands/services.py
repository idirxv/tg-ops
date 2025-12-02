import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import docker
import psutil
from docker.errors import DockerException

from tg_ops.bot.commands.executors import ShellService
from tg_ops.config import Config

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """Data Transfer Object for system status."""

    cpu_percent: float
    ram_used: float
    ram_total: float
    ram_percent: float
    disks: List[str]
    services: Dict[str, bool]


class SystemService:
    """Handles system monitoring logic (CPU, RAM, Services)."""

    def __init__(self, shell_service: ShellService, cfg: Config):
        self.shell_service = shell_service
        self.monitored_services = list(cfg.monitored_services)
        self.monitored_disks = list(cfg.monitored_disks)

    async def get_system_snapshot(self) -> SystemSnapshot:
        """Collects all system metrics."""

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disks_info = []
        for path in self.monitored_disks:
            if os.path.exists(path):
                d = psutil.disk_usage(path)
                used_gb = d.used / (1024**3)
                total_gb = d.total / (1024**3)
                disks_info.append(f"{path} : {used_gb:.1f}/{total_gb:.1f} Go ({d.percent}%)")

        # Async check for services
        services_status = {}
        for svc in self.monitored_services:
            services_status[svc] = await self.shell_service.is_service_active(svc)

        return SystemSnapshot(
            cpu_percent=cpu,
            ram_used=mem.used / (1024**3),
            ram_total=mem.total / (1024**3),
            ram_percent=mem.percent,
            disks=disks_info,
            services=services_status,
        )


class DockerManager:
    """Manages Docker containers."""

    def __init__(self, shell_service: ShellService, cfg: Config):
        self.shell_service = shell_service
        self.monitored_containers = dict(cfg.monitored_containers)
        try:
            self.client = docker.from_env()
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None

    async def _run_blocking(self, func, *args):
        """Helper pour exécuter les appels Docker bloquants dans un thread."""
        return await asyncio.to_thread(func, *args)

    async def get_active_containers(self) -> list[str]:
        """Get list of active container names (Non-blocking)."""
        if not self.client:
            return []

        def _list():
            try:
                containers = self.client.containers.list()
                return [c.name for c in containers]
            except DockerException as e:
                logger.error("Error getting active containers: %s", e)
                return []

        return await self._run_blocking(_list)

    async def is_container_running(self, container_name: str) -> bool:
        """Check if a specific container is running."""
        active = await self.get_active_containers()
        return container_name in active

    def _get_compose_file(self, container_name: str) -> Optional[str]:
        """Get the docker compose file path for a container."""
        path = self.monitored_containers.get(container_name)
        if path and os.path.exists(path):
            return path
        return None

    async def perform_action(self, action: str, container_name: str) -> bool:
        """Executes start/stop/restart logic using docker compose."""
        compose_file = self._get_compose_file(container_name)
        if not compose_file:
            logger.error(f"No compose file found for {container_name}")
            return False

        match action:
            case "start":
                command = f"docker compose -f {compose_file} up -d"
            case "stop":
                command = f"docker compose -f {compose_file} stop"
            case "restart":
                command = f"docker compose -f {compose_file} restart"
            case _:
                return False

        logger.debug(f"Executing docker command: {command}")
        code, _, stderr = await self.shell_service.execute(command)
        if code != 0:
            logger.error(f"Docker action failed: {stderr}")
            return False
        return True

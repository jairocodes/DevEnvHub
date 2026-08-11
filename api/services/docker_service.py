import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import docker


def _container_stats(container) -> dict:
    stats = container.stats(stream=False)
    mem_usage_mb, mem_limit_mb, mem_percent = _memory_stats(stats)
    return {
        "service": container.labels.get("com.docker.compose.service", container.name),
        "cpu_percent": _cpu_percent(stats),
        "mem_usage_mb": mem_usage_mb,
        "mem_limit_mb": mem_limit_mb,
        "mem_percent": mem_percent,
        "uptime_seconds": _uptime_seconds(container.attrs["State"]["StartedAt"]),
    }


def _cpu_percent(stats: dict) -> float:
    cpu_usage = stats.get("cpu_stats", {}).get("cpu_usage", {})
    precpu_usage = stats.get("precpu_stats", {}).get("cpu_usage", {})
    cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get("total_usage", 0)
    system_delta = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - stats.get(
        "precpu_stats", {}
    ).get("system_cpu_usage", 0)
    online_cpus = stats.get("cpu_stats", {}).get("online_cpus") or len(
        cpu_usage.get("percpu_usage") or [1]
    )
    if cpu_delta > 0 and system_delta > 0:
        return round((cpu_delta / system_delta) * online_cpus * 100, 2)
    return 0.0


def _memory_stats(stats: dict) -> tuple[float, float, float]:
    memory = stats.get("memory_stats", {})
    usage = memory.get("usage", 0)
    cache = memory.get("stats", {}).get("cache", 0)
    limit = memory.get("limit", 0) or 1
    net_usage = max(usage - cache, 0)
    usage_mb = round(net_usage / (1024 * 1024), 2)
    limit_mb = round(limit / (1024 * 1024), 2)
    mem_percent = round((net_usage / limit) * 100, 2) if limit else 0.0
    return usage_mb, limit_mb, mem_percent


def _parse_docker_time(value: str) -> datetime:
    # Docker reports nanosecond precision; datetime.fromisoformat only accepts up to 6 digits.
    value = re.sub(r"(\.\d{6})\d*Z$", r"\1Z", value)
    return datetime.fromisoformat(value)


def _uptime_seconds(started_at: str) -> int:
    started = _parse_docker_time(started_at)
    if started.year <= 1:
        return 0
    return max(int((datetime.now(UTC) - started).total_seconds()), 0)


class DockerService:
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self) -> docker.DockerClient:
        # Connecting lazily means importing this module (and api.main, and
        # every test that imports it) doesn't require a running Docker daemon.
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def ping(self) -> bool:
        return self.client.ping()

    def list_containers(self, project_name: str) -> list:
        return self.client.containers.list(
            all=True, filters={"label": f"com.docker.compose.project={project_name}"}
        )

    def get_stats(self, project_name: str) -> list[dict]:
        containers = self.list_containers(project_name)
        if not containers:
            return []
        # container.stats(stream=False) takes ~1-2s each; fetching them
        # concurrently keeps a multi-service environment's snapshot fast.
        with ThreadPoolExecutor(max_workers=len(containers)) as executor:
            return list(executor.map(_container_stats, containers))

    def stream_logs(self, project_name: str) -> Iterator[str]:
        containers = self.list_containers(project_name)
        if not containers:
            return
        # Environments can have more than one container (app + nginx +
        # postgres + redis); prefer the main "app" service over an
        # arbitrary one when it exists.
        container = next(
            (c for c in containers if c.labels.get("com.docker.compose.service") == "app"),
            containers[0],
        )
        for chunk in container.logs(stream=True, follow=True, tail=100):
            yield chunk.decode("utf-8", errors="replace").rstrip("\n")

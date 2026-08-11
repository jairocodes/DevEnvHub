from pathlib import Path

from api.core.paths import TEMPLATES_DIR
from api.services.compose_service import ComposeService


def test_prepare_workspace_renders_resource_limits(tmp_path: Path) -> None:
    service = ComposeService()
    workspace = tmp_path / "workspace"

    compose_file = service.prepare_workspace(
        TEMPLATES_DIR / "node",
        workspace,
        {
            "port": 3000,
            "cpu_limit": 0.5,
            "mem_limit_mb": 512,
            "runtime_version": "20",
            "include_postgres": True,
            "include_redis": True,
        },
    )

    rendered = compose_file.read_text()
    assert 'cpus: "0.5"' in rendered
    assert 'memory: "512M"' in rendered
    assert "{{ cpu_limit }}" not in rendered


def test_prepare_workspace_node_without_services(tmp_path: Path) -> None:
    service = ComposeService()
    workspace = tmp_path / "workspace"

    compose_file = service.prepare_workspace(
        TEMPLATES_DIR / "node",
        workspace,
        {
            "port": 3000,
            "cpu_limit": 0.5,
            "mem_limit_mb": 512,
            "runtime_version": "20",
            "include_postgres": False,
            "include_redis": False,
        },
    )

    rendered = compose_file.read_text()
    assert "postgres" not in rendered
    assert "redis" not in rendered
    assert "depends_on" not in rendered


def test_prepare_workspace_laravel_nginx_fpm_variant(tmp_path: Path) -> None:
    service = ComposeService()
    workspace = tmp_path / "workspace"

    compose_file = service.prepare_workspace(
        TEMPLATES_DIR / "laravel",
        workspace,
        {
            "port": 8080,
            "cpu_limit": 0.5,
            "mem_limit_mb": 512,
            "runtime_version": "8.3",
            "server": "nginx-fpm",
            "include_postgres": True,
            "include_redis": True,
        },
    )

    rendered = compose_file.read_text()
    assert "nginx:" in rendered
    assert "php-fpm:" in rendered
    assert "Dockerfile.fpm" in rendered
    assert (workspace / "nginx.conf").is_file()
    assert "listen 8080" in (workspace / "nginx.conf").read_text()

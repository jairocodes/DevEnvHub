from pathlib import Path

from api.core.paths import TEMPLATES_DIR
from api.services.compose_service import ComposeService


def test_prepare_workspace_renders_resource_limits(tmp_path: Path) -> None:
    service = ComposeService()
    workspace = tmp_path / "workspace"

    compose_file = service.prepare_workspace(
        TEMPLATES_DIR / "node",
        workspace,
        {"port": 3000, "cpu_limit": 0.5, "mem_limit_mb": 512},
    )

    rendered = compose_file.read_text()
    assert 'cpus: "0.5"' in rendered
    assert 'memory: "512M"' in rendered
    assert "{{ cpu_limit }}" not in rendered

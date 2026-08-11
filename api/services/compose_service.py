import json
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

from jinja2 import Template


class ComposeError(RuntimeError):
    pass


class ComposeService:
    RENDERED_FILES: ClassVar[set[str]] = {
        "docker-compose.yml",
        "Dockerfile",
        "Dockerfile.fpm",
        "pom.xml",
        "nginx.conf",
    }

    def prepare_workspace(self, template_dir: Path, workspace: Path, context: dict) -> Path:
        workspace.mkdir(parents=True, exist_ok=True)
        for item in template_dir.iterdir():
            if item.name in ("template.yaml", "README.md"):
                continue
            if item.name in self.RENDERED_FILES:
                rendered = Template(item.read_text()).render(**context)
                (workspace / item.name).write_text(rendered)
            elif item.is_dir():
                shutil.copytree(
                    item,
                    workspace / item.name,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            else:
                shutil.copy(item, workspace / item.name)
        return workspace / "docker-compose.yml"

    def up(self, compose_file: Path, project_name: str) -> None:
        self._run(["up", "-d", "--build"], compose_file, project_name)

    def down(self, compose_file: Path, project_name: str) -> None:
        self._run(["down"], compose_file, project_name)

    def ps(self, compose_file: Path, project_name: str) -> list[dict]:
        output = self._run(["ps", "--format", "json"], compose_file, project_name, capture=True)
        return [json.loads(line) for line in output.splitlines() if line.strip()]

    def _run(
        self, args: list[str], compose_file: Path, project_name: str, capture: bool = False
    ) -> str:
        cmd = ["docker", "compose", "-p", project_name, "-f", str(compose_file), *args]
        result = subprocess.run(
            cmd, cwd=compose_file.parent, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise ComposeError(result.stderr.strip())
        return result.stdout if capture else ""

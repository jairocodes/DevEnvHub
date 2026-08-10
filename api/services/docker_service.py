from collections.abc import Iterator

import docker


class DockerService:
    def __init__(self) -> None:
        self.client = docker.from_env()

    def ping(self) -> bool:
        return self.client.ping()

    def list_containers(self, project_name: str) -> list:
        return self.client.containers.list(
            all=True, filters={"label": f"com.docker.compose.project={project_name}"}
        )

    def stream_logs(self, project_name: str) -> Iterator[str]:
        containers = self.list_containers(project_name)
        if not containers:
            return
        container = containers[0]
        for chunk in container.logs(stream=True, follow=True, tail=100):
            yield chunk.decode("utf-8", errors="replace").rstrip("\n")

from pathlib import Path


class ComposeService:
    def up(self, project_path: Path) -> None:
        raise NotImplementedError

    def down(self, project_path: Path) -> None:
        raise NotImplementedError

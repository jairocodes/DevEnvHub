import yaml
from fastapi import APIRouter

from api.core.paths import TEMPLATES_DIR

router = APIRouter(prefix="/templates", tags=["templates"])


def _load_templates() -> list[dict]:
    templates = []
    for entry in sorted(TEMPLATES_DIR.iterdir()):
        manifest = entry / "template.yaml"
        if manifest.is_file():
            templates.append(yaml.safe_load(manifest.read_text()))
    return templates


@router.get("")
def list_templates() -> list[dict]:
    return _load_templates()

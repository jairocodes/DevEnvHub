import asyncio
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import settings
from api.core.paths import BASE_DIR, TEMPLATES_DIR
from api.db.session import get_db
from api.models.environment import Environment
from api.schemas.environment import EnvironmentCreate, EnvironmentOut
from api.services.compose_service import ComposeError, ComposeService
from api.services.docker_service import DockerService

router = APIRouter(prefix="/environments", tags=["environments"])

DbSession = Annotated[Session, Depends(get_db)]

compose_service = ComposeService()
docker_service = DockerService()

# Auth isn't wired up yet (see api/core/security.py) — every environment is
# scoped to this placeholder user until JWT auth lands on these endpoints.
CURRENT_USER_ID = 1


def _workspace_for(user_id: int, name: str) -> Path:
    return BASE_DIR / settings.data_dir / "environments" / str(user_id) / name


def _allocate_port(db: Session, default_port: int) -> int:
    used_ports = {
        env.port
        for env in db.scalars(select(Environment).where(Environment.status == "running"))
    }
    port = default_port
    while port in used_ports:
        port += 1
    return port


@router.get("", response_model=list[EnvironmentOut])
def list_environments(db: DbSession) -> list[Environment]:
    return list(db.scalars(select(Environment).where(Environment.user_id == CURRENT_USER_ID)))


@router.post("", response_model=EnvironmentOut, status_code=201)
def create_environment(payload: EnvironmentCreate, db: DbSession) -> Environment:
    template_dir = TEMPLATES_DIR / payload.template
    manifest_file = template_dir / "template.yaml"
    if not manifest_file.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown template '{payload.template}'")
    manifest = yaml.safe_load(manifest_file.read_text())

    project_name = f"devenv-{CURRENT_USER_ID}-{payload.name}"
    port = _allocate_port(db, manifest["default_port"])

    environment = Environment(
        user_id=CURRENT_USER_ID,
        name=payload.name,
        template=payload.template,
        project_name=project_name,
        port=port,
        status="starting",
    )
    db.add(environment)
    db.commit()
    db.refresh(environment)

    workspace = _workspace_for(CURRENT_USER_ID, payload.name)
    try:
        compose_file = compose_service.prepare_workspace(template_dir, workspace, {"port": port})
        compose_service.up(compose_file, project_name)
    except ComposeError as exc:
        environment.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    environment.status = "running"
    db.commit()
    db.refresh(environment)
    return environment


@router.delete("/{environment_id}", status_code=204)
def delete_environment(environment_id: int, db: DbSession) -> None:
    environment = db.get(Environment, environment_id)
    if environment is None or environment.user_id != CURRENT_USER_ID:
        raise HTTPException(status_code=404, detail="Environment not found")

    workspace = _workspace_for(CURRENT_USER_ID, environment.name)
    compose_file = workspace / "docker-compose.yml"
    if compose_file.is_file():
        compose_service.down(compose_file, environment.project_name)

    db.delete(environment)
    db.commit()


@router.websocket("/{environment_id}/logs")
async def stream_logs(websocket: WebSocket, environment_id: int, db: DbSession) -> None:
    environment = db.get(Environment, environment_id)
    if environment is None or environment.user_id != CURRENT_USER_ID:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    # docker-py's log stream is a blocking generator; pulling each item on a
    # worker thread keeps the event loop free to serve other connections.
    log_iter = docker_service.stream_logs(environment.project_name)
    try:
        while True:
            line = await asyncio.to_thread(next, log_iter, None)
            if line is None:
                break
            await websocket.send_text(line)
    except WebSocketDisconnect:
        pass

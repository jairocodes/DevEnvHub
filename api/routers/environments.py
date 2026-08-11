import asyncio
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.core.config import settings
from api.core.deps import DbSession, get_current_user, get_current_user_ws
from api.core.paths import BASE_DIR, TEMPLATES_DIR
from api.models.environment import Environment
from api.models.user import User
from api.schemas.environment import EnvironmentCreate, EnvironmentOut
from api.services.compose_service import ComposeError, ComposeService
from api.services.docker_service import DockerService

router = APIRouter(prefix="/environments", tags=["environments"])

CurrentUser = Annotated[User, Depends(get_current_user)]

compose_service = ComposeService()
docker_service = DockerService()


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


def _resolve_options(manifest: dict, submitted: dict[str, str | bool]) -> dict[str, str | bool]:
    declared = {option["key"]: option for option in manifest.get("options", [])}
    unknown = set(submitted) - set(declared)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Unknown template option(s): {', '.join(sorted(unknown))}"
        )

    resolved: dict[str, str | bool] = {}
    for key, option in declared.items():
        value = submitted.get(key, option["default"])
        if option["type"] == "choice" and value not in option["choices"]:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid value for '{key}': must be one of {option['choices']}",
            )
        if option["type"] == "boolean" and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"Invalid value for '{key}': must be true/false")
        resolved[key] = value
    return resolved


@router.get("", response_model=list[EnvironmentOut])
def list_environments(db: DbSession, current_user: CurrentUser) -> list[Environment]:
    return list(db.scalars(select(Environment).where(Environment.user_id == current_user.id)))


@router.post("", response_model=EnvironmentOut, status_code=201)
def create_environment(
    payload: EnvironmentCreate, db: DbSession, current_user: CurrentUser
) -> Environment:
    max_environments = current_user.max_environments or settings.default_max_environments
    running_count = db.scalar(
        select(func.count())
        .select_from(Environment)
        .where(Environment.user_id == current_user.id, Environment.status == "running")
    )
    if running_count >= max_environments:
        raise HTTPException(
            status_code=429,
            detail=f"Environment quota exceeded ({max_environments} running environments max)",
        )

    template_dir = TEMPLATES_DIR / payload.template
    manifest_file = template_dir / "template.yaml"
    if not manifest_file.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown template '{payload.template}'")
    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    options = _resolve_options(manifest, payload.options)

    project_name = f"devenv-{current_user.id}-{payload.name}"
    port = _allocate_port(db, manifest["default_port"])
    cpu_limit = current_user.cpu_limit or settings.default_cpu_limit
    mem_limit_mb = current_user.mem_limit_mb or settings.default_mem_limit_mb

    environment = Environment(
        user_id=current_user.id,
        name=payload.name,
        template=payload.template,
        project_name=project_name,
        port=port,
        status="starting",
    )
    db.add(environment)
    db.commit()
    db.refresh(environment)

    workspace = _workspace_for(current_user.id, payload.name)
    try:
        compose_file = compose_service.prepare_workspace(
            template_dir,
            workspace,
            {"port": port, "cpu_limit": cpu_limit, "mem_limit_mb": mem_limit_mb, **options},
        )
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
def delete_environment(environment_id: int, db: DbSession, current_user: CurrentUser) -> None:
    environment = db.get(Environment, environment_id)
    if environment is None or environment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Environment not found")

    workspace = _workspace_for(current_user.id, environment.name)
    compose_file = workspace / "docker-compose.yml"
    if compose_file.is_file():
        compose_service.down(compose_file, environment.project_name)

    db.delete(environment)
    db.commit()


@router.websocket("/{environment_id}/logs")
async def stream_logs(
    websocket: WebSocket, environment_id: int, db: DbSession, token: str | None = None
) -> None:
    current_user = get_current_user_ws(token, db) if token else None
    if current_user is None:
        await websocket.close(code=4001)
        return

    environment = db.get(Environment, environment_id)
    if environment is None or environment.user_id != current_user.id:
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


@router.websocket("/{environment_id}/metrics")
async def stream_metrics(
    websocket: WebSocket, environment_id: int, db: DbSession, token: str | None = None
) -> None:
    current_user = get_current_user_ws(token, db) if token else None
    if current_user is None:
        await websocket.close(code=4001)
        return

    environment = db.get(Environment, environment_id)
    if environment is None or environment.user_id != current_user.id:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    try:
        while True:
            containers = await asyncio.to_thread(docker_service.get_stats, environment.project_name)
            await websocket.send_json({"containers": containers})
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass

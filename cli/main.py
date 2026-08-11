import asyncio
import json
import os
from pathlib import Path

import click
import httpx
import websockets

API_BASE_URL = os.environ.get("DEVENV_API_URL", "http://localhost:8000")
CONFIG_PATH = Path.home() / ".devenv" / "config.json"


def _save_token(token: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"access_token": token}))


def _load_token() -> str:
    if not CONFIG_PATH.is_file():
        raise click.ClickException("Not logged in. Run 'devenv login' first.")
    return json.loads(CONFIG_PATH.read_text())["access_token"]


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_load_token()}"}


@click.group()
def cli() -> None:
    """devenv - CLI para gestionar entornos de desarrollo con Docker Compose."""


@cli.command()
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def register(email: str, password: str) -> None:
    """Crea una cuenta nueva."""
    response = httpx.post(
        f"{API_BASE_URL}/auth/register", json={"email": email, "password": password}, timeout=30
    )
    if response.status_code >= 400:
        raise click.ClickException(response.json().get("detail", response.text))
    click.echo("Account created. Run 'devenv login' to authenticate.")


@cli.command()
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True)
def login(email: str, password: str) -> None:
    """Inicia sesión y guarda el token localmente."""
    response = httpx.post(
        f"{API_BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=30
    )
    if response.status_code >= 400:
        raise click.ClickException(response.json().get("detail", response.text))
    _save_token(response.json()["access_token"])
    click.echo("Logged in.")


@cli.command()
@click.argument("name")
@click.option("--template", required=True, help="Template a usar (ej. node)")
@click.option(
    "--set",
    "set_options",
    multiple=True,
    metavar="KEY=VALUE",
    help="Fija una opción del template sin preguntar (repetible, ej. --set include_redis=false)",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="No preguntar interactivamente; usa los defaults del template para lo no fijado con --set",
)
def up(name: str, template: str, set_options: tuple[str, ...], yes: bool) -> None:
    """Levanta un entorno a partir de un template."""
    provided: dict[str, str] = {}
    for item in set_options:
        if "=" not in item:
            raise click.ClickException(f"--set espera key=value, recibido: '{item}'")
        key, value = item.split("=", 1)
        provided[key] = value

    options = _resolve_template_options(template, provided, interactive=not yes)

    response = httpx.post(
        f"{API_BASE_URL}/environments",
        json={"name": name, "template": template, "options": options},
        headers=_auth_headers(),
        timeout=600,
    )
    if response.status_code >= 400:
        raise click.ClickException(response.json().get("detail", response.text))
    env = response.json()
    click.echo(f"Environment '{env['name']}' running on port {env['port']}")


def _resolve_template_options(
    template: str, provided: dict[str, str], interactive: bool
) -> dict[str, str | bool]:
    response = httpx.get(f"{API_BASE_URL}/templates", timeout=30)
    response.raise_for_status()
    manifest = next((t for t in response.json() if t["name"] == template), None)
    if manifest is None:
        raise click.ClickException(f"Unknown template '{template}'")

    resolved: dict[str, str | bool] = {}
    for option in manifest.get("options", []):
        key = option["key"]
        if key in provided:
            resolved[key] = _coerce_option_value(option, provided[key])
        elif interactive:
            resolved[key] = _prompt_for_option(option)
    return resolved


def _coerce_option_value(option: dict, raw: str) -> str | bool:
    if option["type"] == "boolean":
        return raw.strip().lower() in ("1", "true", "yes", "y")
    return raw


def _prompt_for_option(option: dict) -> str | bool:
    label = option.get("label", option["key"])
    if option["type"] == "boolean":
        return click.confirm(label, default=option.get("default", False))
    if option["type"] == "choice":
        return click.prompt(
            label, type=click.Choice(option["choices"]), default=option.get("default")
        )
    return click.prompt(label, default=option.get("default"))


@cli.command()
def ls() -> None:
    """Lista los entornos activos."""
    response = httpx.get(f"{API_BASE_URL}/environments", headers=_auth_headers(), timeout=30)
    response.raise_for_status()
    environments = response.json()
    if not environments:
        click.echo("No environments found.")
        return
    for env in environments:
        click.echo(f"{env['id']}\t{env['name']}\t{env['template']}\t{env['status']}\tport {env['port']}")


@cli.command()
@click.argument("name")
def logs(name: str) -> None:
    """Muestra los logs en vivo de un entorno."""
    response = httpx.get(f"{API_BASE_URL}/environments", headers=_auth_headers(), timeout=30)
    response.raise_for_status()
    match = next((env for env in response.json() if env["name"] == name), None)
    if match is None:
        raise click.ClickException(f"Environment '{name}' not found")

    ws_url = f"{API_BASE_URL.replace('http', 'ws', 1)}/environments/{match['id']}/logs?token={_load_token()}"
    asyncio.run(_print_logs(ws_url))


async def _print_logs(ws_url: str) -> None:
    async with websockets.connect(ws_url) as websocket:
        async for line in websocket:
            click.echo(line)


@cli.command()
@click.argument("name")
def stats(name: str) -> None:
    """Muestra métricas de uso (CPU/memoria/uptime) en vivo de un entorno."""
    response = httpx.get(f"{API_BASE_URL}/environments", headers=_auth_headers(), timeout=30)
    response.raise_for_status()
    match = next((env for env in response.json() if env["name"] == name), None)
    if match is None:
        raise click.ClickException(f"Environment '{name}' not found")

    ws_url = f"{API_BASE_URL.replace('http', 'ws', 1)}/environments/{match['id']}/metrics?token={_load_token()}"
    asyncio.run(_print_metrics(ws_url))


async def _print_metrics(ws_url: str) -> None:
    async with websockets.connect(ws_url) as websocket:
        async for message in websocket:
            data = json.loads(message)
            for container in data["containers"]:
                click.echo(
                    f"{container['service']}\t"
                    f"cpu {container['cpu_percent']}%\t"
                    f"mem {container['mem_usage_mb']}/{container['mem_limit_mb']} MB "
                    f"({container['mem_percent']}%)\t"
                    f"uptime {container['uptime_seconds']}s"
                )
            click.echo("---")


if __name__ == "__main__":
    cli()

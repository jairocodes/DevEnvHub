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
def up(name: str, template: str) -> None:
    """Levanta un entorno a partir de un template."""
    response = httpx.post(
        f"{API_BASE_URL}/environments",
        json={"name": name, "template": template},
        headers=_auth_headers(),
        timeout=120,
    )
    if response.status_code >= 400:
        raise click.ClickException(response.json().get("detail", response.text))
    env = response.json()
    click.echo(f"Environment '{env['name']}' running on port {env['port']}")


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


if __name__ == "__main__":
    cli()

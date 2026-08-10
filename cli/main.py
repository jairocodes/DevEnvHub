import asyncio
import os

import click
import httpx
import websockets

API_BASE_URL = os.environ.get("DEVENV_API_URL", "http://localhost:8000")


@click.group()
def cli() -> None:
    """devenv - CLI para gestionar entornos de desarrollo con Docker Compose."""


@cli.command()
@click.argument("name")
@click.option("--template", required=True, help="Template a usar (ej. node)")
def up(name: str, template: str) -> None:
    """Levanta un entorno a partir de un template."""
    response = httpx.post(
        f"{API_BASE_URL}/environments", json={"name": name, "template": template}, timeout=120
    )
    if response.status_code >= 400:
        raise click.ClickException(response.json().get("detail", response.text))
    env = response.json()
    click.echo(f"Environment '{env['name']}' running on port {env['port']}")


@cli.command()
def ls() -> None:
    """Lista los entornos activos."""
    response = httpx.get(f"{API_BASE_URL}/environments", timeout=30)
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
    response = httpx.get(f"{API_BASE_URL}/environments", timeout=30)
    response.raise_for_status()
    match = next((env for env in response.json() if env["name"] == name), None)
    if match is None:
        raise click.ClickException(f"Environment '{name}' not found")

    ws_url = f"{API_BASE_URL.replace('http', 'ws', 1)}/environments/{match['id']}/logs"
    asyncio.run(_print_logs(ws_url))


async def _print_logs(ws_url: str) -> None:
    async with websockets.connect(ws_url) as websocket:
        async for line in websocket:
            click.echo(line)


if __name__ == "__main__":
    cli()

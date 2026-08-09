import click


@click.group()
def cli() -> None:
    """devenv - CLI para gestionar entornos de desarrollo con Docker Compose."""


@cli.command()
def up() -> None:
    """Levanta el entorno definido en devenv.yaml (not implemented yet)."""
    click.echo("not implemented yet")


@cli.command()
def ls() -> None:
    """Lista los entornos activos (not implemented yet)."""
    click.echo("not implemented yet")


@cli.command()
def logs() -> None:
    """Muestra los logs de un entorno (not implemented yet)."""
    click.echo("not implemented yet")


if __name__ == "__main__":
    cli()

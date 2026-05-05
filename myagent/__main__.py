"""Module entrypoint for ``python -m myagent``."""

from myagent.cli.commands import app


def main() -> None:
    """Run the Typer CLI application."""
    app()

if __name__ == "__main__":
    main()

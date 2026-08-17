"""Flask CLI commands: seed, reset-db."""
from __future__ import annotations
import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db
from app.services.seed import seed_demo_data


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed_cmd)
    app.cli.add_command(reset_db_cmd)


@click.command("seed")
@with_appcontext
def seed_cmd():
    """Seed the DB with a demo teacher, student, bank, and exam."""
    result = seed_demo_data()
    if result["created"]:
        click.echo(f"Seeded: {result['teacher']} / {result['student']}  (password: {result['password']})")
    else:
        click.echo(f"Skipped seed: {result['reason']}.")


@click.command("reset-db")
@with_appcontext
def reset_db_cmd():
    """Drop and recreate all tables. Dev only."""
    click.confirm("This will DROP ALL TABLES. Continue?", abort=True)
    db.drop_all()
    db.create_all()
    click.echo("Database reset.")

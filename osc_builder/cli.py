from datetime import datetime, timezone
from typing import TextIO

import click
from dateutil.parser import parse as parse_datetime

from .build import build_dist, convert_csvs


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.argument("variables_file", type=click.File("r"))
@click.argument("themes_file", type=click.File("r"))
@click.argument("projects_file", type=click.File("r"))
@click.argument("products_file", type=click.File("r"))
@click.option("--out-dir", "-o", default="data", type=str)
@click.option("--update-timestamp")
def convert(
    variables_file: TextIO,
    themes_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
    update_timestamp: str = None,
):
    now = datetime.utcnow().replace(tzinfo=timezone.utc, microsecond=0)
    convert_csvs(
        variables_file, themes_file, projects_file, products_file, out_dir,
        parse_datetime(update_timestamp) if update_timestamp else now
    )


@cli.command()
@click.argument("data_dir", type=str)
@click.option("--out-dir", "-o", default="dist", type=str)
@click.option("--root-href", "-r", default="", type=str)
@click.option("--pretty-print/--no-pretty-print", default=True)
@click.option("--add-iso/--no-add-iso", default=True)
@click.option("--updated-files")
@click.option("--update-timestamp")
def build(
    data_dir: str,
    out_dir: str,
    pretty_print: bool,
    root_href: str,
    add_iso: bool,
    updated_files: str,
    update_timestamp: str,
):
    now = datetime.utcnow().replace(tzinfo=timezone.utc, microsecond=0)
    build_dist(
        data_dir,
        out_dir,
        pretty_print,
        root_href,
        add_iso,
        updated_files.split(",") if updated_files else [],
        parse_datetime(update_timestamp) if update_timestamp else now
    )


if __name__ == "__main__":
    cli(obj={})

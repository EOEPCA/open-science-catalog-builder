from typing import TextIO

import click

from .build import convert_csvs, validate_catalog, build_dist


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.argument("variables_file", type=click.File("r"))
@click.argument("themes_file", type=click.File("r"))
@click.argument("eo_missions_file", type=click.File("r"))
@click.argument("projects_file", type=click.File("r"))
@click.argument("products_file", type=click.File("r"))
@click.option("--out-dir", "-o", default="data", type=str)
def convert(
    variables_file: TextIO,
    themes_file: TextIO,
    eo_missions_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
):
    convert_csvs(
        variables_file,
        themes_file,
        eo_missions_file,
        projects_file,
        products_file,
        out_dir,
    )


@cli.command()
@click.argument("data_dir", type=str)
def validate(data_dir: str):
    validate_catalog(data_dir)


@cli.command()
@click.argument("data_dir", type=str)
@click.option("--out-dir", "-o", default="dist", type=str)
@click.option("--root-href", "-r", default="", type=str)
@click.option("--pretty-print/--no-pretty-print", default=True)
@click.option("--add-iso/--no-add-iso", default=True)
@click.option("--update-timestamps/--no-update-timestamps", default=True)
def build(
    data_dir: str,
    out_dir: str,
    pretty_print: bool,
    root_href: str,
    add_iso: bool,
    update_timestamps: bool,
):
    build_dist(
        data_dir,
        out_dir,
        root_href,
        add_iso,
        pretty_print,
        update_timestamps,
    )


if __name__ == "__main__":
    cli(obj={})

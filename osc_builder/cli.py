from typing import TextIO

import click

from .build import convert_csvs, validate_catalog, build_dist, build_metrics
from . import origcsv


@click.group()
@click.pass_context
def cli(ctx):
    pass


ENCODING = "ISO-8859-1"


@cli.command()
@click.argument("variables_file", type=click.File("r", encoding=ENCODING))
@click.argument("themes_file", type=click.File("r", encoding=ENCODING))
@click.argument("eo_missions_file", type=click.File("r", encoding=ENCODING))
@click.argument("projects_file", type=click.File("r", encoding=ENCODING))
@click.argument("products_file", type=click.File("r", encoding=ENCODING))
@click.option("--out-dir", "-o", default="data", type=str)
@click.option("--validate-csvs/--no-validate-csvs", default=True)
def convert(
    variables_file: TextIO,
    themes_file: TextIO,
    eo_missions_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
    validate_csvs: bool,
):
    if validate_csvs:
        print("Validating CSVs...")
        issues = origcsv.validate_csvs(
            variables_file,
            themes_file,
            eo_missions_file,
            projects_file,
            products_file,
        )
        if issues:
            for issue in issues:
                print(issue)
            print(f"Found {len(issues)} issues")
        else:
            print("No issues found")

        variables_file.seek(0)
        themes_file.seek(0)
        eo_missions_file.seek(0)
        projects_file.seek(0)
        products_file.seek(0)

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


@cli.command()
@click.argument("data_dir", type=str)
@click.option("--out", "-o", default="metrics.json", type=str)
@click.option("--add-to-root/--dont-add-to-root", default=True)
def metrics(
    data_dir: str,
    out: str,
    add_to_root: bool,
):
    build_metrics(
        data_dir,
        out,
        add_to_root,
    )


if __name__ == "__main__":
    cli(obj={})

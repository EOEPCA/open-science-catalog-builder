from typing import TextIO
import json
import os

import click
import pystac

from .stac import build_catalog, save_catalog
from .origcsv import (
    load_orig_variables,
    load_orig_themes,
    load_orig_projects,
    load_orig_products,
)
from .metrics import build_metrics
from .codelist import build_codelists
from .io import load_products, load_projects, load_themes, load_variables, store_variables, store_themes, store_projects, store_products


@click.group()
@click.pass_context
def cli(ctx):
    click.echo("cli")


@cli.command()
@click.argument("variables_file", type=click.File("r"))
@click.argument("themes_file", type=click.File("r"))
@click.argument("projects_file", type=click.File("r"))
@click.argument("products_file", type=click.File("r"))
@click.option("--out-dir", "-o", default="data", type=str)
def convert(
    variables_file: TextIO,
    themes_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
):
    variables = load_orig_variables(variables_file)
    themes = load_orig_themes(themes_file)
    projects = load_orig_projects(projects_file)
    products = load_orig_products(products_file)

    store_variables(variables, f"{out_dir}/variables")
    store_themes(themes, f"{out_dir}/themes")
    store_projects(projects, f"{out_dir}/projects")
    store_products(products, f"{out_dir}/products")


@cli.command()
@click.argument("data_dir", type=str)
@click.option("--out-dir", "-o", default="dist", type=str)
@click.option("--pretty-print/--no-pretty-print", default=True)
def build(data_dir: str, out_dir: str, pretty_print: bool):
    variables = load_variables(f"{data_dir}/variables")
    themes = load_themes(f"{data_dir}/themes")
    projects = load_projects(f"{data_dir}/projects")
    products = load_products(f"{data_dir}/products")

    catalog = build_catalog(themes, variables, projects, products)

    os.makedirs(out_dir, exist_ok=True)

    metrics = build_metrics("OSC-Catalog", themes, variables, projects, products)
    with open(f"{out_dir}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2 if pretty_print else None)

    tree = build_codelists(themes, variables, [])
    tree.write(f"{out_dir}/codelists.xml", pretty_print=pretty_print)

    catalog.add_link(pystac.Link(pystac.RelType.ALTERNATE, "./metrics.json", "application/json"))
    catalog.add_link(pystac.Link(pystac.RelType.ALTERNATE, "./codelists.xml", "application/xml"))
    save_catalog(catalog, out_dir)


if __name__ == "__main__":
    cli(obj={})

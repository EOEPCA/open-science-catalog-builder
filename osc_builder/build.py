import json
from math import prod
import os
import shutil
from typing import TextIO
from urllib.parse import urljoin

import pystac

from .codelist import build_codelists
from .io import (
    load_products,
    load_projects,
    load_themes,
    load_variables,
    store_products,
    store_projects,
    store_themes,
    store_variables,
)
from .iso import generate_product_metadata, generate_project_metadata
from .origcsv import (
    load_orig_products,
    load_orig_projects,
    load_orig_themes,
    load_orig_variables,
)
from .metrics import build_metrics
from .stac import build_catalog, save_catalog


def convert_csvs(
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

    store_variables(variables, os.path.join(out_dir, "variables"))
    store_themes(themes, os.path.join(out_dir, "themes"))
    store_projects(projects, os.path.join(out_dir, "projects"))
    store_products(products, os.path.join(out_dir, "products"))


def build_dist(data_dir: str, out_dir: str, pretty_print: bool, root_href: str):
    variables = load_variables(os.path.join(data_dir, "variables"))
    themes = load_themes(os.path.join(data_dir, "themes"))
    projects = load_projects(os.path.join(data_dir, "projects"))
    products = load_products(os.path.join(data_dir, "products"))

    catalog, project_items, product_items = build_catalog(themes, variables, projects, products)

    # making sure output directories exist
    os.makedirs(os.path.join(out_dir, "projects/iso"))
    os.makedirs(os.path.join(out_dir, "products/iso"))

    project_parent_identifiers = {
        project.name: project.id
        for project in projects
    }

    for project, project_item in project_items:
        iso_xml = generate_project_metadata(project)
        href = os.path.join("./iso", f"{project.id}.xml")
        with open(os.path.join(out_dir, "projects", href), "w") as f:
            f.write(iso_xml)
        project_item.add_asset(
            "iso-metadata", pystac.Asset(href, roles=["metadata"])
        )

    for product, product_item in product_items:
        iso_xml = generate_product_metadata(
            product, project_parent_identifiers.get(product.project)
        )
        href = os.path.join("./iso", f"{product.id}.xml")
        with open(os.path.join(out_dir, "products", href), "w") as f:
            f.write(iso_xml)
        product_item.add_asset(
            "iso-metadata", pystac.Asset(href, roles=["metadata"])
        )

    metrics = build_metrics("OSC-Catalog", themes, variables, projects, products)
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2 if pretty_print else None)

    tree = build_codelists(themes, variables, [])
    tree.write(os.path.join(out_dir, "codelists.xml"), pretty_print=pretty_print)

    catalog.add_link(
        pystac.Link(pystac.RelType.ALTERNATE, urljoin(root_href, "metrics.json"), "application/json")
    )
    catalog.add_link(
        pystac.Link(pystac.RelType.ALTERNATE, urljoin(root_href, "codelists.xml"), "application/xml")
    )
    save_catalog(catalog, out_dir, root_href)

    # copy image directories if they exist
    for typedir in ["variables", "themes", "projects", "products"]:
        src_dir = os.path.join(data_dir, typedir, "images")
        if os.path.isdir(src_dir):
            shutil.copytree(
                src_dir,
                os.path.join(out_dir, typedir, "images"),
                dirs_exist_ok=True,
            )

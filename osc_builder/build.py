from datetime import datetime
import json
from itertools import chain
import os
import os.path
import shutil
from typing import TextIO, Optional, List
from urllib.parse import urljoin

import pystac
from slugify import slugify

from .codelist import build_codelists
from .io import (
    load_product_items,
    load_project_items,
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
    update_timestamp: datetime,
):
    variables = load_orig_variables(variables_file)
    themes = load_orig_themes(themes_file)
    projects = load_orig_projects(projects_file)
    products = load_orig_products(products_file)

    store_variables(variables, os.path.join(out_dir, "variables"))
    store_themes(themes, os.path.join(out_dir, "themes"))
    store_projects(
        projects, os.path.join(out_dir, "projects"), update_timestamp
    )
    store_products(
        products, os.path.join(out_dir, "products"), update_timestamp
    )


def build_dist(
    data_dir: str,
    out_dir: str,
    pretty_print: bool,
    root_href: str,
    add_iso_metadata: bool = True,
    updated_files: Optional[List[str]] = None,
    update_timestamp: str = "",
):
    variables = load_variables(os.path.join(data_dir, "variables"))
    themes = load_themes(os.path.join(data_dir, "themes"))
    project_items = load_project_items(os.path.join(data_dir, "projects"))
    product_items = load_product_items(os.path.join(data_dir, "products"))

    # update the "updated" field
    for updated_file in updated_files or []:
        items = chain(
            (item[1] for item in project_items),
            (item[1] for item in product_items),
        )
        for item in items:
            try:
                if os.path.samefile(item.self_href, updated_file):
                    pystac.CommonMetadata(item).updated = update_timestamp
                    break
            except FileNotFoundError:
                print(f"updated file {updated_file} not found")
                break
        else:
            print(f"updated file {updated_file} not found")

    catalog = build_catalog(themes, variables, project_items, product_items)

    # making sure output directories exist
    os.makedirs(os.path.join(out_dir, "projects/iso"))
    os.makedirs(os.path.join(out_dir, "products/iso"))

    project_parent_identifiers = {
        project[0].name: project[0].id for project in project_items
    }

    if add_iso_metadata:
        # generate ISO metadata for each project and add it as an asset
        for project, project_item in project_items:
            iso_xml = generate_project_metadata(
                project,
                urljoin(root_href, f"projects/{slugify(project.title)}.json"),
            )
            href = os.path.join("./iso", f"{project.id}.xml")
            with open(os.path.join(out_dir, "projects", href), "w") as f:
                f.write(iso_xml)
            project_item.add_asset(
                "iso-metadata", pystac.Asset(href, roles=["metadata"])
            )

        # generate ISO metadata for each product and add it as an asset
        for product, product_item in product_items:
            iso_xml = generate_product_metadata(
                product,
                project_parent_identifiers.get(product.project),
                urljoin(root_href, f"products/{slugify(product.title)}.json"),
            )
            href = os.path.join("./iso", f"{product.id}.xml")
            with open(os.path.join(out_dir, "products", href), "w") as f:
                f.write(iso_xml)
            product_item.add_asset(
                "iso-metadata", pystac.Asset(href, roles=["metadata"])
            )

    metrics = build_metrics(
        "OSC-Catalog",
        themes,
        variables,
        [project[0] for project in project_items],
        [product[0] for product in product_items],
    )
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2 if pretty_print else None)

    tree = build_codelists(themes, variables, [])
    tree.write(
        os.path.join(out_dir, "codelists.xml"), pretty_print=pretty_print
    )

    catalog.add_link(
        pystac.Link(
            pystac.RelType.ALTERNATE,
            urljoin(root_href, "metrics.json"),
            "application/json",
        )
    )
    catalog.add_link(
        pystac.Link(
            pystac.RelType.ALTERNATE,
            urljoin(root_href, "codelists.xml"),
            "application/xml",
        )
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

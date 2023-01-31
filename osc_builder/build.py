from datetime import datetime
import json
from itertools import chain
import os
import os.path
import shutil
from typing import TextIO, Optional, List
from urllib.parse import urljoin

import pystac
import pystac.layout

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
    load_orig_eo_missions,
)
from .metrics import build_metrics
from .stac import build_catalog, save_catalog
from .stac import collection_from_product, collection_from_project


def convert_csvs(
    variables_file: TextIO,
    themes_file: TextIO,
    eo_missions_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
    update_timestamp: datetime,
):
    variables = load_orig_variables(variables_file)
    themes = load_orig_themes(themes_file)
    projects = load_orig_projects(projects_file)
    products = load_orig_products(products_file)
    eo_missions = load_orig_eo_missions(eo_missions_file)

    root = pystac.Collection(
        "Open Science Catalog",
        "",
        extent=pystac.Extent(
            pystac.SpatialExtent([-180.0, -90.0, 180.0, 90.0]),
            pystac.TemporalExtent([[None, None]]),
        ),
    )

    project_map: dict[str, pystac.Collection] = {}
    for project in projects:
        collection = collection_from_project(project)
        project_map[collection.id] = collection
        root.add_child(collection)

    product_map: dict[str, pystac.Collection] = {}

    for product in products:
        collection = collection_from_product(product)
        product_map[collection.id] = collection
        project_map[slugify(product.project)].add_child(collection)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "themes.json"), "w") as f:
        json.dump(
            [
                {
                    "name": theme.name,
                    "description": theme.description,
                    "link": theme.link,
                    "image": theme.image,
                }
                for theme in themes
            ],
            f,
            indent=2,
        )
    with open(os.path.join(out_dir, "variables.json"), "w") as f:
        json.dump(
            [
                {
                    "name": variable.name,
                    "description": variable.description,
                    "link": variable.link,
                    "theme": variable.theme,
                }
                for variable in variables
            ],
            f,
            indent=2,
        )
    with open(os.path.join(out_dir, "eo-missions.json"), "w") as f:
        json.dump(
            [
                {
                    "name": eo_mission.name,
                }
                for eo_mission in eo_missions
            ],
            f,
            indent=2,
        )

    # root stuff
    root.add_asset(
        "themes",
        pystac.Asset("./themes.json", "Themes", "Themes", "application/json"),
    )
    root.add_asset(
        "variables",
        pystac.Asset(
            "./variables.json", "Variables", "Variables", "application/json"
        ),
    )
    root.add_asset(
        "eo-missions",
        pystac.Asset(
            "./eo-missions.json",
            "EO Missions",
            "EO Missions",
            "application/json",
        ),
    )

    root.normalize_hrefs(
        out_dir,
        pystac.layout.TemplateLayoutStrategy(
            item_template="items/${id}/${id}.json",
            collection_template="collections/${id}/collection.json",
        ),
    )

    root.save(pystac.CatalogType.ABSOLUTE_PUBLISHED, out_dir)

    # store_variables(variables, os.path.join(out_dir, "variables"))
    # store_themes(themes, os.path.join(out_dir, "themes"))
    # store_projects(
    #     projects, os.path.join(out_dir, "projects"), update_timestamp
    # )
    # store_products(
    #     products, os.path.join(out_dir, "products"), update_timestamp
    # )


def validate_project(
    collection: pystac.Collection, themes: set[str]
) -> list[str]:
    errors = []
    for theme in collection.extra_fields["osc:themes"]:
        if theme not in themes:
            errors.append(f"Theme '{theme}' not valid")
    return errors


def validate_product(
    collection: pystac.Collection,
    themes: set[str],
    variables: set[str],
    eo_missions: set[str],
) -> list[str]:
    errors = []
    variable = collection.extra_fields["osc:variable"]
    if variable not in variables:
        errors.append(f"Variable '{variable}' not valid")
    for theme in collection.extra_fields["osc:themes"]:
        if theme not in themes:
            errors.append(f"Theme '{theme}' not valid")
    for eo_mission in collection.extra_fields["osc:missions"]:
        if eo_mission not in eo_missions:
            errors.append(f"EO Mission '{eo_mission}' not valid")
    return errors


def validate_catalog(data_dir: str):
    root: pystac.Collection = pystac.read_file(
        os.path.join(data_dir, "collection.json")
    )
    assets = root.get_assets()
    with open(os.path.join(data_dir, assets["themes"].href)) as f:
        themes = {theme["name"] for theme in json.load(f)}
    with open(os.path.join(data_dir, assets["variables"].href)) as f:
        variables = {variable["name"] for variable in json.load(f)}
    with open(os.path.join(data_dir, assets["eo-missions"].href)) as f:
        eo_missions = {eo_mission["name"] for eo_mission in json.load(f)}

    validation_errors = []

    for project_collection in root.get_children():
        ret = validate_project(project_collection, themes)
        if ret:
            validation_errors.append((project_collection, ret))
        for product_collection in project_collection.get_children():
            ret = validate_product(
                product_collection, themes, variables, eo_missions
            )
            if ret:
                validation_errors.append((product_collection, ret))

    # TODO: raise Exception if validation_errors


def build_dist(data_dir: str, out_dir: str, root_href: str, add_iso_metadata: bool = True):
    shutil.copytree(
        data_dir,
        out_dir,
        # dirs_exist_ok=True,
    )

    root: pystac.Collection = pystac.read_file(
        os.path.join(out_dir, "collection.json")
    )

    root.normalize_hrefs(
        root_href,
        pystac.layout.TemplateLayoutStrategy(
            item_template="items/${id}/${id}.json",
            collection_template="collections/${id}/collection.json",
        ),
    )
    root.make_all_asset_hrefs_absolute()
    root.save(
        pystac.CatalogType.ABSOLUTE_PUBLISHED,
        out_dir
    )


def _build_dist(
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
                urljoin(root_href, f"projects/{slugify(project_item.id)}.json"),
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
                urljoin(root_href, f"products/{slugify(product_item.id)}.json"),
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

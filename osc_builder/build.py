from datetime import datetime, timezone
import json
import os
import os.path
import shutil
from typing import TextIO
from urllib.parse import urlparse

import pystac
import pystac.layout
import pystac.utils

from slugify import slugify

from .codelist import build_codelists
from .iso import generate_product_metadata, generate_project_metadata
from .origcsv import (
    load_orig_products,
    load_orig_projects,
    load_orig_themes,
    load_orig_variables,
    load_orig_eo_missions,
)
from .metrics import build_metrics
from .stac import (
    MISSIONS_PROP,
    VARIABLE_PROP,
    THEMES_PROP,
    collection_from_product,
    collection_from_project,
    FakeHTTPStacIO,
)
from .types import Theme, Variable, EOMission


# LAYOUT_STRATEGY = pystac.layout.TemplateLayoutStrategy(
#     item_template="items/${id}/${id}.json",
#     collection_template="collections/${id}/collection.json",
# )


def convert_csvs(
    variables_file: TextIO,
    themes_file: TextIO,
    eo_missions_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
    out_dir: str,
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

    # Add themes, variables and eo-missions JSON files as assets
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
        # LAYOUT_STRATEGY,
    )

    root.save(pystac.CatalogType.SELF_CONTAINED, out_dir)


def validate_project(
    collection: pystac.Collection, themes: set[str]
) -> list[str]:
    errors = []
    for theme in collection.extra_fields[THEMES_PROP]:
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
    variable = collection.extra_fields[VARIABLE_PROP]
    if variable not in variables:
        errors.append(f"Variable '{variable}' not valid")
    for theme in collection.extra_fields[THEMES_PROP]:
        if theme not in themes:
            errors.append(f"Theme '{theme}' not valid")
    for eo_mission in collection.extra_fields[MISSIONS_PROP]:
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

    from pprint import pprint

    pprint(validation_errors)
    # TODO: raise Exception if validation_errors


def set_update_timestamps(
    catalog: pystac.Catalog, stac_io: pystac.StacIO
) -> datetime:
    """Updates the `updated` field in the catalog according to the underlying
    files last modification time and its included Items and children. This also
    updates the included STAC Items `updated` property respectively.

    This function recurses into its child catalogs.

    The resulting `updated` time is the latest of the following:

        - the child catalogs `updated` timestamp, which are resolved first
        - its directly included items
        - the modification time of the catalog file itself

    Args:
        catalog (pystac.Catalog): the catalog to update the timestamp for

    Returns:
        datetime: the resulting timestamp
    """

    io = None
    if isinstance(stac_io, FakeHTTPStacIO):
        io = stac_io

    href = catalog.get_self_href()
    path = io._replace_path(href) if io else href
    updated = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)

    for child in catalog.get_children():
        updated = max(updated, set_update_timestamps(child, stac_io))

    for item in catalog.get_items():
        href = item.get_self_href()
        path = io._replace_path(href) if io else href
        item_updated = datetime.fromtimestamp(
            os.path.getmtime(path), tz=timezone.utc
        )
        pystac.CommonMetadata(item).updated = item_updated
        updated = max(updated, item_updated)

    pystac.CommonMetadata(catalog).updated = updated
    return updated


def make_collection_assets_absolute(collection: pystac.Collection):
    for asset in collection.assets.values():
        asset.href = pystac.utils.make_absolute_href(
            asset.href, collection.get_self_href()
        )


def build_dist(
    data_dir: str,
    out_dir: str,
    root_href: str,
    add_iso_metadata: bool = True,
    pretty_print: bool = True,
    update_timestamps: bool = True,
):
    shutil.copytree(
        data_dir,
        out_dir,
    )

    stac_io = FakeHTTPStacIO(out_dir, urlparse(root_href).path)
    pystac.StacIO.set_default(stac_io)
    root: pystac.Collection = pystac.read_file(
        os.path.join(root_href, "collection.json"), stac_io=stac_io
    )

    # new_root = pystac.Catalog("ABC", "abc")
    # new_root.set_self_href(os.path.join(root_href, "catalog.json"))
    # new_root.add_children(root.get_children())
    # new_root.save()
    # root = new_root

    if update_timestamps:
        set_update_timestamps(root, stac_io)

    assets = root.assets
    with open(os.path.join(data_dir, assets["themes"].href)) as f:
        themes = [Theme(**theme) for theme in json.load(f)]
    with open(os.path.join(data_dir, assets["variables"].href)) as f:
        variables = [Variable(**variable) for variable in json.load(f)]
    with open(os.path.join(data_dir, assets["eo-missions"].href)) as f:
        eo_missions = [EOMission(**eo_mission) for eo_mission in json.load(f)]

    # root.normalize_hrefs(root_href)

    # Handle ISO metadata
    if add_iso_metadata:
        for project_collection in root.get_children():
            # create and store ISO metadata for the project
            iso_xml = generate_project_metadata(project_collection)
            href = os.path.join(
                out_dir,
                project_collection.id,
                "iso.xml",
            )
            with open(href, "w") as f:
                f.write(iso_xml)
            project_collection.add_asset(
                "iso-metadata",
                pystac.Asset(
                    "./iso.xml",
                    roles=["metadata"],
                    media_type="application/xml",
                ),
            )
            make_collection_assets_absolute(project_collection)

            # create and store ISO metadata for the products
            for product_collection in project_collection.get_children():
                iso_xml = generate_product_metadata(product_collection)
                href = os.path.join(
                    out_dir,
                    project_collection.id,
                    product_collection.id,
                    "iso.xml",
                )
                with open(href, "w") as f:
                    f.write(iso_xml)
                product_collection.add_asset(
                    "iso-metadata",
                    pystac.Asset(
                        "./iso.xml",
                        roles=["metadata"],
                        media_type="application/xml",
                    ),
                )
                make_collection_assets_absolute(project_collection)

    # create and store metrics for the root
    metrics = build_metrics(
        "OSC-Catalog",
        root,
        themes,
        variables,
        eo_missions,
    )
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2 if pretty_print else None)

    root.add_asset(
        "metrics",
        pystac.Asset(
            "./metrics.json", roles=["metadata"], media_type="application/json"
        ),
    )

    # create and store codelists
    tree = build_codelists(themes, variables, eo_missions)
    tree.write(
        os.path.join(out_dir, "codelists.xml"), pretty_print=pretty_print
    )
    root.add_asset(
        "codelists",
        pystac.Asset(
            "./codelists.xml", roles=["metadata"], media_type="application/xml"
        ),
    )

    # make all collection assets absolute
    make_collection_assets_absolute(root)

    # final href adjustments
    root.make_all_asset_hrefs_absolute()
    root.normalize_hrefs(root_href)
    root.save(pystac.CatalogType.ABSOLUTE_PUBLISHED, root_href)

    for catalog, _, items in root.walk():
        catalog.save(pystac.CatalogType.ABSOLUTE_PUBLISHED)

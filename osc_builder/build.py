from datetime import datetime, timezone
import json
import mimetypes
import os
import os.path
import shutil
from typing import TextIO, Optional
from urllib.parse import urlparse

import pystac
import pystac.layout
import pystac.link
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


mimetypes.add_type("image/webp", ".webp")

# to fix https://github.com/stac-utils/pystac/issues/1112
if "related" not in pystac.link.HIERARCHICAL_LINKS:
    pystac.link.HIERARCHICAL_LINKS.append("related")


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
    catalog_url: Optional[str],
):
    variables = load_orig_variables(variables_file)
    themes = load_orig_themes(themes_file)
    projects = load_orig_projects(projects_file)
    products = load_orig_products(products_file)
    eo_missions = load_orig_eo_missions(eo_missions_file)

    # set root structure
    root = pystac.Catalog(
        "osc",
        "A catalog of publicly available geoscience products, datasets and resources developed in the frame of scientific research Projects funded by ESA EO (Earth Observation)",
        "Open Science Catalog",
    )
    projects_catalog = pystac.Catalog(
        "projects", "Activities funded by ESA", "Projects"
    )
    products_catalog = pystac.Catalog(
        "products",
        "Geoscience products representing the measured or inferred values of one or more variables over a given time range and spatial area",
        "Products",
    )
    themes_catalog = pystac.Catalog(
        "themes",
        "Earth Science topics linked to the grand science challenges set in the ESA strategy",
        "Themes",
    )
    variables_catalog = pystac.Catalog(
        "variables",
        "Geoscience, climate and environmental variables",
        "Variables",
    )
    processes_catalog = pystac.Catalog(
        "processes", "Processes for reproducible science", "Processes"
    )
    eo_missions_catalog = pystac.Catalog(
        "eo-missions",
        "Earth Obeservation Satellite Missions by ESA",
        "EO Missions",
    )

    # add the first level catalogs
    # IMPORTANT: the order is important here, to ensure that the products
    # end up beneath their collection
    # see https://github.com/stac-utils/pystac/issues/1116
    root.add_child(projects_catalog)
    root.add_child(themes_catalog)
    root.add_child(variables_catalog)
    root.add_child(processes_catalog)
    root.add_child(eo_missions_catalog)
    root.add_child(products_catalog)

    themes_map: dict[str, pystac.Catalog] = {}
    for theme in themes:
        catalog = pystac.Catalog(
            id=theme.name, description=theme.description, title=theme.name
        )
        themes_map[theme.name] = catalog
        if theme.image:
            catalog.add_link(
                pystac.Link(
                    rel="preview",
                    target=theme.image,
                    media_type=mimetypes.guess_type(theme.image)[0],
                    title="Image",
                    extra_fields={
                        "proj:epsg": None,
                        "proj:shape": [1080, 1920],
                    },
                )
            )
        catalog.add_link(
            pystac.Link(
                rel=pystac.RelType.VIA,
                target=theme.link,
                media_type="text/html",
                title="Description",
            )
        )
        themes_catalog.add_child(catalog)

    variables_map: dict[str, pystac.Catalog] = {}
    for variable in variables:
        catalog = pystac.Catalog(
            id=variable.name,
            description=variable.description,
            title=variable.name,
        )
        catalog.add_links(
            [
                pystac.Link(
                    rel=pystac.RelType.VIA,
                    target=variable.link,
                    media_type="text/html",
                    title="Description",
                ),
            ]
            + [
                pystac.Link(
                    rel="related",
                    target=themes_map[theme_name],
                    media_type="application/json",
                    title=f"Theme: {themes_map[theme_name].title}",
                )
                for theme_name in variable.themes
            ]
        )
        variables_catalog.add_child(catalog)

        variables_map[variable.name] = catalog

    eo_missions_map: dict[str, pystac.Catalog] = {}
    for eo_mission in eo_missions:
        catalog = pystac.Catalog(
            id=eo_mission.name,
            description=eo_mission.name,
            title=eo_mission.name,
        )
        eo_missions_catalog.add_child(catalog)
        eo_missions_map[eo_mission.name] = catalog

    # add projects
    project_map: dict[str, pystac.Collection] = {}
    for project in projects:
        collection = collection_from_project(project)
        project_map[collection.id] = collection

        # add links to themes
        collection.add_links(
            [
                pystac.Link(
                    rel="related",
                    target=themes_map[theme],
                    media_type="application/json",
                    title=f"Theme: {themes_map[theme].title}",
                )
                for theme in project.themes
            ]
        )

        projects_catalog.add_child(collection)

    # add products
    product_map: dict[str, pystac.Collection] = {}
    for product in products:
        collection = collection_from_product(product)
        product_map[collection.id] = collection
        products_catalog.add_child(collection)

        # link projects/products
        project_collection = project_map[slugify(product.project)]
        collection.add_link(
            pystac.Link(
                rel="related",
                target=project_collection,
                media_type="application/json",
                title=f"Project: {project_collection.title}",
            )
        )
        project_collection.add_link(
            pystac.Link(
                rel="related",
                target=collection,
                media_type="application/json",
                title=f"Product: {collection.title}",
            )
        )

        # add links to themes
        for theme in product.themes:
            theme_catalog = themes_map[theme]
            collection.add_link(
                pystac.Link(
                    rel="related",
                    target=theme_catalog,
                    media_type="application/json",
                    title=f"Theme: {theme_catalog.title}",
                )
            )
            theme_catalog.add_child(collection)

        variable_catalog = variables_map[product.variable]
        collection.add_link(
            pystac.Link(
                rel="related",
                target=variable_catalog,
                media_type="application/json",
                title=f"Variable: {variable_catalog.title}",
            )
        )
        variable_catalog.add_child(collection)

        for eo_mission in product.eo_missions:
            eo_mission_catalog = eo_missions_map[eo_mission]
            collection.add_link(
                pystac.Link(
                    rel="related",
                    target=eo_mission_catalog,
                    media_type="application/json",
                    title=f"EO Mission: {eo_mission_catalog.title}",
                )
            )
            eo_mission_catalog.add_child(collection)

    # save catalog
    root.normalize_and_save(out_dir, pystac.CatalogType.SELF_CONTAINED)

    # TODO: move theme images if exist
    if os.path.isdir("images"):
        for catalog in themes_map.values():
            link = catalog.get_single_link(rel="preview")
            if link:
                out_path = os.path.join(
                    os.path.dirname(catalog.get_self_href()), link.href
                )
                shutil.copyfile(
                    os.path.join("images", link.href),
                    out_path,
                )


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
) -> Optional[datetime]:
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
        Optional[datetime]: the resulting timestamp
    """

    io = None
    if isinstance(stac_io, FakeHTTPStacIO):
        io = stac_io

    href = catalog.get_self_href()
    path = io._replace_path(href) if io else href

    if urlparse(path).scheme not in ("", "file"):
        return None

    updated = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)

    for child_link in catalog.get_child_links():
        if urlparse(child_link.get_href()).scheme not in ("", "file"):
            continue
        child = child_link.resolve_stac_object().target
        child_updated = set_update_timestamps(child, stac_io)
        if child_updated:
            updated = max(updated, child_updated)

    for item in catalog.get_items():
        href = item.get_self_href()
        path = io._replace_path(href) if io else href

        if urlparse(path).scheme not in ("", "file"):
            continue

        item_updated = datetime.fromtimestamp(
            os.path.getmtime(path), tz=timezone.utc
        )
        pystac.CommonMetadata(item).updated = item_updated
        updated = max(updated, item_updated)

    if updated:
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
    root: pystac.Collection = pystac.read_file(
        os.path.join(out_dir, "collection.json")
    )

    if update_timestamps:
        set_update_timestamps(root, None)

    assets = root.assets
    with open(os.path.join(data_dir, assets["themes"].href)) as f:
        themes = [Theme(**theme) for theme in json.load(f)]
    with open(os.path.join(data_dir, assets["variables"].href)) as f:
        variables = [Variable.from_raw(**variable) for variable in json.load(f)]
    with open(os.path.join(data_dir, assets["eo-missions"].href)) as f:
        eo_missions = [EOMission(**eo_mission) for eo_mission in json.load(f)]

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

    # ensure that all data items beneath a product reference the product
    # collection.
    # for project_collection in root.get_children():
    #     for product_collection in project_collection.get_children():
    #         for item in product_collection.get_all_items():
    #             item.set_collection(product_collection)

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
    # make_collection_assets_absolute(root)

    # final href adjustments
    # root.make_all_asset_hrefs_absolute()
    root.save(pystac.CatalogType.SELF_CONTAINED, dest_href=out_dir)

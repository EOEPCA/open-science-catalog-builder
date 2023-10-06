from datetime import datetime, timezone
import json
import os
import os.path
import shutil
from typing import TextIO, Optional, Iterable, List
from urllib.parse import urlparse
from itertools import chain

import pystac
import pystac.layout
import pystac.link
import pystac.utils
from slugify import slugify
from .mystac import STACObject, normpath, make_absolute_hrefs

# from .iso import generate_product_metadata, generate_project_metadata
from .origcsv import (
    load_orig_products,
    load_orig_projects,
    load_orig_themes,
    load_orig_variables,
    load_orig_eo_missions,
)
from .metrics import caclulate_metrics
from .stac import (
    PROJECT_PROP,
    MISSIONS_PROP,
    VARIABLES_PROP,
    THEMES_PROP,
    REGION_PROP,
    collection_from_product,
    collection_from_project,
    catalog_from_theme,
    catalog_from_variable,
    catalog_from_eo_mission,
    get_theme_id,
    get_variable_id,
    get_eo_mission_id,
)

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

    themes_catalog.add_children(
        sorted(
            (catalog_from_theme(theme) for theme in themes),
            key=lambda catalog: catalog.id,
        )
    )
    variables_catalog.add_children(
        sorted(
            (catalog_from_variable(variable) for variable in variables),
            key=lambda catalog: catalog.id,
        )
    )
    eo_missions_catalog.add_children(
        sorted(
            (catalog_from_eo_mission(eo_mission) for eo_mission in eo_missions),
            key=lambda catalog: catalog.id,
        )
    )
    projects_catalog.add_children(
        sorted(
            (collection_from_project(project) for project in projects),
            key=lambda collection: collection.id,
        )
    )
    products_catalog.add_children(
        sorted(
            (collection_from_product(product) for product in products),
            key=lambda collection: collection.id,
        )
    )

    # save catalog
    root.normalize_and_save(out_dir, pystac.CatalogType.SELF_CONTAINED)

    # TODO: move theme images if exist
    if os.path.isdir("images"):
        for catalog in themes_catalog.get_children():
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
    variable = collection.extra_fields[VARIABLES_PROP]
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


def set_update_timestamps(path: str, catalog: STACObject) -> Optional[datetime]:
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

    if urlparse(path).scheme not in ("", "file"):
        return None

    updated = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)

    for link in catalog.get_links("child"):
        child_href = link["href"]
        # only follow relative links
        if urlparse(child_href).scheme not in ("", "file"):
            continue

        child_path = normpath(path, child_href)
        child = STACObject.from_file(child_path)

        child_updated = set_update_timestamps(child_path, child)
        if child_updated:
            updated = max(updated, child_updated)

    for link in catalog.get_links("item"):
        item_href = link["href"]
        if urlparse(item_href).scheme not in ("", "file"):
            continue

        item_path = normpath(path, item_href)
        item_updated = datetime.fromtimestamp(
            os.path.getmtime(item_path), tz=timezone.utc
        )
        item = STACObject.from_file(item_path)
        item.set_updated(item_updated, properties=True)
        item.save()
        updated = max(updated, item_updated)

    if updated:
        catalog.set_updated(updated)
        catalog.save()

    return updated


def link_collections(
    product_collections: Iterable[STACObject],
    project_collections: Iterable[STACObject],
    theme_catalogs: Iterable[STACObject],
    variable_catalogs: Iterable[STACObject],
    eo_mission_catalogs: Iterable[STACObject],
):
    themes_map: dict[str, STACObject] = {
        catalog["id"]: catalog for catalog in theme_catalogs
    }
    variables_map: dict[str, STACObject] = {
        catalog["id"]: catalog for catalog in variable_catalogs
    }
    eo_missions_map: dict[str, STACObject] = {
        catalog["id"]: catalog for catalog in eo_mission_catalogs
    }
    project_map: dict[str, STACObject] = {
        collection["id"]: collection for collection in project_collections
    }

    # link variable -> themes
    for variable_catalog in variable_catalogs:
        for theme_name in variable_catalog.get(THEMES_PROP, []):
            theme = themes_map[get_theme_id(theme_name)]
            variable_catalog.add_object_link(
                theme,
                rel="related",
                title=f"Theme: {theme['title']}",
            )

    # link projects -> themes
    for project_collection in project_collections:
        for theme_name in project_collection.get(THEMES_PROP, []):
            theme = themes_map[get_theme_id(theme_name)]
            project_collection.add_object_link(
                theme,
                rel="related",
                title=f"Theme: {theme['title']}",
            )

    # link products
    for product_collection in product_collections:
        # product -> project
        project_collection = project_map[
            slugify(product_collection[PROJECT_PROP])
        ]
        print(f"Linking {product_collection['id']} -> {project_collection['id']}")
        product_collection.add_object_link(
            project_collection,
            rel="related",
            title=f"Project: {project_collection['title']}",
        )
        project_collection.add_object_link(
            product_collection,
            rel="child",
            title=f"Product: {product_collection['title']}",
        )

        # product -> themes
        for theme_name in product_collection.get(THEMES_PROP, []):
            theme = themes_map[get_theme_id(theme_name)]
            print(f"Linking {product_collection['id']} -> {theme['id']}")
            product_collection.add_object_link(
                theme,
                rel="related",
                title=f"Theme: {theme['title']}",
            )
            theme.add_object_link(
                product_collection,
                rel="child",
                title=f"Product: {product_collection['title']}",
            )

        # product -> variables
        for variable_name in product_collection.get(VARIABLES_PROP, []):
            variable = variables_map[get_variable_id(variable_name)]
            print(f"Linking {product_collection['id']} -> {variable['id']}")
            product_collection.add_object_link(
                variable,
                rel="related",
                title=f"Variable: {variable['title']}",
            )
            variable.add_object_link(
                product_collection,
                rel="child",
                title=f"Product: {product_collection['title']}",
            )

        # product -> eo mission
        for eo_mission_name in product_collection.get(MISSIONS_PROP, []):
            eo_mission = eo_missions_map[get_eo_mission_id(eo_mission_name)]
            print(f"Linking {product_collection['id']} -> {eo_mission['id']}")
            product_collection.add_object_link(
                eo_mission,
                rel="related",
                title=f"EO Mission: {eo_mission['title']}",
            )
            eo_mission.add_object_link(
                product_collection,
                rel="child",
                title=f"Product: {product_collection['title']}",
            )


def apply_keywords(catalog: STACObject):
    keywords = catalog.get("keywords", [])
    keywords.extend(
        f"theme:{name}" for name in catalog.get(THEMES_PROP, [])
    )
    keywords.extend(
        f"variable:{name}"
        for name in catalog.get(VARIABLES_PROP, [])
    )
    keywords.extend(
        f"mission:{name}"
        for name in catalog.get(MISSIONS_PROP, [])
    )
    if region := catalog.get(REGION_PROP):
        keywords.append(f"region:{region}")
    if project := catalog.get(PROJECT_PROP):
        keywords.append(f"project:{project}")

    if len(keywords) > 0:
        catalog["keywords"] = keywords


def build_dist(
    data_dir: str,
    out_dir: str,
    root_href: str,
    add_iso_metadata: bool = True, # unused
    pretty_print: bool = True, # unused
    update_timestamps: bool = True,
):
    shutil.copytree(
        data_dir,
        out_dir,
    )
    root_path = os.path.join(out_dir, "catalog.json")
    root = STACObject.from_file(root_path)

    if update_timestamps:
        set_update_timestamps(root_path, root)

    products = list(root.get_child("products").get_children())
    projects = list(root.get_child("projects").get_children())
    themes = list(root.get_child("themes").get_children())
    variables = list(root.get_child("variables").get_children())
    eo_missions = list(root.get_child("eo-missions").get_children())

    link_collections(
        products,
        projects,
        themes,
        variables,
        eo_missions,
    )

    indent = 2 if pretty_print else None

    # Apply keywords
    catalogs = chain(
        products,
        projects,
        themes,
        variables,
        eo_missions,
    )
    for catalog in catalogs:
        apply_keywords(catalog)
        catalog.save(indent=indent)

    make_absolute_hrefs(root, root_href, "catalog.json", indent)


def build_metrics(
    data_dir: str,
    metrics_file_name: str,
    add_to_root: bool,
    pretty_print: bool = True,
):
    root: pystac.Catalog = pystac.read_file(
        os.path.join(data_dir, "catalog.json")
    )

    metrics = caclulate_metrics("OSC-Catalog", root)

    with open(os.path.join(data_dir, metrics_file_name), "w") as f:
        json.dump(metrics, f, indent=2 if pretty_print else None)

    if add_to_root:
        root.add_link(
            pystac.Link(
                rel="alternate",
                target=metrics_file_name,
                media_type="application/json",
                title="Metrics",
            )
        )
    root.save_object()

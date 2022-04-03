from datetime import date, datetime, time
import mimetypes
import os
import os.path
from typing import Generic, List, Optional, Tuple, TypeVar, Union, cast
from urllib.parse import urljoin, urlparse, urlunparse

from slugify import slugify
import pystac
import pystac.extensions.scientific
import pystac.layout
from pystac.extensions.base import ExtensionManagementMixin, PropertiesExtension
from dateutil.parser import parse as parse_datetime
import pygeoif.geometry

from .codelist import build_codelists
from .metrics import build_metrics
from .types import Contact, Product, Project, Status, Theme, Variable


T = TypeVar("T", pystac.Catalog, pystac.Collection, pystac.Item)

# TODO: fix schema URL
SCHEMA_URI: str = "https://stac-extensions.github.io/osc/v1.0.0/schema.json"
PREFIX: str = "osc:"

TYPE_PROP = f"{PREFIX}type"
PROJECT_PROP = f"{PREFIX}project"
NAME_PROP = f"{PREFIX}name"
THEME_PROP = f"{PREFIX}theme"
THEMES_PROP = f"{PREFIX}themes"
VARIABLE_PROP = f"{PREFIX}variable"
STATUS_PROP = f"{PREFIX}status"
REGION_PROP = f"{PREFIX}region"
CONSORTIUM_PROP = f"{PREFIX}consortium"
TECHNICAL_OFFICER_PROP = f"{PREFIX}technical_officer"
MISSIONS_PROP = f"{PREFIX}missions"


class OSCExtension(
    Generic[T],
    PropertiesExtension,
    ExtensionManagementMixin[Union[pystac.Catalog, pystac.Collection, pystac.Item]],
):
    obj: pystac.STACObject

    def __init__(self, obj: pystac.STACObject) -> None:
        self.obj = obj

    @classmethod
    def ext(cls, obj: T, add_if_missing: bool = False) -> "OSCExtension[T]":
        if isinstance(obj, pystac.Collection):
            cls.validate_has_extension(obj, add_if_missing)
            return cast(OSCExtension[T], CollectionOSCExtension(obj))
        if isinstance(obj, pystac.Catalog):
            cls.validate_has_extension(obj, add_if_missing)
            return cast(OSCExtension[T], CatalogOSCExtension(obj))
        if isinstance(obj, pystac.Item):
            cls.validate_has_extension(obj, add_if_missing)
            return cast(OSCExtension[T], ItemOSCExtension(obj))
        else:
            raise pystac.ExtensionTypeError(
                f"OSC extension does not apply to type '{type(obj).__name__}'"
            )

    @classmethod
    def get_schema_uri(cls) -> str:
        return SCHEMA_URI


class CatalogOSCExtension(OSCExtension[pystac.Catalog]):
    pass


class CollectionOSCExtension(OSCExtension[pystac.Collection]):
    def __init__(self, collection: pystac.Collection):
        self.collection = collection

    def apply_theme(self, theme: Theme):
        self.collection.extra_fields = {
            TYPE_PROP: "Theme",
        }
        self.collection.add_link(
            pystac.Link(
                pystac.RelType.VIA,
                theme.link,
                title="Link",
            )
        )
        if theme.image:
            self.collection.add_asset(
                "image",
                pystac.Asset(
                    theme.image,
                    title="image",
                    roles=["thumbnail"],
                    media_type=mimetypes.guess_type(theme.image)[0],
                ),
            )

    def apply_variable(self, variable: Variable):
        self.collection.extra_fields = {
            THEME_PROP: variable.theme,
            TYPE_PROP: "Variable",
        }
        self.collection.add_link(
            pystac.Link(
                pystac.RelType.VIA,
                variable.link,
                title="Link",
            )
        )


class ItemOSCExtension(OSCExtension[pystac.Item]):
    def __init__(self, item: pystac.Item):
        self.item = item
        self.properties = item.properties

    def apply_product(self, product: Product):
        self.properties.update(
            {
                "title": product.title,
                "description": product.description,
                MISSIONS_PROP: product.eo_missions,
                PROJECT_PROP: product.project,
                THEMES_PROP: product.themes,
                VARIABLE_PROP: product.variable,
                STATUS_PROP: product.status.value,
                REGION_PROP: product.region,
                TYPE_PROP: "Product",
            }
        )

        if isinstance(product.released, date):
            self.properties["created"] = product.released.isoformat()
        # TODO: handle "Planned" value

        if product.start:
            self.properties["start_datetime"] = product.start.isoformat()
        if product.end:
            self.properties["end_datetime"] = product.end.isoformat()
        if product.version:
            self.properties["version"] = product.version

        self.item.add_link(
            pystac.Link(
                pystac.RelType.VIA,
                product.website,
            )
        )
        self.item.add_link(
            pystac.Link(
                pystac.RelType.VIA,
                product.access,
                title="Access",
            )
        )
        if product.documentation:
            self.item.add_link(
                pystac.Link(
                    pystac.RelType.VIA,
                    product.documentation,
                    title="Documentation",
                )
            )

    def apply_project(self, project: Project):
        self.properties.update(
            {
                "title": project.title,
                "description": project.description,
                NAME_PROP: project.name,
                THEMES_PROP: project.themes,
                STATUS_PROP: project.status.value,
                TECHNICAL_OFFICER_PROP: {
                    "name": project.technical_officer.name,
                    "e-mail": project.technical_officer.e_mail,
                },
                CONSORTIUM_PROP: project.consortium,
                TYPE_PROP: "Project",
            }
        )

        if project.start:
            self.properties["start_datetime"] = project.start.isoformat()
        if project.end:
            self.properties["end_datetime"] = project.end.isoformat()

        self.item.add_link(
            pystac.Link(
                pystac.RelType.VIA,
                project.website,
                title="Website",
            )
        )
        self.item.add_link(
            pystac.Link(
                pystac.RelType.VIA, project.eo4_society_link, title="EO4Society Link"
            )
        )


class OSCItem(pystac.Item):
    def set_collection(self, collection: Optional[pystac.Collection]) -> "OSCItem":

        # self.remove_links(pystac.RelType.COLLECTION)
        self.collection_id = None
        if collection is not None:
            self.add_link(pystac.Link.collection(collection))
            # self.collection_id = collection.id

        return self


def item_from_product(product: Product) -> pystac.Item:
    item = OSCItem(
        product.id,
        product.geometry.__geo_interface__ if product.geometry else None,
        product.geometry.bounds if product.geometry else None,
        datetime.combine(product.start, time.min) if product.start else None,
        {
            "start_datetime": None,
            "end_datetime": None,
        },
    )

    osc_ext = cast(ItemOSCExtension, OSCExtension.ext(item, True))
    osc_ext.apply_product(product)

    if product.doi:
        sci_ext = pystac.extensions.scientific.ScientificExtension.ext(item, True)
        sci_ext.apply(product.doi)

    return item


def product_from_item(item: pystac.Item) -> Product:
    properties = item.properties
    via_links = item.get_links(pystac.RelType.VIA)
    return Product(
        item.id,
        Status(properties[STATUS_PROP]),
        website=cast(str, via_links[0].get_href(False)),
        title=properties["title"],
        description=properties["description"],
        project=properties[PROJECT_PROP],
        variable=properties[VARIABLE_PROP],
        themes=properties[THEMES_PROP],
        access=cast(str, via_links[1].get_href(False)),
        documentation=via_links[2].get_href(False) if len(via_links) >= 3 else None,
        doi=None,  # TODO
        version=properties.get("version"),
        start=parse_datetime(properties["start_datetime"]).date()
        if properties.get("start_datetime")
        else None,
        end=parse_datetime(properties["end_datetime"]).date()
        if properties.get("end_datetime")
        else None,
        geometry=pygeoif.geometry.as_shape(item.geometry) if item.geometry else None,
        region=properties[REGION_PROP],
        # released=,
        eo_missions=properties[MISSIONS_PROP],
    )


def item_from_project(project: Project) -> pystac.Item:
    item = OSCItem(
        project.id,
        None,
        None,
        datetime.combine(project.start, time.min),
        {},
    )

    osc_ext = cast(ItemOSCExtension, OSCExtension.ext(item, True))
    osc_ext.apply_project(project)

    return item


def project_from_item(item: pystac.Item) -> Project:
    properties = item.properties
    via_links = item.get_links(pystac.RelType.VIA)
    return Project(
        item.id,
        Status(properties[STATUS_PROP]),
        name=properties[NAME_PROP],
        title=properties["title"],
        description=properties["description"],
        website=cast(str, via_links[0].get_href(False)),
        eo4_society_link=cast(str, via_links[1].get_href(False)),
        consortium=properties[CONSORTIUM_PROP],
        start=parse_datetime(properties["start_datetime"]).date(),
        end=parse_datetime(properties["end_datetime"]).date(),
        technical_officer=Contact(
            properties[TECHNICAL_OFFICER_PROP]["name"],
            properties[TECHNICAL_OFFICER_PROP]["e-mail"],
        ),
        themes=properties[THEMES_PROP],
    )


def collection_from_theme(theme: Theme) -> pystac.Collection:
    collection = pystac.Collection(
        theme.name,
        theme.description,
        extent=pystac.Extent(
            pystac.SpatialExtent([-180.0, -90.0, 180.0, 90.0]),
            pystac.TemporalExtent([[None, None]]),
        ),
    )
    osc_ext = cast(CollectionOSCExtension, OSCExtension.ext(collection, True))
    osc_ext.apply_theme(theme)
    return collection


def collection_from_variable(variable: Variable) -> pystac.Collection:
    collection = pystac.Collection(
        variable.name,
        variable.description,
        extent=pystac.Extent(
            pystac.SpatialExtent([-180.0, -90.0, 180.0, 90.0]),
            pystac.TemporalExtent([[None, None]]),
        ),
    )
    osc_ext = cast(CollectionOSCExtension, OSCExtension.ext(collection, True))
    osc_ext.apply_variable(variable)
    return collection


def build_catalog(
    themes: List[Theme],
    variables: List[Variable],
    projects: List[Project],
    products: List[Product],
) -> Tuple[
    pystac.Catalog, List[Tuple[Project, pystac.Item]], List[Tuple[Product, pystac.Item]]
]:
    catalog = pystac.Catalog("OSC-Catalog", "OSC-Catalog", href="catalog.json")

    # create collections/items from given themes, variables, projects and products
    theme_collections = {
        slugify(theme.name): collection_from_theme(theme) for theme in themes
    }

    variable_collections = {
        slugify(variable.name): collection_from_variable(variable)
        for variable in variables
    }

    project_items = {
        slugify(project.name): item_from_project(project) for project in projects
    }

    product_items = {product.id: item_from_product(product) for product in products}

    # place everything in its accoring collection
    for item in product_items.values():
        collection = variable_collections.get(slugify(item.properties[VARIABLE_PROP]))
        if collection:
            collection.add_item(item)
        else:
            print(f"Missing variable {item.properties[VARIABLE_PROP]}")

        project_item = project_items.get(slugify(item.properties[PROJECT_PROP]))
        if project_item:
            item.add_link(pystac.Link.collection(cast(pystac.Collection, project_item)))
            project_item.add_link(
                pystac.Link.item(item, title=item.properties["title"])
            )
        else:
            print(f"Missing project {item.properties[PROJECT_PROP]}")

    for item in project_items.values():
        for theme_name in item.properties[THEMES_PROP]:
            theme_collection = theme_collections.get(slugify(theme_name))
            if theme_collection:
                theme_collection.add_item(item)
            else:
                print(f"Missing theme {theme_name}")

    for collection in variable_collections.values():
        theme_collection = theme_collections.get(
            slugify(collection.extra_fields[THEME_PROP])
        )
        if theme_collection:
            theme_collection.add_child(collection)
        else:
            print(f"Missing theme {collection.extra_fields[THEME_PROP]}")

    catalog.add_children(theme_collections.values())

    return (
        catalog,
        list(zip(projects, project_items.values())),
        list(zip(products, product_items.values())),
    )


def save_catalog(catalog: pystac.Catalog, output_dir: str, root_href: str = ""):
    # output directory handlign
    os.makedirs(output_dir, exist_ok=True)
    catalog.normalize_hrefs(
        root_href,
        strategy=pystac.layout.CustomLayoutStrategy(
            collection_func=lambda coll, parent_dir, is_root: urljoin(
                root_href,
                f"{coll.extra_fields['osc:type'].lower()}s/{slugify(coll.id)}.json",
            ),
            item_func=lambda item, parent_dir: urljoin(
                root_href, f"{item.properties['osc:type'].lower()}s/{item.id}.json"
            ),
        ),
    )
    catalog.make_all_asset_hrefs_absolute()
    catalog.save(
        pystac.CatalogType.ABSOLUTE_PUBLISHED,
        output_dir,
    )

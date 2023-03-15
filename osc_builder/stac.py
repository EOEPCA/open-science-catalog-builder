from datetime import date, datetime, time, timezone
import os
from os.path import join
from typing import Generic, TypeVar, Union, cast
from urllib.parse import urlparse

from slugify import slugify
import pystac
import pystac.extensions.scientific
import pystac.layout
from pystac.extensions.base import (
    ExtensionManagementMixin,
    PropertiesExtension,
)
import pystac.stac_io
import pystac.link

from .types import Product, Project


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
    ExtensionManagementMixin[
        Union[pystac.Catalog, pystac.Collection, pystac.Item]
    ],
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
        self.properties = collection.extra_fields
        self.links = collection.links
        super().__init__(self.collection)

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

        common = pystac.CommonMetadata(self.collection)

        # TODO: handle "Planned" value
        if isinstance(product.released, date):
            common.created = datetime.combine(
                product.released, time.min, timezone.utc
            )

        if product.start:
            common.start_datetime = product.start
        if product.end:
            common.end_datetime = product.end
        if product.version:
            self.properties["version"] = product.version

        if product.website:
            self.collection.add_link(
                pystac.Link(
                    pystac.RelType.VIA, product.website, title="Website"
                )
            )
        if product.access:
            self.collection.add_link(
                pystac.Link(
                    pystac.RelType.VIA,
                    product.access,
                    title="Access",
                )
            )
        if product.documentation:
            self.collection.add_link(
                pystac.Link(
                    pystac.RelType.VIA,
                    product.documentation,
                    title="Documentation",
                )
            )

        self.collection.keywords = [
            f"theme:{theme}" for theme in product.themes
        ] + [f"variable:{product.variable}", f"region:{product.region}"]

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

        common = pystac.CommonMetadata(self.collection)
        if project.start:
            common.start_datetime = project.start
        if project.end:
            common.end_datetime = project.end

        if project.website:
            self.collection.add_link(
                pystac.Link(
                    pystac.RelType.VIA,
                    project.website,
                    title="Website",
                )
            )
        if project.eo4_society_link:
            self.collection.add_link(
                pystac.Link(
                    pystac.RelType.VIA,
                    project.eo4_society_link,
                    title="EO4Society Link",
                )
            )

        self.collection.keywords = [
            f"theme:{theme}" for theme in project.themes
        ]


class ItemOSCExtension(OSCExtension[pystac.Item]):
    pass


def collection_from_product(product: Product) -> pystac.Collection:
    """Create a pystac.Collection from a given Product

    Args:
        product (Product): the product to convert

    Returns:
        pystac.Collection: the created collection
    """
    slug = slugify(product.id)
    collection = pystac.Collection(
        slug,
        product.description,
        extent=pystac.Extent(
            pystac.SpatialExtent(
                product.geometry.bounds
                if product.geometry
                else [-180.0, -90.0, 180.0, 90.0]
            ),
            pystac.TemporalExtent([[product.start, product.end]]),
        ),
        title=product.title,
    )

    osc_ext: CollectionOSCExtension = OSCExtension.ext(collection, True)
    osc_ext.apply_product(product)
    if product.doi:
        sci_ext = pystac.extensions.scientific.ScientificExtension.ext(
            collection, True
        )
        sci_ext.apply(product.doi)
    return collection


def collection_from_project(project: Project) -> pystac.Item:
    collection = pystac.Collection(
        slugify(project.name),
        project.description,
        extent=pystac.Extent(
            # pystac.SpatialExtent([-180.0, -90.0, 180.0, 90.0]),
            pystac.SpatialExtent([[]]),
            pystac.TemporalExtent([[project.start, project.end]]),
        ),
        title=project.title,
    )

    osc_ext: CollectionOSCExtension = OSCExtension.ext(collection, True)
    osc_ext.apply_project(project)

    return collection


class FakeHTTPStacIO(pystac.stac_io.DefaultStacIO):
    def __init__(self, out_dir: str, path_prefix: str = "/"):
        self.out_dir = out_dir
        self.path_prefix = path_prefix

    def __call__(self):
        # to allow to set an instance as StacIO.default
        return self

    def _replace_path(self, href: str) -> str:
        path = urlparse(href).path
        if path.startswith(self.path_prefix):
            path = path[len(self.path_prefix):]

        return join(self.out_dir, path)

    def read_text(self, source: str, *args, **kwargs) -> str:
        return super().read_text(self._replace_path(source), *args, **kwargs)

    def write_text(
        self, dest: str, txt: str, *args, **kwargs
    ) -> None:
        super().write_text(self._replace_path(dest), txt, *args, **kwargs)

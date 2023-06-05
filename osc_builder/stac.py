from datetime import date, datetime, time, timezone
from os.path import join
from typing import Generic, TypeVar, Union, cast, List, Iterable
from urllib.parse import urlparse
import mimetypes

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

from .types import Product, Project, Theme, Variable, EOMission


mimetypes.add_type("image/webp", ".webp")

T = TypeVar("T", pystac.Catalog, pystac.Collection, pystac.Item)

# TODO: fix schema URL
OSC_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/osc/v1.0.0-rc.1/schema.json"
)
THEMES_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/themes/v1.0.0/schema.json"
)
CONTACTS_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/contacts/v0.1.1/schema.json"
)
PREFIX: str = "osc:"

TYPE_PROP = f"{PREFIX}type"
PROJECT_PROP = f"{PREFIX}project"
NAME_PROP = f"{PREFIX}name"
THEMES_PROP = f"{PREFIX}themes"
VARIABLES_PROP = f"{PREFIX}variables"
STATUS_PROP = f"{PREFIX}status"
REGION_PROP = f"{PREFIX}region"
MISSIONS_PROP = f"{PREFIX}missions"

OSC_THEMES_SCHEME = "OSC:SCHEME:THEMES"


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
        return OSC_SCHEMA_URI


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
                VARIABLES_PROP: product.variables,
                STATUS_PROP: product.status.value.lower(),
                REGION_PROP: product.region,
                TYPE_PROP: "product",
            }
        )
        add_themes(self.collection, product.themes)

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

        self.collection.keywords = (
            [f"theme:{theme}" for theme in product.themes]
            + [f"variable:{variable}" for variable in product.variables]
            + [f"region:{product.region}"]
        )

    def apply_project(self, project: Project):
        self.properties.update(
            {
                "title": project.title,
                "description": project.description,
                NAME_PROP: project.name,
                STATUS_PROP: project.status.value.lower(),
                TYPE_PROP: "project",
                "contacts": [
                    {
                        "name": project.technical_officer.name,
                        "role": "technical_officer",
                        "emails": [
                            {
                                "value": project.technical_officer.e_mail,
                            }
                        ],
                    }
                ]
                + [
                    {
                        "name": consortium_member,
                        "role": "consortium_member",
                    }
                    for consortium_member in project.consortium
                ],
            }
        )
        add_themes(self.collection, project.themes)
        self.collection.stac_extensions.append(CONTACTS_SCHEMA_URI)

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


def add_themes(catalog: pystac.Catalog, themes: List[str]):
    catalog.extra_fields.update(
        {
            "themes": [
                # STAC themes for OSC themes
                {
                    "scheme": OSC_THEMES_SCHEME,
                    "concepts": [{"id": theme} for theme in themes],
                }
            ]
        }
    )
    if THEMES_SCHEMA_URI not in catalog.stac_extensions:
        catalog.stac_extensions.append(THEMES_SCHEMA_URI)


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
            # todo: ESA should provide this
            pystac.SpatialExtent([-180.0, -90.0, 180.0, 90.0]),
            pystac.TemporalExtent([[project.start, project.end]]),
        ),
        title=project.title,
    )

    osc_ext: CollectionOSCExtension = OSCExtension.ext(collection, True)
    osc_ext.apply_project(project)

    return collection


def catalog_from_theme(theme: Theme) -> pystac.Catalog:
    catalog = pystac.Catalog(
        id=get_theme_id(theme.name),
        description=theme.description,
        title=theme.name,
    )
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
    return catalog


def catalog_from_variable(variable: Variable) -> pystac.Catalog:
    catalog = pystac.Catalog(
        id=get_variable_id(variable.name),
        description=variable.description,
        title=variable.name,
    )
    add_themes(catalog, variable.themes)
    catalog.add_link(
        pystac.Link(
            rel=pystac.RelType.VIA,
            target=variable.link,
            media_type="text/html",
            title="Description",
        )
    )
    return catalog


def catalog_from_eo_mission(eo_mission: EOMission) -> pystac.Catalog:
    return pystac.Catalog(
        id=get_eo_mission_id(eo_mission.name),
        description=eo_mission.name,
        title=eo_mission.name,
    )


def get_theme_id(theme_name: str):
    # return f"theme-{slugify(theme_name)}"
    return f"{slugify(theme_name)}"


def get_variable_id(variable_name: str):
    # return f"variable-{slugify(variable_name)}"
    return f"{slugify(variable_name)}"


def get_eo_mission_id(eo_mission_name: str):
    # return f"mission-{slugify(eo_mission_name)}"
    return f"{slugify(eo_mission_name)}"


def get_theme_names(catalog: pystac.Catalog) -> Iterable[str]:
    for theme in catalog.extra_fields.get("themes", []):
        if theme.get("scheme") == OSC_THEMES_SCHEME:
            return [concept["id"] for concept in theme.get("concepts", [])]


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
            path = path[len(self.path_prefix) :]

        return join(self.out_dir, path)

    def read_text(self, source: str, *args, **kwargs) -> str:
        return super().read_text(self._replace_path(source), *args, **kwargs)

    def write_text(self, dest: str, txt: str, *args, **kwargs) -> None:
        super().write_text(self._replace_path(dest), txt, *args, **kwargs)

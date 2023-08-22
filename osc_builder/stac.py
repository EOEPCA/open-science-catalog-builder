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
    "https://stac-extensions.github.io/osc/v1.0.0-rc.2/schema.json"
)
THEMES_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/themes/v1.0.0/schema.json"
)
CONTACTS_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/contacts/v0.1.1/schema.json"
)
CF_SCHEMA_URI: str = (
    "https://stac-extensions.github.io/cf/v1.0.0/schema.json"
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
STANDARD_NAME_PROP = "cf:parameter"

OSC_SCHEME_THEMES = "https://github.com/stac-extensions/osc#theme"
OSC_SCHEME_VARIABLES = "https://github.com/stac-extensions/osc#variable"
OSC_SCHEME_MISSIONS = "https://github.com/stac-extensions/osc#eo-mission"


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
                THEMES_PROP: product.themes,
                MISSIONS_PROP: product.eo_missions,
                PROJECT_PROP: product.project,
                VARIABLES_PROP: product.variables,
                STATUS_PROP: product.status.value.lower(),
                TYPE_PROP: "product",
            }
        )
        if product.standard_name:
            # ToDo: Add the schema to stac_extensions once released
            # self.collection.stac_extensions.append(CF_SCHEMA_URI)
            self.properties[STANDARD_NAME_PROP] = {
                "name": product.standard_name,
            }
        if product.region:
            self.properties[REGION_PROP] = product.region
        self.collection.keywords = product.keywords

        # add_theme_themes(self.collection, product.themes)
        # add_theme_variables(self.collection, product.variables)
        # add_theme_missions(self.collection, product.eo_missions)

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

    def apply_project(self, project: Project):
        contacts = []

        if project.technical_officer.name:
            officer = {
                "name": project.technical_officer.name,
                "role": "technical_officer",
            }
            if project.technical_officer.e_mail:
                officer["emails"] = [
                    {
                        "value": project.technical_officer.e_mail,
                    }
                ]
            contacts.append(officer)

        for consortium_member in project.consortium:
            contacts.append({
                "name": consortium_member,
                "role": "consortium_member",
            })
        
        self.properties.update(
            {
                "title": project.title,
                "description": project.description,
                NAME_PROP: project.name,
                STATUS_PROP: project.status.value.lower(),
                THEMES_PROP: project.themes,
                TYPE_PROP: "project",
                "contacts": contacts,
            }
        )
        # add_theme_themes(self.collection, project.themes)
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


class ItemOSCExtension(OSCExtension[pystac.Item]):
    pass


def add_themes(catalog: pystac.Catalog, themes: List[str], scheme: str):
    themes_prop: list = catalog.extra_fields.setdefault("themes", [])
    for theme_prop in themes_prop:
        if theme_prop.get("scheme") == scheme:
            to_add = set(themes) - {
                concept["id"] for concept in theme_prop["concepts"]
            }
            theme_prop["concepts"].extend({"id": theme} for theme in to_add)
            break
    else:
        themes_prop.append(
            {"scheme": scheme, "concepts": [{"id": theme} for theme in themes]}
        )

    if THEMES_SCHEMA_URI not in catalog.stac_extensions:
        catalog.stac_extensions.append(THEMES_SCHEMA_URI)


def add_theme_themes(catalog: pystac.Catalog, themes: List[str]):
    add_themes(catalog, themes, OSC_SCHEME_THEMES)


def add_theme_variables(catalog: pystac.Catalog, variables: List[str]):
    add_themes(catalog, variables, OSC_SCHEME_VARIABLES)


def add_theme_missions(catalog: pystac.Catalog, missions: List[str]):
    add_themes(catalog, missions, OSC_SCHEME_MISSIONS)


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
            pystac.SpatialExtent([
                product.geometry.bounds
                if product.geometry
                else [-180.0, -90.0, 180.0, 90.0]
            ]),
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
            pystac.SpatialExtent([[-180.0, -90.0, 180.0, 90.0]]),
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
    if theme.link:
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
    add_theme_themes(catalog, variable.themes)
    if variable.link:
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
    catalog = pystac.Catalog(
        id=get_eo_mission_id(eo_mission.name),
        description=eo_mission.description,
        title=eo_mission.name,
    )
    if eo_mission.link:
        catalog.add_link(
            pystac.Link(
                rel=pystac.RelType.VIA,
                target=eo_mission.link,
                media_type="text/html",
                title="Description",
            )
        )
    return catalog


def get_theme_id(theme_name: str):
    # return f"theme-{slugify(theme_name)}"
    return f"{slugify(theme_name)}"


def get_variable_id(variable_name: str):
    # return f"variable-{slugify(variable_name)}"
    return f"{slugify(variable_name)}"


def get_eo_mission_id(eo_mission_name: str):
    # return f"mission-{slugify(eo_mission_name)}"
    return f"{slugify(eo_mission_name)}"


def get_concept_names(catalog: pystac.Catalog, scheme: str):
    for theme in catalog.extra_fields.get("themes", []):
        if theme.get("scheme") == scheme:
            return [concept["id"] for concept in theme.get("concepts", [])]
    return []


def get_theme_names(catalog: pystac.Catalog) -> Iterable[str]:
    return catalog.extra_fields.get(THEMES_PROP, [])
    # return get_concept_names(catalog, OSC_SCHEME_THEMES)


def get_variable_names(catalog: pystac.Catalog) -> Iterable[str]:
    return catalog.extra_fields.get(VARIABLES_PROP, [])
    # return get_concept_names(catalog, OSC_SCHEME_VARIABLES)


def get_mission_names(catalog: pystac.Catalog) -> Iterable[str]:
    return catalog.extra_fields.get(MISSIONS_PROP, [])
    # return get_concept_names(catalog, OSC_SCHEME_MISSIONS)


def apply_keywords(catalog: Union[pystac.Catalog, pystac.Collection]):
    if isinstance(catalog, pystac.Collection):
        keywords = catalog.keywords or []
    else:
        keywords: List[str] = catalog.extra_fields.setdefault("keywords", [])
    keywords.extend(
        f"theme:{name}" for name in catalog.extra_fields.get(THEMES_PROP, [])
    )
    keywords.extend(
        f"variable:{name}"
        for name in catalog.extra_fields.get(VARIABLES_PROP, [])
    )
    keywords.extend(
        f"mission:{name}"
        for name in catalog.extra_fields.get(MISSIONS_PROP, [])
    )
    if region := catalog.extra_fields.get(REGION_PROP):
        keywords.append(f"region:{region}")
    if project := catalog.extra_fields.get(PROJECT_PROP):
        keywords.append(f"project:{project}")

    if isinstance(catalog, pystac.Collection):
        catalog.keywords = keywords


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

    def write_text(self, dest: str, txt: str, *args, **kwargs) -> None:
        super().write_text(self._replace_path(dest), txt, *args, **kwargs)

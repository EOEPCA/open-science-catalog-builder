from copy import deepcopy
from datetime import datetime
from urllib.parse import urlparse

from pygeometa.schemas.iso19139 import ISO19139OutputSchema
from pygeometa.schemas.iso19139_2 import ISO19139_2OutputSchema
import pystac

from .stac import (
    NAME_PROP,
    THEMES_PROP,
    VARIABLE_PROP,
    STATUS_PROP,
    REGION_PROP,
    CONSORTIUM_PROP,
    TECHNICAL_OFFICER_PROP,
    MISSIONS_PROP,
)

LANGUAGE = "eng"

MCF_TEMPLATE = {
    "mcf": {"version": "1.0"},
    "metadata": {"language": LANGUAGE, "charset": "utf8"},
    "spatial": {"datatype": "grid", "geomtype": "solid"},
    "identification": {
        "charset": "utf8",
        "language": "missing",
        "dates": {},
        "keywords": {},
        "status": "onGoing",
        "maintenancefrequency": "continual",
    },
    "content_info": {"type": "image", "dimensions": []},
    "contact": {"pointOfContact": {}, "distributor": {}},
    "distribution": {},
}

STATUSES = {
    "COMPLETED": "completed",
    "ONGOING": "onGoing",
    "Planned": "planned",
    "PLANNED": "planned",
}


def build_theme_keywords(themes: list) -> dict:
    keywords = {
        "keywords": list([f"theme:{t}" for t in themes]),
        "keywords_type": "theme",
    }

    return keywords


def generate_project_metadata(project: pystac.Collection) -> str:
    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()
    extra = project.extra_fields
    mcf["metadata"]["identifier"] = project.id
    mcf["metadata"]["hierarchylevel"] = "datasetcollection"
    mcf["metadata"]["datestamp"] = now
    mcf["identification"]["title"] = project.title
    mcf["identification"]["abstract"] = project.description
    mcf["identification"]["status"] = STATUSES[extra[STATUS_PROP]]

    mcf["identification"]["keywords"]["themes"] = build_theme_keywords(
        extra[THEMES_PROP]
    )

    mcf["identification"]["keywords"]["short-name"] = {
        "keywords": [extra[NAME_PROP]],
        "keywords_type": "theme",
    }

    mcf["identification"]["extents"] = {
        "spatial": [
            {"bbox": bbox, "crs": 4326}
            for bbox in project.extent.spatial.bboxes
        ],
        "temporal": [
            {"begin": start, "end": end}
            for start, end in project.extent.temporal.intervals
        ],
    }

    mcf["contact"]["pointOfContact"] = {
        "organization": ", ".join(extra[CONSORTIUM_PROP]),
        "individualname": extra[TECHNICAL_OFFICER_PROP]["name"],
        "email": extra[TECHNICAL_OFFICER_PROP]["e-mail"],
    }

    website_link = next(
        (link for link in project.get_links() if link.title == "Website"), None
    )
    eo4_society_link = next(
        (
            link
            for link in project.get_links()
            if link.title == "EO4Society Link"
        ),
        None,
    )

    if website_link:
        mcf["distribution"] = {
            "website": {
                "url": website_link.get_absolute_href(),
                "rel": "describedBy",
                "type": "WWW:LINK",
                "name": "website",
                "description": "website",
                "function": "information",
            }
        }

    mcf["distribution"]["self"] = {
        "url": project.get_self_href(),
        "rel": "self",
        "type": "WWW:LINK",
        "name": "self",
        "description": "self",
        "function": "download",
    }

    if eo4_society_link:
        mcf["identification"]["url"] = eo4_society_link.get_absolute_href()

    return ISO19139OutputSchema().write(mcf)


def generate_product_metadata(product: pystac.Collection) -> str:
    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()

    extra = product.extra_fields
    common = pystac.CommonMetadata(product)

    mcf["metadata"]["identifier"] = product.id
    mcf["metadata"]["hierarchylevel"] = "dataset"
    mcf["metadata"]["datestamp"] = now
    mcf["identification"]["title"] = product.title
    mcf["identification"]["abstract"] = product.description
    mcf["identification"]["status"] = STATUSES[extra[STATUS_PROP]]
    mcf["metadata"]["parentidentifier"] = product.get_parent().id

    mcf["identification"]["keywords"]["default"] = {
        "keywords": [f"variable:{extra[VARIABLE_PROP]}"],
        "keywords_type": "theme",
    }

    mcf["identification"]["keywords"]["themes"] = build_theme_keywords(
        extra[THEMES_PROP]
    )

    if "sci:doi" in extra:
        doi_url = urlparse(extra["sci:doi"])
        mcf["identification"]["doi"] = doi_url.path.lstrip("/")

    if extra[REGION_PROP]:
        mcf["identification"]["keywords"]["region"] = {
            "keywords": [extra[REGION_PROP]],
            "keywords_type": "theme",
        }

    if common.created:
        mcf["identification"]["dates"] = {"publication": common.created}

    mcf["identification"]["extents"] = {
        "spatial": [
            {"bbox": bbox, "crs": 4326}
            for bbox in product.extent.spatial.bboxes
        ],
        "temporal": [
            {"begin": start, "end": end}
            for start, end in product.extent.temporal.intervals
        ],
    }

    mcf["acquisition"] = {"platforms": [{"identifier": extra[MISSIONS_PROP]}]}

    website_link = next(
        (lnk for lnk in product.get_links() if lnk.title == "Website"), None
    )
    access_link = next(
        (lnk for lnk in product.get_links() if lnk.title == "Access"), None
    )
    documentation_link = next(
        (lnk for lnk in product.get_links() if lnk.title == "Documentation"),
        None,
    )

    if website_link:
        mcf["distribution"] = {
            "website": {
                "url": website_link.get_absolute_href(),
                "rel": "describedBy",
                "type": "WWW:LINK",
                "name": "website",
                "description": "website",
                "function": "information",
            }
        }

    if access_link:
        mcf["distribution"]["access"] = {
            "url": access_link.get_absolute_href(),
            "rel": "data",
            "type": "WWW:LINK",
            "name": "access",
            "description": "access",
            "function": "download",
        }

    mcf["distribution"]["self"] = {
        "url": product.get_self_href(),
        "rel": "self",
        "type": "WWW:LINK",
        "name": "self",
        "description": "self",
        "function": "self",
    }

    if documentation_link:
        mcf["identification"]["url"] = documentation_link.get_absolute_href()

    return ISO19139_2OutputSchema().write(mcf)

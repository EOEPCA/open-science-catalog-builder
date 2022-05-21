from copy import deepcopy
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from pygeometa.schemas.iso19139 import ISO19139OutputSchema
from pygeometa.schemas.iso19139_2 import ISO19139_2OutputSchema

from .types import Product, Project

LANGUAGE = 'eng'

MCF_TEMPLATE = {
    'mcf': {
        'version': '1.0'
    },
    'metadata': {
        'language': LANGUAGE,
        'charset': 'utf8'
    },
    'spatial': {
        'datatype': 'grid',
        'geomtype': 'solid'
    },
    'identification': {
        'charset': 'utf8',
        'language': 'missing',
        'dates': {},
        'keywords': {},
        'status': 'onGoing',
        'maintenancefrequency': 'continual'
    },
    'content_info': {
        'type': 'image',
        'dimensions': []
    },
    'contact': {
        'pointOfContact': {},
        'distributor': {}
    },
    'distribution': {}
}

STATUSES = {
    'COMPLETED': 'completed',
    'ONGOING': 'onGoing',
    'Planned': 'planned',
    'PLANNED': 'planned',
}


def build_theme_keywords(themes: list) -> dict:
    keywords = {
        'keywords': list([f'theme:{t}' for t in themes]),
        'keywords_type': 'theme'
    }

    return keywords


def generate_project_metadata(project: Project, self_link: Optional[str]) -> str:
    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()

    mcf['metadata']['identifier'] = project.id
    mcf['metadata']['hierarchylevel'] = 'datasetcollection'
    mcf['metadata']['datestamp'] = now
    mcf['identification']['title'] = project.title
    mcf['identification']['abstract'] = project.description
    mcf['identification']['status'] = STATUSES[project.status.value]

    mcf['identification']['keywords']['themes'] = build_theme_keywords(project.themes)

    mcf['identification']['keywords']['short-name'] = {
        'keywords': [project.name],
        'keywords_type': 'theme'
    }

    mcf['identification']['extents'] = {
        'spatial': [{
            'bbox': [-180, -90, 180, 90],
            'crs': 4326
        }],
        'temporal': [{
            'begin': project.start,
            'end': project.end
        }]
    }

    for consortium in project.consortium:
        mcf['contact']['pointOfContact'] = {
            'organization': ', '.join(project.consortium),
            'individualname': project.technical_officer.name,
            'email': project.technical_officer.e_mail
        }

    mcf['distribution'] = {
        'website': {
            'url': project.website,
            'type': 'WWW:LINK',
            'name': 'website',
            'description': 'website',
            'function': 'information'
        }
    }

    if self_link:
        mcf['distribution']['self'] = {
            'url': self_link,
            'type': 'WWW:LINK',
            'name': 'self',
            'description': 'self',
            'function': 'download'
        }

    if project.eo4_society_link:
        mcf['identification']['url'] = project.eo4_society_link

    return ISO19139OutputSchema().write(mcf)


def generate_product_metadata(product: Product, parent_identifier: Optional[str], self_link: Optional[str]) -> str:
    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()

    mcf['metadata']['identifier'] = product.id
    mcf['metadata']['hierarchylevel'] = 'dataset'
    mcf['metadata']['datestamp'] = now
    mcf['identification']['title'] = product.title
    mcf['identification']['abstract'] = product.description
    mcf['identification']['status'] = STATUSES[product.status.value]

    if parent_identifier:
        mcf['metadata']['parentidentifier'] = parent_identifier

    mcf['identification']['keywords']['default'] = {
        'keywords': [f'variable:{product.variable}'],
        'keywords_type': 'theme'
    }

    mcf['identification']['keywords']['themes'] = build_theme_keywords(product.themes)

    if product.doi:
        doi_url = urlparse(product.doi)
        mcf['identification']['doi'] = doi_url.path.lstrip('/')

    if product.region:
        mcf['identification']['keywords']['region'] = {
            'keywords': [product.region],
            'keywords_type': 'theme'
        }

    if product.released not in [None, 'Planned']:
        mcf['identification']['dates'] = {
            'publication': product.released
        }

    if product.geometry:
        bounds = product.geometry.bounds
        bbox = [
            bounds[0],
            bounds[1],
            bounds[2],
            bounds[3]
        ]
    else:
        bbox = [-180, -90, 180, 90]

    mcf['identification']['extents'] = {
        'spatial': [{
            'bbox': bbox,
            'crs': 4326
        }],
        'temporal': [{
            'begin': product.start,
            'end': product.end
        }]
    }

    mcf['acquisition'] = {
        'platforms': [{
            'identifier': product.eo_missions
        }]
    }

    mcf['distribution'] = {
        'website': {
            'url': product.website,
            'type': 'WWW:LINK',
            'name': 'website',
            'description': 'website',
            'function': 'information'
        }
    }

    if product.access:
        mcf['distribution']['access'] = {
            'url': product.access,
            'type': 'WWW:LINK',
            'name': 'access',
            'description': 'access',
            'function': 'download'
        }

    if self_link:
        mcf['distribution']['self'] = {
            'url': self_link,
            'type': 'WWW:LINK',
            'name': 'self',
            'description': 'self',
            'function': 'download'
        }

    if product.documentation:
        mcf['identification']['url'] = product.documentation

    return ISO19139_2OutputSchema().write(mcf)

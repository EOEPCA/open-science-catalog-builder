from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Tuple
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
        'themes': {
            'keywords': themes,
            'keywords_type': 'theme'
        }
    }

    return keywords


def generate_project_metadata(project: Project) -> Tuple[str, str, str]:
    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()

    mcf['metadata']['identifier'] = project.id
    mcf['metadata']['hierarchylevel'] = 'datasetcollection'
    mcf['metadata']['datestamp'] = now
    mcf['identification']['title'] = project.title
    mcf['identification']['abstract'] = project.description
    mcf['identification']['status'] = STATUSES[project.status.value]

    mcf['identification']['keywords']['themes'] = build_theme_keywords([project.themes])  # noqa

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

    if project.eo4_society_link:
        mcf['identification']['url'] = project.eo4_society_link

    iso_os = ISO19139OutputSchema()
    return project.id, project.name, iso_os.write(mcf)


def generate_product_metadata(product: Product, projects: Dict[str, str]):

    mcf = deepcopy(MCF_TEMPLATE)
    now = datetime.now().isoformat()

    mcf['metadata']['identifier'] = product.id
    mcf['metadata']['hierarchylevel'] = 'dataset'
    mcf['metadata']['datestamp'] = now
    mcf['identification']['title'] = product.title
    mcf['identification']['abstract'] = product.description
    mcf['identification']['status'] = STATUSES[product.status.value]

    print(product.project, projects.keys())
    if product.project in projects:
        mcf['metadata']['parentidentifier'] = projects[product.project]

    mcf['identification']['keywords']['default'] = {
        'keywords': [product.variable],
        'keywords_type': 'theme'
    }

    mcf['identification']['keywords']['themes'] = build_theme_keywords(product.themes)  # noqa

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

    if product.documentation:
        mcf['identification']['url'] = product.documentation

    iso_os = ISO19139_2OutputSchema()
    return product.id, iso_os.write(mcf)


def build_iso_docs(projects: List[Project],
                   products: List[Product]) -> List[str]:
    project_isos = [generate_project_metadata(p) for p in projects]

    projects = {}

    for pi in project_isos:
        projects[pi[1]] = pi[0]

    product_isos = [generate_product_metadata(p, projects) for p in products]

    return project_isos + product_isos

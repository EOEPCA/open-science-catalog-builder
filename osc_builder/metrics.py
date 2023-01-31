from operator import or_
from functools import reduce
from itertools import groupby
from typing import Dict, List, Optional, TypedDict
from datetime import datetime

from slugify import slugify

from .types import Product, Project, Theme, Variable, EOMission


class GlobalSummary(TypedDict):
    years: List[int]
    numberOfProducts: int
    numberOfProjects: int
    numberOfVariables: int
    numberOfThemes: int


class VariableSummary(TypedDict):
    years: List[int]
    numberOfProducts: int


class ThemeSummary(TypedDict):
    years: List[int]
    numberOfProducts: int
    numberOfProjects: int
    numberOfVariables: int


class MissionSummary(TypedDict):
    years: List[int]
    numberOfProducts: int
    numberOfVariables: int


class VariableMetrics(TypedDict):
    name: str
    description: str
    summary: VariableSummary


class ThemeMetrics(TypedDict):
    name: str
    description: str
    image: Optional[str]
    website: str
    summary: ThemeSummary
    variables: List[VariableMetrics]


class MissionMetrics(TypedDict):
    name: str
    summary: MissionSummary


class GlobalMetrics(TypedDict):
    id: str
    summary: GlobalSummary
    themes: List[ThemeMetrics]
    missions: List[MissionMetrics]


import pystac
import os.path


def build_variable_metrics():
    pass


def build_theme_metrics():
    pass


def intervals_to_years(intervals: List[List[datetime]]) -> set[int]:
    result = set()
    for start, end in intervals:
        if start is not None and end is not None:
            result |= set(year for year in range(start.year, end.year + 1))
    return result



def build_metrics_(
    id: str,
    root: pystac.Collection,
    themes: List[Theme],
    variables: List[Variable],
    eo_missions: List[EOMission],
) -> GlobalMetrics:

    theme_infos: dict = {
        theme.name: {
            "projects": [],
            "products": [],
            "variables_infos": [],
        }
        for theme in themes
    }

    variable_infos = {
        variable.name: {
            "theme": variable.theme,
            "products": []
        }
        for variable in variables
    }

    eo_mission_infos = {
        eo_mission.name: {
            "products": [],
            "variables": set(),
        }
        for eo_mission in eo_missions
    }

    for variable_info in variable_infos.values():
        theme_infos[variable_info["theme"]]["variable_infos"].append(variable_info)

    for project_collection in root.get_children():
        for theme in project_collection.extra_fields.get("osc:themes", []):
            theme_infos[theme]["projects"].append(project_collection)

        for product_collection in project_collection.get_children():
            for theme in product_collection.extra_fields.get("osc:themes", []):
                theme_infos[theme]["products"].append(product_collection)
            variable = product_collection.extra_fields["osc:variable"]
            variable_infos[variable]["products"].append(product_collection)
            for eo_mission in product_collection.extra_fields.get("osc:missions", []):
                eo_mission_infos[eo_mission]["products"].append(product_collection)
                eo_mission_infos[eo_mission]["variables"].add(variable)

            product_collection.extent.temporal.intervals[0][0]



    return {
        "id": id,
        "summary": {
            "years": sorted(
                reduce(or_, [
                    set(theme["summary"]["years"])
                    for theme in theme_metrics
                ])
            ),
            "numberOfProducts": len(global_products),
            "numberOfProjects": len(global_projects),
            "numberOfVariables": len(variables),
            "numberOfThemes": len(themes),
        },
        "themes": theme_metrics,
        "missions": mission_metrics,
    }

def build_metrics(
    id: str,
    themes: List[Theme],
    variables: List[Variable],
    missions: List[EOMission],
    projects: List[Project],
    products: List[Product],
) -> GlobalMetrics:
    # mapping: theme -> products
    #          variable -> products
    variable_product_map: Dict[str, List[Product]] = {}
    theme_product_map: Dict[str, List[Product]] = {}
    for product in products:
        for theme in product.themes:
            theme_product_map.setdefault(theme, []).append(product)
        variable_product_map.setdefault(slugify(product.variable), []).append(product)

    # mapping: theme -> project
    theme_project_map: Dict[str, List[Project]] = {}
    for project in projects:
        for theme in project.themes:
            theme_project_map.setdefault(theme, []).append(project)

    # mapping: theme -> variable metrics
    variable_metrics: Dict[str, List[VariableMetrics]] = {
        slugify(theme_name): [
            {
                "name": variable.name,
                "description": variable.description,
                "summary": {
                    "years": sorted(
                        reduce(or_, [
                            set(range(product.start.year, product.end.year + 1))
                            for product in variable_product_map.get(slugify(variable.name), [])
                            if product.start and product.end
                        ], set())
                    ),
                    "numberOfProducts": len(variable_product_map.get(slugify(variable.name), []))
                }
            }
            for variable in theme_variables
        ]
        # groupby needs sorting first in order to work as expected
        for theme_name, theme_variables in groupby(
            sorted(variables, key=lambda v: v.theme),
            lambda v: slugify(v.theme)
        )
    }

    # list of theme metrics
    theme_metrics: List[ThemeMetrics] = [
        {
            "name": theme.name,
            "description": theme.description,
            "image": theme.image,
            "website": theme.link,
            # "technicalOfficer": theme_coll.extra_fields["osc:technical_officer"]["name"],
            "summary": {
                "years": sorted(
                    reduce(or_, [
                        set(variable["summary"]["years"])
                        for variable in variable_metrics.get(slugify(theme.name), [])
                    ], set())
                ),
                "numberOfProducts": len(theme_product_map.get(slugify(theme.name), [])),
                "numberOfProjects": len(theme_project_map.get(slugify(theme.name), [])),
                "numberOfVariables": len(variable_metrics.get(slugify(theme.name), [])),
            },
            "variables": variable_metrics[slugify(theme.name)] #.get(theme.name, [])
        }
        for theme in themes
    ]

    # mapping: eo_mission -> Product
    mission_product_map: Dict[str, List[Product]] = {}
    for product in products:
        for mission in product.eo_missions:
            mission_product_map.setdefault(mission, []).append(product)

    mission_metrics: List[MissionMetrics] = [
        {
            "name": mission,
            "summary": {
                "years": sorted(
                    reduce(or_, [
                        set(range(product.start.year, product.end.year + 1))
                        for product in products
                        if product.start and product.end
                    ], set())
                ),
                "numberOfProducts": len(products),
                "numberOfVariables": len(
                    set(product.variable for product in products)
                )
            }
        }
        for mission, products in mission_product_map.items()
    ]

    return {
        "id": id,
        "summary": {
            "years": sorted(
                reduce(or_, [
                    set(theme["summary"]["years"])
                    for theme in theme_metrics
                ])
            ),
            "numberOfProducts": len(products),
            "numberOfProjects": len(projects),
            "numberOfVariables": len(variables),
            "numberOfThemes": len(themes),
        },
        "themes": theme_metrics,
        "missions": mission_metrics,
    }

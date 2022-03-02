from operator import or_
from functools import reduce
from itertools import groupby
from typing import Dict, List, TypedDict

from .types import Product, Project, Theme, Variable


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


class VariableMetrics(TypedDict):
    name: str
    description: str
    summary: VariableSummary


class ThemeMetrics(TypedDict):
    name: str
    description: str
    image: str
    website: str
    summary: ThemeSummary
    variables: List[VariableMetrics]


class GlobalMetrics(TypedDict):
    id: str
    summary: GlobalSummary
    themes: List[ThemeMetrics]


def build_metrics(
    id: str,
    themes: List[Theme],
    variables: List[Variable],
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
        variable_product_map.setdefault(product.variable, []).append(product)

    # mapping: theme -> project
    theme_project_map: Dict[str, List[Project]] = {}
    for project in projects:
        for theme in project.themes:
            theme_project_map.setdefault(theme, []).append(project)

    # mapping: theme -> variable metrics
    variable_metrics: Dict[str, List[VariableMetrics]] = {
        theme_name: [
            {
                "name": variable.name,
                "description": variable.description,
                "summary": {
                    "years": sorted(
                        reduce(or_, [
                            set(range(product.start.year, product.end.year + 1))
                            for product in variable_product_map.get(variable.name, [])
                            if product.start and product.end
                        ], set())
                    ),
                    "numberOfProducts": len(variable_product_map.get(variable.name, []))
                }
            }
            for variable in theme_variables
        ]
        for theme_name, theme_variables in groupby(variables, lambda v: v.theme)
    }

    # list of theme metrics
    theme_metrics: List[ThemeMetrics] = [
        {
            "name": theme.name,
            "description": theme.description,
            "image": "...",
            "website": theme.link,
            # "technicalOfficer": theme_coll.extra_fields["osc:technical_officer"]["name"],
            "summary": {
                "years": sorted(
                    reduce(or_, [
                        set(variable["summary"]["years"])
                        for variable in variable_metrics.get(theme.name, [])
                    ], set())
                ),
                "numberOfProducts": len(theme_product_map.get(theme.name, [])),
                "numberOfProjects": len(theme_project_map.get(theme.name, [])),
                "numberOfVariables": len(variable_metrics.get(theme.name, [])),
            },
            "variables": variable_metrics.get(theme.name, [])
        }
        for theme in themes
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
        "themes": theme_metrics
    }

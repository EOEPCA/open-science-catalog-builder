from dataclasses import asdict
import glob
from os import makedirs
from os.path import join
from typing import List
import json

import pystac
from slugify import slugify

from .types import Product, Project, Theme, Variable
from .stac import item_from_product, item_from_project, product_from_item, project_from_item


def load_products(directory: str) -> List[Product]:
    return [
        product_from_item(pystac.Item.from_file(filename))
        for filename in glob.glob(f"{directory}/*.json")
    ]


def load_projects(directory: str) -> List[Project]:
    return [
        project_from_item(pystac.Item.from_file(filename))
        for filename in glob.glob(f"{directory}/*.json")
    ]


def load_themes(directory: str) -> List[Theme]:
    return [
        Theme(**json.load(open(filename)))
        for filename in glob.glob(f"{directory}/*.json")
    ]


def load_variables(directory: str) -> List[Variable]:
    return [
        Variable(**json.load(open(filename)))
        for filename in glob.glob(f"{directory}/*.json")
    ]


def store_products(products: List[Product], directory: str):
    makedirs(directory, exist_ok=True)
    for product in products:
        item = item_from_product(product)
        item.save_object(False, join(directory, f"{slugify(item.id)}.json"))


def store_projects(projects: List[Project], directory: str):
    makedirs(directory, exist_ok=True)
    for project in projects:
        item = item_from_project(project)
        item.save_object(False, join(directory, f"{slugify(item.id)}.json"))


def store_themes(themes: List[Theme], directory: str):
    makedirs(directory, exist_ok=True)
    for theme in themes:
        with open(join(directory, f"{slugify(theme.name)}.json"), "w") as f:
            json.dump(asdict(theme), f, indent=2)


def store_variables(variables: List[Variable], directory: str):
    makedirs(directory, exist_ok=True)
    for variable in variables:
        with open(join(directory, f"{slugify(variable.name)}.json"), "w") as f:
            json.dump(asdict(variable), f, indent=2)

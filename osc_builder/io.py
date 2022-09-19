from dataclasses import asdict
from datetime import datetime
import glob
from os import makedirs
from os.path import join
from typing import List, Optional, Tuple
import json

import pystac
from slugify import slugify

from .types import Product, Project, Theme, Variable
from .stac import (
    item_from_product,
    item_from_project,
    product_from_item,
    project_from_item,
)


def load_product_items(directory: str) -> List[Tuple[Product, pystac.Item]]:
    result = []
    for filename in glob.glob(f"{directory}/*.json"):
        item = pystac.Item.from_file(filename)
        result.append((product_from_item(item), item))
    return result


def load_project_items(directory: str) -> List[Tuple[Project, pystac.Item]]:
    result = []
    for filename in glob.glob(f"{directory}/*.json"):
        item = pystac.Item.from_file(filename)
        result.append((project_from_item(item), item))
    return result


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


def store_products(products: List[Product], directory: str, update_timestamp: Optional[datetime] = None):
    makedirs(directory, exist_ok=True)
    for product in products:
        item = item_from_product(product, update_timestamp)
        item.save_object(False, join(directory, f"{slugify(item.id)}.json"))


def store_projects(projects: List[Project], directory: str, update_timestamp: Optional[datetime] = None):
    makedirs(directory, exist_ok=True)
    for project in projects:
        item = item_from_project(project, update_timestamp)
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


def store_iso_docs(records: List[str], directory: str):
    makedirs(directory, exist_ok=True)
    for record in records:
        with open(
            join(directory, f"{slugify(record[0])}.xml"), "w", encoding="utf-8"
        ) as f:
            f.write(record[-1])

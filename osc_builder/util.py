from datetime import date
from typing import Any, Optional

from .types_ import ProductSegmentation

def parse_decimal_date(source: Optional[str]) -> Optional[date]:
    if not source:
        return None
    dot_count = source.count(".")
    if not dot_count:
        return date(int(source), 1, 1)
    if dot_count == 1:
        year, month = source.split(".")
        return date(int(year), int(month) + 1, 1)
    elif dot_count == 2:
        year, month, day = source.split(".")
        return date(int(year), int(month), int(day))
    return None


def get_depth(maybe_list: Any) -> int:
    if isinstance(maybe_list, (list, tuple)):
        return get_depth(maybe_list[0]) + 1
    return 0

def get_product_segmentation(products=None) -> [ProductSegmentation]:
    if products is None:
        products = []

    products_segmentation_list: list[ProductSegmentation] = []
    list_name_product_segmentation = list(dict.fromkeys([product.collection for product in products if product.collection]))
    for name in list_name_product_segmentation:
        list_related_product = list(filter(lambda x: x.collection == name, products))
        regions = list(dict.fromkeys([product.region for product in list_related_product if product.region]))
        variables = []
        eo_missions = []
        themes = []
        for product in list_related_product:
            if len(product.variables) != 0:
                variables.append(*product.variables)
            if len(product.eo_missions) != 0:
                eo_missions.append(*product.eo_missions)
            if len(product.themes) != 0:
                themes.append(*product.themes)

        variables = list(dict.fromkeys(variables))
        eo_missions = list(dict.fromkeys(eo_missions))
        themes = list(dict.fromkeys(themes))
        first = list(sorted(list_related_product, key=lambda x: x.start))
        end = list(sorted(list_related_product, key=lambda x: x.end))
        item = ProductSegmentation(
            title=name,
            project=end[0].project,
            themes=themes,
            start=first[0].start,
            end=end[0].end,
            released=first[0].released,
            region=", ".join(regions),
            variables=variables,
            eo_missions=eo_missions,
        )
        products_segmentation_list.append(item)

    return products_segmentation_list

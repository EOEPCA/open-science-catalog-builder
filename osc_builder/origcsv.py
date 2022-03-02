
from datetime import date
from os import PathLike
from typing import List, Literal, TextIO, Union
import csv
from itertools import groupby
import json

from pygeoif import geometry
from dateutil.parser import parse as parse_datetime

from .types import Contact, Product, Project, Status, Theme, Variable
from .util import parse_decimal_date, get_depth


def get_themes(obj: dict) -> List[str]:
    return [
        obj[f"Theme{i}"]
        for i in range(1, 7)
        if obj[f"Theme{i}"]
    ]


def parse_geometry(source: str) -> geometry._Geometry:
    geom = None
    if not source:
        pass
    elif source.startswith("Multipolygon"):
        # geom = geometry.from_wkt(source.replace("Multipolygon", "MULTIPOLYGON"))
        # TODO: figure out a way to parse this
        pass
    else:
        try:
            raw_geom = json.loads(source)
        except ValueError:
            pass
        depth = get_depth(raw_geom)
        if depth == 1:
            geom = geometry.Point(*raw_geom)
        elif depth == 3:
            shell, *holes = raw_geom
            geom = geometry.Polygon(shell, holes or None)

    return geom

    # if geom:
    #     return geom.__geo_interface__
    # return None


def parse_released(value: str) -> Union[date, None, Literal["Planned"]]:
    if not value:
        return None

    if value == "Planned":
        return "Planned"

    return parse_datetime(value).date


def load_orig_products(file: TextIO) -> List[Product]:
    return [
        Product(
            id=f"product-{line['ID']}",
            status=Status(line["Status"].upper()),
            website=line["Website"],
            title=line["Product"],
            description=line["Description"],
            project=line["Project"],
            variable=line["Variable"],
            themes=get_themes(line),
            access=line["Access"],
            documentation=line["Documentation"] or None,
            doi=line["DOI"] or None,
            version=line["Version"] or None,
            start=parse_decimal_date(line["Start"]) if line["Start"] else None,
            end=parse_decimal_date(line["End"]) if line["End"] else None,
            geometry=parse_geometry(line["Polygon"]),
            region=line["Region"] or None,
            released=parse_released(line["Released"]),
            eo_missions=[
                stripped_mission
                for mission in line["EO_Missions"].split(";")
                if (stripped_mission := mission.strip())
            ]
        )
        for line in csv.DictReader(file)
    ]


def load_orig_projects(file: TextIO) -> List[Project]:
    return [
        Project(
            id=f"project-{line['Project_ID']}",
            status=Status(line["Status"].upper()),
            name=line["Project_Name"],
            title=line["Short_Name"],
            description=line["Short_Description"],
            website=line["Website"],
            eo4_society_link=line["Eo4Society_link"],
            consortium=[
                stripped
                for member in line["Consortium"].split(",")
                if (stripped := member.strip())
            ],
            start=parse_datetime(line["Start_Date_Project"]).date(),
            end=parse_datetime(line["End_Date_Project"]).date(),
            technical_officer=Contact(
                line["TO"],
                line["TO_E-mail"],
            ),
            themes=get_themes(line),
        )
        for line in csv.DictReader(file)
    ]


def load_orig_themes(file: TextIO) -> List[Theme]:
    return [
        Theme(
            name=line["theme"],
            description=line["description"],
            link=line["link"],
        )
        for line in csv.DictReader(file)
    ]


def load_orig_variables(file: TextIO) -> List[Variable]:
    return [
        Variable(
            name=line["variable"],
            description=line["variable description"],
            link=line["link"],
            theme=line["theme"],
        )
        for line in csv.DictReader(file)
    ]
